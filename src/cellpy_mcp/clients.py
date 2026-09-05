"""Registering the server with a chat client.

Under stdio there is nothing to host: the client spawns the server as a
subprocess and talks to it over stdin/stdout. That is what makes this usable
with no deployment budget — and it moves the whole setup problem into one JSON
file, which is a worse ask than the terminal we were trying to avoid for the
audience that most needs this.

So: write the block for them. Carefully, because it is someone else's
configuration file and it has their other servers in it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

__all__ = ["CLIENTS", "config_path", "install"]

#: Clients we know where to find. The value is the per-platform location of the
#: file holding the `mcpServers` map.
CLIENTS = ("claude-desktop",)

DEFAULT_CLIENT = "claude-desktop"


def config_path(client: str = DEFAULT_CLIENT) -> Path:
    """Where `client` keeps its MCP server list on this platform."""
    if client != "claude-desktop":
        known = ", ".join(CLIENTS)
        raise ValueError(f"Unknown client {client!r}. Known clients: {known}.")

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
        return base / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def server_entry(roots: list[Path]) -> dict:
    """The block a client needs in order to spawn this server.

    `sys.executable` rather than the `cellpy-mcp` script: the script is only on
    PATH if the environment that owns it is active, and a chat client does not
    activate anything. Naming the interpreter that has the package installed is
    the spelling that works when a GUI launches it from nowhere in particular.
    """
    return {
        "command": sys.executable,
        "args": ["-m", "cellpy_mcp"],
        "env": {"CELLPY_MCP_ROOT": os.pathsep.join(str(root) for root in roots)},
    }


def install(
    roots: list[Path],
    client: str | None = None,
    dry_run: bool = False,
) -> str:
    """Merge an entry for this server into `client`'s configuration.

    Returns the path written (or that would be written). Raises `ValueError`
    with something worth reading when it cannot.

    Merges rather than writes: the file holds the caller's other servers, and
    a tool that replaces it to add one line is a tool that loses their work.
    """
    target = config_path(client or DEFAULT_CLIENT)

    config: dict = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            # Refusing is the whole point. Overwriting an unparseable config
            # would throw away a file we cannot even read to report.
            raise ValueError(
                f"{target} is not valid JSON ({exc}). Fix or move it first — "
                "refusing to overwrite it."
            ) from exc
        if not isinstance(existing, dict):
            raise ValueError(f"{target} does not contain a JSON object.")
        config = existing

    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{target} has an 'mcpServers' that is not an object.")
    servers["cellpy"] = server_entry(roots)

    if dry_run:
        return str(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    # Written whole, then moved into place: a crash midway through leaves the
    # previous configuration rather than half of one.
    temporary = target.with_suffix(target.suffix + ".cellpy-mcp.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return str(target)
