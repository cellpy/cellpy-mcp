"""An MCP server for cellpy — battery cell data, plots, and the cellpy API.

Four things a caller can do without writing Python: load cells and collect them
into frames; render figures and export data; ask what any cellpy call takes and
what its arguments mean; and set up a batch project from a template.

**This module is the contract `cellpy mcp` depends on.** cellpy ships a thin
command group (`cellpy mcp serve | install | status`) that imports this package
and, when it is absent, says how to install it. cellpy deliberately does not
depend on the MCP SDK — it is young and moving, and a long-lived network-facing
process is a security surface a data library should not carry — so the four
names below are load-bearing across a repository boundary. Changing them
without changing cellpy breaks the command:

    __version__
    serve(root=None)
    install(root=None, client=None, dry_run=False) -> str
    describe() -> dict
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

__all__ = ["__version__", "serve", "install", "describe", "build_server", "Sandbox"]


def build_server(sandbox=None, state=None):
    """An `MCPServer` with every tool and prompt registered."""
    from .server import build_server as _build

    return _build(sandbox=sandbox, state=state)


def serve(root: str | Path | None = None) -> None:
    """Run the server over stdio. Blocks until the client disconnects.

    Prints nothing: stdout *is* the protocol channel, and a friendly banner on
    it is a parse error at the other end.
    """
    from .sandbox import Sandbox

    build_server(Sandbox.from_environment(root)).run(transport="stdio")


def install(
    root: str | Path | None = None,
    client: str | None = None,
    dry_run: bool = False,
) -> str:
    """Register this server with a chat client; return the path written."""
    from .clients import install as _install
    from .sandbox import Sandbox

    return _install(Sandbox.from_environment(root).roots, client=client, dry_run=dry_run)


def describe() -> dict:
    """What `cellpy mcp status` reports beyond the two version numbers."""
    from .clients import config_path
    from .sandbox import Sandbox

    sandbox = Sandbox.from_environment()
    described = {"roots": ", ".join(str(root) for root in sandbox.roots)}
    try:
        target = config_path()
    except ValueError:  # pragma: no cover - only if CLIENTS shrinks
        return described
    described["client config"] = f"{target}{'' if target.exists() else ' (not present)'}"
    return described


def __getattr__(name: str):
    # `Sandbox` is re-exported for callers who want to build a server with an
    # explicit set of roots, but importing it eagerly would drag cellpy's
    # config in just because someone imported the package.
    if name == "Sandbox":
        from .sandbox import Sandbox

        return Sandbox
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
