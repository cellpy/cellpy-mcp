"""Shared fixtures.

Tests drive the server **over the real protocol** with an in-process client
rather than calling the tool functions, because calling the functions skips the
schema generation, the argument validation and the error wrapping that are most
of what the SDK does — and those are where the surprises live.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from cellpy_mcp.sandbox import Sandbox
from cellpy_mcp.server import build_server
from cellpy_mcp.state import Session


@pytest.fixture()
def sandbox(tmp_path) -> Sandbox:
    """A sandbox rooted in a temp directory, never the caller's real data."""
    root = tmp_path / "cells"
    root.mkdir()
    return Sandbox([root])


@pytest.fixture()
def root(sandbox) -> Path:
    return sandbox.primary


@pytest.fixture()
def demo_cell(root) -> Path:
    """The cellpy demo cell, copied into the sandbox. Downloads once, then caches."""
    from cellpy.utils import example_data

    target = root / "demo.cellpy"
    shutil.copy(example_data.cellpy_file_path(), target)
    return target


@pytest.fixture()
def server(sandbox):
    return build_server(sandbox=sandbox, state=Session())


@pytest.fixture()
def drive(server):
    """`drive(steps)` runs `steps(call)` against a connected client.

    `call(tool, **arguments)` returns the structured result, or
    `{"refused": <text>}` when the tool raised — which is what a model sees, and
    therefore what is worth asserting on.
    """

    def run(steps):
        from mcp import Client

        async def main():
            async with Client(server) as client:
                # `tool`, not `name`: `describe_api` takes an argument called
                # `name`, and a positional parameter of the same name here makes
                # `call("describe_api", name=...)` a TypeError rather than a call.
                async def call(tool, **arguments):
                    result = await client.call_tool(tool, arguments)
                    text = "".join(getattr(b, "text", "") for b in (result.content or []))
                    if getattr(result, "is_error", False):
                        return {"refused": text}
                    return result.structured_content or json.loads(text)

                return await steps(call)

        return asyncio.run(main())

    return run
