# Claude Telegram Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python daemon that bridges Telegram to a running Claude Code CLI session via tmux, enabling remote interaction from a phone.

**Architecture:** Single-file Python daemon (`bridge.py`) running in a tmux window alongside Claude Code. Polls tmux pane content to detect prompts, sends Telegram notifications, and relays replies back via `tmux send-keys`. A launcher script starts everything in one command.

**Tech Stack:** Python 3.10, python-telegram-bot v21+, python-dotenv, tmux, pytest

**Spec:** `docs/superpowers/specs/2026-04-09-claude-telegram-bridge-design.md`

---

## File Structure

```
~/Projects/claude-telegram-bridge/
├── bridge.py          # Daemon: PromptDetector + tmux functions + Telegram handlers + main
├── test_bridge.py     # Tests for PromptDetector
├── launcher.sh        # Starts tmux session + Claude Code + bridge
├── requirements.txt   # python-telegram-bot, python-dotenv, pytest
├── .env.example       # Template for BOT_TOKEN, CHAT_ID
├── .gitignore         # .env, __pycache__, .venv
└── README.md          # Setup instructions
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `~/Projects/claude-telegram-bridge/requirements.txt`
- Create: `~/Projects/claude-telegram-bridge/.env.example`
- Create: `~/Projects/claude-telegram-bridge/.gitignore`

- [ ] **Step 1: Create project directory and initialize git**

```bash
mkdir -p ~/Projects/claude-telegram-bridge
cd ~/Projects/claude-telegram-bridge
git init
```

- [ ] **Step 2: Create requirements.txt**

Write to `requirements.txt`:

```
python-telegram-bot>=21.0
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 3: Create .env.example**

Write to `.env.example`:

```
BOT_TOKEN=your-bot-token-from-botfather
CHAT_ID=your-telegram-chat-id
TMUX_TARGET=claude:0
POLL_INTERVAL=2
QUIESCENCE_SECONDS=3
```

- [ ] **Step 4: Create .gitignore**

Write to `.gitignore`:

```
.env
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 5: Create virtual environment and install dependencies**

```bash
cd ~/Projects/claude-telegram-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 6: Commit scaffolding**

```bash
cd ~/Projects/claude-telegram-bridge
git add requirements.txt .env.example .gitignore
git commit -m "Initialize project with dependencies and config template"
```

---

### Task 2: PromptDetector — Pattern Matching (TDD)

**Files:**
- Create: `~/Projects/claude-telegram-bridge/bridge.py`
- Create: `~/Projects/claude-telegram-bridge/test_bridge.py`

- [ ] **Step 1: Write failing tests for has_prompt**

Write to `test_bridge.py`:

```python
from bridge import PromptDetector


class TestHasPrompt:
    def test_detects_allow(self):
        assert PromptDetector.has_prompt(["Allow Read of foo.rb"]) is True

    def test_detects_deny(self):
        assert PromptDetector.has_prompt(["Deny this action"]) is True

    def test_detects_yes_no_choice(self):
        assert PromptDetector.has_prompt(["(y)es, (n)o, (a)lways"]) is True

    def test_detects_yn_bracket(self):
        assert PromptDetector.has_prompt(["Continue? [y/n]"]) is True

    def test_detects_claude_prompt_symbol(self):
        assert PromptDetector.has_prompt(["❯ "]) is True
        assert PromptDetector.has_prompt(["❯"]) is True

    def test_detects_question(self):
        assert PromptDetector.has_prompt(["Which approach do you prefer?"]) is True

    def test_ignores_regular_output(self):
        assert PromptDetector.has_prompt(["Reading file foo.rb..."]) is False
        assert PromptDetector.has_prompt(["def hello_world"]) is False

    def test_empty_input(self):
        assert PromptDetector.has_prompt([]) is False
        assert PromptDetector.has_prompt([""]) is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py::TestHasPrompt -v
```

Expected: `ImportError` — `bridge.py` doesn't exist yet.

- [ ] **Step 3: Write minimal bridge.py with has_prompt**

Write to `bridge.py`:

```python
#!/usr/bin/env python3
"""Claude Code <-> Telegram bridge daemon."""

import re


class PromptDetector:
    """Detects when Claude Code is waiting for user input."""

    PROMPT_PATTERNS = [
        r"(?:Allow|Deny)",
        r"\(y\)es.*\(n\)o",
        r"\[y/n\]",
        r"❯\s*$",
        r">\s*$",
        r"\?\s*$",
    ]

    @staticmethod
    def has_prompt(lines: list[str]) -> bool:
        """Check if any lines match a known prompt pattern."""
        for line in lines:
            for pattern in PromptDetector.PROMPT_PATTERNS:
                if re.search(pattern, line):
                    return True
        return False
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py::TestHasPrompt -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/claude-telegram-bridge
git add bridge.py test_bridge.py
git commit -m "Add PromptDetector.has_prompt with pattern matching"
```

---

### Task 3: PromptDetector — Context Extraction (TDD)

**Files:**
- Modify: `~/Projects/claude-telegram-bridge/bridge.py`
- Modify: `~/Projects/claude-telegram-bridge/test_bridge.py`

- [ ] **Step 1: Write failing tests for extract_context**

Append to `test_bridge.py`:

```python
class TestExtractContext:
    def test_extracts_last_n_lines(self):
        content = "\n".join(f"line {i}" for i in range(30))
        result = PromptDetector.extract_context(content, max_lines=5)
        assert result == "line 25\nline 26\nline 27\nline 28\nline 29"

    def test_returns_all_if_fewer_than_max(self):
        content = "line 1\nline 2\nline 3"
        result = PromptDetector.extract_context(content, max_lines=10)
        assert result == "line 1\nline 2\nline 3"

    def test_strips_trailing_whitespace(self):
        content = "line 1\nline 2\n\n"
        result = PromptDetector.extract_context(content)
        assert result == "line 1\nline 2"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py::TestExtractContext -v
```

Expected: `AttributeError` — `extract_context` doesn't exist yet.

- [ ] **Step 3: Add extract_context to PromptDetector**

Add to `PromptDetector` class in `bridge.py`, after `has_prompt`:

```python
    @staticmethod
    def extract_context(content: str, max_lines: int = 20) -> str:
        """Extract the last N lines of content as context."""
        all_lines = content.strip().split("\n")
        return "\n".join(all_lines[-max_lines:])
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py::TestExtractContext -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/claude-telegram-bridge
git add bridge.py test_bridge.py
git commit -m "Add PromptDetector.extract_context for notification context"
```

---

### Task 4: PromptDetector — Stateful Detection (TDD)

**Files:**
- Modify: `~/Projects/claude-telegram-bridge/bridge.py`
- Modify: `~/Projects/claude-telegram-bridge/test_bridge.py`

- [ ] **Step 1: Write failing tests for update**

Append to `test_bridge.py`:

```python
from unittest.mock import patch


class TestUpdate:
    def test_returns_none_on_first_content(self):
        detector = PromptDetector(quiescence_seconds=0)
        result = detector.update("Allow this?")
        assert result is None  # First call is always a content change

    def test_returns_context_when_quiescent_with_prompt(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Allow this?")
        result = detector.update("Allow this?")
        assert result is not None
        assert "Allow this?" in result

    def test_deduplicates_notifications(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Allow this?")
        detector.update("Allow this?")  # First notification
        result = detector.update("Allow this?")  # Same content — no re-notify
        assert result is None

    def test_notifies_again_after_content_changes(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Allow this?")
        detector.update("Allow this?")  # Notifies
        detector.update("Working...")  # Content changed
        detector.update("Allow that?")  # New content
        result = detector.update("Allow that?")  # New prompt — should notify
        assert result is not None
        assert "Allow that?" in result

    def test_no_notification_without_prompt_pattern(self):
        detector = PromptDetector(quiescence_seconds=0)
        detector.update("Just regular output")
        result = detector.update("Just regular output")
        assert result is None

    @patch("bridge.time.monotonic")
    def test_respects_quiescence_period(self, mock_time):
        mock_time.return_value = 100.0
        detector = PromptDetector(quiescence_seconds=3.0)
        detector.update("Allow this?")

        mock_time.return_value = 101.0  # 1s later — not quiescent
        result = detector.update("Allow this?")
        assert result is None

        mock_time.return_value = 104.0  # 4s later — quiescent
        result = detector.update("Allow this?")
        assert result is not None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py::TestUpdate -v
```

Expected: `TypeError` — `PromptDetector.__init__` doesn't accept `quiescence_seconds` yet.

- [ ] **Step 3: Add update method and __init__ to PromptDetector**

Add these imports to the top of `bridge.py`:

```python
import hashlib
import time
```

Add `__init__` and `update` to `PromptDetector` class, before `has_prompt`:

```python
    def __init__(self, quiescence_seconds: float = 3.0):
        self.last_content = ""
        self.last_change_time = 0.0
        self.last_notified_hash = ""
        self.quiescence_seconds = quiescence_seconds

    def update(self, content: str) -> str | None:
        """Feed new pane content. Returns context string if prompt detected, None otherwise."""
        now = time.monotonic()
        if content != self.last_content:
            self.last_content = content
            self.last_change_time = now
            return None
        if now - self.last_change_time < self.quiescence_seconds:
            return None
        content_hash = hashlib.md5(content.encode()).hexdigest()
        if content_hash == self.last_notified_hash:
            return None
        lines = content.strip().split("\n")
        tail = lines[-5:] if len(lines) >= 5 else lines
        if self.has_prompt(tail):
            self.last_notified_hash = content_hash
            return self.extract_context(content)
        return None
```

- [ ] **Step 4: Run all tests — verify they pass**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py -v
```

Expected: All 17 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/claude-telegram-bridge
git add bridge.py test_bridge.py
git commit -m "Add PromptDetector.update with quiescence and deduplication"
```

---

### Task 5: Bridge Daemon — tmux + Telegram + Main Loop

**Files:**
- Modify: `~/Projects/claude-telegram-bridge/bridge.py`

- [ ] **Step 1: Add tmux interaction functions**

Add these imports to the top of `bridge.py`:

```python
import asyncio
import os
import subprocess
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
```

Add after the `PromptDetector` class:

```python
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))
TMUX_TARGET = os.getenv("TMUX_TARGET", "claude:0")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))
QUIESCENCE_SECONDS = float(os.getenv("QUIESCENCE_SECONDS", "3"))


def capture_pane(target: str = TMUX_TARGET, history: int = 200) -> str:
    """Capture the visible content of a tmux pane."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target, "-p", "-S", f"-{history}"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def send_keys(text: str, target: str = TMUX_TARGET) -> None:
    """Send keystrokes to a tmux pane."""
    subprocess.run(["tmux", "send-keys", "-t", target, "--", text, "Enter"])
```

- [ ] **Step 2: Run existing tests — verify nothing broke**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py -v
```

Expected: All 17 tests still PASS.

- [ ] **Step 3: Add Telegram handlers**

Add after `send_keys` in `bridge.py`:

```python
def authorized(update: Update) -> bool:
    """Only allow messages from the configured chat ID."""
    return update.effective_chat.id == CHAT_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Relay incoming Telegram messages to the tmux pane."""
    if not authorized(update):
        return
    send_keys(update.message.text)
    await update.message.reply_text("Sent to Claude.")


async def handle_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send current pane content to the user."""
    if not authorized(update):
        return
    content = capture_pane(history=40)
    # Telegram message limit is 4096 chars
    text = content.strip() or "(empty)"
    if len(text) > 4000:
        text = text[-4000:]
    await update.message.reply_text(text)


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Report whether Claude is working or waiting."""
    if not authorized(update):
        return
    content = capture_pane()
    lines = content.strip().split("\n")
    tail = lines[-5:] if len(lines) >= 5 else lines
    if PromptDetector.has_prompt(tail):
        await update.message.reply_text("Waiting for your input.")
    else:
        await update.message.reply_text("Claude is working...")


async def handle_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shut down the bridge."""
    if not authorized(update):
        return
    await update.message.reply_text("Bridge shutting down.")
    sys.exit(0)
```

- [ ] **Step 4: Add the poller and main entry point**

Add after the handlers in `bridge.py`:

```python
async def poll_tmux(app) -> None:
    """Poll tmux pane and send Telegram notifications when prompts detected."""
    detector = PromptDetector(quiescence_seconds=QUIESCENCE_SECONDS)
    await app.bot.send_message(chat_id=CHAT_ID, text="Bridge connected. Monitoring Claude Code session.")
    while True:
        content = capture_pane()
        context_text = detector.update(content)
        if context_text:
            msg = f"Claude needs your input:\n---\n{context_text}\n---\nReply to respond."
            # Telegram message limit
            if len(msg) > 4000:
                msg = msg[-4000:]
            await app.bot.send_message(chat_id=CHAT_ID, text=msg)
        await asyncio.sleep(POLL_INTERVAL)


async def post_init(app) -> None:
    """Start the tmux poller after the Telegram bot initializes."""
    app.create_task(poll_tmux(app))


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: Set BOT_TOKEN and CHAT_ID in .env")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("screen", handle_screen))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("stop", handle_stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"Bridge starting. Monitoring tmux target: {TMUX_TARGET}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run all tests — verify nothing broke**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py -v
```

Expected: All 17 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/claude-telegram-bridge
git add bridge.py
git commit -m "Add tmux interaction, Telegram handlers, and main daemon loop"
```

---

### Task 6: Launcher Script

**Files:**
- Create: `~/Projects/claude-telegram-bridge/launcher.sh`

- [ ] **Step 1: Write launcher.sh**

Write to `launcher.sh`:

```bash
#!/bin/bash
set -e

SESSION="${TMUX_SESSION:-claude}"
BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check for .env
if [ ! -f "$BRIDGE_DIR/.env" ]; then
    echo "Error: .env not found. Copy .env.example to .env and fill in your credentials."
    echo "  cp $BRIDGE_DIR/.env.example $BRIDGE_DIR/.env"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already exists. Starting bridge only..."
else
    echo "Creating tmux session '$SESSION' with Claude Code..."
    tmux new-session -d -s "$SESSION" -n code
    tmux send-keys -t "$SESSION:code" "claude" Enter
fi

# Kill existing bridge window if present
if tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -q '^bridge$'; then
    tmux kill-window -t "$SESSION:bridge"
fi

# Start bridge in a new window
tmux new-window -t "$SESSION" -n bridge \
    "cd '$BRIDGE_DIR' && source .venv/bin/activate && python3 bridge.py; read -p 'Bridge exited. Press enter to close.'"

# Switch to the code window
tmux select-window -t "$SESSION:code"

# Attach or switch
if [ -n "$TMUX" ]; then
    tmux switch-client -t "$SESSION"
else
    tmux attach -t "$SESSION"
fi
```

- [ ] **Step 2: Make executable**

```bash
chmod +x ~/Projects/claude-telegram-bridge/launcher.sh
```

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/claude-telegram-bridge
git add launcher.sh
git commit -m "Add launcher script for tmux session management"
```

---

### Task 7: README

**Files:**
- Create: `~/Projects/claude-telegram-bridge/README.md`

- [ ] **Step 1: Write README.md**

Write to `README.md`:

```markdown
# Claude Telegram Bridge

Remote control your Claude Code CLI session from your phone via Telegram.
Get push notifications when Claude needs your input, reply by voice dictation.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram, message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, follow the prompts, pick a name
3. Copy the bot token

### 2. Get Your Chat ID

1. Message your new bot (send any message like "hello")
2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
3. Find `"chat":{"id":XXXXXXXX}` in the JSON — that's your chat ID

### 3. Configure

```bash
cd ~/Projects/claude-telegram-bridge
cp .env.example .env
# Edit .env with your BOT_TOKEN and CHAT_ID
```

### 4. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Start Everything

```bash
~/Projects/claude-telegram-bridge/launcher.sh
```

This creates a tmux session with Claude Code + the bridge. You'll get a Telegram message confirming the bridge is connected.

### From Your Phone

- **Receive notifications** when Claude needs your input
- **Reply** with text or voice dictation to respond
- `/screen` — see current terminal output
- `/status` — check if Claude is working or waiting
- `/stop` — shut down the bridge

### Come Back to Your Laptop

```bash
tmux attach -t claude
```

### Stop the Bridge Only

Send `/stop` in Telegram, or switch to the bridge window in tmux and press Ctrl+C.
```

- [ ] **Step 2: Commit**

```bash
cd ~/Projects/claude-telegram-bridge
git add README.md
git commit -m "Add README with setup and usage instructions"
```

---

### Task 8: End-to-End Verification

This task requires the user to have created their Telegram bot and configured `.env`.

- [ ] **Step 1: Verify project structure**

```bash
ls -la ~/Projects/claude-telegram-bridge/
```

Expected files: `bridge.py`, `test_bridge.py`, `launcher.sh`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `.venv/`

- [ ] **Step 2: Run all tests**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
pytest test_bridge.py -v
```

Expected: All 17 tests PASS.

- [ ] **Step 3: Verify bridge starts (requires .env)**

```bash
cd ~/Projects/claude-telegram-bridge
source .venv/bin/activate
timeout 5 python3 bridge.py 2>&1 || true
```

If `.env` is configured: prints "Bridge starting. Monitoring tmux target: claude:0" and sends Telegram message.
If `.env` is missing: prints "Error: Set BOT_TOKEN and CHAT_ID in .env".

- [ ] **Step 4: Full test with launcher**

```bash
~/Projects/claude-telegram-bridge/launcher.sh
```

Verify: tmux session created, Claude Code starts in window 0, bridge runs in window 1, Telegram notification received on phone.
