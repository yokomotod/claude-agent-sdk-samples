from dataclasses import asdict

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    """Message from client to server."""
    prompt: str


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for chat communication."""
    await websocket.accept()

    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        permission_mode="bypassPermissions",
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            while True:
                message_data = await websocket.receive_text()
                message = ChatMessage.model_validate_json(message_data)

                await client.query(message.prompt)

                async for response_message in client.receive_response():
                    data = asdict(response_message)
                    data["type"] = type(response_message).__name__

                    if isinstance(response_message, AssistantMessage):
                        for i, block in enumerate(response_message.content):
                            if isinstance(block, TextBlock):
                                block_data = asdict(block)
                                block_data["type"] = type(block).__name__
                                data["content"][i] = block_data

                    await websocket.send_json(data)

    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        await websocket.close(code=1011, reason=str(e))
