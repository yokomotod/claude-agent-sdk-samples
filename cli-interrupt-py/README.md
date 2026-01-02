# CLI Interrupt example

Demonstrates how to interrupt a running response with Esc key using Claude Agent SDK.

(caution: it works as `permission_mode="bypassPermissions"`)

## Usage

```
uv sync
uv run python main.py
```

## Demo

Press **Esc** during response to interrupt:

```
> Hello
[debug] SystemMessage(subtype='init', ...)

[Esc: Interrupting...]
[debug] UserMessage(content=[TextBlock(text='[Request interrupted by user]')], ...)

[debug] ResultMessage(subtype='error_during_execution', ...)

> Hello
[debug] SystemMessage(subtype='init', ...)

[Esc: Interrupting...]
[debug] UserMessage(content=[TextBlock(text='[Request interrupted by user]')], ...)

[debug] ResultMessage(subtype='error_during_execution', ...)

> Hello (how many times did I say "Hello"?)
[debug] SystemMessage(subtype='init', ...)

[debug] AssistantMessage(content=[TextBlock(text='Hello!\n\nYou said "Hello" **3 times** in this conversation...')])

● Hello!

You said "Hello" **3 times** in this conversation.

[debug] ResultMessage(subtype='success', ...)

>
```

Note: `interrupt()` stops the response but **does not rewind the conversation**.
The interrupted messages remain in the conversation history (as shown above - the agent remembers all 3 "Hello" messages).
