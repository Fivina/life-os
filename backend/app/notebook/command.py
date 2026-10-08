from __future__ import annotations

import re


PATTERNS = (
    re.compile(r"^\s*write\s+this\s+down\s+as\s+an?\s+implementation\s+idea\s*[:,-]?\s*(.+)$", re.I | re.S),
    re.compile(r"^\s*(?:save|park)\s+this\s+as\s+an?\s+implementation\s+idea\s*[:,-]?\s*(.+)$", re.I | re.S),
)


def match_implementation_idea(message: str) -> str | None:
    for pattern in PATTERNS:
        match = pattern.match(message)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None
