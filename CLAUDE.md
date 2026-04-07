# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin that enforces deliberate thinking and blocks sycophancy. Two components:

- **Agent** (`agents/thinking.md`) — System prompt with behavioral rules and a 5-question deliberation checklist. Always active when the plugin is enabled.
- **Hooks** (`hooks/`) — Python scripts that mechanically reject responses missing the `_I THOUGHT_` marker or containing sycophantic phrases.

## Commands

Run tests:
```bash
cd hooks && python3 -m unittest -v
```

There is no build step. Hooks are plain Python scripts.

## Architecture

### Hook Execution

Hooks are configured in `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}` to resolve paths.

- **SessionStart** — Checks that `python3` is installed; warns if missing.
- **Stop** (runs before every response completes):
  1. `check_sycophancy.py` — Rejects if any of 11 regex patterns match in the first 300 chars.
  2. `check_thinking.py` — Rejects if any of these fail (messages < 40 chars are exempt):
     - `_I THOUGHT_` marker absent.
     - No `**EVIDENCE:**` or `**CONJECTURE:**` block present.
     - Block present but malformed: empty, clauses missing required fields, invalid ref type, or a ref that fails structural validation (e.g. `src:` without `path:line`, `quote:` without `session:`/`ts:` metadata, `knowledge:` too short).

### Hook I/O Protocol

Input: JSON via stdin with `{ stop_hook_active, last_assistant_message, transcript_path }`.
Output: exit 0 to pass, exit 2 to reject (error message on stderr). If `stop_hook_active` is true, the hook exits 0 immediately (avoids infinite rejection loops).

### Transcript Parsing (`check_thinking.py`)

The thinking hook concatenates all assistant text blocks from the current turn (via `get_current_turn_text`) and runs the marker check and block parser against the joined text. This is needed because EVIDENCE/CONJECTURE blocks and the `_I THOUGHT_` marker may appear in an earlier text block of the same turn, before tool calls. Turn boundaries skip `tool_result` user entries (interleaved mid-turn between tool_use and response) and only break on real user messages.
