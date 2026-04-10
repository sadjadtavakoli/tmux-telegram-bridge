#!/usr/bin/env python3
"""Claude Code <-> Telegram bridge daemon."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import sys
import time

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters


class PromptDetector:
    """Detects when Claude Code is waiting for user input."""

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

    PROMPT_PATTERNS = [
        r"(?:Allow|Deny)",
        r"\(y\)es.*\(n\)o",
        r"\[y/n\]",
        r"❯\s*$",
        r">\s*$",
        r"\?\s*$",
    ]

    @staticmethod
    def extract_context(content: str, max_lines: int = 20) -> str:
        """Extract the last N lines of content as context."""
        all_lines = content.strip().split("\n")
        return "\n".join(all_lines[-max_lines:])

    @staticmethod
    def has_prompt(lines: list[str]) -> bool:
        """Check if any lines match a known prompt pattern."""
        for line in lines:
            for pattern in PromptDetector.PROMPT_PATTERNS:
                if re.search(pattern, line):
                    return True
        return False


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


async def poll_tmux(app) -> None:
    """Poll tmux pane and send Telegram notifications when prompts detected."""
    detector = PromptDetector(quiescence_seconds=QUIESCENCE_SECONDS)
    await app.bot.send_message(chat_id=CHAT_ID, text="Bridge connected. Monitoring Claude Code session.")
    while True:
        content = capture_pane()
        context_text = detector.update(content)
        if context_text:
            msg = f"Claude needs your input:\n---\n{context_text}\n---\nReply to respond."
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
