from __future__ import annotations

import re


PATTERNS = (
    re.compile(r"^\s*i\s+want\s+to\s+(?:see|watch)\s+(.+?)\s+when\s+it\s+(?:releases|comes\s+out)\s*[.!]?\s*$", re.IGNORECASE),
    re.compile(r"^\s*remind\s+me\s+about\s+(.+?)\s+when\s+it\s+(?:releases|comes\s+out)\s*[.!]?\s*$", re.IGNORECASE),
)


def match_prospective_movie(message: str) -> str | None:
    for pattern in PATTERNS:
        match = pattern.match(message)
        if match:
            title = " ".join(match.group(1).split()).strip(" \"'")
            return title[:255] if title else None
    return None
