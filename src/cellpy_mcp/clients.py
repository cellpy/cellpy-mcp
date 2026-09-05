"""Registering the server with an MCP client.

Under stdio there is nothing to host: the client spawns the server as a
subprocess and talks to it over stdin/stdout. That is what makes this usable
with no deployment budget — and it moves the whole setup problem into one JSON
file, which is a worse ask than the terminal we were trying to avoid for the
audience that most needs this.

So: write the block for them. Carefully, because it is someone else's
configuration file and it has their other servers in it.

**Clients differ in two ways that matter**, and both fail silently if you get
them wrong. The file location is the obvious one. The less obvious one is the
top-level key: VS Code reads `servers`, everyone else reads `mcpServers`. Write
the wrong key into VS Code's file and it parses, saves, and does nothing —
which is why `KEY` is per-client data here rather than a constant.

**Claude Code is deliberately not written to.** Its servers live in
`~/.claude.json` alongside the sign-in session and per-project trust decisions,
or in a project-scoped `.mcp.json` whose location depends on which project you
meant. `claude mcp add` exists, handles scopes, and is the supported path;
`command_for` returns it so callers can show it rather than guess at a file
that important.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CLIENTS", "DEFAULT_CLIENT", "command_for", "config_path", "install", "server_entry"]


@dataclass(frozen=True)
class Client:
    """How one client wants to be told about a server."""

    name: str
    label: str
    #: Top-level key holding the server map. VS Code is the odd one out.
    key: str
    #: `(windows, macos, linux)` paths, relative to the right base directory.
    windows: tuple[str, ...]
    macos: tuple[str, ...]
    linux: tuple[str, ...]
    note: str = ""


_CLIENTS = (
    Client(
        name="claude-desktop",
        label="Claude Desktop",
        key="mcpServers",
        windows=("%APPDATA%", "Claude", "claude_desktop_config.json"),
        macos=("~", "Library", "Application Support", "Claude", "claude_desktop_config.json"),
        linux=("~", ".config", "Claude", "claude_desktop_config.json"),
    ),
    Client(
        name="cursor",
        label="Cursor",
        key="mcpServers",
        # Cursor also reads a project-scoped `.cursor/mcp.json`, which takes
        # priority. This writes the global one, since "my cells" is not a
        # property of whichever repository happens to be open.
        windows=("~", ".cursor", "mcp.json"),
        macos=("~", ".cursor", "mcp.json"),
        linux=("~", ".cursor", "mcp.json"),
        note="global; a project's .cursor/mcp.json overrides it",
    ),
    Client(
        name="vscode",
        label="VS Code",
        key="servers",
        windows=("%APPDATA%", "Code", "User", "mcp.json"),
        macos=("~", "Library", "Application Support", "Code", "User", "mcp.json"),
        linux=("~", ".config", "Code", "User", "mcp.json"),
        note="user profile; VS Code names the key 'servers', not 'mcpServers'",
    ),
)

CLIENTS = {client.name: client for client in _CLIENTS}
DEFAULT_CLIENT = "claude-desktop"

#: Clients we know about but will not write to, and what to do instead.
MANUAL = {
    "claude-code": (
        "Claude Code keeps MCP servers in ~/.claude.json, next to your sign-in "
        "session and per-project trust decisions, or in a project-scoped "
        ".mcp.json. Use its own command instead, which handles scopes:"
    )
}


def _resolve(parts: tuple[str, ...]) -> Path:
    """Turn a path template into a real path.

    `%APPDATA%` is expanded from the environment with a documented fallback,
    rather than assumed: a roaming profile can put it somewhere else, and this
    writes a file.
    """
    first, *rest = parts
    if first == "%APPDATA%":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif first == "~":
        base = Path.home()
    else:
        base = Path(first)
    return base.joinpath(*rest).expanduser()


def config_path(client: str | None = None) -> Path:
    """Where `client` keeps its MCP server list on this platform."""
    name = client or DEFAULT_CLIENT
    if name in MANUAL:
        raise ValueError(
            f"{name} is not registered by editing a file — run this instead:\n"
            f"    {command_for(name)}"
        )
    if name not in CLIENTS:
        known = ", ".join(sorted([*CLIENTS, *MANUAL]))
        raise ValueError(f"Unknown client {name!r}. Known clients: {known}.")

    spec = CLIENTS[name]
    if sys.platform == "win32":
        return _resolve(spec.windows)
    if sys.platform == "darwin":
        return _resolve(spec.macos)
    return _resolve(spec.linux)


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


def command_for(client: str, roots: list[Path] | None = None) -> str:
    """The command to run for a client this cannot register by editing a file."""
    if client != "claude-code":
        raise ValueError(f"No command form for {client!r}.")
    root = os.pathsep.join(str(r) for r in (roots or []))
    parts = ["claude", "mcp", "add", "cellpy"]
    if root:
        parts += ["--env", f"CELLPY_MCP_ROOT={root}"]
    parts += ["--", sys.executable, "-m", "cellpy_mcp"]
    return " ".join(shlex.quote(part) if " " in part else part for part in parts)


def install(
    roots: list[Path],
    client: str | None = None,
    dry_run: bool = False,
) -> str:
    """Merge an entry for this server into `client`'s configuration.

    Returns the path written (or that would be written). Raises `ValueError`
    with something worth reading when it cannot.

    Merges rather than writes: the file holds the caller's other servers, and a
    tool that replaces it to add one line is a tool that loses their work.
    """
    name = client or DEFAULT_CLIENT
    target = config_path(name)
    key = CLIENTS[name].key

    config: dict = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8") or "{}")
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

    servers = config.setdefault(key, {})
    if not isinstance(servers, dict):
        raise ValueError(f"{target} has a {key!r} that is not an object.")
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
