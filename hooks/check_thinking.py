#!/usr/bin/env python3
"""
Stop hook: blocks responses that lack the _I THOUGHT_ marker or evidence.

The marker proves Claude worked through the 5-question deliberation
checklist before producing output. Without it, the response was likely
generated on autopilot. Short responses (< 40 chars) are exempt — not
every "Done." needs a full deliberation cycle.

The hook also requires every substantive response to include either an
<EVIDENCE> block (facts supporting the output) or <CONJECTURE> blocks
(explicitly flagging unsupported claims). A response with neither is
blocked.

The hook checks both the last assistant message and the full transcript
(if available) because markers may appear in an earlier text block
of the same turn, before tool calls.
"""

import json
import re
import sys

MARKER = "_I THOUGHT_"
MIN_LENGTH = 40

_EVIDENCE_RE = re.compile(r"\*\*EVIDENCE:\*\*", re.IGNORECASE)
_CONJECTURE_RE = re.compile(r"\*\*CONJECTURE:\*\*", re.IGNORECASE)


def check_thinking(message: str) -> str | None:
    if len(message) < MIN_LENGTH:
        return None
    if MARKER in message:
        return None
    return (
        "Response missing _I THOUGHT_ proof of checklist. "
        "Work through the 5 questions before responding."
    )


def check_evidence(message: str) -> str | None:
    if len(message) < MIN_LENGTH:
        return None
    if _EVIDENCE_RE.search(message):
        return None
    if _CONJECTURE_RE.search(message):
        return None
    return (
        "Response missing **EVIDENCE:** or **CONJECTURE:** block. "
        "Every substantive response must cite supporting facts "
        "or explicitly flag unsupported claims."
    )


def check_transcript_for_pattern(transcript_path: str, pattern: re.Pattern | str) -> bool:
    """Search the current assistant turn in the transcript for a pattern.

    Works with both compiled regexes and plain strings.
    """
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

    joined = "\n".join(assistant_texts)
    if isinstance(pattern, re.Pattern):
        return pattern.search(joined) is not None
    return pattern in joined


def check_transcript_for_marker(transcript_path: str) -> bool:
    return check_transcript_for_pattern(transcript_path, MARKER)


def _check_in_transcript_or_message(transcript_path: str | None, message: str,
                                     pattern: re.Pattern | str) -> bool:
    """Return True if pattern is found in transcript turn or message."""
    if transcript_path and check_transcript_for_pattern(transcript_path, pattern):
        return True
    if isinstance(pattern, re.Pattern):
        return pattern.search(message) is not None
    return pattern in message


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

    # Check _I THOUGHT_ marker
    if not _check_in_transcript_or_message(transcript_path, message, MARKER):
        print(
            "Response missing _I THOUGHT_ proof of checklist. "
            "Work through the 5 questions before responding.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Check evidence/conjecture
    has_evidence = _check_in_transcript_or_message(transcript_path, message, _EVIDENCE_RE)
    has_conjecture = _check_in_transcript_or_message(transcript_path, message, _CONJECTURE_RE)
    if not has_evidence and not has_conjecture:
        print(
            "Response missing **EVIDENCE:** or **CONJECTURE:** block. "
            "Every substantive response must cite supporting facts "
            "or explicitly flag unsupported claims.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)
