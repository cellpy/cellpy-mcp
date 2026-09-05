"""The boundary.

The caller is a language model acting on text it may have read in a file, which
is a less trustworthy caller than a person typing a path. So the interesting
cases are the hostile ones, and they are checked here rather than only through
the tools.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cellpy_mcp.sandbox import Refused, Sandbox, default_roots

pytestmark = pytest.mark.essential


@pytest.mark.parametrize(
    "hostile",
    [
        "../escape.cellpy",
        "../../etc/passwd",
        "/etc/passwd",
        "~/secrets.cellpy",
        r"\\somehost\share\x.cellpy",
    ],
)
def test_paths_outside_the_roots_are_refused(sandbox, hostile):
    with pytest.raises(Refused):
        sandbox.resolve(hostile, must_exist=False)


def test_a_unc_path_is_refused_without_asking_the_network(sandbox):
    """The volume is settled from the string before any filesystem call.

    `Path.resolve()` on `\\\\host\\share` asks Windows to go and find *host*,
    which can block for minutes — and a boundary that waits on a name server is
    one a name server could answer differently. There is no timing assertion
    here; the point is that this returns at all, promptly, on every platform.
    """
    with pytest.raises(Refused):
        sandbox.resolve(r"\\somehost\share\x.cellpy", must_exist=False)


def test_a_refusal_says_where_you_could_have_written_instead(sandbox):
    """Error text is read by a model, so it has to name the next move."""
    with pytest.raises(Refused) as raised:
        sandbox.resolve("../escape.cellpy", must_exist=False)
    assert str(sandbox.primary) in str(raised.value)


def test_relative_paths_land_in_the_primary_root(tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (second / "cell.cellpy").write_text("", encoding="utf-8")

    sandbox = Sandbox([first, second])

    # Even though the file exists under the *second* root, a bare name means
    # the primary one. Resolving against each root in turn would make the same
    # string mean different files depending on what happens to exist.
    assert sandbox.resolve("cell.cellpy", must_exist=False) == first / "cell.cellpy"
    # Naming the second root explicitly still works.
    assert sandbox.resolve(str(second / "cell.cellpy")) == second / "cell.cellpy"


def test_every_root_is_writable_not_just_the_first(tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    sandbox = Sandbox([first, second])
    assert sandbox.resolve(str(second / "out" / "f.json"), must_exist=False)


def test_duplicate_roots_are_collapsed(tmp_path):
    """Two cellpy settings routinely point at the same directory."""
    (tmp_path / "one").mkdir()
    sandbox = Sandbox([tmp_path / "one", tmp_path / "one", tmp_path / "one" / "."])
    assert len(sandbox.roots) == 1


def test_a_missing_file_is_a_different_message_from_a_forbidden_one(sandbox):
    with pytest.raises(Refused, match="does not exist"):
        sandbox.resolve("nope.cellpy")


# -- where the roots come from ---------------------------------------------------


def test_the_environment_takes_several_roots(tmp_path, monkeypatch):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv("CELLPY_MCP_ROOT", os.pathsep.join([str(first), str(second)]))
    assert Sandbox.from_environment().roots == [first.resolve(), second.resolve()]


def test_an_explicit_root_beats_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CELLPY_MCP_ROOT", str(tmp_path / "ignored"))
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    assert Sandbox.from_environment(chosen).roots == [chosen.resolve()]


def test_remote_cellpy_paths_are_not_treated_as_local_directories(monkeypatch, tmp_path):
    """`rawdatadir` is often `scp://host/…` on a real machine.

    Containment is `pathlib`-based and cannot express "inside that remote
    share", so such a root has to be dropped rather than silently turned into a
    relative directory called `scp:` — which is what `Path()` would make of it.
    """
    local = tmp_path / "cellpyfiles"
    local.mkdir()

    class Paths:
        rawdatadir = "scp://d1-odin-01.example.com/home/someone/projects"
        cellpydatadir = str(local)
        outdatadir = ""
        notebookdir = None

    monkeypatch.setattr("cellpy.config.paths", Paths(), raising=False)
    assert default_roots() == [local.resolve()]


def test_an_unconfigured_cellpy_still_gets_a_narrow_root(monkeypatch):
    """Never "/": a server that starts wide open ships wide open."""

    class Paths:
        rawdatadir = cellpydatadir = outdatadir = notebookdir = None

    monkeypatch.setattr("cellpy.config.paths", Paths(), raising=False)
    roots = default_roots()
    assert roots == [(Path.home() / "cellpy_mcp").expanduser().resolve()]
    assert roots != [Path(Path().anchor)]
