import readline  # for better input

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ClaudeSDKClient,
    ClaudeAgentOptions,
)


async def main():
    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        permission_mode="bypassPermissions",  # Caution!
    )

    async with ClaudeSDKClient(options=options) as client:
        while True:
            user_input = input("> ")
            if user_input.lower() == "/exit":
                break
            if not user_input.strip():
                continue

            await client.query(user_input.strip())

            async for message in client.receive_response():
                print(f"[debug] {message}\n")

                if isinstance(message, AssistantMessage):
                    print("● ", end="")
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text, end="")
                    print("\n")


anyio.run(main)
