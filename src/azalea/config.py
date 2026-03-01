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
OVERRIDES = BASE / "overrides"

API = "https://api.modrinth.com/v2"
