"""`.cfz` on render (cellpy/cellpy-mcp#9)."""

from __future__ import annotations

import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

from cellpy_mcp.cells import render_cfz
from cellpy_mcp.sandbox import Refused
from cellpy_mcp.state import Session

pytestmark = pytest.mark.essential


class _Frame:
    def __init__(self, height: int):
        self.height = height


class _Collection:
    def __init__(self, height: int = 4):
        self.data = _Frame(height)


def _state(**meta) -> Session:
    state = Session()
    state.cells["cell-1"] = object()
    state.cells["cell-2"] = object()
    state.collections["collection-1"] = _Collection()
    state.collection_meta["collection-1"] = {
        "kind": "cycles",
        "cells": ["cell-1"],
        "family": None,
        "cycles": [1, 2],
        **meta,
    }
    return state


def _fake_bundle(cell, *, kind, path, **kwargs):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"format": "cellpy-figure", "format_version": 1}),
        )
        archive.writestr("figure.json", "{}")
        archive.writestr("data.parquet", b"")
        archive.writestr("README.txt", 'pip install "cellpy-figure[mpl]"\n')
    return path


def test_film_is_refused(tmp_path: Path):
    with pytest.raises(Refused, match="film"):
        render_cfz(_state(), "collection-1", tmp_path / "film.cfz", "film")


def test_missing_translator_names_the_extra(monkeypatch, tmp_path: Path):
    monkeypatch.setitem(
        sys.modules,
        "cellpy.plotting.bundle",
        types.ModuleType("cellpy.plotting.bundle"),
    )
    with pytest.raises(Refused, match="plotting-mpl"):
        render_cfz(_state(), "collection-1", tmp_path / "out.cfz", None)


def test_several_cells_are_refused(tmp_path: Path):
    state = _state(cells=["cell-1", "cell-2"])
    with pytest.raises(Refused, match="one cell"):
        render_cfz(state, "collection-1", tmp_path / "out.cfz", None)


def test_summary_without_a_family_is_refused(tmp_path: Path):
    state = _state(kind="summary", family=None)
    with pytest.raises(Refused, match="family"):
        render_cfz(state, "collection-1", tmp_path / "out.cfz", None)


def test_render_cfz_reports_the_bundle(monkeypatch, tmp_path: Path):
    seen = {}

    def spy(cell, *, kind, path, **kwargs):
        seen["kind"] = kind
        seen["cycles"] = kwargs.get("cycles")
        return _fake_bundle(cell, kind=kind, path=path, **kwargs)

    monkeypatch.setattr("cellpy_mcp.cells._save_bundle", spy)
    target = tmp_path / "out.cfz"
    out = render_cfz(_state(), "collection-1", target, None)
    assert seen == {"kind": "cycles", "cycles": [1, 2]}
    assert out["path"] == str(target)
    assert out["bytes"] == target.stat().st_size
    assert out["format_version"] == 1
    assert out["rows"] == 4
    assert "manifest.json" in zipfile.ZipFile(target).namelist()
