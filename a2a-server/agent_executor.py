"""
Chat agent executor using OpenAI for the A2A server.
"""

import os

import openai

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


class ChatAgentExecutor(AgentExecutor):
    """A2A agent executor that uses OpenAI to generate responses."""

    def __init__(self):
        self._client = None
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def client(self):
        if self._client is None:
            self._client = openai.AsyncOpenAI()
        return self._client

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Extract user message text from the request
        user_text = ""
        if context.message:
            for part in context.message.parts:
                if part.root.kind == "text":
                    user_text = part.root.text
                    break

        if not user_text:
            await event_queue.enqueue_event(
                new_agent_text_message("I didn't receive any text message.")
            )
            return

        # Call OpenAI
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {"role": "user", "content": user_text},
            ],
        )

        result = response.choices[0].message.content or "No response generated."
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise Exception("cancel not supported")
