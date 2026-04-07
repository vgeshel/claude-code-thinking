#!/usr/bin/env python3
import json
import os
import shutil
import tempfile
import unittest

from check_thinking import (
    check_thinking,
    check_evidence,
    check_transcript_for_marker,
    check_transcript_for_pattern,
    extract_block,
    parse_evidence_clauses,
    parse_conjecture_clauses,
    validate_evidence_clauses,
    validate_conjecture_clauses,
    get_current_turn_text,
    _EVIDENCE_HEADER_RE,
    _CONJECTURE_HEADER_RE,
)


# ---------------------------------------------------------------------------
# Fixture helpers for well-formed blocks
# ---------------------------------------------------------------------------

VALID_EVIDENCE = """**EVIDENCE:**
- claim: The sycophancy hook rejects responses containing agreement phrases.
  - src: hooks/check_sycophancy.py:14-26
  - src: hooks/check_sycophancy.py:53
"""

VALID_CONJECTURE = """**CONJECTURE:**
- claim: The failing test is likely caused by a race condition.
  - basis: Only fails intermittently (3/10 runs), isolated test passes reliably.
  - likelihood: medium — consistent with race behavior but could also be environmental.
"""

THOUGHT = "_I THOUGHT_"


def _wrap(body: str) -> str:
    """Wrap a body in the thinking marker so it passes check_thinking."""
    return f"{THOUGHT}\n\nHere is a detailed response that is long enough to be checked.\n\n{body}"


# ---------------------------------------------------------------------------
# check_thinking (marker check)
# ---------------------------------------------------------------------------

class TestCheckThinking(unittest.TestCase):
    def test_returns_none_for_short_messages(self):
        self.assertIsNone(check_thinking("Done."))

    def test_returns_none_when_marker_is_present(self):
        msg = "_I THOUGHT_\n\nHere is a detailed response that is long enough to be checked by the hook."
        self.assertIsNone(check_thinking(msg))

    def test_returns_error_when_marker_is_absent_from_long_message(self):
        msg = "Here is a detailed response that is long enough to be checked by the hook but has no marker."
        result = check_thinking(msg)
        self.assertIn("_I THOUGHT_", result)

    def test_returns_none_for_exactly_39_chars(self):
        self.assertIsNone(check_thinking("a" * 39))

    def test_returns_error_for_40_plus_chars_without_marker(self):
        self.assertIsNotNone(check_thinking("a" * 40))


# ---------------------------------------------------------------------------
# check_evidence — happy paths
# ---------------------------------------------------------------------------

class TestCheckEvidenceHappyPaths(unittest.TestCase):
    def test_short_messages_are_exempt(self):
        self.assertIsNone(check_evidence("Done."))

    def test_valid_evidence_block_passes(self):
        self.assertIsNone(check_evidence(_wrap(VALID_EVIDENCE)))

    def test_valid_conjecture_block_passes(self):
        self.assertIsNone(check_evidence(_wrap(VALID_CONJECTURE)))

    def test_both_blocks_together_pass(self):
        body = VALID_EVIDENCE + "\n" + VALID_CONJECTURE
        self.assertIsNone(check_evidence(_wrap(body)))

    def test_header_is_case_insensitive(self):
        body = "**evidence:**\n- claim: X\n  - src: foo/bar.py:1\n"
        self.assertIsNone(check_evidence(_wrap(body)))

    def test_all_four_ref_types_accepted(self):
        body = """**EVIDENCE:**
- claim: Multiple ref types work together.
  - src: hooks/check_thinking.py:42
  - url: https://example.com/docs
  - quote: "verbatim text" [session: abc-123, ts: 2026-04-07T14:32:10Z]
  - knowledge: Python stdlib `re` module documentation
"""
        self.assertIsNone(check_evidence(_wrap(body)))

    def test_src_with_line_range_accepted(self):
        body = "**EVIDENCE:**\n- claim: range works\n  - src: hooks/check_thinking.py:10-50\n"
        self.assertIsNone(check_evidence(_wrap(body)))

    def test_multiple_clauses_each_with_refs(self):
        body = """**EVIDENCE:**
- claim: First interpretation.
  - src: a/b.py:1
- claim: Second interpretation.
  - url: https://example.com/
"""
        self.assertIsNone(check_evidence(_wrap(body)))


# ---------------------------------------------------------------------------
# check_evidence — rejection: missing blocks
# ---------------------------------------------------------------------------

class TestCheckEvidenceMissingBlocks(unittest.TestCase):
    def test_rejects_when_no_block_at_all(self):
        msg = _wrap("Here is a detailed response with no evidence or conjecture tags at all.")
        result = check_evidence(msg)
        self.assertIsNotNone(result)
        self.assertIn("EVIDENCE", result)
        self.assertIn("CONJECTURE", result)


# ---------------------------------------------------------------------------
# check_evidence — rejection: malformed EVIDENCE
# ---------------------------------------------------------------------------

class TestCheckEvidenceMalformedEvidence(unittest.TestCase):
    def test_rejects_empty_evidence_block(self):
        body = "**EVIDENCE:**\n\n(nothing here)\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("empty", result.lower())

    def test_rejects_claim_without_any_refs(self):
        body = "**EVIDENCE:**\n- claim: An assertion with no backing refs.\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("no refs", result)

    def test_rejects_src_ref_without_line_number(self):
        body = "**EVIDENCE:**\n- claim: bad src\n  - src: hooks/check_thinking.py\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("src", result.lower())

    def test_rejects_src_ref_with_non_path_identifier(self):
        body = "**EVIDENCE:**\n- claim: bad src\n  - src: notapath:42\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("src", result.lower())

    def test_rejects_url_ref_without_scheme(self):
        body = "**EVIDENCE:**\n- claim: bad url\n  - url: example.com/docs\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("url", result.lower())

    def test_rejects_quote_without_verbatim_string(self):
        body = "**EVIDENCE:**\n- claim: bad quote\n  - quote: no quoted text here [session: x, ts: 2026-04-07T00:00:00Z]\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("quote", result.lower())
        self.assertIn("verbatim", result.lower())

    def test_rejects_quote_without_session_metadata(self):
        body = '**EVIDENCE:**\n- claim: bad quote\n  - quote: "something said" [ts: 2026-04-07T00:00:00Z]\n'
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("session", result.lower())

    def test_rejects_quote_without_timestamp_metadata(self):
        body = '**EVIDENCE:**\n- claim: bad quote\n  - quote: "something said" [session: abc]\n'
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("ts", result.lower())

    def test_rejects_trivial_knowledge_ref(self):
        body = "**EVIDENCE:**\n- claim: foo\n  - knowledge: short\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("knowledge", result.lower())

    def test_rejects_unknown_ref_type(self):
        body = "**EVIDENCE:**\n- claim: foo\n  - gut_feeling: my training data says so\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("unknown", result.lower())


# ---------------------------------------------------------------------------
# check_evidence — rejection: malformed CONJECTURE
# ---------------------------------------------------------------------------

class TestCheckEvidenceMalformedConjecture(unittest.TestCase):
    def test_rejects_empty_conjecture_block(self):
        body = "**CONJECTURE:**\n"
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("empty", result.lower())

    def test_rejects_conjecture_without_basis(self):
        body = """**CONJECTURE:**
- claim: The bug is caused by a timing issue.
  - likelihood: medium — consistent with intermittent failures.
"""
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("basis", result.lower())

    def test_rejects_conjecture_without_likelihood(self):
        body = """**CONJECTURE:**
- claim: The bug is caused by a timing issue.
  - basis: Fails intermittently, no reproduction steps.
"""
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("likelihood", result.lower())

    def test_rejects_invalid_likelihood_value(self):
        body = """**CONJECTURE:**
- claim: X
  - basis: intermittent failures
  - likelihood: probably — sort of maybe
"""
        result = check_evidence(_wrap(body))
        self.assertIsNotNone(result)
        self.assertIn("likelihood", result.lower())

    def test_accepts_all_three_likelihood_values(self):
        for lik in ("low", "medium", "high"):
            body = f"""**CONJECTURE:**
- claim: X
  - basis: some reasoning here
  - likelihood: {lik} — rationale
"""
            self.assertIsNone(check_evidence(_wrap(body)), f"failed for {lik}")


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------

class TestExtractBlock(unittest.TestCase):
    def test_returns_none_when_header_missing(self):
        self.assertIsNone(extract_block("no header here", _EVIDENCE_HEADER_RE))

    def test_extracts_body_until_next_header(self):
        text = "**EVIDENCE:**\n- claim: X\n  - src: a/b.py:1\n\n**CONJECTURE:**\n- claim: Y\n"
        body = extract_block(text, _EVIDENCE_HEADER_RE)
        self.assertIsNotNone(body)
        self.assertIn("claim: X", body)
        self.assertNotIn("claim: Y", body)

    def test_extracts_until_end_when_no_next_header(self):
        text = "**EVIDENCE:**\n- claim: X\n  - src: a/b.py:1\n"
        body = extract_block(text, _EVIDENCE_HEADER_RE)
        self.assertIn("claim: X", body)


class TestParseEvidenceClauses(unittest.TestCase):
    def test_parses_single_clause(self):
        block = "\n- claim: foo\n  - src: a/b.py:1\n"
        clauses, err = parse_evidence_clauses(block)
        self.assertIsNone(err)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]["claim"], "foo")
        self.assertEqual(len(clauses[0]["refs"]), 1)
        self.assertEqual(clauses[0]["refs"][0]["type"], "src")

    def test_parses_multiple_clauses(self):
        block = "\n- claim: A\n  - src: a/b.py:1\n- claim: B\n  - url: https://example.com\n"
        clauses, err = parse_evidence_clauses(block)
        self.assertIsNone(err)
        self.assertEqual(len(clauses), 2)


class TestValidateEvidenceClauses(unittest.TestCase):
    def test_rejects_empty_list(self):
        self.assertIsNotNone(validate_evidence_clauses([]))

    def test_rejects_clause_with_no_refs(self):
        result = validate_evidence_clauses([{"claim": "X", "refs": []}])
        self.assertIsNotNone(result)
        self.assertIn("no refs", result)

    def test_accepts_valid_clause(self):
        clauses = [{"claim": "X", "refs": [{"type": "src", "path": "a/b.py", "start": 1, "end": 1}]}]
        self.assertIsNone(validate_evidence_clauses(clauses))


class TestParseConjectureClauses(unittest.TestCase):
    def test_parses_full_clause(self):
        block = "\n- claim: X\n  - basis: reason\n  - likelihood: high — because\n"
        clauses, err = parse_conjecture_clauses(block)
        self.assertIsNone(err)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]["claim"], "X")
        self.assertEqual(clauses[0]["basis"], "reason")
        self.assertEqual(clauses[0]["likelihood"], "high")


class TestValidateConjectureClauses(unittest.TestCase):
    def test_rejects_empty_list(self):
        self.assertIsNotNone(validate_conjecture_clauses([]))

    def test_rejects_missing_basis(self):
        clauses = [{"claim": "X", "basis": None, "likelihood": "high"}]
        result = validate_conjecture_clauses(clauses)
        self.assertIn("basis", result.lower())

    def test_rejects_missing_likelihood(self):
        clauses = [{"claim": "X", "basis": "r", "likelihood": None}]
        result = validate_conjecture_clauses(clauses)
        self.assertIn("likelihood", result.lower())

    def test_accepts_valid_clause(self):
        clauses = [{"claim": "X", "basis": "r", "likelihood": "medium"}]
        self.assertIsNone(validate_conjecture_clauses(clauses))


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

class TestCheckTranscriptForMarker(unittest.TestCase):
    def _write_fake_transcript(self, lines):
        tmp_dir = tempfile.mkdtemp(prefix="hook-test-")
        file_path = os.path.join(tmp_dir, "transcript.jsonl")
        with open(file_path, "w") as f:
            f.write("\n".join(json.dumps(line) for line in lines))
        return file_path

    def _cleanup(self, file_path):
        shutil.rmtree(os.path.dirname(file_path))

    def test_returns_true_when_marker_in_current_assistant_turn(self):
        p = self._write_fake_transcript([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "_I THOUGHT_\n\nResponse."}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "Read"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Final text without marker."}]}},
        ])
        self.assertTrue(check_transcript_for_marker(p))
        self._cleanup(p)

    def test_returns_false_when_no_marker_in_current_turn(self):
        p = self._write_fake_transcript([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "No marker here."}]}},
        ])
        self.assertFalse(check_transcript_for_marker(p))
        self._cleanup(p)

    def test_ignores_marker_from_previous_turn(self):
        p = self._write_fake_transcript([
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "_I THOUGHT_\n\nOld."}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "new question"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "No marker in new turn."}]}},
        ])
        self.assertFalse(check_transcript_for_marker(p))
        self._cleanup(p)

    def test_skips_tool_result_user_entries_within_same_turn(self):
        p = self._write_fake_transcript([
            {"type": "user", "message": {"content": [{"type": "text", "text": "do something"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "_I THOUGHT_\n\nPlan."}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Bash"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Results without marker."}]}},
        ])
        self.assertTrue(check_transcript_for_marker(p))
        self._cleanup(p)

    def test_returns_false_for_nonexistent_file(self):
        self.assertFalse(check_transcript_for_marker("/tmp/nonexistent-transcript.jsonl"))


class TestGetCurrentTurnText(unittest.TestCase):
    def _write_fake_transcript(self, lines):
        tmp_dir = tempfile.mkdtemp(prefix="hook-test-")
        file_path = os.path.join(tmp_dir, "transcript.jsonl")
        with open(file_path, "w") as f:
            f.write("\n".join(json.dumps(line) for line in lines))
        return file_path

    def _cleanup(self, file_path):
        shutil.rmtree(os.path.dirname(file_path))

    def test_returns_text_in_chronological_order(self):
        p = self._write_fake_transcript([
            {"type": "user", "message": {"content": [{"type": "text", "text": "q"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Read"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "second"}]}},
        ])
        text = get_current_turn_text(p)
        self.assertLess(text.index("first"), text.index("second"))
        self._cleanup(p)

    def test_finds_structured_evidence_across_text_blocks(self):
        # Evidence in an earlier text block should be parseable even if
        # the final text block has no evidence.
        early = f"{THOUGHT}\n\n{VALID_EVIDENCE}"
        p = self._write_fake_transcript([
            {"type": "user", "message": {"content": [{"type": "text", "text": "fix it"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": early}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Edit"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Done."}]}},
        ])
        text = get_current_turn_text(p)
        self.assertIsNone(check_evidence(text))
        self._cleanup(p)


if __name__ == "__main__":
    unittest.main()
