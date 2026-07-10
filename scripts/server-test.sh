#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")/.." &>/dev/null && pwd 2>/dev/null)"

echo "==> Making temp modpack:"
bash "$ROOT_DIR/scripts/client-test.sh"

echo "==> Removing old test server modpack..."
rm -rf "$ROOT_DIR/server-test" || true

echo "==> Creating temp dir..."
mkdir -p "$ROOT_DIR/server-test"
cd "$ROOT_DIR/server-test"

echo "==> Initializing server test modpack..."
azalea server init ../modpack-test
