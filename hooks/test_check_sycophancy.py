#!/usr/bin/env python3
import unittest

from check_sycophancy import check_sycophancy


class TestCheckSycophancy(unittest.TestCase):
    def test_returns_none_for_normal_messages(self):
        self.assertIsNone(check_sycophancy("Here is the implementation."))

    def test_detects_you_are_right(self):
        self.assertIsNotNone(check_sycophancy("You are right, let me fix that."))

    def test_detects_good_point(self):
        self.assertIsNotNone(check_sycophancy("Good point. I will update the code."))

    def test_detects_that_makes_sense(self):
        self.assertIsNotNone(check_sycophancy("That makes sense. Updating now."))

    def test_detects_great_idea(self):
        self.assertIsNotNone(check_sycophancy("Great idea! Let me implement that."))

    def test_detects_great_question(self):
        self.assertIsNotNone(check_sycophancy("Great question! The answer is..."))

    def test_is_case_insensitive(self):
        self.assertIsNotNone(check_sycophancy("YOU ARE RIGHT about this."))

    def test_only_checks_first_300_chars(self):
        long = "x" * 301 + "you are right"
        self.assertIsNone(check_sycophancy(long))


if __name__ == "__main__":
    unittest.main()
