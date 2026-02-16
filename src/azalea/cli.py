# --------------------------------------------------------------------------------------------
# azalea - A Python Minecraft Modpack manager
# --------------------------------------------------------------------------------------------
# Author: Matej Stastny
# Date: 2026-02-14 (YYYY-MM-DD)
# License: MIT
# Link: https://github.com/matejstastny/azalea
# --------------------------------------------------------------------------------------------

import argparse, json, sys, zipfile, time, platform

from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import quote


# ---------------- CONFIG ----------------


BASE = Path(".")
CONFIG = BASE / "azalea.json"
MODS = BASE / "mods"
RESOURCEPACKS = BASE / "resourcepacks"
SHADERPACKS = BASE / "shaderpacks"
DATAPACKS = BASE / "datapacks"
OVERRIDES = BASE / "overrides"

API = "https://api.modrinth.com/v2"


# ---------------- LOGGING ----------------


class Log:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    PURPLE = "\033[0;35m"


def log_info(msg):
    print(f"{Log.CYAN} {msg}{Log.RESET}")


def log_ok(msg):
    print(f"{Log.GREEN} {msg}{Log.RESET}")


def log_warn(msg):
    print(f"{Log.YELLOW} {msg}{Log.RESET}")


def log_err(msg):
    print(f"{Log.RED} {msg}{Log.RESET}")


def log_deb(msg):
    print(f"{Log.PURPLE}󰨰 {msg}{Log.RESET}")


# ---------------- UI HELPERS ----------------


def clear_lines(n):
    for _ in range(n):
        sys.stdout.write("\033[1A")
        sys.stdout.write("\033[2K")
    sys.stdout.flush()


def spinner(msg, duration=0.6):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    end = time.time() + duration
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r{Log.BLUE}{frames[i % len(frames)]} {msg}{Log.RESET}")
        sys.stdout.flush()
        time.sleep(0.05)
        i += 1
    sys.stdout.write("\r")
    sys.stdout.write("\033[2K")
    print(f"{Log.BLUE}󱗾 {msg}{Log.RESET}")


def get_version() -> str:
    try:
        return version("azalea")
    except PackageNotFoundError:
        return "unknown"


def print_version():
    title = f"{Log.BOLD}{Log.CYAN}Azalea CLI ✿{Log.RESET}"
    v = f"{Log.GREEN}{get_version()}{Log.RESET}"
    py = f"{Log.YELLOW}{platform.python_version()}{Log.RESET}"
    plat = f"{Log.BLUE}{platform.system()}-{platform.machine()}{Log.RESET}"
    url = f"{Log.CYAN}https://github.com/matejstastny/azalea{Log.RESET}"

    block = (
        f"{title}\n"
        f"{Log.BOLD}Version   {Log.RESET}: {v}\n"
        f"{Log.BOLD}Python    {Log.RESET}: {py}\n"
        f"{Log.BOLD}Platform  {Log.RESET}: {plat}\n"
        f"{Log.BOLD}Project   {Log.RESET}: {url}"
    )

    print(block)
    raise SystemExit(0)


# ---------------- UTIL ----------------


def http_json(url):
    req = Request(url, headers={"User-Agent": "azalea/0.1"})
    with urlopen(req) as r:
        return json.loads(r.read().decode())


def ensure_dirs():
    MODS.mkdir(exist_ok=True)
    RESOURCEPACKS.mkdir(exist_ok=True)
    SHADERPACKS.mkdir(exist_ok=True)
    DATAPACKS.mkdir(exist_ok=True)
    OVERRIDES.mkdir(exist_ok=True)


def load_config():
    if not CONFIG.exists():
        sys.exit("Not an Azalea pack. Run `azalea init`")
    return json.loads(CONFIG.read_text())


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def safe_name(s):
    """Make a filesystem-safe name."""
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ."
    cleaned = "".join(c if c in keep else "-" for c in s)
    return "-".join(cleaned.strip().split())


# ---------------- VERSION MATCHING ----------------


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


# ---------------- MODRINTH ----------------


def search_projects(query):
    """Search Modrinth and interactively ask the user to choose."""
    facets = quote(
        '[["project_type:mod","project_type:resourcepack","project_type:shader","project_type:datapack"]]'
    )
    data = http_json(f"{API}/search?query={quote(query)}&limit=10&facets={facets}")
    hits = data.get("hits", [])

    if not hits:
        log_warn("No matching projects found")
        return None

    spinner("Searching Modrinth…")
    spinner("Fetching results…")

    log_info("Select a project:")
    for i, h in enumerate(hits, 1):
        title = h.get("title") or h.get("slug")
        print(f"  {Log.BOLD}{i}){Log.RESET} {title}")

    printed_lines = len(hits) + 1

    while True:
        choice = input("Enter number (or press Enter to cancel): ").strip()
        if not choice:
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(hits):
            selected = hits[int(choice) - 1]
            title = selected.get("title") or selected.get("slug")

            clear_lines(printed_lines + 1)

            log_ok(f"Selected: {title}")
            return selected
        log_warn("Invalid selection.")


def resolve_project(user_input):
    if "modrinth.com" in user_input:
        slug = user_input.rstrip("/").split("/")[-1]
    else:
        slug = user_input

    try:
        return http_json(f"{API}/project/{slug}")
    except HTTPError as e:
        if e.code != 404:
            raise

    result = search_projects(slug)
    if not result:
        log_err("No project selected")
        sys.exit(1)

    return http_json(f"{API}/project/{result['project_id']}")


def find_best_version(project_id, mc, loader):
    spinner("Resolving compatible version")
    versions = http_json(f"{API}/project/{project_id}/version")
    matches = [
        v
        for v in versions
        if mc_version_matches(mc, v.get("game_versions", []))
        and (
            not v.get("loaders")
            or loader in v.get("loaders", [])
            or "minecraft" in v.get("loaders", [])
            or "datapack" in v.get("loaders", [])
            or any(
                l in v.get("loaders", []) for l in ("iris", "optifine")
            )  # todo: better shader handeling
        )
    ]
    if not matches:
        return None
    return matches[0]


# ---------------- MINECRAFT VERSION RESOLUTION ----------------


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
    """Return the latest compatible Fabric version string, or None"""
    try:
        url = f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}"
        data = http_json(url)
        if not data:
            return None
        return data[0]["loader"]["version"]
    except Exception:
        return None


# ---------------- INSTALL ----------------


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
    elif project_type == "datapack":
        target_dir = DATAPACKS
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

    deps = [
        d["project_id"]
        for d in version["dependencies"]
        if d["dependency_type"] == "required"
    ]

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
        },
        "explicit": explicit,
        "dependencies": deps,
    }

    save_json(target_dir / f"{slug}.json", data)
    log_ok(f"Installed {slug}")

    for dep in deps:
        install_mod(dep, installed, explicit=False)


# ---------------- REMOVE ----------------


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


# ---------------- CHECK ----------------


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


# ---------------- EXPORT ----------------


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
            manifest["files"].append(
                {
                    "path": f"{prefix}/{mod['file']['filename']}",
                    "hashes": {"sha512": mod["file"]["sha512"]},
                    "downloads": [mod["file"]["url"]],
                    "fileSize": 0,
                }
            )

    add_files_from(MODS, "mods")
    add_files_from(RESOURCEPACKS, "resourcepacks")
    add_files_from(SHADERPACKS, "shaderpacks")
    add_files_from(DATAPACKS, "datapacks")

    spinner("Building mrpack archive", duration=0.8)

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("modrinth.index.json", json.dumps(manifest, indent=2))

        if OVERRIDES.exists():
            for file in OVERRIDES.rglob("*"):
                if file.is_file():
                    z.write(file, f"overrides/{file.relative_to(OVERRIDES)}")

    log_ok(f"Exported {path}")


# ---------------- INIT ----------------


def init():
    if CONFIG.exists():
        log_warn("Already initialized")
        return

    ensure_dirs()

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


# ---------------- UPGRADE ----------------


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
        if new_loader:
            cfg["loader_version"] = new_loader
            log_info(f"Updated Fabric loader to {new_loader}")
        else:
            log_warn("Could not resolve a Fabric loader for the new version")

    save_json(CONFIG, cfg)
    log_ok(f"Pack upgraded to Minecraft {target_mc}")


# ---------------- CLI ----------------


def main():
    p = argparse.ArgumentParser(prog="azalea")
    sub = p.add_subparsers(dest="cmd")

    p.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version information and exit",
    )

    sub.add_parser("init")

    a = sub.add_parser("add", help="Add a Modrinth mod")
    a.add_argument("mod", help="Mod name")

    r = sub.add_parser("remove", help="Remove Modrinth mod")
    r.add_argument("slug", help="Mod slug")

    c = sub.add_parser(
        "check", help="Check if the modpack is compatible with a Minecraft version"
    )
    c.add_argument("mc", help="Target Minecraft version")

    sub.add_parser("export", help="Export a .mrpack to dist/")

    u = sub.add_parser(
        "upgrade",
        help="Upgrade the modpack to latest or specified Minecraft version",
    )
    u.add_argument(
        "mc",
        nargs="?",
        help="Target Minecraft version (defaults to latest release)",
    )

    args = p.parse_args()

    try:
        if args.version:
            print_version()
        elif args.cmd == "init":
            init()
        elif args.cmd == "add":
            install_mod(args.mod)
        elif args.cmd == "remove":
            remove_mod(args.slug)
        elif args.cmd == "check":
            check(args.mc)
        elif args.cmd == "export":
            export()
        elif args.cmd == "upgrade":
            upgrade(args.mc)
        else:
            p.print_help()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
