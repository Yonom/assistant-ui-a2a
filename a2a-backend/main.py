#!/usr/bin/env python3
"""
A2A Backend - Bridge between assistant-transport protocol and A2A servers.

This server receives assistant-transport requests from the frontend and
forwards them to an A2A server using the a2a-sdk client with streaming.
"""

import os
import traceback
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from contextlib import asynccontextmanager

import uvicorn
import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from assistant_stream.serialization import DataStreamResponse
from assistant_stream import RunController, create_run

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendStreamingMessageRequest,
)

# Load environment variables
load_dotenv()

# Default A2A server URL (can be overridden per-request from the frontend)
DEFAULT_A2A_SERVER_URL = os.getenv("A2A_SERVER_URL", "http://localhost:9999")


# --- Request models (assistant-transport protocol) ---


class MessagePart(BaseModel):
    type: str = Field(..., description="The type of message part")
    text: Optional[str] = Field(None, description="Text content")
    image: Optional[str] = Field(None, description="Image URL or data")


class UserMessage(BaseModel):
    role: str = Field(default="user", description="Message role")
    parts: List[MessagePart] = Field(..., description="Message parts")


class AddMessageCommand(BaseModel):
    type: str = Field(default="add-message", description="Command type")
    message: UserMessage = Field(..., description="User message")


class AddToolResultCommand(BaseModel):
    type: str = Field(default="add-tool-result", description="Command type")
    toolCallId: str = Field(..., description="ID of the tool call")
    result: Dict[str, Any] = Field(..., description="Tool execution result")


class AssistantRequest(BaseModel):
    commands: List[Union[AddMessageCommand, AddToolResultCommand]] = Field(
        ..., description="List of commands to execute"
    )
    system: Optional[str] = Field(None, description="System prompt")
    tools: Optional[Dict[str, Any]] = Field(None, description="Available tools")
    runConfig: Optional[Dict[str, Any]] = Field(
        None, description="Run configuration"
    )
    state: Optional[Dict[str, Any]] = Field(None, description="State")
    a2aServerUrl: Optional[str] = Field(
        None, description="A2A server URL (passed from frontend)"
    )


# --- Helper functions ---


def extract_text_from_a2a_response(data: dict) -> Optional[str]:
    """Extract text from an A2A response chunk (dict form).

    Handles multiple response shapes:
    - Message: result.parts (kind=message)
    - TaskStatusUpdateEvent: result.status.message.parts
    - TaskArtifactUpdateEvent: result.artifact.parts
    - Task: result.artifacts[].parts or result.status.message.parts
    """
    result = data.get("result", {})
    if not isinstance(result, dict):
        return None

    def extract_from_parts(parts):
        for part in parts:
            if isinstance(part, dict) and part.get("kind") == "text":
                return part.get("text", "")
        return None

    # Direct message: result.parts (kind=message)
    if result.get("kind") == "message":
        parts = result.get("parts", [])
        text = extract_from_parts(parts)
        if text is not None:
            return text

    # Check status.message.parts (TaskStatusUpdateEvent or Task)
    status = result.get("status", {})
    if status and isinstance(status, dict):
        message = status.get("message", {})
        if message and isinstance(message, dict):
            parts = message.get("parts", [])
            text = extract_from_parts(parts)
            if text is not None:
                return text

    # Check artifact.parts (TaskArtifactUpdateEvent)
    artifact = result.get("artifact", {})
    if artifact and isinstance(artifact, dict):
        text = extract_from_parts(artifact.get("parts", []))
        if text is not None:
            return text

    # Check artifacts[].parts (Task with artifacts)
    artifacts = result.get("artifacts", [])
    if artifacts and isinstance(artifacts, list):
        for art in artifacts:
            if isinstance(art, dict):
                text = extract_from_parts(art.get("parts", []))
                if text is not None:
                    return text

    return None


# --- FastAPI app ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"A2A Backend starting (default A2A server: {DEFAULT_A2A_SERVER_URL})")
    yield
    print("A2A Backend shutting down")


app = FastAPI(
    title="A2A Backend",
    description="Bridge between assistant-transport and A2A protocol",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.post("/assistant")
async def assistant_endpoint(request: AssistantRequest):
    # Resolve A2A server URL: prefer per-request, fall back to default
    a2a_server_url = request.a2aServerUrl or DEFAULT_A2A_SERVER_URL

    async def run_callback(controller: RunController):
        try:
            # Extract user message from command
            cmd = request.commands[0]
            user_text = ""

            if cmd.type == "add-message":
                for part in cmd.message.parts:
                    if part.type == "text" and part.text:
                        user_text = part.text
                        break

                # Add user message to state (LangChain format)
                controller.state["messages"].append(
                    {
                        "type": "human",
                        "content": [{"type": "text", "text": user_text}],
                    }
                )
            elif cmd.type == "add-tool-result":
                # Pass through tool results
                controller.state["messages"][-1]["parts"][-1]["result"] = (
                    cmd.result
                )
                return

            if not user_text:
                controller.state["messages"].append(
                    {
                        "type": "ai",
                        "content": "I didn't receive a text message.",
                    }
                )
                return

            # Create AI message with a2a_agent tool call
            tool_call_id = f"call_{uuid4().hex[:8]}"
            tool_call = {
                "id": tool_call_id,
                "name": "a2a_agent",
                "args": {
                    "query": user_text,
                    "serverUrl": a2a_server_url,
                    "status": "connecting",
                    "agentName": "",
                    "response": "",
                },
            }
            controller.state["messages"].append(
                {
                    "type": "ai",
                    "content": "",
                    "tool_calls": [tool_call],
                }
            )
            ai_idx = len(controller.state["messages"]) - 1
            tc_args = controller.state["messages"][ai_idx]["tool_calls"][0][
                "args"
            ]

            # Connect to A2A server and stream response
            async with httpx.AsyncClient(timeout=60.0) as httpx_client:
                # Resolve agent card
                resolver = A2ACardResolver(
                    httpx_client=httpx_client,
                    base_url=a2a_server_url,
                )
                agent_card = await resolver.get_agent_card()
                tc_args["agentName"] = agent_card.name

                # Create A2A client
                a2a_client = A2AClient(
                    httpx_client=httpx_client,
                    agent_card=agent_card,
                )

                # Build A2A message
                send_payload: dict[str, Any] = {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": user_text}],
                        "messageId": uuid4().hex,
                    }
                }

                # Stream from A2A server
                tc_args["status"] = "working"
                latest_text = ""
                try:
                    streaming_request = SendStreamingMessageRequest(
                        id=str(uuid4()),
                        params=MessageSendParams(**send_payload),
                    )
                    stream = a2a_client.send_message_streaming(
                        streaming_request
                    )
                    async for chunk in stream:
                        chunk_dict = chunk.model_dump(
                            mode="json", exclude_none=True
                        )
                        text = extract_text_from_a2a_response(chunk_dict)
                        if text and text != latest_text:
                            latest_text = text
                            tc_args["response"] = text
                except Exception as e:
                    print(
                        f"Streaming failed, falling back to non-streaming: {e}"
                    )

                # Fallback to non-streaming
                if not latest_text:
                    try:
                        non_streaming_request = SendMessageRequest(
                            id=str(uuid4()),
                            params=MessageSendParams(**send_payload),
                        )
                        response = await a2a_client.send_message(
                            non_streaming_request
                        )
                        resp_dict = response.model_dump(
                            mode="json", exclude_none=True
                        )
                        text = extract_text_from_a2a_response(resp_dict)
                        if text:
                            latest_text = text
                            tc_args["response"] = text
                    except Exception as e2:
                        print(f"Non-streaming also failed: {e2}")

                if not latest_text:
                    latest_text = "No response from A2A server."
                    tc_args["response"] = latest_text

                # Mark tool call complete and add tool result
                tc_args["status"] = "complete"
                controller.state["messages"].append(
                    {
                        "type": "tool",
                        "tool_call_id": tool_call_id,
                        "name": "a2a_agent",
                        "content": latest_text,
                        "status": "success",
                    }
                )

        except Exception as e:
            print(f"Error in A2A bridge: {e}")
            traceback.print_exc()
            controller.state["messages"].append(
                {"type": "ai", "content": f"Error: {str(e)}"}
            )

    stream = create_run(run_callback, state=request.state)
    return DataStreamResponse(stream)


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    print(f"Starting A2A Backend on {host}:{port}")
    print(f"Default A2A Server URL: {DEFAULT_A2A_SERVER_URL}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
