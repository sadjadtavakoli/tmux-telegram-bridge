#!/usr/bin/env python3
"""Claude Code <-> Telegram bridge daemon."""

from __future__ import annotations

import hashlib
import re
import time


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
