"""Azalea CLI entry point - argument parsing and dispatch only."""

import argparse
import sys

from azalea.commands import (
    check,
    export,
    info,
    init,
    install_from_file,
    install_mod,
    list_installed,
    pin_mod,
    readme,
    remove_from_file,
    remove_mod,
    search,
    unpin_mod,
    update_all,
    upgrade,
)
from azalea.log import log_err, print_version
from azalea.server import (
    server_diff,
    server_info,
    server_init,
    server_logs,
    server_pin,
    server_run,
    server_unpin,
    server_update,
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

    sub.add_parser("list", help="List installed mods, resource packs, and shaders")

    a = sub.add_parser("add", help="Add a Modrinth mod")
    a.add_argument("mod", nargs="?", help="Mod name or slug")
    a.add_argument(
        "-f",
        "--file",
        help="Install mods from file (one per line)",
    )

    r = sub.add_parser("remove", help="Remove a Modrinth mod")
    r.add_argument("slug", nargs="?", help="Mod slug")
    r.add_argument(
        "-f",
        "--file",
        help="Remove mods listed in file (one per line)",
    )

    c = sub.add_parser("check", help="Check if the modpack is compatible with a Minecraft version")
    c.add_argument(
        "mc", nargs="?", help="Target Minecraft version (defaults to current pack version)"
    )

    exp = sub.add_parser(
        "export",
        help="Export a .mrpack to dist/ (presets: overrides/presets/*.txt -> overrides/options.txt)",
    )
    exp.add_argument(
        "-c",
        "--client",
        action="store_true",
        help=(
            "Export client-side content only (skip server-side mods). "
            "When using presets: place <preset-name>.txt files in overrides/presets; "
            "their contents will be used as overrides/options.txt inside each preset .mrpack."
        ),
    )
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

    s = sub.add_parser("search", help="Search Modrinth for mods, resourcepacks, or shaders")
    s.add_argument("query", help="Search query")

    i = sub.add_parser("info", help="Display details of an installed mod")
    i.add_argument("slug", help="Mod slug")

    pin = sub.add_parser("pin", help="Lock a mod to its current version (skip during updates)")
    pin.add_argument("slug", help="Mod slug")

    unpin = sub.add_parser("unpin", help="Remove a pin from a mod")
    unpin.add_argument("slug", help="Mod slug")

    sv = sub.add_parser("server", help="Manage a Minecraft server built from an Azalea pack")
    sv_sub = sv.add_subparsers(dest="server_cmd")

    si = sv_sub.add_parser("init", help="Init a server from a pack source")
    si.add_argument(
        "source",
        help="GitHub URL (https://github.com/owner/repo[@tag]) or local path",
    )

    sv_sub.add_parser("update", help="Update the server from its stored source")
    sv_sub.add_parser("diff", help="Preview changes without applying them")
    sv_sub.add_parser("run", help="Run the server")
    sv_sub.add_parser("info", help="Show current server config")

    slogs = sv_sub.add_parser("logs", help="Tail the server log")
    slogs.add_argument(
        "-n",
        "--lines",
        type=int,
        default=50,
        help="Number of lines to show (default: 50)",
    )

    spin = sv_sub.add_parser("pin", help="Pin the server to a specific release tag")
    spin.add_argument("tag", help="Release tag to pin to (e.g. v1.2.0)")

    sv_sub.add_parser("unpin", help="Remove the release pin, track latest")

    args = p.parse_args()

    try:
        if args.version:
            print_version()
        elif args.cmd == "init":
            init()
        elif args.cmd == "list":
            list_installed()
        elif args.cmd == "add":
            if args.file:
                install_from_file(args.file)
            elif args.mod:
                install_mod(args.mod)
            else:
                log_err("Provide a mod slug or use -f <file>")
                sys.exit(1)
        elif args.cmd == "remove":
            if args.file:
                remove_from_file(args.file)
            elif args.slug:
                remove_mod(args.slug)
            else:
                log_err("Provide a mod slug or use -f <file>")
                sys.exit(1)
        elif args.cmd == "check":
            check(args.mc)
        elif args.cmd == "export":
            export(client_only=args.client)
        elif args.cmd == "readme":
            readme()
        elif args.cmd == "update":
            update_all(force=getattr(args, "force", False))
        elif args.cmd == "upgrade":
            upgrade(args.mc)
        elif args.cmd == "search":
            search(args.query)
        elif args.cmd == "info":
            info(args.slug)
        elif args.cmd == "pin":
            pin_mod(args.slug)
        elif args.cmd == "unpin":
            unpin_mod(args.slug)
        elif args.cmd == "server":
            if args.server_cmd == "init":
                server_init(args.source)
            elif args.server_cmd == "update":
                server_update()
            elif args.server_cmd == "diff":
                server_diff()
            elif args.server_cmd == "run":
                server_run()
            elif args.server_cmd == "info":
                server_info()
            elif args.server_cmd == "logs":
                server_logs(args.lines)
            elif args.server_cmd == "pin":
                server_pin(args.tag)
            elif args.server_cmd == "unpin":
                server_unpin()
            else:
                sv.print_help()
        else:
            p.print_help()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
