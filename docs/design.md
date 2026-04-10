# Claude Telegram Bridge — Design Spec

A lightweight Python daemon that bridges a phone (Telegram) to a running Claude Code CLI session (tmux). Push notifications when Claude needs input, reply via voice dictation.

## Architecture

Single Python process running alongside Claude Code in a tmux session.

```
tmux session "claude"
├── window 0: Claude Code CLI (the active session)
└── window 1: bridge.py (daemon, runs in background)
```

`bridge.py` runs two concurrent async tasks:

1. **Poller** — every 2 seconds, captures the tmux pane content and checks if Claude is waiting for input.
2. **Telegram bot** — listens for incoming messages from the user and relays them into the tmux pane.

## Prompt Detection

The poller runs `tmux capture-pane -t claude:0 -p` every 2 seconds and feeds the output to a `PromptDetector`.

### Detection algorithm

1. Compare captured content to the previous capture.
2. If content changed, update `last_content` and reset a quiescence timer.
3. If content has been stable for 3+ seconds (quiescent), scan the last 5 lines for prompt patterns.
4. If a pattern matches and we haven't already notified for this content, trigger a notification.

### Prompt patterns (regex)

| Pattern | What it catches |
|---|---|
| `Allow\|Deny` | Tool permission prompts |
| `\(y\)es.*\(n\)o` | Yes/no permission choices |
| `\[y/n\]` | Generic yes/no prompts |
| `❯\s*$` | Claude Code input prompt (waiting for new message) |
| `>\s*$` | Generic shell/input prompt |
| `\?\s*$` | Lines ending with a question mark |

### Deduplication

The detector stores a hash of the content at the time of the last notification. It will not re-notify until the content changes and becomes quiescent again with a new prompt.

### Context extraction

When a prompt is detected, the last 20 lines of pane output are included in the Telegram notification so the user has enough context to understand what Claude is asking.

## Telegram Interaction

### Bot setup (one-time)

1. Message @BotFather on Telegram, create a new bot, get the token.
2. Send a message to the bot to establish a chat.
3. Get the chat ID (the bridge prints it on first run, or use the Telegram API).
4. Store `BOT_TOKEN` and `CHAT_ID` in `.env`.

### Notifications sent to user

When a prompt is detected:

```
Claude needs your input:
---
[last 20 lines of tmux pane output]
---
Reply to respond.
```

When the bridge starts:

```
Bridge connected. Monitoring Claude Code session.
```

### User replies

Any text message from the user is relayed into the tmux pane via:

```bash
tmux send-keys -t claude:0 "<message>" Enter
```

This works for:
- Permission responses: "y", "yes", "n"
- New instructions: "push the changes", "check the PR status"
- Feedback: "that looks wrong, revert the last change"
- Any free-form text Claude would accept

### Utility commands

| Command | Action |
|---|---|
| `/screen` | Capture and send the last 40 lines of pane output |
| `/status` | Report whether Claude is working or waiting for input |
| `/stop` | Shut down the bridge daemon |

## Project Structure

```
~/Projects/claude-telegram-bridge/
├── bridge.py          # Single-file daemon
├── launcher.sh        # Starts tmux session + Claude Code + bridge
├── requirements.txt   # python-telegram-bot, python-dotenv
├── .env.example       # Template: BOT_TOKEN=, CHAT_ID=
└── README.md          # Setup instructions
```

### bridge.py (~200 lines)

Single file containing:
- `PromptDetector` class — quiescence + pattern matching logic
- `poll_tmux()` async function — capture pane, run detection, send notifications
- `handle_message()` — Telegram message handler, relays text to tmux
- `handle_command()` — handles /screen, /status, /stop
- `main()` — starts poller + Telegram bot concurrently with asyncio

### launcher.sh

```bash
#!/bin/bash
SESSION="claude"
BRIDGE_DIR="$(dirname "$0")"

# Kill existing session if any
tmux kill-session -t "$SESSION" 2>/dev/null

# Create session with Claude Code
tmux new-session -d -s "$SESSION" -n claude "claude"

# Start bridge in a second window
tmux new-window -t "$SESSION" -n bridge "cd $BRIDGE_DIR && python3 bridge.py"

# Attach
tmux attach -t "$SESSION"
```

## Configuration

All configuration via `.env` file in the project directory:

```
BOT_TOKEN=<telegram bot token from BotFather>
CHAT_ID=<your telegram chat ID>
TMUX_SESSION=claude
TMUX_TARGET=claude:0
POLL_INTERVAL=2
QUIESCENCE_SECONDS=3
```

## Dependencies

- `python-telegram-bot>=21.0` — async Telegram bot framework
- `python-dotenv` — load .env config
- Python 3.10+ (system Python)
- tmux 3.6+ (system tmux)

No external APIs, no server, no cloud. Runs entirely on the local Mac.

## Edge Cases

- **Claude generating long output**: Content keeps changing, quiescence timer resets. No false notifications.
- **Multiple rapid prompts**: Each new prompt changes the content, so after quiescence the latest prompt is notified.
- **User sends message while Claude is working**: `tmux send-keys` buffers the input; Claude sees it when it next reads stdin.
- **Bridge crashes**: Claude Code keeps running in tmux. Restart bridge with `python3 bridge.py` in window 1. No data loss.
- **Mac sleeps**: tmux session persists. Bridge reconnects to Telegram on wake. May miss prompts during sleep — next poll catches up.
- **Multiple users**: Only `CHAT_ID` receives notifications and can send commands. Other users are ignored.

## Security

- Bot token and chat ID stored in `.env` (gitignored).
- Only the configured chat ID can interact with the bot.
- No data leaves the local machine except Telegram messages (which contain terminal output snippets).
- `.env` is in `.gitignore`.

## Daily Usage

```bash
# Start everything:
~/Projects/claude-telegram-bridge/launcher.sh

# Walk away. Get notifications on phone. Reply via dictation.

# Come back:
tmux attach -t claude

# Stop bridge without killing Claude:
# Send /stop in Telegram, or Ctrl+C in window 1
```
