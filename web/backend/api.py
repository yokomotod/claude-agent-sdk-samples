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
    # Debug: Check ASGI spec version
    import inspect
    frame = inspect.currentframe()
    if frame and frame.f_back and frame.f_back.f_locals.get('scope'):
        scope = frame.f_back.f_locals['scope']
        spec_version = scope.get("asgi", {}).get("spec_version", "unknown")
        print(f"[debug] ASGI spec version: {spec_version}")
    return StreamingResponse(
        generate_response(payload.prompt, payload.last_session_id),
        media_type="text/event-stream",
    )


async def generate_response(
    prompt: str, last_session_id: str | None
) -> AsyncIterator[str]:
    print(f"[debug] api.py: generate_response started")
    try:
        client = _client_sessions.get(last_session_id) if last_session_id else None

        if client is None:
            if last_session_id:
                print(
                    f"[debug] Starting new session (resuming from last_session_id={last_session_id})"
                )
            else:
                print(
                    f"[debug] Starting new session (no last_session_id provided)"
                )
            options = ClaudeAgentOptions(
                system_prompt={"type": "preset", "preset": "claude_code"},
                setting_sources=["user", "project", "local"],
                permission_mode="bypassPermissions",  # Caution!
                resume=last_session_id,
            )
            client = ClaudeSDKClient(options=options)
            await client.connect()
        else:
            print(f"[debug] Continuing existing session (session_id={last_session_id})")

        print(f"[debug] api.py: About to call client.query() with prompt: {prompt[:50]}...")
        await client.query(prompt)
        print(f"[debug] api.py: client.query() completed")

        print(f"[debug] api.py: About to start iterating client.receive_response()")
        async for message in client.receive_response():
            print(f"[debug] api.py: Received message: {message}")

            if isinstance(message, SystemMessage):
                session_id = message.data["session_id"]
                if last_session_id:
                    assert session_id == last_session_id, (
                        f"Session ID mismatch: expected {last_session_id}, got {session_id}"
                    )
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
    finally:
        print(f"[debug] api.py: generate_response ending (generator cleanup)")



    # print("[debug] Sending test query to establish session")
    # await client.query("てすと")

    # async for message in client.receive_response():
    #     print(f"[debug] {message}")

    #     if isinstance(message, SystemMessage):
    #         session_id = message.data["session_id"]
    #         if last_session_id:
    #             assert session_id == last_session_id, (
    #                 f"Session ID mismatch: expected {last_session_id}, got {session_id}"
    #             )
    #             assert client == _client_sessions[session_id], (
    #                 "Client instance mismatch for the same session ID"
    #             )
    #         _client_sessions[session_id] = client

    #     data = asdict(message)
    #     data["type"] = type(message).__name__

    #     if isinstance(message, AssistantMessage):
    #         for i, block in enumerate(message.content):
    #             if isinstance(block, TextBlock):
    #                 block_data = asdict(block)
    #                 block_data["type"] = type(block).__name__
    #                 data["content"][i] = block_data

    #     yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
