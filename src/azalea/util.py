"""HTTP helpers, config I/O, and filesystem utilities."""

import json
import sys
from urllib.request import Request, urlopen

from azalea.config import CONFIG, OVERRIDES


def http_json(url):
    req = Request(url, headers={"User-Agent": "azalea/0.1"})
    with urlopen(req) as r:
        return json.loads(r.read().decode())


def ensure_overrides_dir():
    OVERRIDES.mkdir(exist_ok=True)


def load_config():
    if not CONFIG.exists():
        sys.exit("Not an Azalea pack. Run `azalea init`")
    return json.loads(CONFIG.read_text())


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def safe_name(s):
    """Make a filesystem-safe name."""
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ."
    cleaned = "".join(c if c in keep else "-" for c in s)
    return "-".join(cleaned.strip().split())
