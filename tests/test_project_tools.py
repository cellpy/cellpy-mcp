"""Batch templating.

The happy path downloads a cookiecutter from GitHub, so it is marked `network`
and deselected in CI. What CI does test is the boundary — reached before any
network call — and the workaround that makes the tool work at all.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.essential


def test_it_refuses_before_it_writes_anything(drive, root):
    async def steps(call):
        return (
            await call("new_project", project="../escape", experiment="e1"),
            await call("new_project", project="ok", experiment=""),
            await call("new_project", project="ok", experiment="e1", directory=".."),
        )

    escape, empty, outside = drive(steps)
    assert "not a folder name" in escape["refused"]
    assert "needed" in empty["refused"]
    assert "outside the data directories" in outside["refused"]
    # Nothing was created on the way to refusing.
    assert not (root / "ok").exists()
    assert not (root / "escape").exists()


def test_a_name_with_a_separator_is_not_a_folder_name(drive):
    """`project` names one directory. A path there would walk out of the root."""

    async def steps(call):
        return (
            await call("new_project", project="a/b", experiment="e1"),
            await call("new_project", project="a\\b", experiment="e1"),
        )

    for result in drive(steps):
        assert "not a folder name" in result["refused"]


def test_templates_can_be_listed_without_a_terminal(drive):
    """`cellpy new --list` prints and returns nothing; this returns data."""

    async def steps(call):
        return await call("list_templates")

    result = drive(steps)
    assert result["default"]
    assert result["default"] in result["registered"]


@pytest.mark.network
def test_a_project_is_created_without_a_single_prompt(drive, root):
    """The workaround, verified.

    `create_project(..., no_input=True)` still prompts when the project
    directory does not exist (cellpy `cli_api.py:1601`, filed as
    jepegit/cellpy#990), and a server has no stdin to answer with — under stdio
    it raises `ValueError: I/O operation on closed file`. `new_project` creates
    the directory first, which skips that branch.

    If cellpy#990 lands and this starts passing for a different reason, the
    workaround can go; until then this is what says it still works.
    """

    async def steps(call):
        return await call("new_project", project="demo", experiment="exp001")

    result = drive(steps)
    assert len(result["notebooks"]) >= 5
    assert all(name.endswith(".ipynb") for name in result["notebooks"])
    assert (root / "demo").is_dir()
    assert result["next_step"].startswith("cellpy serve")
