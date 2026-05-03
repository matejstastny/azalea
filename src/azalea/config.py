# --------------------------------------------------------------------------------------------
# azalea - A Python Minecraft Modpack manager
# --------------------------------------------------------------------------------------------
# Author: Matej Stastny
# Date: 2026-02-14 (YYYY-MM-DD)
# License: MIT
# Link: https://github.com/matejstastny/azalea
# --------------------------------------------------------------------------------------------

from pathlib import Path

BASE = Path(".")
CONFIG = BASE / "azalea.json"
MODS = BASE / "mods"
RESOURCEPACKS = BASE / "resourcepacks"
SHADERPACKS = BASE / "shaderpacks"
BASE_OVERRIDES = BASE / "overrides"
CLIENT_OVERRIDES = BASE_OVERRIDES / "client"
SERVER_OVERRIDES = BASE_OVERRIDES / "server"
SHARED_OVERRIDES = BASE_OVERRIDES / "shared"
PRESETS_OVERRIDES = BASE_OVERRIDES / "presets"

API = "https://api.modrinth.com/v2"
