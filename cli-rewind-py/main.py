import asyncio
from contextlib import asynccontextmanager
import os
import select
import sys
import tty
import termios
import readline  # for better input

from dataclasses import dataclass, field

from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    UserMessage,
    ResultMessage,
)


@dataclass
class HistoryEntry:
    """A single entry in the conversation history."""
    user_uuid: str
    assistant_uuid: str  # Used for resume_session_at
    content: str  # User message content


@dataclass
class SessionState:
    """Tracks session state for rewind support."""
    session_id: str | None = None
    history: list[HistoryEntry] = field(default_factory=list)

    def add_message(self, user_uuid: str, assistant_uuid: str, content: str):
        self.history.append(HistoryEntry(user_uuid=user_uuid, assistant_uuid=assistant_uuid, content=content))

    def get_rewind_targets(self) -> list[HistoryEntry]:
        """Get messages that can be rewound to (before sending them).

        First message excluded - no previous assistant response to resume from.
        """
        return self.history[1:] if len(self.history) > 1 else []


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


def show_rewind_menu(state: SessionState) -> HistoryEntry | None:
    """Show rewind menu and return selected entry, or None if cancelled."""
    targets = state.get_rewind_targets()
    if not targets:
        print("No messages to rewind to.")
        return None

    print("\n=== Rewind to: ===")
    for i, entry in enumerate(targets, 1):
        preview = entry.content[:50] + "..." if len(entry.content) > 50 else entry.content
        print(f"  {i}. {preview}")
    print("  0. Cancel")

    try:
        choice = input("Select: ").strip()
        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(targets):
            return targets[idx - 1]
    except (ValueError, EOFError, KeyboardInterrupt):
        pass
    return None


def create_options(
    resume: str | None = None,
    resume_session_at: str | None = None,
) -> ClaudeAgentOptions:
    """Create ClaudeAgentOptions with optional resume settings."""
    extra_args: dict[str, str | None] = {"replay-user-messages": None}
    if resume_session_at:
        extra_args["resume-session-at"] = resume_session_at

    return ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        permission_mode="bypassPermissions",  # Caution!
        extra_args=extra_args,
        resume=resume,
        enable_file_checkpointing=True,  # Required for rewind_files()
        env={**os.environ, "CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING": "1"},
    )


async def run_session(state: SessionState, rewind_to: str | None = None) -> str | None:
    """Run a conversation session. Returns rewind target uuid or None to exit."""
    # Truncate history if rewinding
    if rewind_to:
        for i, entry in enumerate(state.history):
            if entry.assistant_uuid == rewind_to:
                state.history = state.history[:i + 1]
                break
        else:
            raise ValueError(f"Rewind target not found in history: {rewind_to}")

    options = create_options(
        resume=state.session_id,
        resume_session_at=rewind_to,
    )

    async with ClaudeSDKClient(options=options) as client:
        if rewind_to:
            print(f"[Rewound to: {state.history[-1].content[:30]}...]")

        while True:
            try:
                user_input = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return None

            if user_input.lower() == "/exit":
                return None

            if user_input.lower() == "/rewind":
                entry = show_rewind_menu(state)
                if entry:
                    # "Rewind to before sending this message"
                    # - File: restore to checkpoint at this message's send time
                    # - Conversation: resume after previous turn's response
                    idx = state.history.index(entry)
                    prev_entry = state.history[idx - 1]  # Always exists (first message excluded)

                    print("[Restoring files...]")
                    await client.rewind_files(entry.user_uuid)
                    return prev_entry.assistant_uuid
                continue

            if not user_input.strip():
                continue

            current_user_uuid: str | None = None
            current_assistant_uuid: str | None = None
            await client.query(user_input.strip())

            async with esc_interruptable(client):
                # Use raw messages to get assistant uuid (not exposed in SDK's AssistantMessage)
                async for raw in client._query.receive_messages():
                    msg_type = raw.get("type")
                    print(f"[debug] {raw}\n")

                    if msg_type == "user":
                        # Only pucapture the first user message (not tool results)
                        content = raw.get("message", {}).get("content")
                        if current_user_uuid is None and isinstance(content, str):
                            current_user_uuid = raw.get("uuid")

                    elif msg_type == "assistant":
                        current_assistant_uuid = raw.get("uuid")
                        # Print assistant message
                        content = raw.get("message", {}).get("content", [])
                        print("● ", end="")
                        for block in content:
                            if block.get("type") == "text":
                                print(block.get("text", ""), end="")
                        print("\n")

                    elif msg_type == "result":
                        if state.session_id is None:
                            state.session_id = raw.get("session_id")
                        if current_user_uuid and current_assistant_uuid:
                            state.add_message(current_user_uuid, current_assistant_uuid, user_input.strip())
                        break  # End of response


async def main():
    state = SessionState()
    rewind_to = None

    while True:
        rewind_to = await run_session(state, rewind_to)
        if rewind_to is None:
            break

    print("Bye!")


asyncio.run(main())
