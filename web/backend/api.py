import json
from collections.abc import AsyncIterator
from dataclasses import asdict

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


app = FastAPI()

# Session management: session_id -> ClaudeSDKClient
_client_sessions: dict[str, ClaudeSDKClient] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
)


class Payload(BaseModel):
    prompt: str
    last_session_id: str | None


@app.post("/api/chat")
async def chat(
    payload: Payload,
) -> StreamingResponse:
    return StreamingResponse(
        generate_response(payload.prompt, payload.last_session_id),
        media_type="text/event-stream",
    )


async def generate_response(
    prompt: str, last_session_id: str | None
) -> AsyncIterator[str]:
    client = _client_sessions.get(last_session_id) if last_session_id else None

    if client is None:
        options = ClaudeAgentOptions(
            system_prompt={"type": "preset", "preset": "claude_code"},
            setting_sources=["user", "project", "local"],
            permission_mode="bypassPermissions",  # Caution!
            resume=last_session_id,
        )
        client = ClaudeSDKClient(options=options)
        await client.connect()

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
