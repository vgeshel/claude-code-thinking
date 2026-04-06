#!/usr/bin/env python3
"""
Stop hook: blocks responses that begin with sycophantic agreement phrases.

Sycophancy is a canary for shallow thinking. When Claude reflexively agrees
("you're right", "good point", "great idea"), it usually means it hasn't
evaluated the user's input deeply enough. This hook forces a full rethink,
not just a surface-level rephrasing that removes the trigger phrase.
"""

import json
import re
import sys

SYCOPHANCY_PATTERNS = [
    re.compile(r"you.re right", re.IGNORECASE),
    re.compile(r"you are right", re.IGNORECASE),
    re.compile(r"good point", re.IGNORECASE),
    re.compile(r"great idea", re.IGNORECASE),
    re.compile(r"that makes sense", re.IGNORECASE),
    re.compile(r"good catch", re.IGNORECASE),
    re.compile(r"excellent suggestion", re.IGNORECASE),
    re.compile(r"absolutely right", re.IGNORECASE),
    re.compile(r"that.s a great", re.IGNORECASE),
    re.compile(r"great question", re.IGNORECASE),
    re.compile(r"good question", re.IGNORECASE),
]


def check_sycophancy(message: str) -> str | None:
    snippet = message[:300]
    for pattern in SYCOPHANCY_PATTERNS:
        if pattern.search(snippet):
            return (
                f'Sycophancy detected: "{snippet[:80]}..." — reflexive agreement '
                "is a sign of shallow thinking. Stop, re-examine the user's input "
                "critically, and respond with your honest, independent assessment. "
                "Do not simply remove the agreeable phrase — actually rethink."
            )
    return None


if __name__ == "__main__":
    try:
        parsed = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if parsed.get("stop_hook_active"):
        sys.exit(0)

    message = parsed.get("last_assistant_message", "")
    result = check_sycophancy(message)
    if result:
        print(result, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
