"""`python -m cellpy_mcp` — what a chat client spawns.

`cellpy mcp serve` is the discoverable spelling and goes through cellpy's shim.
This is the same thing without it, and it is what `install` writes into a client
config: naming the interpreter and the module directly is one fewer layer to be
wrong about when a GUI launches it from nowhere in particular.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cellpy-mcp", description="MCP server for cellpy."
    )
    subcommands = parser.add_subparsers(dest="command")

    serve = subcommands.add_parser("serve", help="run over stdio (the default)")
    serve.add_argument("--root", help="a directory the server may read and write")

    install = subcommands.add_parser("install", help="register with a chat client")
    install.add_argument("--root", help="a directory the server may read and write")
    install.add_argument("--client", help="which chat client to register with")
    install.add_argument(
        "--dry-run", action="store_true", help="print the target instead of writing"
    )

    subcommands.add_parser("status", help="report the roots and the client config")

    args = parser.parse_args(argv)

    from . import describe, install as do_install, serve as do_serve

    # No subcommand means serve: a client config that says `-m cellpy_mcp` and
    # nothing else must start a server, not print usage to the protocol channel.
    if args.command in (None, "serve"):
        do_serve(root=getattr(args, "root", None))
        return 0

    if args.command == "install":
        try:
            target = do_install(root=args.root, client=args.client, dry_run=args.dry_run)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        verb = "would register" if args.dry_run else "registered"
        print(f"{verb} 'cellpy' in {target}")
        if not args.dry_run:
            print("restart the client to pick it up.")
        return 0

    for key, value in describe().items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
