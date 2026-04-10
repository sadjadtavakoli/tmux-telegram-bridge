#!/usr/bin/env python3
"""Claude Code <-> Telegram bridge daemon."""

from __future__ import annotations

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
