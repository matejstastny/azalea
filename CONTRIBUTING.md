# Contributing

## Setup

You need Python 3.10+ and a virtual environment. There are two ways to get going:

**With [`uv`](https://docs.astral.sh/uv/):**
```bash
uv venv
uv pip install -e ".[dev]"
```

**With plain pip:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install the pre-commit hooks so ruff runs automatically before every commit:
```bash
pre-commit install
```

## Making changes

After setup, `azalea` points at your local source. The fastest way to test a change is to run the affected command against a real or throw-away pack:

```bash
mkdir /tmp/test-pack && cd /tmp/test-pack
azalea init
azalea add sodium
azalea list
```

## Running checks

```bash
ruff check .        # lint
ruff format .       # format
mypy src/azalea     # type check
```

Or run all at once via pre-commit:
```bash
pre-commit run --all-files
```

CI runs the same checks on every push that touches `src/` or `pyproject.toml`.

## Project layout

```
src/azalea/
  cli.py        # argument parsing and dispatch only
  commands.py   # all pack command implementations
  modrinth.py   # Modrinth API calls
  minecraft.py  # MC version + loader resolution
  server.py     # server build/run/update commands
  config.py     # path constants and API base URL
  util.py       # http_json, load_config, save_json, helpers
  log.py        # coloured output, spinning context manager
```

`azalea` has no third-party runtime dependencies — only the Python standard library. Keep it that way.

## Pull requests

- Keep changes focused; one concern per PR
- Run `pre-commit run --all-files` and `mypy src/azalea` before opening a PR
- Describe *why* in the PR body, not just *what*
