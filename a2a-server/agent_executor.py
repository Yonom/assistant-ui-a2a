"""
Kitchen-sink A2A agent executor demonstrating all major A2A features:
- Streaming text via TaskStatusUpdateEvent
- Artifacts (text, data, file)
- Task states (working, input-required, completed, failed, canceled)
- Multiple skills
"""

import asyncio
import base64
import os
import json

import openai

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Artifact,
    DataPart,
    FilePart,
    FileWithBytes,
    Message,
    Part,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from a2a.utils import new_agent_text_message, new_text_artifact, new_data_artifact


def _status_update(
    context: RequestContext,
    state: TaskState,
    text: str | None = None,
    final: bool = False,
) -> TaskStatusUpdateEvent:
    message = None
    if text:
        message = Message(
            role="agent",
            parts=[Part(root=TextPart(text=text))],
            message_id=f"status-{context.task_id}",
        )
    return TaskStatusUpdateEvent(
        task_id=context.task_id,
        context_id=context.context_id,
        status=TaskStatus(state=state, message=message),
        final=final,
    )


def _artifact_update(
    context: RequestContext,
    artifact: Artifact,
    append: bool = False,
    last_chunk: bool = True,
) -> TaskArtifactUpdateEvent:
    return TaskArtifactUpdateEvent(
        task_id=context.task_id,
        context_id=context.context_id,
        artifact=artifact,
        append=append,
        last_chunk=last_chunk,
    )


class KitchenSinkExecutor(AgentExecutor):
    """Dispatches to skill-specific handlers based on the request metadata."""

    def __init__(self):
        self._client = None
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._cancelled = set()

    @property
    def client(self):
        if self._client is None:
            self._client = openai.AsyncOpenAI()
        return self._client

    def _extract_text(self, context: RequestContext) -> str:
        if context.message:
            for part in context.message.parts:
                if part.root.kind == "text":
                    return part.root.text
        return ""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_text = self._extract_text(context)
        if not user_text:
            await event_queue.enqueue_event(
                new_agent_text_message("I didn't receive any text message.")
            )
            return

        # Route to skill based on keyword prefix
        lower = user_text.lower().strip()
        if lower.startswith("/artifacts"):
            await self._skill_artifacts(context, event_queue, user_text)
        elif lower.startswith("/multistep"):
            await self._skill_multistep(context, event_queue, user_text)
        elif lower.startswith("/fail"):
            await self._skill_fail(context, event_queue, user_text)
        elif lower.startswith("/slow"):
            await self._skill_slow(context, event_queue, user_text)
        else:
            await self._skill_chat(context, event_queue, user_text)

    async def _skill_chat(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        user_text: str,
    ) -> None:
        """Stream an OpenAI chat response with status updates."""
        await event_queue.enqueue_event(
            _status_update(context, TaskState.working, "Thinking...")
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_text},
            ],
            stream=True,
        )

        full_text = ""
        async for chunk in response:
            if context.task_id in self._cancelled:
                self._cancelled.discard(context.task_id)
                return
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                await event_queue.enqueue_event(
                    _status_update(context, TaskState.working, full_text)
                )

        await event_queue.enqueue_event(
            _status_update(context, TaskState.completed, full_text, final=True)
        )

    async def _skill_artifacts(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        user_text: str,
    ) -> None:
        """Generate artifacts: code, data, and file."""
        query = user_text.split(maxsplit=1)[1] if " " in user_text else "a Python hello world"

        await event_queue.enqueue_event(
            _status_update(context, TaskState.working, "Generating code...")
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Generate code for the user request. Return ONLY code, no markdown fences.",
                },
                {"role": "user", "content": query},
            ],
        )
        code = response.choices[0].message.content or "print('hello')"

        # Text artifact: the generated code
        await event_queue.enqueue_event(
            _artifact_update(
                context,
                new_text_artifact("Generated Code", code, "Source code"),
            )
        )

        await event_queue.enqueue_event(
            _status_update(context, TaskState.working, "Analyzing code...")
        )
        await asyncio.sleep(0.5)

        # Data artifact: metadata
        await event_queue.enqueue_event(
            _artifact_update(
                context,
                new_data_artifact(
                    "Code Metadata",
                    {
                        "language": "python",
                        "lines": len(code.splitlines()),
                        "characters": len(code),
                        "query": query,
                    },
                    "Analysis of the generated code",
                ),
            )
        )

        # File artifact: the code as a downloadable file
        file_bytes = base64.b64encode(code.encode()).decode()
        file_artifact = Artifact(
            artifact_id=f"file-{context.task_id}",
            name="code.py",
            description="Downloadable Python file",
            parts=[
                Part(
                    root=FilePart(
                        file=FileWithBytes(
                            bytes=file_bytes,
                            name="code.py",
                            mime_type="text/x-python",
                        )
                    )
                )
            ],
        )
        await event_queue.enqueue_event(
            _artifact_update(context, file_artifact)
        )

        await event_queue.enqueue_event(
            _status_update(
                context,
                TaskState.completed,
                f"Generated code with {len(code.splitlines())} lines and 3 artifacts.",
                final=True,
            )
        )

    async def _skill_multistep(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        user_text: str,
    ) -> None:
        """Demonstrate the input-required state."""
        query = user_text.split(maxsplit=1)[1] if " " in user_text else ""

        if not query:
            # First call: ask for input
            await event_queue.enqueue_event(
                _status_update(
                    context,
                    TaskState.input_required,
                    "What topic would you like me to research? Please reply with: /multistep <topic>",
                    final=True,
                )
            )
            return

        # Process the topic
        await event_queue.enqueue_event(
            _status_update(context, TaskState.working, f"Researching: {query}")
        )
        await asyncio.sleep(1)

        await event_queue.enqueue_event(
            _status_update(context, TaskState.working, f"Gathering sources on: {query}")
        )
        await asyncio.sleep(1)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Write a brief research summary (3-4 paragraphs) on the given topic.",
                },
                {"role": "user", "content": query},
            ],
        )
        result = response.choices[0].message.content or "No results."

        await event_queue.enqueue_event(
            _artifact_update(
                context,
                new_text_artifact("Research Summary", result, f"Research on: {query}"),
            )
        )

        await event_queue.enqueue_event(
            _status_update(context, TaskState.completed, result, final=True)
        )

    async def _skill_fail(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        user_text: str,
    ) -> None:
        """Demonstrate the failed state."""
        await event_queue.enqueue_event(
            _status_update(context, TaskState.working, "Starting operation...")
        )
        await asyncio.sleep(1)

        await event_queue.enqueue_event(
            _status_update(
                context,
                TaskState.failed,
                "Simulated failure: This skill intentionally fails to demonstrate error handling.",
                final=True,
            )
        )

    async def _skill_slow(
        self,
        context: RequestContext,
        event_queue: EventQueue,
        user_text: str,
    ) -> None:
        """Long-running task that can be cancelled."""
        steps = [
            "Initializing...",
            "Step 1/5: Loading data...",
            "Step 2/5: Processing...",
            "Step 3/5: Analyzing...",
            "Step 4/5: Compiling results...",
            "Step 5/5: Finalizing...",
        ]

        for i, step in enumerate(steps):
            if context.task_id in self._cancelled:
                self._cancelled.discard(context.task_id)
                return
            await event_queue.enqueue_event(
                _status_update(context, TaskState.working, step)
            )
            await asyncio.sleep(2)

        await event_queue.enqueue_event(
            _status_update(
                context,
                TaskState.completed,
                "Long-running task completed successfully after all 5 steps.",
                final=True,
            )
        )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        self._cancelled.add(context.task_id)
        await event_queue.enqueue_event(
            _status_update(
                context,
                TaskState.canceled,
                "Task was cancelled by the user.",
                final=True,
            )
        )
