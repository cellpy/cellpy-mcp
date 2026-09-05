"""The names `cellpy mcp` imports across a repository boundary.

cellpy ships a shim — `cellpy mcp serve | install | status` — that imports this
package and delegates to it. cellpy does not depend on the MCP SDK, so it
cannot import anything deeper than the top level, and it has no way to find out
that a name moved except by a user's command breaking.

So these are pinned here, in the repository that can break them. If one of
these tests fails, the fix is not to change the test — it is to change
jepegit/cellpy in the same release, or not to move the name.
"""

from __future__ import annotations

import inspect

import pytest

import cellpy_mcp

pytestmark = pytest.mark.essential


def test_the_four_names_cellpy_imports_exist():
    assert isinstance(cellpy_mcp.__version__, str)
    for name in ("serve", "install", "describe"):
        assert callable(getattr(cellpy_mcp, name)), name


@pytest.mark.parametrize(
    "name, parameters",
    [
        ("serve", ["root"]),
        ("install", ["root", "client", "dry_run"]),
        ("describe", []),
    ],
)
def test_the_signatures_are_the_ones_cellpy_calls_with(name, parameters):
    """cellpy calls these by keyword, so the *names* are the contract."""
    signature = inspect.signature(getattr(cellpy_mcp, name))
    assert list(signature.parameters) == parameters
    # Every argument optional: `cellpy mcp serve` with no flags must work.
    for parameter in signature.parameters.values():
        assert parameter.default is not inspect.Parameter.empty, parameter.name


def test_describe_returns_strings_a_reporter_can_print():
    """`cellpy mcp status` prints these as `key: value` rows and nothing else."""
    described = cellpy_mcp.describe()
    assert isinstance(described, dict)
    assert described, "describe() with nothing to say makes `status` pointless"
    for key, value in described.items():
        assert isinstance(key, str) and isinstance(value, str)


def test_install_reports_where_without_writing(monkeypatch, tmp_path):
    """A dry run returns the path it *would* write and leaves nothing behind."""
    target = tmp_path / "client" / "config.json"
    monkeypatch.setattr("cellpy_mcp.clients.config_path", lambda client=None: target)

    where = cellpy_mcp.install(root=str(tmp_path), dry_run=True)

    assert where == str(target)
    assert not target.exists()
    assert not target.parent.exists()
