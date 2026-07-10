"""HTTP helpers, config I/O, and filesystem utilities."""

import json
import sys
from urllib.request import Request, urlopen

from azalea.config import CLIENT_OVERRIDES, CONFIG, SERVER_OVERRIDES, SHARED_OVERRIDES
from azalea.log import log_err


def http_json(url):
    req = Request(url, headers={"User-Agent": "azalea/0.1"})
    with urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def ensure_pack_dirs():
    SHARED_OVERRIDES.mkdir(parents=True, exist_ok=True)
    CLIENT_OVERRIDES.mkdir(parents=True, exist_ok=True)
    SERVER_OVERRIDES.mkdir(parents=True, exist_ok=True)


def load_config():
    if not CONFIG.exists():
        log_err("Not an Azalea pack. Run `azalea init`")
        sys.exit(1)
    return json.loads(CONFIG.read_text())


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def safe_name(s):
    """Make a filesystem-safe name."""
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ."
    cleaned = "".join(c if c in keep else "-" for c in s)
    return "-".join(cleaned.strip().split())


def download_file(url, save_path):
    """Download a file from a URL and save it."""
    try:
        with urlopen(url) as response:
            content = response.read()
        save_path.write_bytes(content)
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False
