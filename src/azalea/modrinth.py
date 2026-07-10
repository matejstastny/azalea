"""Modrinth API: project search, resolution, and version finding."""

import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from azalea.config import API, MODS
from azalea.log import Log, clear_lines, log_err, log_info, log_ok, log_warn, spinning
from azalea.minecraft import mc_version_matches
from azalea.util import http_json

# Maps installed mod slugs → the Modrinth loader name they provide for shaders.
# Only loaders whose corresponding mod is actually installed will be accepted.
_SHADER_LOADER_MODS = {
    "iris": "iris",
    "oculus": "iris",  # Forge port of Iris, exposes the same "iris" loader tag
    "optifabric": "optifine",
}


def _installed_shader_loaders() -> set:
    """Return the set of shader loader names present in the pack's mods/ directory."""
    active = set()
    for slug, loader_name in _SHADER_LOADER_MODS.items():
        if (MODS / f"{slug}.json").exists():
            active.add(loader_name)
    return active


def search_projects(query):
    """Search Modrinth and interactively ask the user to choose."""
    facets = quote(
        '[["project_type:mod","project_type:resourcepack","project_type:shader","project_type:datapack"]]'
    )
    with spinning("Searching Modrinth"):
        data = http_json(f"{API}/search?query={quote(query)}&limit=10&facets={facets}")
    hits = data.get("hits", [])

    if not hits:
        log_warn("No matching projects found")
        return None

    log_info("Select a project:")
    printed_lines = 1
    for i, h in enumerate(hits, 1):
        title = h.get("title") or h.get("slug")
        desc = (h.get("description", "") or "")[:80]
        downloads = h.get("downloads", 0)
        print(f"  {Log.BOLD}{i}){Log.RESET} {Log.CYAN}{title}{Log.RESET}")
        printed_lines += 1
        if desc:
            print(f"     {desc}")
            printed_lines += 1
        print(f"     {Log.GREEN}{downloads:,} downloads{Log.RESET}")
        printed_lines += 1

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
    versions = http_json(f"{API}/project/{project_id}/version")
    shader_loaders = _installed_shader_loaders()
    matches = [
        v
        for v in versions
        if mc_version_matches(mc, v.get("game_versions", []))
        and (
            not v.get("loaders")
            or loader in v.get("loaders", [])
            or "minecraft" in v.get("loaders", [])
            or "datapack" in v.get("loaders", [])
            or bool(shader_loaders & set(v.get("loaders", [])))
        )
    ]
    if not matches:
        return None
    return matches[0]


def download_content(version_id, directory):
    """Download a mod/resourcepack/shader from Modrinth and save it."""
    data = http_json(f"{API}/version/{version_id}")
    files = data.get("files", [])

    if not files:
        log_warn("No files found in version")
        return None

    f = next((item for item in files if item.get("primary")), files[0])
    filename = f.get("filename") or f"{version_id}.bin"
    url = f.get("url")

    if url:
        try:
            with spinning(f"Downloading {filename}"):
                with urlopen(url) as response:
                    content = response.read()

            directory.mkdir(parents=True, exist_ok=True)
            save_path = directory / filename
            save_path.write_bytes(content)
            log_ok(f"Downloaded: {filename}")
            return str(save_path)
        except HTTPError as e:
            log_err(f"Download failed: HTTP {e.code}")
            return None
        except Exception as e:
            log_err(f"Download failed: {e}")
            return None

    log_warn("Download URL not found")
    return None
