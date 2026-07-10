"""Prism Launcher integration: export and import pack."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from azalea.commands import export
from azalea.log import log_err, log_info, log_ok
from azalea.util import safe_name


def _find_prism() -> list[str] | None:
    """Return the Prism Launcher command as a list, or None if not found."""
    for name in ("prismlauncher", "PrismLauncher"):
        if shutil.which(name):
            return [name]
    if shutil.which("flatpak"):
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "org.prismlauncher.PrismLauncher" in result.stdout:
            return ["flatpak", "run", "org.prismlauncher.PrismLauncher"]
    return None


def _patch_mrpack(src: Path, tag: str) -> Path:
    """Return a copy of src with the pack name suffixed by [tag]."""
    with zipfile.ZipFile(src, "r") as z:
        manifest = json.loads(z.read("modrinth.index.json"))
        other = {name: z.read(name) for name in z.namelist() if name != "modrinth.index.json"}

    manifest["name"] = f"{manifest['name']} [{tag}]"

    dest = src.parent / src.name.replace(".mrpack", f"-{safe_name(tag)}.mrpack")
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("modrinth.index.json", json.dumps(manifest, indent=2))
        for name, data in other.items():
            z.writestr(name, data)

    return dest


def prism_import(client_only: bool = False, tag: str = "azalea-dev") -> None:
    """Export the pack and open it in Prism Launcher's import dialog."""
    cmd = _find_prism()
    if not cmd:
        log_err("Prism Launcher not found — make sure 'prismlauncher' is in your PATH")
        log_err("Download from: https://prismlauncher.org")
        return

    path = export(client_only=client_only)
    if path is None:
        return

    if path.suffix == ".zip":
        log_err("This pack uses presets, which produce a .zip of .mrpack files.")
        log_err("Prism can only import individual .mrpack files.")
        log_err(f"Extract one from {path} and import it manually.")
        return

    dev_path = _patch_mrpack(path, tag)

    log_info(f"Opening {dev_path.name} in Prism Launcher…")
    subprocess.Popen(cmd + ["--import", str(dev_path.resolve())])
    log_ok("Prism Launcher launched")
