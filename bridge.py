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
        r"^❯\s*$",
        r"\?\s*$",
    ]

    @staticmethod
    def extract_context(content: str, max_lines: int = 20) -> str:
        """Extract the last N lines of content, cleaned of terminal noise."""
        all_lines = content.strip().split("\n")
        tail = all_lines[-max_lines:]
        cleaned = []
        for line in tail:
            stripped = line.strip()
            # Skip lines that are just horizontal rules (─, ━, ═, -)
            if stripped and all(c in "─━═─-—" for c in stripped):
                continue
            # Skip empty lines
            if not stripped:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

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
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))
QUIESCENCE_SECONDS = float(os.getenv("QUIESCENCE_SECONDS", "3"))

# Mutable target — changed via /watch command
current_target = os.getenv("TMUX_TARGET", "claude:1")


def list_panes() -> str:
    """List all tmux panes with their current commands."""
    result = subprocess.run(
        ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}  #{pane_current_command}  #{window_name}"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def capture_pane(target: str | None = None, history: int = 200) -> str:
    """Capture the visible content of a tmux pane."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target or current_target, "-p", "-S", f"-{history}"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def send_keys(text: str, target: str | None = None) -> None:
    """Send keystrokes to a tmux pane."""
    subprocess.run(["tmux", "send-keys", "-t", target or current_target, "--", text, "Enter"])


def authorized(update: Update) -> bool:
    """Only allow messages from the configured chat ID."""
    return update.effective_chat.id == CHAT_ID


def send_tmux_keys(keys: list[str], target: str | None = None) -> None:
    """Send a sequence of tmux key names one at a time with a delay between them."""
    t = target or current_target
    for key in keys:
        subprocess.run(["tmux", "send-keys", "-t", t, key])
        time.sleep(0.15)


# Claude Code uses interactive menus (arrow keys + Enter).
# The first option is pre-selected, so Enter = accept first option.
# Map voice-friendly words to tmux key sequences.
MENU_MAPPINGS = {
    # Accept first option (usually "Allow once")
    "yes": (["Enter"], "Enter (accept)"),
    "yeah": (["Enter"], "Enter (accept)"),
    "yep": (["Enter"], "Enter (accept)"),
    "allow": (["Enter"], "Enter (accept)"),
    "ok": (["Enter"], "Enter (accept)"),
    "okay": (["Enter"], "Enter (accept)"),
    "accept": (["Enter"], "Enter (accept)"),
    "confirm": (["Enter"], "Enter (accept)"),
    "y": (["Enter"], "Enter (accept)"),
    # Second option (usually "Allow always" or similar)
    "always": (["Down", "Enter"], "Down + Enter (2nd option)"),
    "allow always": (["Down", "Enter"], "Down + Enter (2nd option)"),
    # Deny / last option
    "no": (["Escape"], "Escape (deny/cancel)"),
    "nope": (["Escape"], "Escape (deny/cancel)"),
    "deny": (["Escape"], "Escape (deny/cancel)"),
    "cancel": (["Escape"], "Escape (deny/cancel)"),
    "n": (["Escape"], "Escape (deny/cancel)"),
    # Navigation keys
    "up": (["Up"], "Up arrow"),
    "down": (["Down"], "Down arrow"),
    "enter": (["Enter"], "Enter"),
    "escape": (["Escape"], "Escape"),
    "esc": (["Escape"], "Escape"),
    "tab": (["Tab"], "Tab"),
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Relay incoming Telegram messages to the tmux pane."""
    if not authorized(update):
        return
    text = update.message.text.strip()
    lower = text.lower()

    # Check for menu/key mappings
    if lower in MENU_MAPPINGS:
        keys, label = MENU_MAPPINGS[lower]
        send_tmux_keys(keys)
        await update.message.reply_text(f"Sent: {label}")
    # Numeric selection: "1" = Enter, "2" = Down+Enter, "3" = Down+Down+Enter
    elif lower in ("1", "2", "3", "4", "5"):
        n = int(lower)
        keys = ["Down"] * (n - 1) + ["Enter"]
        send_tmux_keys(keys)
        label = f"Option {n}" if n > 1 else "Enter (1st option)"
        await update.message.reply_text(f"Sent: {label}")
    else:
        # Regular message — send with Enter for Claude's input prompt
        send_keys(text)
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


async def handle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch which tmux pane the bridge monitors."""
    global current_target
    if not authorized(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(f"Currently watching: {current_target}\n\nUsage: /watch <session:window.pane>\nExample: /watch 0:1\n\nUse /list to see available panes.")
        return
    new_target = args[0]
    # Verify the target exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", new_target.split(":")[0].split(".")[0]],
        capture_output=True,
    )
    current_target = new_target
    # Reset detector so it doesn't carry stale state from the previous pane
    global _detector
    _detector = PromptDetector(quiescence_seconds=QUIESCENCE_SECONDS)
    await update.message.reply_text(f"Now watching: {current_target}")


async def handle_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available tmux panes."""
    if not authorized(update):
        return
    panes = list_panes()
    msg = f"Available panes:\n\n{panes}\n\nCurrently watching: {current_target}\n\nUse /watch <target> to switch."
    await update.message.reply_text(msg)


async def handle_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shut down the bridge."""
    if not authorized(update):
        return
    await update.message.reply_text("Bridge shutting down.")
    sys.exit(0)


_detector = None

async def poll_tmux(app) -> None:
    """Poll tmux pane and send Telegram notifications when prompts detected."""
    global _detector
    _detector = PromptDetector(quiescence_seconds=QUIESCENCE_SECONDS)
    await app.bot.send_message(chat_id=CHAT_ID, text=f"Bridge connected. Watching: {current_target}")
    while True:
        content = capture_pane()
        context_text = _detector.update(content)
        if context_text:
            msg = f"Claude needs your input:\n\n{context_text}"
            if len(msg) > 4000:
                msg = msg[-4000:]
            await app.bot.send_message(chat_id=CHAT_ID, text=msg)
        await asyncio.sleep(POLL_INTERVAL)


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: Set BOT_TOKEN and CHAT_ID in .env")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("screen", handle_screen))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("watch", handle_watch))
    app.add_handler(CommandHandler("list", handle_list))
    app.add_handler(CommandHandler("stop", handle_stop))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print(f"Bridge starting. Monitoring tmux target: {current_target}")

    async def run() -> None:
        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            poller_task = asyncio.create_task(poll_tmux(app))
            print("Bridge running. Press Ctrl+C to stop.")
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            finally:
                poller_task.cancel()
                await app.updater.stop()
                await app.stop()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nBridge stopped.")


if __name__ == "__main__":
    main()
