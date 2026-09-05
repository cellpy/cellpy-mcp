"""`search_api` and `describe_api`, driven over the protocol."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.essential


def test_it_follows_the_reference_the_docstring_points_at(drive):
    """The finding this family turns on.

    `CellpyCell.get_cap` takes 23 arguments, documents none of them, and spends
    its one-line docstring pointing elsewhere. The delegate documents 22 of 24
    in a full ``Args:`` block. Following the pointer is the difference between
    an unanswerable call and a documented one, so it is asserted rather than
    left to be noticed.

    This goes through the installed cellpy, whose spelling of that pointer has
    already changed once (see `test_follow_reference` for both forms tested
    against text we control). If it breaks, check the docstring before the code.
    """

    async def steps(call):
        return await call("describe_api", name="get_cap")

    result = drive(steps)
    assert result["path"] == "cellpy.readers.cellreader.CellpyCell.get_cap"
    assert result["delegates_to"] == "cellpy.readers.capacity_curves.get_cap"
    assert "Args:" in result["delegate_doc"]
    assert len(result["parameters"]) > 20
    # One stray argument is fine; twenty-three would mean the hop was not made.
    assert len(result["undocumented_parameters"]) <= 2


def test_a_method_is_rendered_the_way_you_would_call_it(drive):
    """`self` in a rendered signature invites a model to pass it."""

    async def steps(call):
        return await call("describe_api", name="get_cap")

    result = drive(steps)
    assert result["signature"].startswith("get_cap(cycle=")
    assert "self" not in result["signature"]
    assert not any(p["name"] in ("self", "cls") for p in result["parameters"])


def test_defaults_survive_where_prose_does_not(drive):
    """Half the arguments are undocumented; their defaults never are.

    `cellpy.get` takes everything by keyword with a default — including
    `filename` — so the defaults are the only thing that says what a call
    without arguments would do.
    """

    async def steps(call):
        return await call("describe_api", name="cellpy.get")

    parameters = {p["name"]: p for p in drive(steps)["parameters"]}
    assert parameters["auto_summary"]["default"] == "True"
    assert parameters["filename"]["default"] == "None"
    assert parameters["estimate_area"]["default"] == "True"


def test_it_will_not_import_outside_cellpy(drive):
    """Resolving a dotted path is importing it, and the caller is a model.

    The refusal has to name the actual reason. Falling through to "no such
    cellpy call" would be true of `os.system` and would teach the caller that
    some other spelling might work.
    """

    async def steps(call):
        return (
            await call("describe_api", name="os.system"),
            await call("describe_api", name="subprocess.run"),
            await call("describe_api", name="nonsense_call"),
        )

    system, subprocess_run, missing = drive(steps)
    assert "not part of cellpy" in system["refused"]
    assert "not part of cellpy" in subprocess_run["refused"]
    assert "No cellpy call" in missing["refused"]


def test_source_is_there_when_asked_for_and_not_otherwise(drive):
    """The honest fallback for the thin half — but it costs context, so opt in."""

    async def steps(call):
        return (
            await call("describe_api", name="cellpy.collect.collect_ica"),
            await call("describe_api", name="cellpy.collect.collect_ica", include_source=True),
        )

    without, with_source = drive(steps)
    assert "source" not in without
    assert "def collect_ica" in with_source["source"]


def test_search_points_at_the_module_that_defines_the_call(drive):
    """`utils.helpers` re-exports `CellpyCell`; a path through it sends the
    reader to the wrong file. Identity-deduping the index is what fixes it."""

    async def steps(call):
        return await call("search_api", query="get_mass")

    result = drive(steps)
    paths = [match["path"] for match in result["matches"]]
    assert "cellpy.readers.cellreader.CellpyCell.get_mass" in paths
    assert not any("utils.helpers" in path for path in paths)
    assert result["indexed"] > 100


def test_a_bare_heading_is_not_a_summary(drive):
    """`set_mass` opens with `Warning:`, which describes nothing on its own."""

    async def steps(call):
        return await call("search_api", query="set_mass")

    summaries = [m["summary"] for m in drive(steps)["matches"] if m["name"] == "set_mass"]
    assert summaries and summaries[0].strip() != "Warning:"


def test_a_near_miss_suggests_something(drive):
    """A refusal a model can act on beats one it can only report."""

    async def steps(call):
        return (
            await call("describe_api", name="get_ca"),
            await call("describe_api", name="zzzz_not_a_call"),
        )

    near, nothing = drive(steps)
    assert "Did you mean" in near["refused"]
    assert "get_cap" in near["refused"]
    # And when there is genuinely nothing close, it does not invent a suggestion.
    assert "Did you mean" not in nothing["refused"]


def test_an_empty_query_is_refused(drive):
    async def steps(call):
        return await call("search_api", query="   ")

    assert "refused" in drive(steps)


# -- the resolver, against text we control ---------------------------------------
#
# The tests above go through the installed cellpy, which makes them hostage to
# cellpy's prose: the reference spelling changed between 2.1.3 and 2.1.3.post2
# and took three of these assertions with it. These pin the mechanism instead.


def test_follow_reference_reads_both_spellings():
    """A Sphinx role, and the bare backticks cellpy 2.1.3.post2 left behind."""
    from cellpy_mcp.api import follow_reference

    index = [{"name": "get_cap", "path": "cellpy.readers.capacity_curves.get_cap"}]

    role, _doc = follow_reference(
        "Gets the capacity. See :func:`cellpy.readers.capacity_curves.get_cap`.", index
    )
    bare, _doc = follow_reference("Gets the capacity. See `get_cap`.", index)

    assert role == "cellpy.readers.capacity_curves.get_cap"
    assert bare == "cellpy.readers.capacity_curves.get_cap"


def test_a_bare_name_is_only_followed_to_a_module_level_function():
    """The method is what we are reading; following it back says nothing.

    Restricting to module-level entries is also what disambiguates the two
    `get_cap`s without guessing.
    """
    from cellpy_mcp.api import follow_reference

    only_the_method = [
        {"name": "get_cap", "path": "cellpy.readers.cellreader.CellpyCell.get_cap"}
    ]
    assert follow_reference("See `get_cap`.", only_the_method) == (None, "")


def test_an_ambiguous_bare_name_is_not_guessed_at():
    """Two candidates would mean attaching someone else's arguments to a call."""
    from cellpy_mcp.api import follow_reference

    ambiguous = [
        {"name": "to_csv", "path": "cellpy.exporters.tabular.to_csv"},
        {"name": "to_csv", "path": "cellpy.utils.helpers.to_csv"},
    ]
    assert follow_reference("See `to_csv`.", ambiguous) == (None, "")


def test_a_reference_to_something_outside_cellpy_is_not_followed():
    """Resolving a reference imports it, and docstrings are not trusted input."""
    from cellpy_mcp.api import follow_reference

    assert follow_reference("See :func:`os.system`.", []) == (None, "")
    assert follow_reference("See `subprocess.run`.", []) == (None, "")
