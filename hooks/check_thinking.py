#!/usr/bin/env python3
"""
Stop hook: blocks responses that lack deliberation or structured evidence.

Three gates:

1. **_I THOUGHT_ marker** — proof the 5-question deliberation checklist
   was worked through before producing output.

2. **Structured EVIDENCE / CONJECTURE blocks** — every substantive response
   must include at least one of:
       **EVIDENCE:**     listing facts with typed refs (src/url/quote/knowledge)
       **CONJECTURE:**   listing assumptions with basis and likelihood
   Blocks are parsed; malformed blocks (empty, missing refs, invalid ref
   types, missing basis/likelihood) are rejected.

3. **Anti-fabrication** — the parser rejects ref shapes that are structurally
   invalid (e.g., a src ref without a file path and line number, a quote
   ref without session/ts metadata). This does not verify that refs point
   at real things — it only makes fabrication more work than honesty.

Short responses (< 40 chars) are exempt. Both the last assistant message
and the full current-turn transcript are checked, because markers and
blocks may appear in an earlier text block of the same turn, before tool
calls.
"""

import json
import re
import sys

MARKER = "_I THOUGHT_"
MIN_LENGTH = 40

# Header regexes — match markdown bold **EVIDENCE:** / **CONJECTURE:**
_EVIDENCE_HEADER_RE = re.compile(r"\*\*EVIDENCE:\*\*", re.IGNORECASE)
_CONJECTURE_HEADER_RE = re.compile(r"\*\*CONJECTURE:\*\*", re.IGNORECASE)

# Any top-level block header (used to find block boundaries)
_ANY_HEADER_RE = re.compile(r"\*\*(?:EVIDENCE|CONJECTURE):\*\*", re.IGNORECASE)

# Clause field regexes — `- claim:`, `- basis:`, `- likelihood:`
# Allow optional **bold** around the field name.
_CLAIM_RE = re.compile(
    r"^\s*-\s*(?:\*\*)?claim(?:\*\*)?\s*:\s*(.+?)\s*$", re.IGNORECASE
)
_BASIS_RE = re.compile(
    r"^\s*-\s*(?:\*\*)?basis(?:\*\*)?\s*:\s*(.+?)\s*$", re.IGNORECASE
)
_LIKELIHOOD_RE = re.compile(
    r"^\s*-\s*(?:\*\*)?likelihood(?:\*\*)?\s*:\s*(low|medium|high)\b.*$",
    re.IGNORECASE,
)

# Ref regexes — each ref sub-bullet starts with a type keyword.
_REF_URL_RE = re.compile(r"^\s*-\s*url\s*:\s*(https?://\S+)\s*$", re.IGNORECASE)
_REF_SRC_RE = re.compile(
    r"^\s*-\s*src\s*:\s*(\S+):(\d+)(?:-(\d+))?\s*$", re.IGNORECASE
)
_REF_QUOTE_RE = re.compile(r"^\s*-\s*quote\s*:\s*(.+?)\s*$", re.IGNORECASE)
_REF_KNOWLEDGE_RE = re.compile(
    r"^\s*-\s*knowledge\s*:\s*(.+?)\s*$", re.IGNORECASE
)

# Ref type keywords — used to detect unknown ref types and reject them.
_REF_TYPE_LINE_RE = re.compile(
    r"^\s*-\s*([a-zA-Z_]+)\s*:\s*.+$"
)
_KNOWN_REF_TYPES = {"url", "src", "quote", "knowledge"}
_CLAUSE_FIELDS = {"claim", "basis", "likelihood"}

# Quote ref must include session: and ts: metadata plus a "verbatim" string.
_QUOTE_SESSION_RE = re.compile(r"session\s*:\s*\S+", re.IGNORECASE)
_QUOTE_TS_RE = re.compile(r"ts\s*:\s*\S+", re.IGNORECASE)
_QUOTE_VERBATIM_RE = re.compile(r'"[^"]+"')


# ---------------------------------------------------------------------------
# Thinking marker check
# ---------------------------------------------------------------------------

def check_thinking(message: str) -> str | None:
    """Return an error message if the thinking marker is missing, else None."""
    if len(message) < MIN_LENGTH:
        return None
    if MARKER in message:
        return None
    return (
        "Response missing _I THOUGHT_ proof of checklist. "
        "Work through the 5 questions before responding."
    )


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_block(text: str, header_re: re.Pattern) -> str | None:
    """Return the text body of a block, from just after its header until
    the next EVIDENCE/CONJECTURE header or end of string. Returns None if
    the header is not present."""
    match = header_re.search(text)
    if not match:
        return None
    start = match.end()
    rest = text[start:]
    next_match = _ANY_HEADER_RE.search(rest)
    if next_match:
        return rest[: next_match.start()]
    return rest


# ---------------------------------------------------------------------------
# Ref parsing & validation
# ---------------------------------------------------------------------------

def _parse_ref_line(line: str) -> tuple[dict | None, str | None]:
    """Try to parse one ref sub-bullet. Returns (ref_dict, error).
    If the line doesn't look like a ref line at all, returns (None, None).
    If it looks like a ref but is malformed, returns (None, error_message)."""

    if m := _REF_URL_RE.match(line):
        return {"type": "url", "value": m.group(1)}, None

    if m := _REF_SRC_RE.match(line):
        path = m.group(1)
        start_line = int(m.group(2))
        end_line = int(m.group(3)) if m.group(3) else start_line
        if "/" not in path and "." not in path:
            return None, (
                f'invalid src ref (path must contain "/" or "."): '
                f"{line.strip()}"
            )
        if end_line < start_line:
            return None, (
                f"invalid src ref (end line before start): {line.strip()}"
            )
        return (
            {"type": "src", "path": path, "start": start_line, "end": end_line},
            None,
        )

    if m := _REF_QUOTE_RE.match(line):
        body = m.group(1)
        if not _QUOTE_VERBATIM_RE.search(body):
            return None, (
                'quote ref must include a verbatim "quoted" string: '
                f"{line.strip()}"
            )
        if not _QUOTE_SESSION_RE.search(body):
            return None, (
                f"quote ref must include session: metadata: {line.strip()}"
            )
        if not _QUOTE_TS_RE.search(body):
            return None, (
                f"quote ref must include ts: (timestamp) metadata: "
                f"{line.strip()}"
            )
        return {"type": "quote", "value": body}, None

    if m := _REF_KNOWLEDGE_RE.match(line):
        desc = m.group(1).strip()
        if len(desc) < 10:
            return None, (
                "knowledge ref must include a substantive, specific "
                f"description (>= 10 chars): {line.strip()}"
            )
        return {"type": "knowledge", "value": desc}, None

    # Line looks like a typed bullet but doesn't match any known ref shape.
    tm = _REF_TYPE_LINE_RE.match(line)
    if tm:
        kind = tm.group(1).lower()
        if kind in _KNOWN_REF_TYPES:
            # Matched the keyword but failed its specific regex — malformed.
            return None, f"malformed {kind} ref: {line.strip()}"
        if kind in _CLAUSE_FIELDS:
            # It's a clause field, not a ref — signal "not a ref".
            return None, None
        return None, (
            f'unknown ref type "{kind}" (allowed: url, src, quote, '
            f"knowledge): {line.strip()}"
        )

    # Not a recognisable ref-shaped line (e.g. blank, free text).
    return None, None


# ---------------------------------------------------------------------------
# EVIDENCE block parsing & validation
# ---------------------------------------------------------------------------

def parse_evidence_clauses(block_text: str) -> tuple[list[dict], str | None]:
    """Parse EVIDENCE block body into a list of {claim, refs} clauses.
    Returns (clauses, error). If error is non-None, clauses may be partial."""
    clauses: list[dict] = []
    current: dict | None = None

    for line in block_text.split("\n"):
        if not line.strip():
            continue

        claim_match = _CLAIM_RE.match(line)
        if claim_match:
            if current is not None:
                clauses.append(current)
            current = {"claim": claim_match.group(1).strip(), "refs": []}
            continue

        if current is None:
            # Stray non-claim text before the first claim — ignore.
            continue

        ref, err = _parse_ref_line(line)
        if err:
            return clauses, err
        if ref:
            current["refs"].append(ref)

    if current is not None:
        clauses.append(current)

    return clauses, None


def validate_evidence_clauses(clauses: list[dict]) -> str | None:
    if not clauses:
        return (
            "EVIDENCE block is empty — it must contain at least one "
            "`- claim:` clause with refs."
        )
    for i, c in enumerate(clauses, 1):
        label = c["claim"][:60] if c["claim"] else ""
        if not c["claim"]:
            return f"EVIDENCE clause {i} has empty claim text."
        if not c["refs"]:
            return (
                f"EVIDENCE clause {i} (\"{label}\") has no refs — "
                "every claim must cite at least one ref "
                "(src / url / quote / knowledge)."
            )
    return None


# ---------------------------------------------------------------------------
# CONJECTURE block parsing & validation
# ---------------------------------------------------------------------------

def parse_conjecture_clauses(block_text: str) -> tuple[list[dict], str | None]:
    """Parse CONJECTURE block body into a list of {claim, basis, likelihood}
    clauses. Returns (clauses, error)."""
    clauses: list[dict] = []
    current: dict | None = None

    for line in block_text.split("\n"):
        if not line.strip():
            continue

        claim_match = _CLAIM_RE.match(line)
        if claim_match:
            if current is not None:
                clauses.append(current)
            current = {
                "claim": claim_match.group(1).strip(),
                "basis": None,
                "likelihood": None,
            }
            continue

        if current is None:
            continue

        basis_match = _BASIS_RE.match(line)
        if basis_match:
            current["basis"] = basis_match.group(1).strip()
            continue

        lik_match = _LIKELIHOOD_RE.match(line)
        if lik_match:
            current["likelihood"] = lik_match.group(1).lower()
            continue

    if current is not None:
        clauses.append(current)

    return clauses, None


def validate_conjecture_clauses(clauses: list[dict]) -> str | None:
    if not clauses:
        return (
            "CONJECTURE block is empty — it must contain at least one "
            "`- claim:` clause with basis and likelihood."
        )
    for i, c in enumerate(clauses, 1):
        label = c["claim"][:60] if c["claim"] else ""
        if not c["claim"]:
            return f"CONJECTURE clause {i} has empty claim text."
        if not c["basis"]:
            return (
                f"CONJECTURE clause {i} (\"{label}\") missing `- basis:` "
                "line explaining what supports the conjecture."
            )
        if c["likelihood"] not in ("low", "medium", "high"):
            return (
                f"CONJECTURE clause {i} (\"{label}\") missing or invalid "
                "`- likelihood:` — must be one of low / medium / high."
            )
    return None


# ---------------------------------------------------------------------------
# Top-level evidence check
# ---------------------------------------------------------------------------

def check_evidence(message: str) -> str | None:
    """Return an error message if the evidence/conjecture requirement is
    violated, else None. Short messages (< 40 chars) are exempt."""
    if len(message) < MIN_LENGTH:
        return None

    evidence_block = extract_block(message, _EVIDENCE_HEADER_RE)
    conjecture_block = extract_block(message, _CONJECTURE_HEADER_RE)

    if evidence_block is None and conjecture_block is None:
        return (
            "Response missing **EVIDENCE:** or **CONJECTURE:** block. "
            "Every substantive response must cite supporting facts "
            "(structured EVIDENCE) or explicitly flag unsupported claims "
            "(structured CONJECTURE). See agents/thinking.md for the format."
        )

    if evidence_block is not None:
        clauses, err = parse_evidence_clauses(evidence_block)
        if err:
            return f"EVIDENCE block malformed: {err}"
        err = validate_evidence_clauses(clauses)
        if err:
            return err

    if conjecture_block is not None:
        clauses, err = parse_conjecture_clauses(conjecture_block)
        if err:
            return f"CONJECTURE block malformed: {err}"
        err = validate_conjecture_clauses(clauses)
        if err:
            return err

    return None


# ---------------------------------------------------------------------------
# Transcript handling
# ---------------------------------------------------------------------------

def get_current_turn_text(transcript_path: str) -> str:
    """Concatenate all assistant text blocks from the current turn, in
    chronological order. The current turn is everything after the most
    recent real user message (tool_result user entries are interleaved
    mid-turn and do not count)."""
    try:
        with open(transcript_path, "r") as f:
            lines = f.read().strip().split("\n")
    except (OSError, IOError):
        return ""

    assistant_texts_reversed: list[str] = []
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        entry_type = parsed.get("type", "")
        msg = parsed.get("message", {})
        content = msg.get("content", []) if isinstance(msg, dict) else []

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
                    assistant_texts_reversed.append(block["text"])

    return "\n".join(reversed(assistant_texts_reversed))


def check_transcript_for_pattern(
    transcript_path: str, pattern: re.Pattern | str
) -> bool:
    """Backward-compatible helper used by tests: search the current turn's
    text for a pattern (compiled regex or literal string)."""
    text = get_current_turn_text(transcript_path)
    if isinstance(pattern, re.Pattern):
        return pattern.search(text) is not None
    return pattern in text


def check_transcript_for_marker(transcript_path: str) -> bool:
    return check_transcript_for_pattern(transcript_path, MARKER)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _full_turn_text(transcript_path: str | None, message: str) -> str:
    """Return the full text of the current assistant turn, using the
    transcript if available, else the single last-message string."""
    if transcript_path:
        text = get_current_turn_text(transcript_path)
        if text:
            return text
    return message


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
    full_text = _full_turn_text(transcript_path, message)

    if MARKER not in full_text:
        print(
            "Response missing _I THOUGHT_ proof of checklist. "
            "Work through the 5 questions before responding.",
            file=sys.stderr,
        )
        sys.exit(2)

    err = check_evidence(full_text)
    if err:
        print(err, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)
