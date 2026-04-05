#!/usr/bin/env python3
import json
import os
import shutil
import tempfile
import unittest

from check_thinking import check_thinking, check_transcript_for_marker


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


if __name__ == "__main__":
    unittest.main()
