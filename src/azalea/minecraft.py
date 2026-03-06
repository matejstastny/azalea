"""Minecraft version utilities: matching, resolution, and loader version lookup."""

import sys
import xml.etree.ElementTree as ET
from urllib.request import urlopen

from azalea.config import API
from azalea.log import log_err, log_info
from azalea.util import http_json

SUPPORTED_LOADERS = ["fabric", "quilt", "neoforge", "forge"]


def mc_version_matches(target: str, supported: list[str]) -> bool:
    for v in supported:
        if v == target:
            return True

        if v.endswith(".x"):
            prefix = v[:-2]
            if target == prefix or target.startswith(prefix + "."):
                return True

        if target.endswith(".x"):
            prefix = target[:-2]
            if v == prefix or v.startswith(prefix + "."):
                return True

    return False


def get_release_versions():
    """Return list of major Minecraft versions from Modrinth"""
    data = http_json(f"{API}/tag/game_version")
    releases = [v for v in data if v.get("version_type") == "release"]
    return releases


def resolve_target_mc(user_arg):
    """Validate a Minecraft version string/latest"""
    releases = get_release_versions()
    if not releases:
        log_err("Failed to fetch Minecraft version list from Modrinth")
        sys.exit(1)

    if user_arg.lower() == "latest":
        latest = max(releases, key=lambda v: v.get("date_published", ""))
        version = latest["version"]
        log_info(f"Resolved latest Minecraft release: {version}")
        return version

    parts = user_arg.split(".")
    if not all(p.isdigit() for p in parts):
        log_err("Invalid Minecraft version format. Use versions like 1.21 or 1.21.1")
        sys.exit(1)

    valid_versions = {v["version"] for v in releases}
    if user_arg not in valid_versions:
        log_err(f"Minecraft version '{user_arg}' is not a valid released version")
        sys.exit(1)

    return user_arg


def get_latest_release_version():
    """Return the latest stable Minecraft version string, or None"""
    try:
        releases = get_release_versions()
        if not releases:
            return None
        latest = max(releases, key=lambda v: v.get("date_published", ""))
        return latest.get("version")
    except Exception:
        return None


def get_latest_fabric_loader(mc_version):
    """Return the latest compatible Fabric loader version string, or None"""
    try:
        url = f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}"
        data = http_json(url)
        if not data:
            return None
        return data[0]["loader"]["version"]
    except Exception:
        return None


def get_latest_quilt_loader(mc_version):
    """Return the latest compatible Quilt loader version string, or None"""
    try:
        url = f"https://meta.quiltmc.org/v3/versions/loader/{mc_version}"
        data = http_json(url)
        if not data:
            return None
        return data[0]["loader"]["version"]
    except Exception:
        return None


def get_latest_neoforge_loader(mc_version):
    """Return the latest NeoForge version for the given MC version, or None.

    NeoForge version scheme (1.20.2+): {mcMinor}.{mcPatch}.{build}
    e.g. MC 1.21.4 → NeoForge 21.4.x
         MC 1.21   → NeoForge 21.0.x
    """
    try:
        parts = mc_version.split(".")
        if len(parts) == 2:
            neo_prefix = f"{parts[1]}.0."
        elif len(parts) == 3:
            neo_prefix = f"{parts[1]}.{parts[2]}."
        else:
            return None

        with urlopen(
            "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml",
            timeout=10,
        ) as resp:
            tree = ET.parse(resp)

        versions = [v.text for v in tree.findall(".//version") if v.text]
        matching = [v for v in versions if v.startswith(neo_prefix)]
        return matching[-1] if matching else None
    except Exception:
        return None


def get_latest_forge_loader(mc_version):
    """Return the latest Forge version for the given MC version, or None."""
    try:
        data = http_json(
            "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
        )
        promos = data.get("promos", {})
        for suffix in ("recommended", "latest"):
            key = f"{mc_version}-{suffix}"
            if key in promos:
                return promos[key]
        return None
    except Exception:
        return None


def get_latest_loader_version(loader: str, mc_version: str):
    """Return the latest version string for the given loader, or None."""
    if loader == "fabric":
        return get_latest_fabric_loader(mc_version)
    elif loader == "quilt":
        return get_latest_quilt_loader(mc_version)
    elif loader == "neoforge":
        return get_latest_neoforge_loader(mc_version)
    elif loader == "forge":
        return get_latest_forge_loader(mc_version)
    return None
