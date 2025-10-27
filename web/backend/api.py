import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


app = FastAPI()

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
    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        permission_mode="bypassPermissions",  # Caution!
        resume=last_session_id,
    )

    async for message in query(prompt=prompt, options=options):
        print(f"[debug] {message}")

        data = asdict(message)
        data["type"] = type(message).__name__

        if isinstance(message, AssistantMessage):
            for i, block in enumerate(message.content):
                if isinstance(block, TextBlock):
                    block_data = asdict(block)
                    block_data["type"] = type(block).__name__
                    data["content"][i] = block_data

        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
