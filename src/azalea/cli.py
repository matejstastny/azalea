"""Azalea CLI entry point — argument parsing and dispatch only."""

import argparse
import sys

from azalea.log import log_err, print_version
from azalea.commands import (
    init,
    install_mod,
    install_from_file,
    remove_mod,
    check,
    export,
    readme,
    update_all,
    upgrade,
)


def main():
    p = argparse.ArgumentParser(prog="azalea")
    sub = p.add_subparsers(dest="cmd")

    p.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version information and exit",
    )

    sub.add_parser("init")

    a = sub.add_parser("add", help="Add a Modrinth mod")
    a.add_argument("mod", nargs="?", help="Mod name or slug")
    a.add_argument(
        "-f",
        "--file",
        help="Install mods from file (one per line)",
    )

    r = sub.add_parser("remove", help="Remove Modrinth mod")
    r.add_argument("slug", help="Mod slug")

    c = sub.add_parser(
        "check", help="Check if the modpack is compatible with a Minecraft version"
    )
    c.add_argument("mc", help="Target Minecraft version")

    sub.add_parser("export", help="Export a .mrpack to dist/")
    sub.add_parser("readme", help="Update README.md mod table")
    upd = sub.add_parser("update", help="Update all installed content to latest versions")
    upd.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force refresh metadata even if already on latest version",
    )

    u = sub.add_parser(
        "upgrade",
        help="Upgrade the modpack to latest or specified Minecraft version",
    )
    u.add_argument(
        "mc",
        nargs="?",
        help="Target Minecraft version (defaults to latest release)",
    )

    args = p.parse_args()

    try:
        if args.version:
            print_version()
        elif args.cmd == "init":
            init()
        elif args.cmd == "add":
            if args.file:
                install_from_file(args.file)
            elif args.mod:
                install_mod(args.mod)
            else:
                log_err("Provide a mod slug or use -f <file>")
                sys.exit(1)
        elif args.cmd == "remove":
            remove_mod(args.slug)
        elif args.cmd == "check":
            check(args.mc)
        elif args.cmd == "export":
            export()
        elif args.cmd == "readme":
            readme()
        elif args.cmd == "update":
            update_all(force=getattr(args, "force", False))
        elif args.cmd == "upgrade":
            upgrade(args.mc)
        else:
            p.print_help()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
