"""Unit tests for azalea.util helpers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azalea.util import safe_name


class TestSafeName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(safe_name("My Pack"), "My-Pack")

    def test_special_chars(self):
        self.assertEqual(safe_name("pack: v1.0!"), "pack--v1.0-")

    def test_strips_leading_trailing(self):
        self.assertEqual(safe_name("  hello world  "), "hello-world")

    def test_dots_and_dashes_preserved(self):
        self.assertEqual(safe_name("1.21.4-mc"), "1.21.4-mc")

    def test_empty(self):
        self.assertEqual(safe_name(""), "")


if __name__ == "__main__":
    unittest.main()
