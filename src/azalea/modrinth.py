"""Modrinth API: project search, resolution, and version finding."""

import sys
from urllib.error import HTTPError
from urllib.parse import quote

from azalea.config import API
from azalea.log import Log, clear_lines, log_err, log_info, log_ok, log_warn, spinner
from azalea.minecraft import mc_version_matches
from azalea.util import http_json


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
                loader in v.get("loaders", []) for loader in ("iris", "optifine")
            )  # todo: better shader handeling
        )
    ]
    if not matches:
        return None
    return matches[0]
