#!/usr/bin/env python3
import json
import os
import shutil
import tempfile
import unittest

from check_thinking import check_thinking, check_evidence, check_transcript_for_marker, check_transcript_for_pattern, _EVIDENCE_RE, _CONJECTURE_RE

# Markdown-formatted tags used in test strings
E_TAG = "**EVIDENCE:**"
C_TAG = "**CONJECTURE:**"


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


class TestCheckEvidence(unittest.TestCase):
    def test_returns_none_for_short_messages(self):
        self.assertIsNone(check_evidence("Done."))

    def test_returns_none_when_evidence_present(self):
        msg = f"_I THOUGHT_\n\nThe fix works.\n\n{E_TAG}\nTest output: all 5 tests pass."
        self.assertIsNone(check_evidence(msg))

    def test_returns_none_when_conjecture_present(self):
        msg = f"_I THOUGHT_\n\n{C_TAG} This is likely caused by a race condition.\n\nHere is a possible fix."
        self.assertIsNone(check_evidence(msg))

    def test_returns_error_when_neither_present(self):
        msg = "_I THOUGHT_\n\nHere is a detailed response with no evidence or conjecture tags at all."
        result = check_evidence(msg)
        self.assertIn("EVIDENCE", result)

    def test_is_case_insensitive(self):
        msg = "_I THOUGHT_\n\nThe fix works.\n\n**evidence:**\nTest output: pass."
        self.assertIsNone(check_evidence(msg))

    def test_conjecture_case_insensitive(self):
        msg = "_I THOUGHT_\n\n**Conjecture:** Might be a timeout issue.\n\nHere is a possible fix that is long enough."
        self.assertIsNone(check_evidence(msg))


class TestCheckTranscriptForEvidence(unittest.TestCase):
    def _write_fake_transcript(self, lines):
        tmp_dir = tempfile.mkdtemp(prefix="hook-test-")
        file_path = os.path.join(tmp_dir, "transcript.jsonl")
        with open(file_path, "w") as f:
            f.write("\n".join(json.dumps(line) for line in lines))
        return file_path

    def _cleanup(self, file_path):
        shutil.rmtree(os.path.dirname(file_path))

    def test_finds_evidence_in_earlier_text_block(self):
        p = self._write_fake_transcript([
            {"type": "user", "message": {"content": [{"type": "text", "text": "fix the bug"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": f"_I THOUGHT_\n\nPlan.\n\n{E_TAG}\nError at line 5."}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Edit"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Fixed."}]}},
        ])
        self.assertTrue(check_transcript_for_pattern(p, _EVIDENCE_RE))
        self._cleanup(p)

    def test_finds_conjecture_in_transcript(self):
        p = self._write_fake_transcript([
            {"type": "user", "message": {"content": [{"type": "text", "text": "why is this slow?"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": f"_I THOUGHT_\n\n{C_TAG} Likely a N+1 query."}]}},
        ])
        self.assertTrue(check_transcript_for_pattern(p, _CONJECTURE_RE))
        self._cleanup(p)

    def test_does_not_find_evidence_from_previous_turn(self):
        p = self._write_fake_transcript([
            {"type": "assistant", "message": {"content": [{"type": "text", "text": f"{E_TAG}\nOld evidence."}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "new question"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "No evidence in new turn."}]}},
        ])
        self.assertFalse(check_transcript_for_pattern(p, _EVIDENCE_RE))
        self._cleanup(p)


if __name__ == "__main__":
    unittest.main()
