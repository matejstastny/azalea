"""Server management: build, update, diff, start, status, logs, pin, unpin."""

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from azalea.config import API
from azalea.log import Log, log_err, log_info, log_ok, log_warn, spinner
from azalea.minecraft import get_latest_fabric_installer_version
from azalea.modrinth import download_content, find_best_version
from azalea.util import download_file, http_json, save_json

GITHUB_API = "https://api.github.com"
SERVER_CONFIG_FILE = "azalea-server.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_server_config():
    """Load azalea-server.json from the current working directory."""
    server_config_path = Path(".") / SERVER_CONFIG_FILE
    if not server_config_path.exists():
        log_err(f"Not a server directory — {SERVER_CONFIG_FILE} not found in {Path('.').resolve()}")
        sys.exit(1)
    return json.loads(server_config_path.read_text())


def _parse_source(source):
    """Return ("github", {owner, repo, tag}) or ("local", {path}).

    GitHub URL format: https://github.com/owner/repo[@tag]
    """
    if "github.com" in source:
        tag = None
        clean = source.strip()
        if clean.startswith("https://"):
            path_part = clean[len("https://") :]
            if "@" in path_part:
                idx = path_part.index("@")
                tag = path_part[idx + 1 :] or None
                path_part = path_part[:idx]
            clean = "https://" + path_part
        clean = clean.rstrip("/").removesuffix(".git")
        if "github.com/" in clean:
            repo_part = clean.split("github.com/", 1)[1]
        else:
            repo_part = clean.split("github.com:", 1)[1]
        parts = repo_part.split("/")
        if len(parts) < 2:
            log_err(f"Cannot parse owner/repo from: {source}")
            sys.exit(1)
        return "github", {"owner": parts[0], "repo": parts[1], "tag": tag}
    else:
        return "local", {"path": Path(source).resolve()}


def _github_release(owner, repo, tag):
    """Fetch release JSON from GitHub API. tag=None means latest."""
    if tag:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/tags/{tag}"
    else:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    req = Request(
        url,
        headers={"User-Agent": "azalea/0.1", "Accept": "application/vnd.github.v3+json"},
    )
    try:
        with urlopen(req) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log_err(f"Failed to fetch release from GitHub: {e}")
        sys.exit(1)


def _download_pack_github(owner, repo, tag, tmp):
    """Download + extract the pack source from GitHub. Returns (pack_root, release_tag)."""
    release = _github_release(owner, repo, tag)
    release_tag = release.get("tag_name", tag or "latest")
    zipball_url = release.get("zipball_url") or (
        f"https://github.com/{owner}/{repo}/archive/refs/tags/{release_tag}.zip"
    )

    spinner(f"Downloading {owner}/{repo} @ {release_tag}")
    req = Request(zipball_url, headers={"User-Agent": "azalea/0.1"})
    with urlopen(req) as r:
        content = r.read()

    extract_dir = Path(tmp) / "pack_source"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        z.extractall(extract_dir)

    # GitHub zipball has one top-level dir like "owner-repo-abc1234/"
    subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
    if len(subdirs) == 1:
        pack_root = subdirs[0]
    else:
        pack_root = next((d for d in subdirs if (d / "azalea.json").exists()), extract_dir)

    return pack_root, release_tag


def _collect_server_mods(pack_root):
    """Return {slug: version_number} for server-side mods declared in the pack."""
    mods = {}
    mods_dir = pack_root / "mods"
    if mods_dir.exists():
        for f in mods_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("side") in ("server", "both"):
                    mods[data["slug"]] = data.get("version_number", "?")
            except Exception:
                pass
    return mods


def _required_java_major(jar_path):
    """Infer required Java major from class file versions inside a jar."""
    max_class_major = None
    try:
        with zipfile.ZipFile(jar_path) as jar:
            for name in jar.namelist():
                if not name.endswith(".class"):
                    continue
                with jar.open(name) as f:
                    header = f.read(8)
                if len(header) < 8 or header[:4] != b"\xca\xfe\xba\xbe":
                    continue
                class_major = int.from_bytes(header[6:8], "big")
                if max_class_major is None or class_major > max_class_major:
                    max_class_major = class_major
    except Exception:
        return None

    if max_class_major is None:
        return None

    return max_class_major - 44


def _required_java_major_from_minecraft_version(mc_version):
    """Resolve required Java major from Mojang version metadata."""
    if not mc_version:
        return None

    manifest_urls = [
        "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
        "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json",
    ]

    for manifest_url in manifest_urls:
        try:
            req = Request(manifest_url, headers={"User-Agent": "azalea/0.1"})
            with urlopen(req) as r:
                manifest = json.loads(r.read().decode())

            versions = manifest.get("versions", [])
            entry = next((v for v in versions if str(v.get("id")) == str(mc_version)), None)
            if not entry or not entry.get("url"):
                continue

            req2 = Request(entry["url"], headers={"User-Agent": "azalea/0.1"})
            with urlopen(req2) as r:
                version_meta = json.loads(r.read().decode())

            java_version = version_meta.get("javaVersion", {})
            major = java_version.get("majorVersion")
            if isinstance(major, int):
                return major
        except Exception:
            continue

    return None


def _current_java_major(java_bin):
    """Return installed Java major version for the selected java executable."""
    try:
        proc = subprocess.run([java_bin, "-version"], capture_output=True, text=True, check=False)
    except Exception:
        return None

    output = (proc.stderr or "") + "\n" + (proc.stdout or "")
    m = re.search(r'"([0-9][0-9._+]*)"', output)
    if not m:
        return None

    v = m.group(1)
    first = v.split(".")[0]
    if first == "1":
        parts = v.split(".")
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1])
        return None
    if first.isdigit():
        return int(first)
    return None


_DEFAULT_RUN = {
    "ram": "4G",
    "java_bin": "java",
    "jvm_args": [],
    "game_args": ["nogui"],
    "jar_name": "server.jar",
}


def _apply_overrides(pack_root, server_dir):
    """Copy pack overrides/ (shared) then server/ (server-specific) into server_dir."""
    for src_name in ("overrides", "server"):
        src = pack_root / src_name
        if src.exists():
            for file in src.rglob("*"):
                if file.is_file():
                    rel = file.relative_to(src)
                    dest = server_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, dest)


def _ensure_fabric_api(mod_versions, mods_dir, mc, loader):
    """Ensure a compatible Fabric API is present in the server mods directory."""
    if "fabric-api" in mod_versions:
        return

    log_info("Fabric API missing from pack mods; installing it for server compatibility")
    try:
        project = http_json(f"{API}/project/fabric-api")
    except Exception as e:
        log_err(f"Failed to resolve fabric-api project: {e}")
        sys.exit(1)

    version = find_best_version(project["id"], mc, loader)
    if not version:
        log_err(f"No compatible fabric-api version for Minecraft {mc} / {loader}")
        sys.exit(1)

    if not download_content(version["id"], mods_dir):
        log_err("Failed to download required fabric-api")
        sys.exit(1)

    mod_versions["fabric-api"] = version.get("version_number", "?")


def _build(pack_root, source, installed_tag, accept_eula):
    """Core build: download mods + jar, apply overrides, write server config."""
    cfg_path = pack_root / "azalea.json"
    if not cfg_path.exists():
        log_err("azalea.json not found in source")
        sys.exit(1)
    cfg = json.loads(cfg_path.read_text())
    mc = cfg["minecraft_version"]
    loader = cfg["loader"]
    loader_version = cfg["loader_version"]

    log_info(f"MC {mc}  ·  {loader} {loader_version}")

    server_dir = Path(".")
    server_dir.mkdir(parents=True, exist_ok=True)
    mods_dir = server_dir / "mods"
    if mods_dir.exists():
        shutil.rmtree(mods_dir)
    mods_dir.mkdir()

    # Download server-side mods
    mod_versions = {}
    mods_src = pack_root / "mods"
    if mods_src.exists():
        for f in mods_src.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("side") not in ("server", "both"):
                    continue
                if download_content(data["version_id"], mods_dir):
                    mod_versions[data["slug"]] = data.get("version_number", "?")
            except Exception as e:
                log_warn(f"Skipped {f.stem}: {e}")

    _ensure_fabric_api(mod_versions, mods_dir, mc, loader)
    log_ok(f"Downloaded {len(mod_versions)} server mods")

    # Download server jar (Fabric only for now)
    if loader != "fabric":
        log_err(f"Server build currently only supports Fabric (loader: {loader})")
        sys.exit(1)

    installer_version = get_latest_fabric_installer_version()
    if not installer_version:
        log_err("Could not resolve Fabric installer version")
        sys.exit(1)

    fabric_url = (
        f"https://meta.fabricmc.net/v2/versions/loader"
        f"/{mc}/{loader_version}/{installer_version}/server/jar"
    )
    spinner(f"Downloading Fabric {loader_version} server jar")
    if not download_file(fabric_url, server_dir / "server.jar"):
        log_err("Failed to download server jar")
        sys.exit(1)
    log_ok("Downloaded server.jar")

    # Overrides from pack
    _apply_overrides(pack_root, server_dir)

    # EULA
    if accept_eula:
        (server_dir / "eula.txt").write_text("eula=true\n")
        log_info("eula.txt written (EULA accepted)")

    # Preserve existing run config so user edits survive updates
    existing_run = {}
    existing_server_config_path = server_dir / SERVER_CONFIG_FILE
    if existing_server_config_path.exists():
        try:
            existing_run = json.loads(existing_server_config_path.read_text()).get("run", {})
        except Exception:
            pass

    # Server config file
    server_config = {
        "source": source,
        "pinned_tag": None,
        "installed_tag": installed_tag,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "pack": {
            "name": cfg.get("name", ""),
            "version": cfg.get("version", ""),
            "minecraft_version": mc,
            "loader": loader,
            "loader_version": loader_version,
        },
        "mods": mod_versions,
        "run": existing_run if existing_run else dict(_DEFAULT_RUN),
    }
    save_json(server_dir / SERVER_CONFIG_FILE, server_config)
    log_ok(f"Server built → {server_dir}")


# ---------------------------------------------------------------------------
# Public commands
# ---------------------------------------------------------------------------


def server_init(source, accept_eula=False):
    """Build a server from a GitHub URL or local pack directory."""
    s_type, s_data = _parse_source(source)

    # Normalize stored source: strip @tag from URL, tag goes into pinned_tag if specified
    if s_type == "github":
        stored_source = f"https://github.com/{s_data['owner']}/{s_data['repo']}"
        url_tag = s_data.get("tag")
    else:
        stored_source = str(s_data["path"])
        url_tag = None

    with tempfile.TemporaryDirectory() as tmp:
        if s_type == "github":
            pack_root, release_tag = _download_pack_github(
                s_data["owner"], s_data["repo"], url_tag, tmp
            )
        else:
            pack_root = s_data["path"]
            release_tag = None

        _build(pack_root, stored_source, release_tag, accept_eula)

    # Auto-pin when a specific tag was given in the URL
    if url_tag:
        server_config_path = Path(".") / SERVER_CONFIG_FILE
        server_config = json.loads(server_config_path.read_text())
        server_config["pinned_tag"] = url_tag
        save_json(server_config_path, server_config)
        log_info(f"Pinned to {url_tag}")


def server_update():
    """Re-build the server using the stored source (respects pinned_tag)."""
    server_config = _load_server_config()
    source = server_config["source"]
    pinned_tag = server_config.get("pinned_tag")

    s_type, s_data = _parse_source(source)
    if pinned_tag:
        s_data["tag"] = pinned_tag

    with tempfile.TemporaryDirectory() as tmp:
        if s_type == "github":
            pack_root, release_tag = _download_pack_github(
                s_data["owner"], s_data["repo"], s_data.get("tag"), tmp
            )
        else:
            pack_root = s_data["path"]
            release_tag = None

        if release_tag and release_tag == server_config.get("installed_tag"):
            log_ok(f"Already on latest ({release_tag})")
            return

        _build(pack_root, source, release_tag, accept_eula=False)

    # Restore pinned_tag (overwritten by _build)
    if pinned_tag:
        server_config_path = Path(".") / SERVER_CONFIG_FILE
        updated_server_config = json.loads(server_config_path.read_text())
        updated_server_config["pinned_tag"] = pinned_tag
        save_json(server_config_path, updated_server_config)


def server_diff():
    """Preview what server_update would change, without applying it."""
    server_config = _load_server_config()
    source = server_config["source"]
    pinned_tag = server_config.get("pinned_tag")

    s_type, s_data = _parse_source(source)
    if pinned_tag:
        s_data["tag"] = pinned_tag

    with tempfile.TemporaryDirectory() as tmp:
        if s_type == "github":
            pack_root, release_tag = _download_pack_github(
                s_data["owner"], s_data["repo"], s_data.get("tag"), tmp
            )
        else:
            pack_root = s_data["path"]
            release_tag = None

        cfg_path = pack_root / "azalea.json"
        if not cfg_path.exists():
            log_err("azalea.json not found in source")
            return
        new_cfg = json.loads(cfg_path.read_text())
        new_mods = _collect_server_mods(pack_root)

    cur = server_config.get("pack", {})
    cur_mods = server_config.get("mods", {})

    print()
    any_change = False

    def _row(label, old, new):
        nonlocal any_change
        if old != new:
            print(
                f"  {Log.BOLD}{label:<10}{Log.RESET} "
                f"{Log.YELLOW}{old}{Log.RESET} → {Log.GREEN}{new}{Log.RESET}"
            )
            any_change = True

    if release_tag:
        _row("Tag", server_config.get("installed_tag", "?"), release_tag)
    _row("Pack", cur.get("version", "?"), new_cfg.get("version", "?"))
    _row("MC", cur.get("minecraft_version", "?"), new_cfg.get("minecraft_version", "?"))
    _row("Loader", cur.get("loader_version", "?"), new_cfg.get("loader_version", "?"))

    added = set(new_mods) - set(cur_mods)
    removed = set(cur_mods) - set(new_mods)
    changed = {s for s in new_mods if s in cur_mods and new_mods[s] != cur_mods[s]}

    for slug in sorted(added):
        print(f"  {Log.GREEN}+ {slug} {new_mods[slug]}{Log.RESET}")
        any_change = True
    for slug in sorted(removed):
        print(f"  {Log.RED}- {slug}{Log.RESET}")
        any_change = True
    for slug in sorted(changed):
        print(f"  {Log.CYAN}~ {slug}  {cur_mods[slug]} → {new_mods[slug]}{Log.RESET}")
        any_change = True

    if not any_change:
        log_ok("Already up to date")
    print()


def server_status():
    """Show current server config."""
    server_config = _load_server_config()
    pack = server_config.get("pack", {})
    pinned = server_config.get("pinned_tag")

    tag_str = server_config.get("installed_tag") or "local"
    if pinned:
        tag_str += f"  {Log.YELLOW}(pinned at {pinned}){Log.RESET}"

    server_dir = Path(".")
    jar_ok = (server_dir / "server.jar").exists()
    jar_str = "present" if jar_ok else f"{Log.YELLOW}missing{Log.RESET}"

    print()
    print(
        f"  {Log.BOLD}{Log.CYAN}{pack.get('name', '(unnamed)')}{Log.RESET}"
        f"  v{pack.get('version', '?')}"
    )
    print(f"  {'Source':<10}: {server_config.get('source', '?')}")
    print(f"  {'Tag':<10}: {tag_str}")
    print(f"  {'MC':<10}: {pack.get('minecraft_version', '?')}")
    print(f"  {'Loader':<10}: {pack.get('loader', '?')} {pack.get('loader_version', '?')}")
    print(f"  {'Mods':<10}: {len(server_config.get('mods', {}))} server mods")
    print(f"  {'Built':<10}: {server_config.get('installed_at', '?')}")
    print(f"  {'Jar':<10}: {jar_str}")
    print()


def server_run():
    """Start the Minecraft server."""
    server_dir = Path(".")
    server_config = _load_server_config()
    run = {**_DEFAULT_RUN, **server_config.get("run", {})}

    jar = server_dir / run["jar_name"]
    if not jar.exists():
        log_err(f"{run['jar_name']} not found — run `azalea server build` first")
        sys.exit(1)

    ram = run["ram"]
    java_bin = run["java_bin"]
    jvm_args = run["jvm_args"] if isinstance(run["jvm_args"], list) else run["jvm_args"].split()
    game_args = run["game_args"] if isinstance(run["game_args"], list) else run["game_args"].split()

    pack = server_config.get("pack", {})
    required_java = _required_java_major_from_minecraft_version(pack.get("minecraft_version"))
    required_source = "minecraft metadata"
    if required_java is None:
        required_java = _required_java_major(jar)
        required_source = "jar scan"

    current_java = _current_java_major(java_bin)

    log_info(
        "Current Java version: "
        f"{current_java if current_java is not None else 'unknown'}, "
        f"Required: {required_java if required_java is not None else 'unknown'} ({required_source})"
    )

    if required_java is not None and current_java is not None and current_java < required_java:
        log_err(
            f"Java {required_java}+ is required for {run['jar_name']} (found Java {current_java})"
        )
        sys.exit(1)
    elif required_java is None:
        log_warn("Could not detect required Java version from server.jar; starting anyway")
    elif current_java is None:
        log_warn("Could not detect current Java version; starting anyway")

    cmd = [java_bin, f"-Xms{ram}", f"-Xmx{ram}"] + jvm_args + ["-jar", run["jar_name"]] + game_args
    log_info(f"Starting {server_config.get('pack', {}).get('name', 'server')}…")
    log_info(" ".join(cmd))
    subprocess.run(cmd, cwd=server_dir)


def server_logs(lines=50):
    """Tail the server log."""
    server_dir = Path(".")
    _load_server_config()  # validate it's a server dir

    log_file = server_dir / "logs" / "latest.log"
    if not log_file.exists():
        log_warn("logs/latest.log not found — server may not have run yet")
        return

    try:
        subprocess.run(["tail", "-f", "-n", str(lines), str(log_file)])
    except KeyboardInterrupt:
        pass


def server_pin(tag):
    """Pin the server to a specific release tag."""
    server_config = _load_server_config()
    server_config["pinned_tag"] = tag
    save_json(Path(".") / SERVER_CONFIG_FILE, server_config)
    log_ok(f"Pinned to {tag}  (run `azalea server update` to apply)")


def server_unpin():
    """Remove the release pin — update will use the latest release."""
    server_config = _load_server_config()
    if not server_config.get("pinned_tag"):
        log_info("Not pinned")
        return
    old = server_config.pop("pinned_tag")
    save_json(Path(".") / SERVER_CONFIG_FILE, server_config)
    log_ok(f"Unpinned (was {old}) — will track latest release")
