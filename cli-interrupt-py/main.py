import asyncio
from contextlib import asynccontextmanager
import os
import select
import sys
import tty
import termios
import readline  # for better input

from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ClaudeSDKClient,
    ClaudeAgentOptions,
)


async def _watch_esc_key(client: ClaudeSDKClient, stop_fd: int):
    """Watch for Esc key and call interrupt."""
    fd = sys.stdin.fileno()

    def read_key_or_stop():
        """Read a single key in cbreak mode, or return None if stopped."""
        # Save current terminal settings to restore later
        old_settings = termios.tcgetattr(fd)
        try:
            # cbreak mode: unbuffered input (detect keypress immediately),
            # but output processing still works (newlines work correctly)
            tty.setcbreak(fd)
            while True:
                # Wait for either: user input OR stop signal via pipe
                readable, _, _ = select.select([sys.stdin, stop_fd], [], [])
                if stop_fd in readable:
                    return None
                if sys.stdin in readable:
                    return sys.stdin.read(1)
        finally:
            # Restore terminal from cbreak mode (set by tty.setcbreak above)
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    loop = asyncio.get_running_loop()
    while True:
        key = await loop.run_in_executor(None, read_key_or_stop)
        if key is None:  # stopped
            return
        if key == '\x1b':  # Esc key
            print("\n[Esc: Interrupting...]")
            await client.interrupt()
            return
        print(f"[debug] key {repr(key)} pressed, ignoring (press Esc to interrupt)")


@asynccontextmanager
async def esc_interruptable(client: ClaudeSDKClient):
    """Context manager that enables Esc key to interrupt the client."""
    stop_read_fd, stop_write_fd = os.pipe()
    task = asyncio.create_task(_watch_esc_key(client, stop_read_fd))
    try:
        yield
    finally:
        os.write(stop_write_fd, b'x')  # Signal to stop watching (wakes up select)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        os.close(stop_read_fd)
        os.close(stop_write_fd)


async def main():
    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        permission_mode="bypassPermissions",  # Caution!
    )

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                user_input = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_input.lower() == "/exit":
                break
            if not user_input.strip():
                continue

            await client.query(user_input.strip())

            async with esc_interruptable(client):
                async for message in client.receive_response():
                    print(f"[debug] {message}\n")

                    if isinstance(message, AssistantMessage):
                        print("● ", end="")
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                print(block.text, end="")
                        print("\n")

        print("Bye!")


asyncio.run(main())
