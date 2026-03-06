"""Unit tests for the interactive azalea init command."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azalea.commands import _pick_loader, _pick_mc_version, _prompt, init

FAKE_RELEASES = [
    {"version": "1.21.4", "version_type": "release", "date_published": "2024-12-03"},
    {"version": "1.21.1", "version_type": "release", "date_published": "2024-08-08"},
    {"version": "1.21", "version_type": "release", "date_published": "2024-06-13"},
    {"version": "1.20.6", "version_type": "release", "date_published": "2024-04-29"},
]


class TestPrompt(unittest.TestCase):
    def test_returns_user_input(self):
        with patch("builtins.input", return_value="Cool Pack"):
            self.assertEqual(_prompt("Name", "My Pack"), "Cool Pack")

    def test_returns_default_on_empty(self):
        with patch("builtins.input", return_value=""):
            self.assertEqual(_prompt("Name", "My Pack"), "My Pack")

    def test_returns_default_on_eof(self):
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(_prompt("Name", "fallback"), "fallback")


class TestPickMcVersion(unittest.TestCase):
    def test_select_by_number(self):
        with patch("builtins.input", return_value="2"):
            result = _pick_mc_version(FAKE_RELEASES)
        self.assertEqual(result, "1.21.1")

    def test_select_by_version_string(self):
        with patch("builtins.input", return_value="1.20.6"):
            result = _pick_mc_version(FAKE_RELEASES)
        self.assertEqual(result, "1.20.6")

    def test_empty_input_picks_latest(self):
        with patch("builtins.input", return_value=""):
            result = _pick_mc_version(FAKE_RELEASES)
        self.assertEqual(result, "1.21.4")  # most recent

    def test_retries_on_invalid(self):
        with patch("builtins.input", side_effect=["bad", "1"]):
            result = _pick_mc_version(FAKE_RELEASES)
        self.assertEqual(result, "1.21.4")

    def test_eof_returns_latest(self):
        with patch("builtins.input", side_effect=EOFError):
            result = _pick_mc_version(FAKE_RELEASES)
        self.assertEqual(result, "1.21.4")


class TestPickLoader(unittest.TestCase):
    def test_select_fabric_by_number(self):
        with patch("builtins.input", return_value="1"):
            self.assertEqual(_pick_loader(), "fabric")

    def test_select_quilt_by_number(self):
        with patch("builtins.input", return_value="2"):
            self.assertEqual(_pick_loader(), "quilt")

    def test_select_by_name(self):
        with patch("builtins.input", return_value="neoforge"):
            self.assertEqual(_pick_loader(), "neoforge")

    def test_default_is_fabric(self):
        with patch("builtins.input", return_value=""):
            self.assertEqual(_pick_loader(), "fabric")

    def test_eof_returns_fabric(self):
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(_pick_loader(), "fabric")


class TestInit(unittest.TestCase):
    @patch("azalea.commands.get_latest_loader_version", return_value="0.16.0")
    @patch("azalea.commands.get_release_versions", return_value=FAKE_RELEASES)
    def test_init_writes_config(self, _releases, _loader_ver):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg_path = td / "azalea.json"

            inputs = iter(
                [
                    "Test Pack",  # name
                    "Alice",  # author
                    "0.2.0",  # version
                    "MIT",  # license
                    "1",  # MC version: pick first (1.21.4)
                    "1",  # loader: fabric
                ]
            )

            with (
                patch("azalea.commands.CONFIG", cfg_path),
                patch("azalea.commands.ensure_overrides_dir"),
                patch("builtins.input", side_effect=inputs),
            ):
                init()

            self.assertTrue(cfg_path.exists())
            data = json.loads(cfg_path.read_text())
            self.assertEqual(data["name"], "Test Pack")
            self.assertEqual(data["author"], "Alice")
            self.assertEqual(data["version"], "0.2.0")
            self.assertEqual(data["license"], "MIT")
            self.assertEqual(data["minecraft_version"], "1.21.4")
            self.assertEqual(data["loader"], "fabric")
            self.assertEqual(data["loader_version"], "0.16.0")

    @patch("azalea.commands.get_release_versions", return_value=FAKE_RELEASES)
    def test_init_warns_if_already_initialized(self, _):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg_path = td / "azalea.json"
            cfg_path.write_text("{}")

            with (
                patch("azalea.commands.CONFIG", cfg_path),
                patch("azalea.commands.log_warn") as mock_warn,
            ):
                init()
                mock_warn.assert_called_once()

    @patch("azalea.commands.get_latest_loader_version", return_value=None)
    @patch("azalea.commands.get_release_versions", return_value=FAKE_RELEASES)
    def test_init_handles_missing_loader_version(self, _releases, _loader_ver):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg_path = td / "azalea.json"

            inputs = iter(["", "", "", "", "", ""])  # all defaults
            with (
                patch("azalea.commands.CONFIG", cfg_path),
                patch("azalea.commands.ensure_overrides_dir"),
                patch("builtins.input", side_effect=inputs),
            ):
                init()

            data = json.loads(cfg_path.read_text())
            self.assertEqual(data["loader_version"], "")


if __name__ == "__main__":
    unittest.main()
