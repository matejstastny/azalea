# Azalea — Claude Reference

## Project
Python Minecraft modpack manager, installable via `pipx`. Entry point: `azalea.cli:main`.

## Formatting
Run `ruff format src/` after every Python file change.

## Package structure
```
src/azalea/
├── __init__.py      empty
├── cli.py           main() + argparse dispatch only
├── config.py        path constants (BASE, CONFIG, MODS, RESOURCEPACKS, SHADERPACKS, OVERRIDES) + API URL
├── log.py           Log class, log_* functions, spinner, clear_lines, print_version
├── util.py          http_json, load_config, save_json, ensure_overrides_dir, safe_name
├── minecraft.py     mc_version_matches, get_release_versions, resolve_target_mc, get_latest_release_version, get_latest_fabric_loader
├── modrinth.py      search_projects, resolve_project, find_best_version
└── commands.py      all command implementations: init, install_mod, install_from_file, prune_unused_deps, remove_mod, check, export, upgrade, update_all, readme
```

## Import DAG (no circular imports)
```
config      ← stdlib only
log         ← stdlib only
util        ← config
minecraft   ← config, log, util
modrinth    ← config, log, util, minecraft
commands    ← config, log, util, minecraft, modrinth
cli         ← log, commands
```

## Tooling
- Formatter: `ruff` (v0.15.4), configured in `pyproject.toml` — line-length 100, double quotes, space indent
- Build: `setuptools`, packages found under `src/`
- Python ≥ 3.9, target-version py310
- Installed via `pipx` for local development

## Testing commands
```bash
PYTHONPATH=src python3 -c "from azalea import config, log, util, minecraft, modrinth, commands"
PYTHONPATH=src python3 -m azalea.cli --help
PYTHONPATH=src python3 -m azalea.cli --version
```
