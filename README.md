<div align="center">

# ✿ azalea

**A minimal CLI for managing Minecraft modpacks - powered by Modrinth**

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
[![pipx](https://img.shields.io/badge/install-pipx-0ea5e9?style=flat-square)](https://pipx.pypa.io)
[![Modrinth](https://img.shields.io/badge/modrinth-api-1bd96a?logo=modrinth&logoColor=white&style=flat-square)](https://modrinth.com)

</div>

<img src="https://github.com/matejstastny/azalea/blob/main/assets/icon.png?raw=true" alt="Azalea icon" width="20%" align="right">

## Features

- Search and install mods, resource packs, and shaders directly from Modrinth
- Automatic dependency installation and uninstallation
- Check modpack compatibility before upgrading Minecraft
- Upgrade to a new Minecraft version with a single command
- Export to `.mrpack` for use with any Modrinth-compatible launcher
- Auto-generate mod tables in your project `README`
- Build and run a Minecraft server directly from a pack source

## Install

```bash
pipx install git+https://github.com/matejstastny/azalea.git
```

## Quick start

```bash
azalea init                                      # interactive setup
azalea init --yes                                # non-interactive, all defaults
azalea init --mc 1.21.1 --loader neoforge        # non-interactive, specific values
azalea add sodium                                # install a mod by slug or search term
azalea list                                      # show all installed content
azalea export                                    # build a .mrpack archive in dist/
```

## Commands

| Command | Description |
|---------|-------------|
| `azalea init` | Initialise a new pack interactively |
| `azalea init --yes` | Non-interactive init with defaults (`--mc`, `--loader`, `--name`, `--author`, `--pack-version`, `--license` to override) |
| `azalea list` | List all installed mods, resource packs, and shaders |
| `azalea add <slug>` | Add a mod, resource pack, or shader from Modrinth |
| `azalea add -f <file>` | Batch install from a text file (one slug per line) |
| `azalea remove <slug>` | Remove a mod and prune unused dependencies |
| `azalea remove -f <file>` | Batch remove from a text file (one slug per line) |
| `azalea search <query>` | Browse Modrinth without installing |
| `azalea info <slug>` | Show details of an installed mod |
| `azalea pin <slug>` | Lock a mod to its current version (skip during updates) |
| `azalea unpin <slug>` | Remove a version lock |
| `azalea update` | Update all installed content to the latest compatible versions |
| `azalea update -f` | Force re-fetch metadata even if already on latest |
| `azalea upgrade [mc]` | Upgrade the pack to a new Minecraft version |
| `azalea check [mc]` | Check compatibility of all mods against a target MC version |
| `azalea export` | Export a `.mrpack` archive to `dist/` |
| `azalea export --client` | Export client-only content (skips server-side mods) |
| `azalea readme` | Regenerate the mod table in your project `README.md` |
| `azalea prism` | Export the pack and open it in Prism Launcher |
| `azalea prism --client` | Export client-only and open in Prism Launcher |

## Server

`azalea server` builds and manages a Fabric server from any Azalea pack hosted on GitHub (or a local path). It downloads server-side mods, installs the Fabric server jar, and applies your pack's overrides automatically.

```bash
# Build a server from a GitHub release
azalea server init https://github.com/you/your-pack

# Pin to a specific release tag
azalea server init https://github.com/you/your-pack@v1.2.0

# Start, update, and inspect
azalea server run
azalea server update
azalea server diff       # preview changes before applying
azalea server info       # show version, mods, server IP
azalea server logs       # tail logs/latest.log
```

| Command | Description |
|---------|-------------|
| `azalea server init <source>` | Build a server from a GitHub URL or local pack path |
| `azalea server update` | Rebuild the server from its stored source |
| `azalea server diff` | Preview what `update` would change |
| `azalea server run` | Start the Minecraft server |
| `azalea server info` | Show current config, mod count, and LAN address |
| `azalea server logs [-n N]` | Tail `logs/latest.log` (default: last 50 lines) |
| `azalea server pin <tag>` | Lock the server to a specific release tag |
| `azalea server unpin` | Remove the pin and track the latest release |

The source URL accepts an optional `@tag` suffix to pin on first install. Run config (RAM, JVM flags, game args) is stored in `azalea-server.json` and survives updates.

You can add a `"post_build"` field to the `run` section to run a shell script at the end of every `init` and `update`. Useful for copying extra files, restarting a service, or sending a notification:

```json
"run": {
  "post_build": "./post-build.sh"
}
```

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
    "sha1": "..."
  },
  "explicit": true,
  "dependencies": []
}
```

The same structure is used for resource packs (`resourcepacks/`) and shaders (`shaderpacks/`).

**`azalea-server.json`** — written by `azalea server init`, stores source info and run config:
```json
{
  "source": "https://github.com/you/your-pack",
  "pinned_tag": null,
  "installed_tag": "v1.2.0",
  "pack": { "name": "My Pack", "minecraft_version": "1.21.4", "loader": "fabric", "loader_version": "0.16.10" },
  "mods": { "sodium": "mc1.21.4-0.6.5-fabric" },
  "run": {
    "ram": "4G",
    "java_bin": "java",
    "jvm_args": [],
    "game_args": ["nogui"],
    "jar_name": "server.jar",
    "post_build": "./post-build.sh"
  }
}
```

</details>

<div align="center">
<sub>Used by: <a href="https://github.com/matejstastny/starlight">Starlight</a> <a href="https://github.com/matejstastny/velarium">Velarium</a></sub>
</div>
