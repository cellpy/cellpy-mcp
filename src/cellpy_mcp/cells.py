"""Loading cells, collecting them into frames, and writing figures and data.

One rule shapes all of it: **tools return handles and facts, never data.** A
tool result goes into a model's context window; one collected summary is ~29 kB
of CSV and a raw figure can be several MB, so frames stay here behind an id and
only `preview_collection` returns rows — capped, whatever it is asked for.

The second rule is that results carry the traps. `render` returns `trace_types`
beside `points_plotted` and `rows_collected`, so an agent that asked for a
density film can see it got `histogram2d` rather than lines, and one that forgot
`direction="both"` can see it plotted 891 of 2328 rows. Those failures produce
*plausible output*, which is exactly what prose warnings are bad at preventing
and what a structured result is good at.
"""

from __future__ import annotations

from typing import Any

from .sandbox import Refused

__all__ = ["register", "MAX_PREVIEW_ROWS"]

#: Hard cap on rows a tool will put in front of a model, whatever it asks for.
MAX_PREVIEW_ROWS = 20


def register(server, state, sandbox) -> None:
    @server.tool()
    def list_instruments() -> dict:
        """Which cellpy loaders exist, and which can actually run on this machine."""
        import shutil
        import sys

        import cellpy

        def arbin_res_readable() -> bool:
            try:
                if sys.platform != "win32":
                    return shutil.which("mdb-export") is not None
                import pyodbc

                return any("microsoft access driver" in d.lower() for d in pyodbc.drivers())
            except Exception:  # noqa: BLE001 - no opinion means "assume it works"
                return True

        usable = arbin_res_readable()
        out = []
        for entry in cellpy.list_instruments():
            item = {"id": entry["id"], "suffixes": entry.get("suffixes", []), "usable": True}
            if entry["id"] == "arbin_res" and not usable:
                item["usable"] = False
                item["reason"] = (
                    "needs mdbtools (posix) or the Access Database Engine (Windows)"
                )
            out.append(item)
        return {"instruments": out, **sandbox.describe()}

    @server.tool()
    def load_cell(
        path: str,
        instrument: str | None = None,
        mass_mg: float | None = None,
    ) -> dict:
        """Load one cell file and return a handle plus what the data can support.

        `mass_mg` is the active-material mass. Without it every `*_gravimetric`
        column is computed against a default of 1.0 mg — the numbers still
        appear, they are simply wrong, so supply it when you know it.
        """
        import cellpy

        target = sandbox.resolve(path)
        kwargs: dict[str, Any] = {"filename": str(target)}
        if instrument:
            kwargs["instrument"] = instrument
        if mass_mg is not None:
            kwargs["mass"] = mass_mg

        cell = cellpy.get(**kwargs)
        handle = state.handle("cell")
        state.cells[handle] = cell

        cycles = list(cell.get_cycle_numbers())
        return {
            "handle": handle,
            "name": cell.cell_name,
            "cycles": len(cycles),
            "first_cycle": cycles[0] if cycles else None,
            "last_cycle": cycles[-1] if cycles else None,
            "mass_mg": cell.mass,
            "mass_was_supplied": mass_mg is not None,
            # Names only. The frame itself stays here.
            "summary_columns": sorted(cell.data.summary.columns),
        }

    @server.tool()
    def list_cells() -> dict:
        """The cells loaded in this session."""
        return {
            "cells": [
                {"handle": h, "name": c.cell_name, "cycles": len(c.get_cycle_numbers())}
                for h, c in state.cells.items()
            ]
        }

    @server.tool()
    def describe_plot_families() -> dict:
        """Summary plot families cellpy offers, and whether the loaded cells support them.

        Availability is judged on what a family *asks the summary for*
        (`summary_options().columns`), not on the columns it draws — the drawn
        list includes columns the collector manufactures, and checking those
        reports "missing columns" for families that work perfectly well.
        """
        from cellpy.plotting import registry

        if not state.cells:
            raise Refused("Load a cell first — availability depends on the data.")

        have: set[str] = set()
        hdr = None
        for cell in state.cells.values():
            have |= set(cell.data.summary.columns)
            hdr = hdr if hdr is not None else cell.schema.summary

        families = []
        for name, description in registry.families(entry_point="summary_plot"):
            try:
                needs = registry.get(name).summary_options(hdr).columns
            except Exception as exc:  # noqa: BLE001 - a broken family is data, not a crash
                families.append({"name": name, "available": False, "reason": str(exc)})
                continue
            missing = [column for column in needs if column not in have]
            entry = {"name": name, "description": description, "available": not missing}
            if missing:
                entry["missing_columns"] = missing
            families.append(entry)
        return {"families": families}

    @server.tool()
    def collect(
        kind: str,
        cells: list[str] | None = None,
        columns: list[str] | None = None,
        family: str | None = None,
        cycles: list[int] | None = None,
        group_it: bool = False,
        max_cycle: int | None = None,
    ) -> dict:
        """Build a collection. `kind` is one of: summary, cycles, ica, dva.

        Returns a handle and the frame's shape — never the frame. Use
        preview_collection for rows, export_collection for the numbers.

        For `summary`, give either `columns` or `family` (a name from
        describe_plot_families; the family supplies its own collect options).
        For `cycles` / `ica` / `dva`, give `cycles`.
        """
        from cellpy.collect import (
            collect_cycles,
            collect_dva,
            collect_ica,
            collect_summaries,
            from_cells,
        )
        from cellpy.collect.options import CurveOptions
        from cellpy.plotting import registry

        # Check the argument before the state: telling an agent "no cells
        # loaded" when it also misspelled `kind` costs it a round trip to find
        # that out.
        if kind not in ("summary", "cycles", "ica", "dva"):
            raise Refused(f"Unknown kind {kind!r}. Use summary, cycles, ica or dva.")

        handles = cells or list(state.cells)
        if not handles:
            raise Refused("No cells loaded.")

        # from_cells accepts anything and silently drops what is not a cell, so
        # the mapping is built from checked lookups only (cellpy#939).
        chosen = {h: state.cell(h) for h in handles}
        batch = from_cells({state.cells[h].cell_name or h: c for h, c in chosen.items()})

        if kind == "summary":
            if family:
                hdr = next(iter(chosen.values())).schema.summary
                options = (
                    registry.get(family)
                    .summary_options(hdr)
                    .replace(only_selected=False, group_it=group_it, max_cycle=max_cycle)
                )
                collection = collect_summaries(batch, options=options)
            else:
                if not columns:
                    raise Refused("Give either `columns` or `family` for kind='summary'.")
                missing = [
                    column
                    for column in columns
                    if not any(column in cell.data.summary.columns for cell in chosen.values())
                ]
                if missing:
                    # Collecting these would draw an empty chart rather than fail.
                    raise Refused("These cells have no " + ", ".join(missing) + ".")
                collection = collect_summaries(
                    batch,
                    columns=tuple(columns),
                    only_selected=False,
                    group_it=group_it,
                    max_cycle=max_cycle,
                )
        elif kind == "cycles":
            collection = collect_cycles(batch, options=CurveOptions(cycles=tuple(cycles or ())))
        else:
            collector = collect_ica if kind == "ica" else collect_dva
            # `cycles` as an override rather than inside an options object:
            # `cellpy.collect.IcaOptions` took a `cycles` field, is deprecated
            # in 2.2, and is removed in 2.3. The replacement
            # (`cellpy.ica.IcaOptions`) has no such field and exists as far back
            # as this package's cellpy floor, so passing cycles alongside works
            # on every supported version and warns on none.
            collection = collector(batch, cycles=tuple(cycles or ()))

        handle = state.handle("collection")
        state.collections[handle] = collection
        data = collection.data
        result = {
            "handle": handle,
            "kind": kind,
            "rows": data.height,
            "columns": data.columns,
            "is_grouped": bool(collection.is_grouped),
        }
        if "direction" in data.columns:
            # Plotting defaults to charge; say so here rather than let it surprise.
            result["directions"] = dict(
                data.group_by("direction").len().sort("direction").iter_rows()
            )
            result["note"] = (
                "Plots draw direction='charge' by default; "
                "pass direction='both' to render."
            )
        return result

    @server.tool()
    def preview_collection(handle: str, rows: int = 5) -> dict:
        """A few rows, capped. This is the only tool that returns data, on purpose."""
        collection = state.collection(handle)
        count = max(1, min(int(rows), MAX_PREVIEW_ROWS))
        return {
            "rows_shown": count,
            "rows_total": collection.data.height,
            "records": collection.data.head(count).to_dicts(),
        }

    @server.tool()
    def render(
        handle: str,
        path: str,
        kind: str | None = None,
        layout: str = "per_cell",
        direction: str | None = None,
        spread: bool = False,
    ) -> dict:
        """Draw a collection and write the figure to `path` (.json or .html).

        `kind="film"` gives a 2-D density rendering. Note it is a **kind**, not
        a layout: on cellpy 2.1.2 `layout="film"` silently drew lines instead
        (fixed in 2.1.3). The returned `trace_types` is how you check what you
        actually got.
        """
        import plotly.io as pio

        collection = state.collection(handle)
        target = sandbox.resolve(path, must_exist=False)
        if target.suffix.lower() not in (".json", ".html"):
            raise Refused("Write a .json or .html figure.")

        kwargs: dict[str, Any] = {"layout": layout}
        if kind:
            kwargs["kind"] = kind
        if direction:
            kwargs["direction"] = direction
        if spread and collection.is_grouped:
            kwargs["spread"] = True

        figure = collection.plot(**kwargs)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix.lower() == ".json":
            target.write_text(pio.to_json(figure), encoding="utf-8")
        else:
            target.write_text(pio.to_html(figure, include_plotlyjs="cdn"), encoding="utf-8")

        points = sum(len(t.x) for t in figure.data if getattr(t, "x", None) is not None)
        return {
            "path": str(target),
            "bytes": target.stat().st_size,
            "traces": len(figure.data),
            "trace_types": sorted({t.type for t in figure.data}),
            "points_plotted": points,
            "rows_collected": collection.data.height,
        }

    @server.tool()
    def export_collection(handle: str, path: str) -> dict:
        """Write the collected frame to `path` (.csv, .parquet or .json)."""
        collection = state.collection(handle)
        target = sandbox.resolve(path, must_exist=False)
        suffix = target.suffix.lower()
        target.parent.mkdir(parents=True, exist_ok=True)

        if suffix == ".csv":
            target.write_text(collection.data.write_csv(), encoding="utf-8")
        elif suffix == ".parquet":
            collection.data.write_parquet(target)
        elif suffix == ".json":
            target.write_text(collection.data.write_json(), encoding="utf-8")
        else:
            raise Refused("Write a .csv, .parquet or .json file.")

        return {
            "path": str(target),
            "bytes": target.stat().st_size,
            "rows": collection.data.height,
        }
