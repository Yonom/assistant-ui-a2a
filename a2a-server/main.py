#!/usr/bin/env python3
"""
Example A2A Server - A chat assistant powered by OpenAI.

This server implements the A2A protocol using the a2a-sdk and serves
as a test target for the a2a-backend bridge.
"""

import os

import uvicorn
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from agent_executor import ChatAgentExecutor

load_dotenv()


if __name__ == "__main__":
    skill = AgentSkill(
        id="chat",
        name="Chat",
        description="General-purpose chat assistant powered by OpenAI",
        tags=["chat", "assistant"],
        examples=["Hello!", "What is Python?", "Tell me a joke"],
    )

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9999"))

    agent_card = AgentCard(
        name="Chat Assistant",
        description="A general-purpose chat assistant powered by OpenAI",
        url=f"http://localhost:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ChatAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    print(f"Starting A2A Chat Server on {host}:{port}")
    uvicorn.run(server.build(), host=host, port=port)
