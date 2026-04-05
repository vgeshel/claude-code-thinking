#!/usr/bin/env python3
"""
Stop hook: blocks responses that lack the _I THOUGHT_ marker.

The marker proves Claude worked through the 5-question deliberation
checklist before producing output. Without it, the response was likely
generated on autopilot. Short responses (< 40 chars) are exempt — not
every "Done." needs a full deliberation cycle.

The hook checks both the last assistant message and the full transcript
(if available) because the marker may appear in an earlier text block
of the same turn, before tool calls.
"""

import json
import sys

MARKER = "_I THOUGHT_"
MIN_LENGTH = 40


def check_thinking(message: str) -> str | None:
    if len(message) < MIN_LENGTH:
        return None
    if MARKER in message:
        return None
    return (
        "Response missing _I THOUGHT_ proof of checklist. "
        "Work through the 5 questions before responding."
    )


def check_transcript_for_marker(transcript_path: str) -> bool:
    try:
        with open(transcript_path, "r") as f:
            lines = f.read().strip().split("\n")
    except (OSError, IOError):
        return False

    assistant_texts: list[str] = []
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        entry_type = parsed.get("type", "")
        message = parsed.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []

        # Stop at real user messages, but skip tool_result entries (they're
        # interleaved in the same turn between assistant tool_use and response)
        if entry_type == "user":
            is_tool_result = any(
                isinstance(block, dict) and block.get("type") == "tool_result"
                for block in content
            )
            if not is_tool_result:
                break
            continue

        if entry_type == "assistant" and content:
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ):
                    assistant_texts.append(block["text"])

    return MARKER in "\n".join(assistant_texts)


if __name__ == "__main__":
    try:
        parsed = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if parsed.get("stop_hook_active"):
        sys.exit(0)

    message = parsed.get("last_assistant_message", "")
    if len(message) < MIN_LENGTH:
        sys.exit(0)

    transcript_path = parsed.get("transcript_path")
    if transcript_path and check_transcript_for_marker(transcript_path):
        sys.exit(0)

    if MARKER in message:
        sys.exit(0)

    print(
        "Response missing _I THOUGHT_ proof of checklist. "
        "Work through the 5 questions before responding.",
        file=sys.stderr,
    )
    sys.exit(2)
