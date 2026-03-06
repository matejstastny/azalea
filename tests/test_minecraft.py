"""Unit tests for azalea.minecraft version utilities."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azalea.minecraft import mc_version_matches, resolve_target_mc


class TestMcVersionMatches(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(mc_version_matches("1.21", ["1.20", "1.21"]))

    def test_no_match(self):
        self.assertFalse(mc_version_matches("1.22", ["1.20", "1.21"]))

    def test_wildcard_in_supported(self):
        self.assertTrue(mc_version_matches("1.21.1", ["1.21.x"]))
        self.assertTrue(mc_version_matches("1.21", ["1.21.x"]))
        self.assertFalse(mc_version_matches("1.22.0", ["1.21.x"]))

    def test_wildcard_in_target(self):
        self.assertTrue(mc_version_matches("1.21.x", ["1.21.1"]))
        self.assertFalse(mc_version_matches("1.21.x", ["1.22.0"]))

    def test_empty_supported_list(self):
        self.assertFalse(mc_version_matches("1.21", []))


FAKE_VERSIONS = [
    {"version": "1.21.4", "version_type": "release", "date_published": "2024-12-03"},
    {"version": "1.21", "version_type": "release", "date_published": "2024-06-13"},
    {"version": "1.20.6", "version_type": "release", "date_published": "2024-04-29"},
    {"version": "1.21-pre1", "version_type": "alpha", "date_published": "2024-06-01"},
]


class TestResolveTargetMc(unittest.TestCase):
    @patch("azalea.minecraft.get_release_versions")
    def test_latest_resolves_newest(self, mock_versions):
        mock_versions.return_value = [v for v in FAKE_VERSIONS if v["version_type"] == "release"]
        result = resolve_target_mc("latest")
        self.assertEqual(result, "1.21.4")

    @patch("azalea.minecraft.get_release_versions")
    def test_valid_version_returns_as_is(self, mock_versions):
        mock_versions.return_value = [v for v in FAKE_VERSIONS if v["version_type"] == "release"]
        result = resolve_target_mc("1.21")
        self.assertEqual(result, "1.21")

    @patch("azalea.minecraft.get_release_versions")
    def test_invalid_version_exits(self, mock_versions):
        mock_versions.return_value = [v for v in FAKE_VERSIONS if v["version_type"] == "release"]
        with self.assertRaises(SystemExit):
            resolve_target_mc("9.99")

    @patch("azalea.minecraft.get_release_versions")
    def test_non_numeric_version_exits(self, mock_versions):
        mock_versions.return_value = [v for v in FAKE_VERSIONS if v["version_type"] == "release"]
        with self.assertRaises(SystemExit):
            resolve_target_mc("latest-snapshot")


if __name__ == "__main__":
    unittest.main()
