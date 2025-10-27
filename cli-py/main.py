import readline  # for better input

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    SystemMessage,
    TextBlock,
    query,
    ClaudeAgentOptions,
)


async def main():
    last_session_id = None

    while True:
        user_input = input("> ")
        if user_input.lower() == "/exit":
            break
        if not user_input.strip():
            continue

        options = ClaudeAgentOptions(
            system_prompt={"type": "preset", "preset": "claude_code"},
            setting_sources=["user", "project", "local"],
            permission_mode="bypassPermissions",  # Caution!
            resume=last_session_id,  # note: must resume since it launches new `claude -p` process every time
        )

        async for message in query(prompt=user_input.strip(), options=options):
            print(f"[debug] {message}\n")

            if isinstance(message, SystemMessage):
                last_session_id = message.data["session_id"]

            if isinstance(message, AssistantMessage):
                print("● ", end="")
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="")
                print("\n")


anyio.run(main)
