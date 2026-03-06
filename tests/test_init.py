"""Unit tests for the interactive azalea init command."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azalea.commands import _connector, _field, _pick_loader, _pick_mc_version, init

FAKE_RELEASES = [
    {"version": "1.21.4", "version_type": "release", "date_published": "2024-12-03"},
    {"version": "1.21.1", "version_type": "release", "date_published": "2024-08-08"},
    {"version": "1.21", "version_type": "release", "date_published": "2024-06-13"},
    {"version": "1.20.6", "version_type": "release", "date_published": "2024-04-29"},
]


# ---------------------------------------------------------------------------
# Tests: _connector
# ---------------------------------------------------------------------------


class TestConnector(unittest.TestCase):
    def test_last_item_gets_end_connector(self):
        self.assertEqual(_connector(4, 5), "└─")

    def test_non_last_item_gets_branch_connector(self):
        self.assertEqual(_connector(0, 5), "├─")
        self.assertEqual(_connector(3, 5), "├─")

    def test_single_item_is_end_connector(self):
        self.assertEqual(_connector(0, 1), "└─")


# ---------------------------------------------------------------------------
# Tests: _field
# ---------------------------------------------------------------------------


class TestField(unittest.TestCase):
    def test_returns_user_input(self):
        with patch("builtins.input", return_value="Cool Pack"):
            self.assertEqual(_field("├─", "Name", "My Pack"), "Cool Pack")

    def test_returns_default_on_empty(self):
        with patch("builtins.input", return_value=""):
            self.assertEqual(_field("├─", "Name", "My Pack"), "My Pack")

    def test_returns_empty_string_when_no_default(self):
        with patch("builtins.input", return_value=""):
            self.assertEqual(_field("├─", "Author"), "")

    def test_returns_default_on_eof(self):
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(_field("└─", "License", ""), "")

    def test_end_connector_accepted(self):
        with patch("builtins.input", return_value="MIT"):
            self.assertEqual(_field("└─", "License"), "MIT")


# ---------------------------------------------------------------------------
# Tests: _pick_mc_version
# ---------------------------------------------------------------------------


class TestPickMcVersion(unittest.TestCase):
    def _run(self, inputs):
        side_effects = iter(inputs)
        with (
            patch("builtins.input", side_effect=side_effects),
            patch("azalea.commands.save_cursor"),
            patch("azalea.commands.restore_cursor_clear"),
        ):
            return _pick_mc_version(FAKE_RELEASES)

    def test_select_by_letter_a(self):
        # "a" = first item = most recent
        self.assertEqual(self._run(["a"]), "1.21.4")

    def test_select_by_letter_b(self):
        self.assertEqual(self._run(["b"]), "1.21.1")

    def test_select_by_version_string(self):
        self.assertEqual(self._run(["1.20.6"]), "1.20.6")

    def test_empty_input_picks_latest(self):
        self.assertEqual(self._run([""]), "1.21.4")

    def test_invalid_then_valid(self):
        # invalid input → warning + retry; second attempt is "c"
        self.assertEqual(self._run(["z", "c"]), "1.21")

    def test_eof_returns_latest(self):
        with (
            patch("builtins.input", side_effect=EOFError),
            patch("azalea.commands.save_cursor"),
            patch("azalea.commands.restore_cursor_clear"),
        ):
            self.assertEqual(_pick_mc_version(FAKE_RELEASES), "1.21.4")


# ---------------------------------------------------------------------------
# Tests: _pick_loader
# ---------------------------------------------------------------------------


class TestPickLoader(unittest.TestCase):
    def _run(self, inputs):
        side_effects = iter(inputs)
        with (
            patch("builtins.input", side_effect=side_effects),
            patch("azalea.commands.save_cursor"),
            patch("azalea.commands.restore_cursor_clear"),
        ):
            return _pick_loader()

    def test_default_is_fabric(self):
        self.assertEqual(self._run([""]), "fabric")

    def test_select_by_name(self):
        self.assertEqual(self._run(["quilt"]), "quilt")
        self.assertEqual(self._run(["neoforge"]), "neoforge")
        self.assertEqual(self._run(["forge"]), "forge")

    def test_invalid_then_valid(self):
        self.assertEqual(self._run(["badloader", "fabric"]), "fabric")

    def test_eof_returns_fabric(self):
        with (
            patch("builtins.input", side_effect=EOFError),
            patch("azalea.commands.save_cursor"),
            patch("azalea.commands.restore_cursor_clear"),
        ):
            self.assertEqual(_pick_loader(), "fabric")


# ---------------------------------------------------------------------------
# Tests: init
# ---------------------------------------------------------------------------


class TestInit(unittest.TestCase):
    @patch("azalea.commands.get_latest_loader_version", return_value="0.16.0")
    @patch("azalea.commands.get_release_versions", return_value=FAKE_RELEASES)
    def test_init_writes_config(self, _releases, _loader_ver):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg_path = td / "azalea.json"

            # 4 field inputs + MC letter + loader name
            inputs = iter(["Test Pack", "Alice", "0.2.0", "MIT", "a", "fabric"])

            with (
                patch("azalea.commands.CONFIG", cfg_path),
                patch("azalea.commands.ensure_overrides_dir"),
                patch("azalea.commands.save_cursor"),
                patch("azalea.commands.restore_cursor_clear"),
                patch("builtins.input", side_effect=inputs),
            ):
                init()

            self.assertTrue(cfg_path.exists())
            data = json.loads(cfg_path.read_text())
            self.assertEqual(data["name"], "Test Pack")
            self.assertEqual(data["author"], "Alice")
            self.assertEqual(data["version"], "0.2.0")
            self.assertEqual(data["license"], "MIT")
            self.assertEqual(data["minecraft_version"], "1.21.4")  # "a" = first
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
                patch("azalea.commands.save_cursor"),
                patch("azalea.commands.restore_cursor_clear"),
                patch("builtins.input", side_effect=inputs),
            ):
                init()

            data = json.loads(cfg_path.read_text())
            self.assertEqual(data["loader_version"], "")
            self.assertEqual(data["loader"], "fabric")
            self.assertEqual(data["minecraft_version"], "1.21.4")  # default = "a" = first


if __name__ == "__main__":
    unittest.main()
