# cellpy-mcp

An [MCP](https://modelcontextprotocol.io) server for
[cellpy](https://github.com/jepegit/cellpy). It lets an agent — or a chat
window — load battery cells, collect them into frames, render figures, export
data, look up how any cellpy call works, and set up a batch project. Without
writing any Python.

```bash
pip install cellpy-mcp
cellpy mcp install        # register it with your chat client
```

Then restart the client and ask it to plot something.

## Who it is for

- **People building on cellpy** — a GUI, a script that automates cell handling.
  The tools are the useful API, and `describe_api` gives real signatures from
  the version you have installed.
- **People who just want to ask.** Open a chat window, point it at a file, ask
  for capacity versus cycle. The prompts below are pickable starting points, so
  you do not have to know what to ask for.
- **People who would rather not use a terminal.** `new_project` is `cellpy new`
  without the command line.

Nothing is hosted. Under stdio your chat client starts the server itself, on
your machine, reading your files — there is no service to sign up for and
nothing leaves the machine except what you paste into the chat.

## What it can do

Cells and figures:

| Tool | What it gives you |
|---|---|
| `list_instruments` | loaders, and whether each can actually run on this machine |
| `load_cell` | a handle, cycle count, mass, summary column names |
| `list_cells` | what is loaded |
| `describe_plot_families` | the 20 summary families, marked available or missing-columns |
| `collect` | a handle, row count, columns, `is_grouped`, direction counts |
| `preview_collection` | a few rows, capped at 20 |
| `render` | writes a figure; returns trace types and points plotted |
| `export_collection` | writes csv/parquet/json; returns rows and bytes |

The cellpy API — "how does this call work, and what are its arguments":

| Tool | What it gives you |
|---|---|
| `search_api` | calls matching a name or a docstring line |
| `describe_api` | signature, argument types and defaults, docstring, `undocumented_parameters`, optionally source |

Batch templating:

| Tool | What it gives you |
|---|---|
| `list_templates` | registered and local templates, and which is the default |
| `new_project` | a project from a template; returns the notebooks it made |

Prompts: `analyse_cell`, `start_batch_project`, `explain_call`.

## Where it may read and write

Everything is confined to a set of roots, and both reads and writes are checked
— an unchecked write would make the read check decoration.

By default the roots are the directories cellpy already knows about
(`rawdatadir`, `cellpydatadir`, `outdatadir`, `notebookdir`), because you told
cellpy where your data is when you set it up. Override with `CELLPY_MCP_ROOT`,
which takes several directories separated the way `PATH` separates them:

```bash
CELLPY_MCP_ROOT=/data/cells:/data/out cellpy mcp serve
```

Roots that are not plain local directories are dropped: `rawdatadir` is often
`scp://host/…`, and containment here is `pathlib`-based and cannot express
"inside that remote share". If cellpy has no configured paths at all, the
single root is `~/cellpy_mcp` — never your whole filesystem.

## Four things it does on purpose

**Handles, not data.** Only `preview_collection` returns rows. A tool result
goes into a model's context window, and one collected summary is ~29 kB of CSV
while a raw figure can be several MB.

**Results carry the traps.** `render` returns `trace_types` alongside
`points_plotted` and `rows_collected`, so an agent that asked for a density film
can see it got `histogram2d` rather than lines, and one that forgot
`direction="both"` can see it plotted 891 of 2328 rows. `describe_api` returns
`undocumented_parameters` for the same reason: cellpy documents about half its
arguments, and a model should know when the package never said.

**It follows the docstring's own cross-references.** `CellpyCell.get_cap` takes
23 arguments, documents none, and points at
`cellpy.readers.capacity_curves.get_cap` — which documents 22 of 24. Following
that takes argument coverage across the documented API from 51% to 72%. Only a
docs site resolves those markers; nobody reading a docstring does.

**One client per process.** State is process-wide, deliberately: the MCP SDK
does not give a tool a stable session identity, and under stdio each client
spawns its own process anyway. Do not put this behind a shared HTTP endpoint as
written.

## Limits worth knowing

- `load_cell` blocks, with no progress and no cancellation, so a slow load can
  look like a hang to a client. This is the gap most worth closing.
- No quota and no eviction: an agent can fill the sandbox with figures, and
  cells stay in memory until the process exits.
- `new_project` has to create the project directory itself, because `cellpy new`
  prompts even with `no_input=True`
  ([cellpy#990](https://github.com/jepegit/cellpy/issues/990)). It also
  downloads a cookiecutter from GitHub on first use.

## Running it without cellpy's shim

`cellpy mcp serve` needs cellpy 2.2 or newer. Otherwise:

```bash
python -m cellpy_mcp serve
python -m cellpy_mcp install --dry-run
python -m cellpy_mcp status
```

## Background

The design, the measurements behind it, and a two-round prototype log are in
[cellpy#840](https://github.com/jepegit/cellpy/issues/840).

MIT licensed.
