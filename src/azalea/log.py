"""Logging utilities, spinner, and version display."""

import sys
import time
import platform

from importlib.metadata import version, PackageNotFoundError


class Log:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    PURPLE = "\033[0;35m"


def log_info(msg):
    print(f"{Log.CYAN} {msg}{Log.RESET}")


def log_ok(msg):
    print(f"{Log.GREEN} {msg}{Log.RESET}")


def log_warn(msg):
    print(f"{Log.YELLOW} {msg}{Log.RESET}")


def log_err(msg):
    print(f"{Log.RED} {msg}{Log.RESET}")


def log_deb(msg):
    print(f"{Log.PURPLE}󰨰 {msg}{Log.RESET}")


def clear_lines(n):
    for _ in range(n):
        sys.stdout.write("\033[1A")
        sys.stdout.write("\033[2K")
    sys.stdout.flush()


def spinner(msg, duration=0.6):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    end = time.time() + duration
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r{Log.BLUE}{frames[i % len(frames)]} {msg}{Log.RESET}")
        sys.stdout.flush()
        time.sleep(0.05)
        i += 1
    sys.stdout.write("\r")
    sys.stdout.write("\033[2K")
    print(f"{Log.BLUE}󱗾 {msg}{Log.RESET}")


def get_version() -> str:
    try:
        return version("azalea")
    except PackageNotFoundError:
        return "unknown"


def print_version():
    title = f"{Log.BOLD}{Log.CYAN}Azalea CLI ✿{Log.RESET}"
    v = f"{Log.GREEN}{get_version()}{Log.RESET}"
    py = f"{Log.YELLOW}{platform.python_version()}{Log.RESET}"
    plat = f"{Log.BLUE}{platform.system()}-{platform.machine()}{Log.RESET}"
    url = f"{Log.CYAN}https://github.com/matejstastny/azalea{Log.RESET}"

    block = (
        f"{title}\n"
        f"{Log.BOLD}Version   {Log.RESET}: {v}\n"
        f"{Log.BOLD}Python    {Log.RESET}: {py}\n"
        f"{Log.BOLD}Platform  {Log.RESET}: {plat}\n"
        f"{Log.BOLD}Project   {Log.RESET}: {url}"
    )

    print(block)
    raise SystemExit(0)
