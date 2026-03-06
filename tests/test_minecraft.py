"""Unit tests for azalea.minecraft version utilities."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azalea.minecraft import (
    SUPPORTED_LOADERS,
    get_latest_loader_version,
    mc_version_matches,
    resolve_target_mc,
)


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


class TestSupportedLoaders(unittest.TestCase):
    def test_all_expected_loaders_present(self):
        for loader in ("fabric", "quilt", "neoforge", "forge"):
            self.assertIn(loader, SUPPORTED_LOADERS)


class TestGetLatestLoaderVersion(unittest.TestCase):
    @patch("azalea.minecraft.get_latest_fabric_loader", return_value="0.16.0")
    def test_dispatches_fabric(self, mock_fn):
        result = get_latest_loader_version("fabric", "1.21")
        mock_fn.assert_called_once_with("1.21")
        self.assertEqual(result, "0.16.0")

    @patch("azalea.minecraft.get_latest_quilt_loader", return_value="0.27.0")
    def test_dispatches_quilt(self, mock_fn):
        result = get_latest_loader_version("quilt", "1.21")
        mock_fn.assert_called_once_with("1.21")
        self.assertEqual(result, "0.27.0")

    @patch("azalea.minecraft.get_latest_neoforge_loader", return_value="21.1.175")
    def test_dispatches_neoforge(self, mock_fn):
        result = get_latest_loader_version("neoforge", "1.21.1")
        mock_fn.assert_called_once_with("1.21.1")
        self.assertEqual(result, "21.1.175")

    @patch("azalea.minecraft.get_latest_forge_loader", return_value="51.0.33")
    def test_dispatches_forge(self, mock_fn):
        result = get_latest_loader_version("forge", "1.21")
        mock_fn.assert_called_once_with("1.21")
        self.assertEqual(result, "51.0.33")

    def test_unknown_loader_returns_none(self):
        result = get_latest_loader_version("unknown-loader", "1.21")
        self.assertIsNone(result)

    @patch("azalea.minecraft.get_latest_quilt_loader", return_value=None)
    def test_returns_none_on_api_failure(self, _):
        result = get_latest_loader_version("quilt", "1.21")
        self.assertIsNone(result)

    @patch(
        "azalea.minecraft.get_latest_neoforge_loader",
        return_value="21.4.93-beta",
    )
    def test_neoforge_prefix_1_21_4(self, mock_fn):
        """NeoForge for MC 1.21.4 should resolve versions starting with 21.4."""
        get_latest_loader_version("neoforge", "1.21.4")
        mock_fn.assert_called_once_with("1.21.4")


class TestGetLatestForgeLoader(unittest.TestCase):
    @patch(
        "azalea.minecraft.http_json",
        return_value={
            "promos": {
                "1.21-recommended": "51.0.33",
                "1.21-latest": "51.0.35",
                "1.20.6-recommended": "50.1.0",
            }
        },
    )
    def test_prefers_recommended(self, _):
        from azalea.minecraft import get_latest_forge_loader

        self.assertEqual(get_latest_forge_loader("1.21"), "51.0.33")

    @patch(
        "azalea.minecraft.http_json",
        return_value={
            "promos": {
                "1.21-latest": "51.0.35",
            }
        },
    )
    def test_falls_back_to_latest(self, _):
        from azalea.minecraft import get_latest_forge_loader

        self.assertEqual(get_latest_forge_loader("1.21"), "51.0.35")

    @patch("azalea.minecraft.http_json", return_value={"promos": {}})
    def test_returns_none_when_missing(self, _):
        from azalea.minecraft import get_latest_forge_loader

        self.assertIsNone(get_latest_forge_loader("9.99"))


if __name__ == "__main__":
    unittest.main()
