"""The one exception type the tools raise.

`Refused` subclasses the SDK's `ToolError`, and that detail is load-bearing
rather than tidy.

Every refusal in this package is written to be *read by a model* — "these cells
have no discharge_capacity_absolute", "outside the data directories. Allowed:
…", "Did you mean …?". The whole design leans on the idea that a tool result,
including a failure, is where you put the thing documentation is bad at
conveying.

mcp 2.1 forwards a message to the model **only** when the exception is a
`ToolError`. Anything else is treated as a crash: the caller gets a bare "Error
executing tool describe_api" and the actual text, as the SDK's own comment puts
it, "stays on the server". mcp 2.0 did not draw that line, which is why the
prototype this grew from raised a plain `ValueError` and appeared to work.

So a refusal that is not a `ToolError` is not a refusal — it is a crash with a
helpful message nobody will ever see.
"""

from __future__ import annotations

from mcp.server.mcpserver.exceptions import ToolError

__all__ = ["Refused"]


class Refused(ToolError):
    """The request is not allowed. The message is meant for the model to read."""
