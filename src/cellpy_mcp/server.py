"""Assembling the server.

Built by a function rather than at import time, so a test can make one with its
own sandbox instead of monkeypatching a module global into place. The prototype
this grew from read its root at import, which meant every test had to import the
module fresh in the right order — the same import-time-resolution shape that
makes cellpy's own `examplesdir` such a nuisance.
"""

from __future__ import annotations

from . import api, cells, projects, prompts
from .sandbox import Sandbox
from .state import Session

__all__ = ["build_server"]

INSTRUCTIONS = """\
Battery cell data via cellpy.

- Cells and figures: load cells, collect them into frames, then render or \
export. Tools return handles and summaries, never frames — use \
preview_collection to see rows, and render/export to produce files.
- The API: use search_api and describe_api to answer questions about how a \
cellpy call works. Prefer them over recalling a signature; they read the \
version that is installed. cellpy leaves many arguments undocumented, so check \
undocumented_parameters and read the source rather than guessing.
- Batch projects: list_templates and new_project set up the notebook template \
that `cellpy new` produces.

Every path is confined to the configured data directories. A refusal names \
them; do not try to work around it."""


def build_server(sandbox: Sandbox | None = None, state: Session | None = None):
    """An `MCPServer` with every tool and prompt registered."""
    # NOTE: `mcp.server.mcpserver.Context` — *not* `mcp.server.context.Context`.
    # Both exist in mcp 2.0 and only the first is recognised by `@server.tool()`;
    # the other registers without complaint and then fails schema generation
    # with a pydantic error naming neither the import nor the fix. Nothing here
    # takes a `Context` any more (see `state`), which is why it is only a note.
    from mcp.server import MCPServer

    sandbox = sandbox or Sandbox.from_environment()
    state = state or Session()

    server = MCPServer(name="cellpy", instructions=INSTRUCTIONS)
    cells.register(server, state, sandbox)
    api.register(server, state)
    projects.register(server, sandbox)
    prompts.register(server)

    # Handy for tests and for `cellpy mcp status`; not part of the protocol.
    server.cellpy_sandbox = sandbox
    server.cellpy_state = state
    return server
