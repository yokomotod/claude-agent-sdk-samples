# CLI Rewind example

Demonstrates how to rewind conversation and file state using Claude Agent SDK.

Features:
- **Esc key** to interrupt a running response
- **/rewind** command to rewind to a previous message (undoes both conversation and file changes)

(caution: it works as `permission_mode="bypassPermissions"`)

## Usage

```
uv sync
uv run python main.py
```

## Demo

### Rewind conversation and files

```
> Create a text file
● Creating a text file.
● `sample.txt` created with sample content.

> Edit the file
● Editing the file.
● Added 2 lines to the file.

> /rewind

=== Rewind to: ===
  1. Edit the file
  0. Cancel
Select: 1
[Restoring files...]
[Rewound to: Create a text file...]

> What was my previous message?
● Your previous message was:

**"Create a text file"**
```

The `/rewind` command:
1. Shows messages that can be rewound (selecting = "undo this message")
2. Restores files to their state before that message was sent
3. Resumes conversation from the previous assistant response

### Interrupt with Esc key

Press **Esc** during response to interrupt:

```
> Hello
● Hello! How can I help...
[Esc: Interrupting...]
```

Note: `interrupt()` stops the response but **does not rewind the conversation**.
Use `/rewind` to undo messages from conversation history.
