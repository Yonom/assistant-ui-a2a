#!/usr/bin/env python3
"""
Kitchen-sink A2A Server demonstrating all major protocol features.

Skills:
  - chat:      Streaming chat (default)
  - artifacts: Generates code + data + file artifacts
  - multistep: Demonstrates input-required state
  - fail:      Demonstrates failed state
  - slow:      Long-running cancellable task
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
    AgentProvider,
    AgentSkill,
)

from agent_executor import KitchenSinkExecutor

load_dotenv()


if __name__ == "__main__":
    skills = [
        AgentSkill(
            id="chat",
            name="Chat",
            description="General-purpose streaming chat assistant",
            tags=["chat", "streaming"],
            examples=["Hello!", "Explain quantum computing", "Tell me a joke"],
        ),
        AgentSkill(
            id="artifacts",
            name="Artifact Generator",
            description="Generates code with text, data, and file artifacts",
            tags=["code", "artifacts", "files"],
            examples=[
                "/artifacts a fibonacci function",
                "/artifacts a REST API in FastAPI",
            ],
        ),
        AgentSkill(
            id="multistep",
            name="Multi-Step Research",
            description="Multi-step task that requests user input (input-required state)",
            tags=["research", "multistep", "input-required"],
            examples=["/multistep", "/multistep quantum computing"],
        ),
        AgentSkill(
            id="fail",
            name="Failure Demo",
            description="Demonstrates the failed task state",
            tags=["error", "demo"],
            examples=["/fail"],
        ),
        AgentSkill(
            id="slow",
            name="Slow Task",
            description="Long-running cancellable task (12 seconds) to test cancel",
            tags=["cancel", "long-running"],
            examples=["/slow"],
        ),
    ]

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9999"))

    agent_card = AgentCard(
        name="A2A Kitchen Sink",
        description="Demonstrates all major A2A protocol features: streaming, artifacts, task states, multi-step, and cancellation.",
        url=f"http://localhost:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
        provider=AgentProvider(
            organization="assistant-ui",
            url="https://github.com/Yonom/assistant-ui-a2a",
        ),
    )

    request_handler = DefaultRequestHandler(
        agent_executor=KitchenSinkExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    print(f"Starting A2A Kitchen Sink Server on {host}:{port}")
    print(f"Skills: {', '.join(s.name for s in skills)}")
    uvicorn.run(server.build(), host=host, port=port)
