"""All CLI command implementations."""

import json
import zipfile
from pathlib import Path

from azalea.config import API, BASE, CONFIG, MODS, OVERRIDES, RESOURCEPACKS, SHADERPACKS
from azalea.log import log_err, log_info, log_ok, log_warn, spinner
from azalea.minecraft import (
    get_latest_fabric_loader,
    get_latest_release_version,
    mc_version_matches,
    resolve_target_mc,
)
from azalea.modrinth import find_best_version, resolve_project
from azalea.util import ensure_overrides_dir, http_json, load_config, safe_name, save_json


def install_mod(identifier, installed=None, explicit=True):
    if installed is None:
        installed = set()

    cfg = load_config()
    mc, loader = cfg["minecraft_version"], cfg["loader"]

    proj = resolve_project(identifier)
    pid, slug = proj["id"], proj["slug"]

    project_type = proj.get("project_type", "mod")

    if project_type == "modpack":
        log_err(f"{slug} is a modpack, not an installable project type")
        return
    elif project_type == "resourcepack":
        target_dir = RESOURCEPACKS
    elif project_type == "shader":
        target_dir = SHADERPACKS
    else:
        target_dir = MODS

    if slug in installed:
        existing = target_dir / f"{slug}.json"
        if explicit and existing.exists():
            data = json.loads(existing.read_text())
            if not data.get("explicit", False):
                data["explicit"] = True
                save_json(existing, data)
                log_info(f"Promoted {slug} to explicit mod")
        return
    installed.add(slug)

    version = find_best_version(pid, mc, loader)
    if not version:
        log_err(f"No compatible version for {slug}")
        return

    file = version["files"][0]

    deps = [d["project_id"] for d in version["dependencies"] if d["dependency_type"] == "required"]

    client_supported = proj.get("client_side", "unknown") != "unsupported"
    server_supported = proj.get("server_side", "unknown") != "unsupported"

    if client_supported and server_supported:
        side = "both"
    elif client_supported:
        side = "client"
    elif server_supported:
        side = "server"
    else:
        side = "unknown"

    data = {
        "project_id": pid,
        "slug": slug,
        "version_id": version["id"],
        "version_number": version["version_number"],
        "side": side,
        "file": {
            "url": file["url"],
            "filename": file["filename"],
            "sha512": file["hashes"]["sha512"],
            "sha1": file["hashes"].get("sha1"),
        },
        "explicit": explicit,
        "dependencies": deps,
    }

    target_dir.mkdir(exist_ok=True)
    save_json(target_dir / f"{slug}.json", data)
    log_ok(f"Installed {slug}")

    for dep in deps:
        install_mod(dep, installed, explicit=False)


def install_from_file(file_path: str):
    p = Path(file_path)

    if not p.exists():
        log_err(f"File not found: {file_path}")
        return

    failed = []
    installed_any = []
    installed = set()

    for raw in p.read_text().splitlines():
        line = raw.strip()

        if not line or line.startswith("#"):
            continue
        name = line

        try:
            install_mod(line, installed=installed, explicit=True)
            installed_any.append(name)
        except SystemExit:
            log_err(f"Failed to install {line}")
            failed.append(name)
            continue
        except Exception as e:
            log_err(f"Failed to install {line}: {e}")
            failed.append(name)
            continue

    if installed_any:
        log_ok(f"Batch install complete: {len(installed_any)} installed")
    if failed:
        log_warn(f"{len(failed)} entries failed: " + ", ".join(failed))


def prune_unused_deps():
    """Remove mods that are only dependencies and no longer required."""
    mods = []
    for f in MODS.glob("*.json"):
        mods.append(json.loads(f.read_text()))

    by_id = {m["project_id"]: m for m in mods}
    needed = set(m["project_id"] for m in mods if m.get("explicit"))

    stack = list(needed)
    while stack:
        cur = stack.pop()
        mod = by_id.get(cur)
        if not mod:
            continue
        for dep in mod.get("dependencies", []):
            if dep not in needed:
                needed.add(dep)
                stack.append(dep)

    removed = []
    for f in MODS.glob("*.json"):
        data = json.loads(f.read_text())
        if data["project_id"] not in needed:
            f.unlink()
            removed.append(data["slug"])

    return removed


def remove_mod(slug):
    p = MODS / f"{slug}.json"
    if not p.exists():
        log_warn("Not installed")
        return
    p.unlink()
    log_info(f"Removed {slug}")

    removed = prune_unused_deps()
    if removed:
        log_info("Pruned unused dependencies: " + ", ".join(removed))


def check(user_arg):
    cfg = load_config()
    loader = cfg["loader"]

    target_mc = resolve_target_mc(user_arg)

    incompatible = []

    for f in MODS.glob("*.json"):
        mod = json.loads(f.read_text())
        pid = mod["project_id"]
        slug = mod["slug"]

        spinner(f"Checking {slug}", duration=0.2)

        versions = http_json(f"{API}/project/{pid}/version")

        compatible = any(
            mc_version_matches(target_mc, v.get("game_versions", []))
            and (
                not v.get("loaders")
                or loader in v.get("loaders", [])
                or "minecraft" in v.get("loaders", [])
            )
            for v in versions
        )

        if not compatible:
            incompatible.append(slug)

    if incompatible:
        for slug in incompatible:
            print(f"{slug} - no version available for Minecraft {target_mc}")
    else:
        log_ok(f"All mods support Minecraft {target_mc}")


def export():
    cfg = load_config()

    out_dir = BASE / "dist"
    out_dir.mkdir(exist_ok=True)

    pack_name = safe_name(cfg.get("name", "pack"))
    pack_ver = safe_name(cfg.get("version", "0"))
    mc_ver = safe_name(cfg.get("minecraft_version", "mc"))

    filename = f"{pack_name}-{pack_ver}-mc{mc_ver}.mrpack"
    path = out_dir / filename

    deps = {
        "minecraft": cfg["minecraft_version"],
    }

    if cfg.get("loader") == "fabric" and cfg.get("loader_version"):
        deps["fabric-loader"] = cfg["loader_version"]
    elif cfg.get("loader") and cfg.get("loader_version"):
        deps[f"{cfg['loader']}-loader"] = cfg["loader_version"]

    manifest = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": cfg["version"],
        "name": cfg["name"],
        "dependencies": deps,
        "files": [],
    }

    def add_files_from(dir_path, prefix):
        for f in dir_path.glob("*.json"):
            mod = json.loads(f.read_text())
            hashes = {"sha512": mod["file"]["sha512"]}

            if mod["file"].get("sha1"):
                hashes["sha1"] = mod["file"]["sha1"]

            manifest["files"].append(
                {
                    "path": f"{prefix}/{mod['file']['filename']}",
                    "hashes": hashes,
                    "downloads": [mod["file"]["url"]],
                    "fileSize": 0,
                }
            )

    add_files_from(MODS, "mods")
    add_files_from(RESOURCEPACKS, "resourcepacks")
    add_files_from(SHADERPACKS, "shaderpacks")

    spinner("Building mrpack archive", duration=0.8)

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("modrinth.index.json", json.dumps(manifest, indent=2))

        if OVERRIDES.exists():
            for file in OVERRIDES.rglob("*"):
                if file.is_file():
                    z.write(file, f"overrides/{file.relative_to(OVERRIDES)}")

    log_ok(f"Exported {path}")


def init():
    if CONFIG.exists():
        log_warn("Already initialized")
        return

    ensure_overrides_dir()

    mc_version = get_latest_release_version()
    if not mc_version:
        mc_version = "1.21"
        log_warn("Could not resolve latest Minecraft version, using fallback 1.21")
    else:
        log_info(f"Using Minecraft {mc_version}")

    # TD: other modloader support (long term goal)
    loader = "fabric"

    loader_version = get_latest_fabric_loader(mc_version)
    if not loader_version:
        loader_version = ""
        log_warn("Could not resolve compatible Fabric loader version")
    else:
        log_info(f"Using Fabric {loader_version}")

    data = {
        "name": "My Pack",
        "author": "Created by Azalea",
        "version": "1.0.0",
        "license": "",
        "minecraft_version": mc_version,
        "loader": loader,
        "loader_version": loader_version,
    }

    save_json(CONFIG, data)
    log_ok("Azalea pack initialized")


def upgrade(target_mc_arg=None):
    cfg = load_config()
    current_mc = cfg["minecraft_version"]
    loader = cfg["loader"]
    loader_ver = cfg["loader_version"]

    if target_mc_arg:
        target_mc = resolve_target_mc(target_mc_arg)
    else:
        spinner("Resolving latest Minecraft version")
        latest = get_latest_release_version()
        if not latest:
            log_err("Could not resolve latest Minecraft version")
            return
        target_mc = latest

    if target_mc == current_mc:
        log_warn(f"Pack already on Minecraft {current_mc}")
        return

    spinner(f"Checking upgrade compatibility: {current_mc} → {target_mc}")

    incompatible = []

    for f in MODS.glob("*.json"):
        mod = json.loads(f.read_text())
        pid = mod["project_id"]
        slug = mod["slug"]

        spinner(f"Checking {slug}", duration=0.2)

        versions = http_json(f"{API}/project/{pid}/version")

        compatible = any(
            mc_version_matches(target_mc, v.get("game_versions", []))
            and (
                not v.get("loaders")
                or loader in v.get("loaders", [])
                or "minecraft" in v.get("loaders", [])
            )
            for v in versions
        )

        if not compatible:
            incompatible.append(slug)

    if incompatible:
        log_err("Upgrade blocked. These mods have no compatible version:")
        for slug in incompatible:
            print(f"  - {slug}")
        return

    cfg["minecraft_version"] = target_mc

    # todo: implement when more loaders implemented
    if loader == "fabric":
        new_loader = get_latest_fabric_loader(target_mc)

        if new_loader == loader_ver:
            log_info("Fabric version already latest")
        elif new_loader:
            cfg["loader_version"] = new_loader
            log_info(f"Updated Fabric loader to {new_loader}")
        else:
            log_warn("Could not resolve a Fabric loader for the new version")

    save_json(CONFIG, cfg)
    log_ok(f"Pack upgraded to Minecraft {target_mc}")


def update_all(force=False):
    cfg = load_config()
    mc = cfg["minecraft_version"]
    loader = cfg["loader"]

    updated = []
    skipped = []
    failed = []

    def update_from(dir_path):
        if not dir_path.exists():
            return

        for f in dir_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                pid = data["project_id"]
                slug = data.get("slug", pid)
                current_version = data.get("version_id")

                spinner(f"Checking {slug}", duration=0.2)

                newest = find_best_version(pid, mc, loader)
                if not newest:
                    failed.append(slug)
                    continue

                if newest["id"] == current_version and not force:
                    skipped.append(slug)
                    continue

                file = newest["files"][0]

                data.update(
                    {
                        "version_id": newest["id"],
                        "version_number": newest.get("version_number", "?"),
                        "file": {
                            "url": file["url"],
                            "filename": file["filename"],
                            "sha512": file["hashes"]["sha512"],
                            "sha1": file["hashes"].get("sha1"),
                        },
                        "dependencies": [
                            d["project_id"]
                            for d in newest.get("dependencies", [])
                            if d.get("dependency_type") == "required"
                        ],
                    }
                )

                save_json(f, data)
                updated.append(slug)
            except Exception:
                failed.append(f.stem)

    update_from(MODS)
    update_from(RESOURCEPACKS)
    update_from(SHADERPACKS)

    if updated:
        log_ok(f"Updated {len(updated)} projects: " + ", ".join(updated))
    if skipped:
        log_info("Already latest: " + ", ".join(skipped))
    if failed:
        log_warn("Failed to update: " + ", ".join(failed))


def readme():
    readme_path = BASE / "README.md"

    if not readme_path.exists():
        log_err("README.md not found in project root")
        return

    content = readme_path.read_text()

    start_tag = "<!-- AZALEA_MODLIST_START -->"
    end_tag = "<!-- AZALEA_MODLIST_END -->"

    if start_tag not in content:
        log_err("README start marker missing:")
        log_err(start_tag)
        return
    if end_tag not in content:
        log_err("README end marker missing:")
        log_err(end_tag)
        return

    entries = []

    def collect_from(dir_path, type_name):
        if not dir_path.exists():
            return
        for f in dir_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue

            name = data.get("slug", "unknown")
            pid = data.get("project_id", "")
            side = data.get("side", "?")
            version = data.get("version_number", "?")

            url = f"https://modrinth.com/project/{pid}"
            entries.append(f"| [{name}]({url}) | {type_name} | {side} | {version} |")

    collect_from(MODS, "mod")
    collect_from(RESOURCEPACKS, "resourcepack")
    collect_from(SHADERPACKS, "shader")

    header = [
        "| Name | Type | Side | Version |",
        "|------|------|------|---------|",
    ]

    table_lines = header + sorted(entries, key=str.lower)
    table_block = "\n".join(table_lines)

    before = content.split(start_tag)[0]
    after = content.split(end_tag)[1]

    new_content = before + start_tag + "\n" + table_block + "\n" + end_tag + after

    readme_path.write_text(new_content)
    log_ok("README mod list updated")
