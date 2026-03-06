"""All CLI command implementations."""

import json
import zipfile
from pathlib import Path
from urllib.parse import quote

from azalea.config import API, BASE, CONFIG, MODS, OVERRIDES, RESOURCEPACKS, SHADERPACKS
from azalea.log import Log, clear_lines, log_err, log_info, log_ok, log_warn, spinner
from azalea.minecraft import (
    SUPPORTED_LOADERS,
    get_latest_loader_version,
    get_latest_release_version,
    get_release_versions,
    mc_version_matches,
    resolve_target_mc,
)
from azalea.modrinth import find_best_version, resolve_project
from azalea.util import ensure_overrides_dir, http_json, load_config, safe_name, save_json

_ALL_CONTENT_DIRS = [
    (MODS, "mod"),
    (RESOURCEPACKS, "resourcepack"),
    (SHADERPACKS, "shader"),
]


def _find_installed(slug):
    """Return (path, type_name) for an installed slug, or (None, None)."""
    for dir_path, type_name in _ALL_CONTENT_DIRS:
        p = dir_path / f"{slug}.json"
        if p.exists():
            return p, type_name
    return None, None


def _check_compat(target_mc, loader):
    """Check all installed mods for compatibility with target_mc.

    Returns list of incompatible slugs.
    """
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

    return incompatible


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
        if project_type == "resourcepack":
            log_warn(f"No version of {slug} matches Minecraft {mc}; installing latest available")
            all_versions = http_json(f"{API}/project/{pid}/version")
            version = all_versions[0] if all_versions else None
        if not version:
            log_err(f"No compatible version for {slug}")
            return

    file = version["files"][0]
    file_size = file.get("size", 0)

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
            "size": file_size,
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
    p, _ = _find_installed(slug)
    if not p:
        log_warn("Not installed")
        return
    p.unlink()
    log_info(f"Removed {slug}")

    removed = prune_unused_deps()
    if removed:
        log_info("Pruned unused dependencies: " + ", ".join(removed))


def remove_from_file(file_path: str):
    p = Path(file_path)

    if not p.exists():
        log_err(f"File not found: {file_path}")
        return

    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        remove_mod(line)


def check(user_arg=None):
    cfg = load_config()
    loader = cfg["loader"]

    if user_arg is None:
        target_mc = cfg["minecraft_version"]
        log_info(f"Checking against current pack version: {target_mc}")
    else:
        target_mc = resolve_target_mc(user_arg)

    incompatible = _check_compat(target_mc, loader)

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
                    "fileSize": mod["file"].get("size", 0),
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


def _prompt(label: str, default: str = "") -> str:
    """Display a prompt and return the user's input, falling back to default."""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {Log.BOLD}{label}{Log.RESET}{suffix}: ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def _pick_mc_version(releases: list) -> str:
    """Show a numbered list of recent MC versions and return the user's choice."""
    recent = sorted(releases, key=lambda v: v["date_published"], reverse=True)[:15]
    all_valid = {r["version"] for r in releases}

    print(f"\n  {Log.BOLD}Minecraft version{Log.RESET} (type a number or version directly):")
    for i, r in enumerate(recent, 1):
        print(f"    {i}) {r['version']}")
    print()

    while True:
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            return recent[0]["version"]

        if not choice:
            return recent[0]["version"]
        if choice.isdigit() and 1 <= int(choice) <= len(recent):
            return recent[int(choice) - 1]["version"]
        if choice in all_valid:
            return choice
        log_warn("  Invalid selection, try again")


def _pick_loader() -> str:
    """Show the supported loaders and return the user's choice."""
    print(f"\n  {Log.BOLD}Loader{Log.RESET}:")
    for i, loader in enumerate(SUPPORTED_LOADERS, 1):
        print(f"    {i}) {loader}")
    print()

    while True:
        try:
            choice = input("  Select [1]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            return SUPPORTED_LOADERS[0]

        if choice.isdigit() and 1 <= int(choice) <= len(SUPPORTED_LOADERS):
            return SUPPORTED_LOADERS[int(choice) - 1]
        if choice in SUPPORTED_LOADERS:
            return choice
        log_warn("  Invalid selection, try again")


def init():
    if CONFIG.exists():
        log_warn("Already initialized")
        return

    ensure_overrides_dir()

    spinner("Fetching Minecraft versions")
    releases = get_release_versions()
    if not releases:
        log_warn("Could not fetch Minecraft versions; using fallback 1.21")
        releases = [{"version": "1.21", "date_published": "2024-06-13"}]

    print(f"\n{Log.BOLD}{Log.CYAN}  Azalea — New Pack{Log.RESET}\n")

    name = _prompt("Pack name", "My Pack")
    author = _prompt("Author", "")
    version = _prompt("Version", "0.1.0")
    license_ = _prompt("License", "")

    mc_version = _pick_mc_version(releases)
    loader = _pick_loader()

    spinner(f"Resolving {loader} loader version")
    loader_version = get_latest_loader_version(loader, mc_version)
    if loader_version:
        log_info(f"Using {loader} {loader_version}")
    else:
        loader_version = ""
        log_warn(f"Could not resolve {loader} loader version for Minecraft {mc_version}")

    data = {
        "name": name,
        "author": author,
        "version": version,
        "license": license_,
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

    incompatible = _check_compat(target_mc, loader)

    if incompatible:
        log_err("Upgrade blocked. These mods have no compatible version:")
        for slug in incompatible:
            print(f"  - {slug}")
        return

    cfg["minecraft_version"] = target_mc

    new_loader_ver = get_latest_loader_version(loader, target_mc)
    if new_loader_ver == loader_ver:
        log_info(f"{loader} loader already latest")
    elif new_loader_ver:
        cfg["loader_version"] = new_loader_ver
        log_info(f"Updated {loader} loader to {new_loader_ver}")
    else:
        log_warn(f"Could not resolve a {loader} loader version for Minecraft {target_mc}")

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

                if data.get("pinned"):
                    skipped.append(f"{slug} (pinned)")
                    continue

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
                            "size": file.get("size", 0),
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

            slug = data.get("slug", "unknown")
            side = data.get("side", "?")
            version = data.get("version_number", "?")

            url = f"https://modrinth.com/project/{slug}"
            entries.append(f"| [{slug}]({url}) | {type_name} | {side} | {version} |")

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


def search(query):
    """Search Modrinth and display results."""
    facets = quote(
        '[["project_type:mod","project_type:resourcepack","project_type:shader","project_type:datapack"]]'
    )
    spinner("Searching Modrinth…")
    data = http_json(f"{API}/search?query={quote(query)}&limit=10&facets={facets}")
    hits = data.get("hits", [])

    if not hits:
        log_warn("No results found")
        return

    print()
    for i, h in enumerate(hits, 1):
        title = h.get("title") or h.get("slug")
        slug = h.get("slug", "")
        project_type = h.get("project_type", "mod")
        desc = h.get("description", "")
        downloads = h.get("downloads", 0)

        print(
            f"  {Log.BOLD}{i}){Log.RESET} {Log.CYAN}{title}{Log.RESET}"
            f"  {Log.YELLOW}({slug}){Log.RESET}  [{project_type}]"
        )
        if desc:
            print(f"     {desc[:90]}")
        print(f"     {Log.GREEN}{downloads:,} downloads{Log.RESET}")
        print()


def info(slug):
    """Display details of an installed mod/resourcepack/shader."""
    p, type_name = _find_installed(slug)

    if not p:
        log_warn(f"{slug} is not installed")
        return

    data = json.loads(p.read_text())
    pinned = data.get("pinned", False)
    explicit = data.get("explicit", True)
    deps = data.get("dependencies", [])

    print()
    print(f"  {Log.BOLD}{Log.CYAN}{data['slug']}{Log.RESET}")
    print(f"  {'Type':<12}: {type_name}")
    print(f"  {'Version':<12}: {data.get('version_number', '?')}")
    print(f"  {'Side':<12}: {data.get('side', '?')}")
    print(f"  {'Explicit':<12}: {explicit}")
    print(f"  {'Pinned':<12}: {pinned}")
    if deps:
        print(f"  {'Dependencies':<12}: {', '.join(deps)}")
    print(f"  {'URL':<12}: https://modrinth.com/project/{data['slug']}")
    print()


def pin_mod(slug):
    """Lock a mod to its current version, skipping it during updates."""
    p, _ = _find_installed(slug)
    if not p:
        log_warn(f"{slug} is not installed")
        return
    data = json.loads(p.read_text())
    data["pinned"] = True
    save_json(p, data)
    log_ok(f"Pinned {slug} at {data.get('version_number', '?')}")


def unpin_mod(slug):
    """Remove the pin from a mod so it can be updated again."""
    p, _ = _find_installed(slug)
    if not p:
        log_warn(f"{slug} is not installed")
        return
    data = json.loads(p.read_text())
    if not data.get("pinned"):
        log_info(f"{slug} is not pinned")
        return
    del data["pinned"]
    save_json(p, data)
    log_ok(f"Unpinned {slug}")
