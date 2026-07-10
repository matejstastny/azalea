#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")/.." &>/dev/null && pwd 2>/dev/null)"

if ! command -v azalea &>/dev/null; then
	echo "Azalea not installed!"
	exit 1
fi

echo "==> Removing old test modpack..."
rm -rf "$ROOT_DIR/modpack-test"

echo "==> Creating temp dir..."
mkdir -p "$ROOT_DIR/modpack-test"
cd "$ROOT_DIR/modpack-test"

echo "==> Initing using azalea..."
azalea init --mc 1.21.1

echo "==> Installing sodium as client mod test..."
azalea add sodium

echo "==> Installing xaero as dependency mod test..."
azalea add xaeros-minimap

echo "==> Installing lithium as server mod test..."
azalea add lithium

echo "Done!"
