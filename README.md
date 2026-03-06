<div align="center">

# ✿ azalea

**A minimal CLI for managing Minecraft modpacks - powered by Modrinth**

[![Python](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
[![pipx](https://img.shields.io/badge/install-pipx-0ea5e9?style=flat-square)](https://pipx.pypa.io)
[![Modrinth](https://img.shields.io/badge/modrinth-api-1bd96a?logo=modrinth&logoColor=white&style=flat-square)](https://modrinth.com)

</div>

<img src="https://github.com/matejstastny/azalea/blob/main/assets/repo-icon.png?raw=true" alt="Azalea icon" width="20%" align="right">

## Features

- Search and install mods, resource packs, and shaders directly from Modrinth
- Automatic dependency installation and uninstallation
- Check modpack compatibility before upgrading Minecraft
- Upgrade to a new Minecraft version with a single command
- Export to `.mrpack` for use with any Modrinth-compatible launcher
- Auto-generate mod tables in your project `README`
- Supports Fabric, Quilt, NeoForge, and Forge
- Pin mods to prevent them from being updated

## Install

```bash
pipx install git+https://github.com/matejstastny/azalea.git
```

## Quick start

```bash
azalea init              # create azalea.json in the current directory
azalea add sodium        # install a mod by slug or search term
azalea export            # build a .mrpack archive in dist/
```

## Commands

| Command | Description |
|---------|-------------|
| `azalea init` | Interactively initialise a new pack (name, author, MC version, loader) |
| `azalea add <slug>` | Add a mod, resource pack, or shader from Modrinth |
| `azalea add -f <file>` | Batch install from a text file (one slug per line) |
| `azalea remove <slug>` | Remove a mod and prune unused dependencies |
| `azalea remove -f <file>` | Batch remove mods listed in a file |
| `azalea search <query>` | Search Modrinth and display results |
| `azalea info <slug>` | Show details of an installed mod (version, side, dependencies, pin status) |
| `azalea pin <slug>` | Lock a mod to its current version — skipped during `update` |
| `azalea unpin <slug>` | Remove a pin so the mod is updated normally again |
| `azalea update` | Update all installed content to the latest compatible versions |
| `azalea upgrade [mc]` | Upgrade the pack to a new Minecraft version |
| `azalea check [mc]` | Check mod compatibility (defaults to current pack version) |
| `azalea export` | Export a `.mrpack` archive to `dist/` |
| `azalea readme` | Regenerate the mod table in your project `README.md` |

<details>
<summary>File format</summary>

**`azalea.json`** — pack manifest stored in the project root:
```json
{
  "name": "My Pack",
  "author": "you",
  "version": "1.0.0",
  "license": "MIT",
  "minecraft_version": "1.21.4",
  "loader": "fabric",
  "loader_version": "0.16.10"
}
```

**`mods/<slug>.json`** — one file per installed project:
```json
{
  "project_id": "AANobbMI",
  "slug": "sodium",
  "version_id": "mc1.21.4-0.6.5-fabric",
  "version_number": "mc1.21.4-0.6.5+build.1",
  "side": "client",
  "file": {
    "url": "https://cdn.modrinth.com/...",
    "filename": "sodium-fabric-0.6.5+mc1.21.4.jar",
    "sha512": "...",
    "sha1": "...",
    "size": 1234567
  },
  "explicit": true,
  "pinned": false,
  "dependencies": []
}
```

The same structure is used for resource packs (`resourcepacks/`) and shaders (`shaderpacks/`).
</details>

<div align="center">
<sub>Used by: <a href="https://github.com/matejstastny/starlight">Starlight</a> <a href="https://github.com/matejstastny/velarium">Velarium</a></sub>
</div>
