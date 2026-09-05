"""Loading, collecting, rendering and exporting — over the protocol."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.essential


def test_the_whole_arc(drive, demo_cell, root):
    """Load -> collect -> render -> export, as a client actually does it."""

    async def steps(call):
        cell = await call("load_cell", path="demo.cellpy", mass_mg=0.29)
        ica = await call("collect", kind="ica", cycles=[1, 5, 10])
        figure = await call(
            "render",
            handle=ica["handle"],
            path="out/film.json",
            kind="film",
            direction="both",
        )
        data = await call("export_collection", handle=ica["handle"], path="out/ica.csv")
        return cell, ica, figure, data

    cell, ica, figure, data = drive(steps)

    assert cell["cycles"] == 304
    assert cell["mass_was_supplied"] is True
    # Names only — the frame must not travel.
    assert "summary_columns" in cell and "rows" not in cell

    # The direction counts are reported so an agent can notice a partial plot.
    assert set(ica["directions"]) == {"charge", "discharge"}

    # A film is a *kind*; the result says which it got rather than hoping.
    assert figure["trace_types"] == ["histogram2d"]
    assert figure["points_plotted"] == ica["rows"], "direction='both' draws everything"
    assert (root / "out" / "film.json").is_file()
    assert data["rows"] == ica["rows"]


def test_a_default_direction_plot_says_it_drew_less(drive, demo_cell):
    """The trap made visible: fewer points than rows, reported rather than hidden."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        ica = await call("collect", kind="ica", cycles=[1, 5, 10])
        return ica, await call("render", handle=ica["handle"], path="out/f.json", kind="film")

    ica, figure = drive(steps)
    assert figure["points_plotted"] < figure["rows_collected"] == ica["rows"]


def test_no_tool_returns_a_frame(drive, demo_cell):
    """Only preview returns rows, and it caps whatever it is asked for."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        collected = await call(
            "collect", kind="summary", columns=["discharge_capacity_gravimetric"]
        )
        return collected, await call(
            "preview_collection", handle=collected["handle"], rows=10_000
        )

    collected, preview = drive(steps)
    assert collected["rows"] == 304
    assert preview["rows_shown"] == 20  # MAX_PREVIEW_ROWS, not 10_000
    assert preview["rows_total"] == 304
    assert len(preview["records"]) == 20


def test_availability_is_answered_rather_than_discovered_by_drawing(drive, demo_cell):
    async def steps(call):
        blind = await call("describe_plot_families")
        await call("load_cell", path="demo.cellpy")
        return blind, await call("describe_plot_families")

    blind, described = drive(steps)
    assert "refused" in blind, "availability depends on data; say so"

    families = described["families"]
    assert len(families) == 20
    unavailable = [family for family in families if not family["available"]]
    assert unavailable, "the demo cell genuinely lacks the *_absolute columns"
    assert all("missing_columns" in family for family in unavailable), "name what is missing"


def test_writes_are_sandboxed_too(drive, demo_cell):
    """A write primitive outside the boundary would make the read check decor."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        collected = await call(
            "collect", kind="summary", columns=["discharge_capacity_gravimetric"]
        )
        return (
            await call("export_collection", handle=collected["handle"], path="../loot.csv"),
            await call("export_collection", handle=collected["handle"], path="out/x.exe"),
        )

    outside, wrong_kind = drive(steps)
    assert "outside the data directories" in outside["refused"]
    assert ".csv" in wrong_kind["refused"]


def test_unknown_handles_and_kinds_are_told_what_to_do(drive):
    """Error text is read by a model, so it has to name the next call."""

    async def steps(call):
        return (
            await call("preview_collection", handle="collection-99"),
            await call("collect", kind="nope"),
        )

    handle, kind = drive(steps)
    assert "collect" in handle["refused"]
    assert "summary" in kind["refused"] and "ica" in kind["refused"]


def test_collecting_a_column_the_cells_lack_is_refused_not_drawn(drive, demo_cell):
    """It would otherwise produce an empty chart, which looks like an answer."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        return await call("collect", kind="summary", columns=["not_a_column"])

    assert "not_a_column" in drive(steps)["refused"]
