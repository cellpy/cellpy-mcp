"""What the server remembers between calls.

**One client per process, and that is not laziness — it is measured.**

The obvious design is a per-session store, and the SDK looks like it offers the
key: the tool `Context` has a `session`. It is a *different* `ServerSession`
object on every call (three distinct objects across three calls on one
connection), so a `WeakKeyDictionary` keyed on it hands every call a fresh,
empty state — and fails silently: the server does not error, it forgets the
cell you just loaded and then says "load a cell first".

(There is a second `Context` class, `mcp.server.context.Context`, which *does*
have a `session_id` and is not the one injected into tools. Annotating with it
registers without complaint and then fails schema generation with a pydantic
error naming neither the import nor the fix.)

So state is process-wide and honest about it. Under stdio — how MCP servers are
normally launched — each client spawns its own process, and that *is* the
isolation. A shared streamable-http deployment would need a session token
passed in the tool arguments, or one process per client anyway.

The rule that survives, and it is narrow: a tool must never call
`config.reload()` or `config.set_load_options()`, both of which are
process-global. `config.override()` is contextvar-scoped and is the only safe
way to vary settings for one call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Session"]


@dataclass
class Session:
    cells: dict[str, Any] = field(default_factory=dict)
    collections: dict[str, Any] = field(default_factory=dict)
    counter: int = 0
    #: Built on first use by `api._index` and then kept: it imports ten modules
    #: and cellpy is not a cheap import.
    api_index: list[dict] | None = None

    def handle(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-{self.counter}"

    def cell(self, handle: str):
        from .sandbox import Refused

        if handle not in self.cells:
            raise Refused(f"No cell {handle!r}. Call list_cells to see what is loaded.")
        return self.cells[handle]

    def collection(self, handle: str):
        from .sandbox import Refused

        if handle not in self.collections:
            raise Refused(f"No collection {handle!r}. Call collect first.")
        return self.collections[handle]
