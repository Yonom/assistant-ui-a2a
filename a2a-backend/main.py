#!/usr/bin/env python3
"""
A2A Backend - Bridge between assistant-transport protocol and A2A servers.

Streams rich A2A events (status updates, artifacts, task states) to the
frontend as tool call state updates.
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

load_dotenv()

DEFAULT_A2A_SERVER_URL = os.getenv("A2A_SERVER_URL", "http://localhost:9999")


# --- Request models ---


class MessagePart(BaseModel):
    type: str
    text: Optional[str] = None
    image: Optional[str] = None


class UserMessage(BaseModel):
    role: str = "user"
    parts: List[MessagePart]


class AddMessageCommand(BaseModel):
    type: str = "add-message"
    message: UserMessage


class AddToolResultCommand(BaseModel):
    type: str = "add-tool-result"
    toolCallId: str
    result: Dict[str, Any]


class AssistantRequest(BaseModel):
    commands: List[Union[AddMessageCommand, AddToolResultCommand]]
    system: Optional[str] = None
    tools: Optional[Dict[str, Any]] = None
    runConfig: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None
    a2aServerUrl: Optional[str] = None



def _extract_text_from_parts(parts: list) -> str | None:
    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get("kind") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts) if texts else None


def _parse_artifact(artifact: dict) -> dict:
    """Parse an artifact dict into a frontend-friendly format."""
    parts = []
    for part in artifact.get("parts", []):
        if not isinstance(part, dict):
            continue
        kind = part.get("kind", "")
        if kind == "text":
            parts.append({"kind": "text", "text": part.get("text", "")})
        elif kind == "data":
            parts.append({"kind": "data", "data": part.get("data", {})})
        elif kind == "file":
            file_info = part.get("file", {})
            parts.append({
                "kind": "file",
                "name": file_info.get("name", "file"),
                "mimeType": file_info.get("mime_type", ""),
                "hasBytes": "bytes" in file_info,
                "uri": file_info.get("uri"),
            })
    return {
        "artifactId": artifact.get("artifact_id", ""),
        "name": artifact.get("name", ""),
        "description": artifact.get("description"),
        "parts": parts,
    }


def _parse_agent_card(agent_card) -> dict:
    """Convert agent card to a frontend-friendly dict."""
    skills = []
    for s in (agent_card.skills or []):
        skills.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "tags": s.tags or [],
            "examples": s.examples or [],
        })
    return {
        "name": agent_card.name,
        "description": agent_card.description,
        "version": agent_card.version,
        "url": agent_card.url,
        "skills": skills,
        "streaming": agent_card.capabilities.streaming if agent_card.capabilities else False,
        "provider": {
            "organization": agent_card.provider.organization,
            "url": agent_card.provider.url,
        } if agent_card.provider else None,
    }


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
    a2a_server_url = request.a2aServerUrl or DEFAULT_A2A_SERVER_URL

    async def run_callback(controller: RunController):
        try:
            cmd = request.commands[0]
            user_text = ""

            if cmd.type == "add-message":
                for part in cmd.message.parts:
                    if part.type == "text" and part.text:
                        user_text = part.text
                        break

                controller.state["messages"].append({
                    "type": "human",
                    "content": [{"type": "text", "text": user_text}],
                })
            elif cmd.type == "add-tool-result":
                controller.state["messages"][-1]["parts"][-1]["result"] = cmd.result
                return

            if not user_text:
                controller.state["messages"].append({
                    "type": "ai",
                    "content": "I didn't receive a text message.",
                })
                return

            # Create tool call to represent the A2A agent invocation
            tool_call_id = f"call_{uuid4().hex[:8]}"
            tool_call = {
                "id": tool_call_id,
                "name": "a2a_agent",
                "args": {
                    "query": user_text,
                    "serverUrl": a2a_server_url,
                    "taskState": "connecting",
                    "agentCard": None,
                    "statusText": "",
                    "artifacts": [],
                    "error": None,
                },
            }
            controller.state["messages"].append({
                "type": "ai",
                "content": "",
                "tool_calls": [tool_call],
            })
            ai_idx = len(controller.state["messages"]) - 1
            tc_args = controller.state["messages"][ai_idx]["tool_calls"][0]["args"]

            # Connect to A2A server
            async with httpx.AsyncClient(timeout=120.0) as httpx_client:
                resolver = A2ACardResolver(
                    httpx_client=httpx_client,
                    base_url=a2a_server_url,
                )
                agent_card = await resolver.get_agent_card()
                tc_args["agentCard"] = _parse_agent_card(agent_card)
                tc_args["taskState"] = "submitted"

                a2a_client = A2AClient(
                    httpx_client=httpx_client,
                    agent_card=agent_card,
                )

                send_payload: dict[str, Any] = {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": user_text}],
                        "messageId": uuid4().hex,
                    }
                }

                latest_text = ""
                final_state = "completed"

                try:
                    streaming_request = SendStreamingMessageRequest(
                        id=str(uuid4()),
                        params=MessageSendParams(**send_payload),
                    )
                    stream = a2a_client.send_message_streaming(streaming_request)
                    async for chunk in stream:
                        # chunk is Task | Message | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
                        chunk_dict = chunk.model_dump(mode="json", exclude_none=True)
                        kind = chunk_dict.get("kind", "")

                        if kind == "status-update":
                            status = chunk_dict.get("status", {})
                            state = status.get("state", "unknown")
                            tc_args["taskState"] = state
                            message = status.get("message", {})
                            if message:
                                text = _extract_text_from_parts(message.get("parts", []))
                                if text:
                                    latest_text = text
                                    tc_args["statusText"] = latest_text
                            if state in ("failed", "canceled", "rejected"):
                                tc_args["error"] = latest_text or state
                                final_state = state
                            elif state == "completed":
                                final_state = "completed"

                        elif kind == "artifact-update":
                            artifact = _parse_artifact(chunk_dict.get("artifact", {}))
                            existing = None
                            for a in tc_args["artifacts"]:
                                if a["artifactId"] == artifact["artifactId"]:
                                    existing = a
                                    break
                            if existing and chunk_dict.get("append"):
                                existing["parts"].extend(artifact["parts"])
                            elif existing:
                                existing.update(artifact)
                            else:
                                tc_args["artifacts"].append(artifact)

                        elif kind == "message":
                            text = _extract_text_from_parts(chunk_dict.get("parts", []))
                            if text:
                                latest_text = text
                                tc_args["statusText"] = latest_text

                        elif kind == "task":
                            status = chunk_dict.get("status", {})
                            state = status.get("state", "completed")
                            tc_args["taskState"] = state
                            message = status.get("message", {})
                            if message:
                                text = _extract_text_from_parts(message.get("parts", []))
                                if text:
                                    latest_text = text
                                    tc_args["statusText"] = latest_text
                            for a in chunk_dict.get("artifacts", []):
                                tc_args["artifacts"].append(_parse_artifact(a))
                            if state in ("failed", "canceled", "rejected"):
                                tc_args["error"] = latest_text or state
                            final_state = state

                except Exception as e:
                    # SSE close errors are expected after stream ends
                    if latest_text or tc_args["artifacts"]:
                        print(f"Stream ended (may be normal SSE close): {e}")
                    else:
                        print(f"Streaming failed, falling back to non-streaming: {e}")
                        traceback.print_exc()

                # Fallback to non-streaming
                if not latest_text and not tc_args["artifacts"]:
                    try:
                        non_streaming_request = SendMessageRequest(
                            id=str(uuid4()),
                            params=MessageSendParams(**send_payload),
                        )
                        response = await a2a_client.send_message(non_streaming_request)
                        # response.root.result is Task | Message
                        result = response.root.result
                        result_dict = result.model_dump(mode="json", exclude_none=True)
                        kind = result_dict.get("kind", "")
                        if kind == "task":
                            status = result_dict.get("status", {})
                            message = status.get("message", {})
                            if message:
                                text = _extract_text_from_parts(message.get("parts", []))
                                if text:
                                    latest_text = text
                                    tc_args["statusText"] = latest_text
                            for a in result_dict.get("artifacts", []):
                                tc_args["artifacts"].append(_parse_artifact(a))
                            state = status.get("state", "completed")
                            if state in ("failed", "canceled", "rejected"):
                                tc_args["error"] = latest_text or state
                            final_state = state
                        elif kind == "message":
                            text = _extract_text_from_parts(result_dict.get("parts", []))
                            if text:
                                latest_text = text
                                tc_args["statusText"] = latest_text
                    except Exception as e2:
                        print(f"Non-streaming also failed: {e2}")
                        tc_args["error"] = str(e2)
                        final_state = "failed"

                if not latest_text and not tc_args["artifacts"]:
                    latest_text = "No response from A2A server."
                    tc_args["statusText"] = latest_text

                tc_args["taskState"] = final_state

                # Add tool result message
                tool_status = "success" if final_state == "completed" else "error"
                controller.state["messages"].append({
                    "type": "tool",
                    "tool_call_id": tool_call_id,
                    "name": "a2a_agent",
                    "content": latest_text or "Task completed.",
                    "status": tool_status,
                })

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
