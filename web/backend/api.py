import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    SystemMessage,
    TextBlock,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


# Session management: session_id -> ClaudeSDKClient
_client_sessions: dict[str, ClaudeSDKClient] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with a long-lived task group."""
    async with anyio.create_task_group() as tg:
        app.state.task_group = tg
        yield
        # Task group will be cleaned up when app shuts down


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
)


class Payload(BaseModel):
    prompt: str
    last_session_id: str | None


async def get_or_create_client(app: FastAPI, session_id: str | None) -> ClaudeSDKClient:
    """Get existing client or create a new one in the app's task group."""
    if session_id and session_id in _client_sessions:
        return _client_sessions[session_id]

    # Create new client
    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        permission_mode="bypassPermissions",  # Caution!
        resume=session_id,
    )
    client = ClaudeSDKClient(options=options)

    # Connect in the app's long-lived task group scope
    ready_event = anyio.Event()

    async def connect_in_app_scope():
        """Connect client in the lifespan task group scope."""
        await client.connect()
        ready_event.set()
        # Keep the task alive to maintain the client
        await anyio.Event().wait()

    # Start the connection task in the app's task group
    app.state.task_group.start_soon(connect_in_app_scope)

    # Wait for connection to be ready
    await ready_event.wait()

    # Store temporarily (will be updated with actual session_id)
    if session_id:
        _client_sessions[session_id] = client

    return client


@app.post("/api/chat")
async def chat(
    payload: Payload,
) -> StreamingResponse:
    return StreamingResponse(
        generate_response(app, payload.prompt, payload.last_session_id),
        media_type="text/event-stream",
    )


async def generate_response(
    app: FastAPI, prompt: str, last_session_id: str | None
) -> AsyncIterator[str]:
    # Get or create client
    client = await get_or_create_client(app, last_session_id)

    await client.query(prompt)

    async for message in client.receive_response():
        if isinstance(message, SystemMessage):
            session_id = message.data["session_id"]
            _client_sessions[session_id] = client

        data = asdict(message)
        data["type"] = type(message).__name__

        if isinstance(message, AssistantMessage):
            for i, block in enumerate(message.content):
                if isinstance(block, TextBlock):
                    block_data = asdict(block)
                    block_data["type"] = type(block).__name__
                    data["content"][i] = block_data

        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
