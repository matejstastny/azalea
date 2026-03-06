"""Unit tests for azalea.commands — Modrinth API calls are mocked."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azalea.commands import (
    check,
    info,
    install_mod,
    pin_mod,
    prune_unused_deps,
    remove_mod,
    search,
    unpin_mod,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FAKE_PROJECT = {
    "id": "proj-001",
    "slug": "sodium",
    "project_type": "mod",
    "client_side": "required",
    "server_side": "optional",
}

FAKE_VERSION = {
    "id": "ver-001",
    "version_number": "0.5.0",
    "game_versions": ["1.21"],
    "loaders": ["fabric"],
    "dependencies": [],
    "files": [
        {
            "url": "https://cdn.modrinth.com/sodium-0.5.0.jar",
            "filename": "sodium-0.5.0.jar",
            "size": 1234567,
            "hashes": {
                "sha512": "abc" * 28,
                "sha1": "deadbeef",
            },
        }
    ],
}


def _mod_data(slug="sodium", explicit=True, pinned=False, deps=None):
    d = {
        "project_id": f"proj-{slug}",
        "slug": slug,
        "version_id": "ver-001",
        "version_number": "0.5.0",
        "side": "client",
        "explicit": explicit,
        "dependencies": deps or [],
        "file": {
            "url": "https://cdn.modrinth.com/sodium.jar",
            "filename": "sodium.jar",
            "sha512": "abc" * 28,
            "sha1": "deadbeef",
            "size": 1000,
        },
    }
    if pinned:
        d["pinned"] = True
    return d


def _write_json(path: Path, data: dict):
    path.write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# Tests: install_mod
# ---------------------------------------------------------------------------


class TestInstallMod(unittest.TestCase):
    @patch("azalea.commands.find_best_version", return_value=FAKE_VERSION)
    @patch("azalea.commands.resolve_project", return_value=FAKE_PROJECT)
    @patch(
        "azalea.commands.load_config",
        return_value={"minecraft_version": "1.21", "loader": "fabric"},
    )
    def test_install_creates_json(self, _cfg, _resolve, _find):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            with (
                patch("azalea.commands.MODS", td),
                patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "mod")]),
            ):
                install_mod("sodium")

            out = td / "sodium.json"
            self.assertTrue(out.exists())
            data = json.loads(out.read_text())
            self.assertEqual(data["slug"], "sodium")
            self.assertEqual(data["version_number"], "0.5.0")
            self.assertEqual(data["file"]["size"], 1234567)
            self.assertEqual(data["side"], "both")  # required + optional → both

    @patch("azalea.commands.http_json", return_value=[FAKE_VERSION])
    @patch("azalea.commands.find_best_version", return_value=None)
    @patch(
        "azalea.commands.resolve_project",
        return_value={**FAKE_PROJECT, "project_type": "resourcepack", "slug": "some-rp"},
    )
    @patch(
        "azalea.commands.load_config",
        return_value={"minecraft_version": "1.21", "loader": "fabric"},
    )
    def test_resourcepack_version_fallback(self, _cfg, _resolve, _find, mock_http):
        """Resource packs with no exact match should fall back to latest version with a warning."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            with (
                patch("azalea.commands.RESOURCEPACKS", td),
                patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "resourcepack")]),
            ):
                install_mod("some-rp")

        # http_json called to get all versions as fallback
        mock_http.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: remove_mod
# ---------------------------------------------------------------------------


class TestRemoveMod(unittest.TestCase):
    def test_remove_from_mods(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            slug = "sodium"
            mod_file = td / f"{slug}.json"
            _write_json(mod_file, _mod_data(slug))

            with (
                patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "mod")]),
                patch("azalea.commands.MODS", td),
            ):
                remove_mod(slug)

            self.assertFalse(mod_file.exists())

    def test_remove_warns_if_not_installed(self):
        with (
            patch("azalea.commands._ALL_CONTENT_DIRS", []),
            patch("azalea.commands.MODS", Path("/nonexistent/mods")),
            patch("azalea.commands.log_warn") as mock_warn,
        ):
            remove_mod("nonexistent-slug")
            mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: prune_unused_deps
# ---------------------------------------------------------------------------


class TestPruneUnusedDeps(unittest.TestCase):
    def test_removes_implicit_unreferenced(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # sodium (explicit) depends on dep; orphan is not referenced
            _write_json(td / "sodium.json", _mod_data("sodium", explicit=True, deps=["proj-dep"]))
            _write_json(td / "dep.json", _mod_data("dep", explicit=False))

            orphan = _mod_data("orphan", explicit=False)
            orphan["project_id"] = "proj-orphan"  # not in any deps list
            _write_json(td / "orphan.json", orphan)

            with patch("azalea.commands.MODS", td):
                removed = prune_unused_deps()

            self.assertIn("orphan", removed)
            self.assertFalse((td / "orphan.json").exists())
            self.assertTrue((td / "sodium.json").exists())
            self.assertTrue((td / "dep.json").exists())


# ---------------------------------------------------------------------------
# Tests: check
# ---------------------------------------------------------------------------


class TestCheck(unittest.TestCase):
    @patch("azalea.commands._check_compat", return_value=[])
    @patch(
        "azalea.commands.load_config",
        return_value={"minecraft_version": "1.21", "loader": "fabric"},
    )
    def test_check_defaults_to_current_version(self, _cfg, mock_compat):
        with patch("azalea.commands.log_ok") as mock_ok:
            check()  # no argument
            mock_compat.assert_called_once_with("1.21", "fabric")
            mock_ok.assert_called_once()

    @patch("azalea.commands._check_compat", return_value=["bad-mod"])
    @patch("azalea.commands.resolve_target_mc", return_value="1.20")
    @patch(
        "azalea.commands.load_config",
        return_value={"minecraft_version": "1.21", "loader": "fabric"},
    )
    def test_check_with_explicit_version(self, _cfg, _resolve, mock_compat):
        check("1.20")
        mock_compat.assert_called_once_with("1.20", "fabric")


# ---------------------------------------------------------------------------
# Tests: pin / unpin
# ---------------------------------------------------------------------------


class TestPinUnpin(unittest.TestCase):
    def test_pin_sets_flag(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_json(td / "sodium.json", _mod_data("sodium"))

            with patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "mod")]):
                pin_mod("sodium")

            data = json.loads((td / "sodium.json").read_text())
            self.assertTrue(data.get("pinned"))

    def test_unpin_removes_flag(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_json(td / "sodium.json", _mod_data("sodium"))

            with patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "mod")]):
                pin_mod("sodium")
                unpin_mod("sodium")

            data = json.loads((td / "sodium.json").read_text())
            self.assertFalse(data.get("pinned", False))

    def test_unpin_warns_if_not_pinned(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_json(td / "sodium.json", _mod_data("sodium"))

            with (
                patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "mod")]),
                patch("azalea.commands.log_info") as mock_info,
            ):
                unpin_mod("sodium")
                mock_info.assert_called_once()

    def test_pin_warns_if_not_installed(self):
        with (
            patch("azalea.commands._ALL_CONTENT_DIRS", []),
            patch("azalea.commands.log_warn") as mock_warn,
        ):
            pin_mod("nonexistent")
            mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: info
# ---------------------------------------------------------------------------


class TestInfo(unittest.TestCase):
    def test_info_prints_details(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_json(td / "sodium.json", _mod_data("sodium", pinned=True))

            buf = io.StringIO()
            with (
                patch("azalea.commands._ALL_CONTENT_DIRS", [(td, "mod")]),
                redirect_stdout(buf),
            ):
                info("sodium")

            output = buf.getvalue()
            self.assertIn("sodium", output)
            self.assertIn("True", output)  # pinned

    def test_info_warns_if_not_installed(self):
        with (
            patch("azalea.commands._ALL_CONTENT_DIRS", []),
            patch("azalea.commands.log_warn") as mock_warn,
        ):
            info("not-there")
            mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: search loader filtering
# ---------------------------------------------------------------------------


class TestSearch(unittest.TestCase):
    def _run_search(self, query, config=None):
        """Run search() and return the facets string that was passed to http_json."""
        captured_url = []

        def fake_http(url):
            captured_url.append(url)
            return {"hits": []}

        patches = [patch("azalea.commands.http_json", side_effect=fake_http)]
        if config is not None:
            patches.append(patch("azalea.commands.CONFIG"))
            patches.append(patch("azalea.commands.load_config", return_value=config))

        with patches[0]:
            if len(patches) > 1:
                with patches[1] as mock_cfg_path, patches[2]:
                    mock_cfg_path.exists.return_value = True
                    search(query)
            else:
                with patch("azalea.commands.CONFIG") as mock_cfg_path:
                    mock_cfg_path.exists.return_value = False
                    search(query)

        return captured_url[0] if captured_url else ""

    def test_no_config_sends_single_facet_group(self):
        url = self._run_search("sodium")
        # Only one facet group — no loader filter
        import json
        from urllib.parse import unquote, urlparse, parse_qs

        qs = parse_qs(urlparse(url).query)
        facets = json.loads(unquote(qs["facets"][0]))
        self.assertEqual(len(facets), 1)

    def test_with_fabric_config_adds_loader_facet(self):
        url = self._run_search("sodium", config={"loader": "fabric"})
        import json
        from urllib.parse import unquote, urlparse, parse_qs

        qs = parse_qs(urlparse(url).query)
        facets = json.loads(unquote(qs["facets"][0]))
        # Two groups: project_type AND loader-aware group
        self.assertEqual(len(facets), 2)
        loader_group = facets[1]
        self.assertIn("categories:fabric", loader_group)
        # Resource packs and shaders always pass through
        self.assertIn("project_type:resourcepack", loader_group)
        self.assertIn("project_type:shader", loader_group)

    def test_forge_only_mod_excluded_by_facet(self):
        """A Forge-only mod would not satisfy categories:fabric, so the API
        excludes it.  We verify the facet is built correctly for forge packs."""
        url = self._run_search("optifine", config={"loader": "forge"})
        import json
        from urllib.parse import unquote, urlparse, parse_qs

        qs = parse_qs(urlparse(url).query)
        facets = json.loads(unquote(qs["facets"][0]))
        loader_group = facets[1]
        self.assertIn("categories:forge", loader_group)
        self.assertNotIn("categories:fabric", loader_group)


if __name__ == "__main__":
    unittest.main()
