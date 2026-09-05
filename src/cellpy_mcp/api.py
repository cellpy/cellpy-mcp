"""Answering "how does this cellpy call work" from the installed package.

The observation this family exists for: people do not read API documentation.
No amount of rewriting fixes it, because the cost was never the reading — it is
knowing a page exists, finding it, and trusting that it describes the version
installed. A tool call removes all three.

What it cannot do is invent documentation that was never written. Measured over
the 44 calls in cellpy's own API reference against cellpy 2.1.3:

    no docstring at all                                3
    one-line docstring                                13
    has an Args:/Parameters: section            14 of 44
    parameters named in their own docstring   100 of 195   (51%)

`CellpyCell.get_cap` takes 23 arguments and documents none of them, so a tool
that returned the docstring and stopped would answer half its questions with a
sentence and a shrug — and, worse, let a model fill the silence. Three things
follow, and they are the design:

1. The *signature* is always there. Names, annotations and especially defaults
   survive when prose does not, so they are returned structured rather than
   rendered into one string.
2. `undocumented_parameters` is returned explicitly. Same principle as
   `render`'s `trace_types`: the result carries the trap, so a model that would
   otherwise guess at `categorical_column=` can see the package never said.
3. `include_source` exists because a model reads Python well. It is the honest
   fallback for the thin half, and the one thing a chat user cannot do for
   themselves — they will not be grepping site-packages.
"""

from __future__ import annotations

import re
from typing import Any

from .sandbox import Refused

__all__ = ["register"]

#: Import is execution, and the caller is a language model acting on text it
#: may have read in a file. `describe_api("os.system")` must not become a way
#: to import arbitrary modules, so resolution is confined to these roots.
API_ROOTS = ("cellpy", "cellpycore")

#: Modules the index covers. Walking a package imports every submodule it finds
#: — including optional loaders whose third-party dependencies are absent — so
#: the list is written down rather than discovered.
API_MODULES = (
    "cellpy",
    "cellpy.collect",
    "cellpy.config",
    "cellpy.plotting",
    "cellpy.plotting.registry",
    "cellpy.readers.capacity_curves",
    "cellpy.readers.cellreader",
    "cellpy.exporters.tabular",
    "cellpy.utils.batch",
    "cellpy.utils.example_data",
    "cellpy.utils.helpers",
    "cellpy.utils.ica",
)

#: Docstrings can be long (`Collection.plot` is 24 lines) and a tool result is
#: context. Long enough for an Args: section, short enough not to be the reply.
MAX_DOC_CHARS = 4000
MAX_SOURCE_LINES = 200

#: ``See :func:`cellpy.readers.capacity_curves.get_cap` `` — cellpy 2.1.3 and
#: earlier, and anything written to Sphinx conventions.
_ROLE_REFERENCE = re.compile(r":(?:func|meth|obj|class):`~?([\w.]+)`")

#: ``See `get_cap`.`` — what cellpy 2.1.3.post2 leaves behind. The negative
#: lookbehind keeps this from also matching the tail of a role reference.
_BARE_REFERENCE = re.compile(r"(?<![:`\w])`~?([\w.]+)`")


def _is_class_member(path: str) -> bool:
    """True for `module.Class.method`, false for `module.function`.

    cellpy has no capitalised module names, so a capitalised segment before the
    last one means the entry hangs off a class.
    """
    parts = path.split(".")
    return len(parts) > 1 and parts[-2][:1].isupper()


def resolve_dotted(path: str) -> Any:
    """Import as far as the path allows, then getattr the rest — inside API_ROOTS."""
    import importlib

    if path.split(".")[0] not in API_ROOTS:
        joined = " and ".join(API_ROOTS)
        raise Refused(f"{path!r} is not part of cellpy. This tool only describes {joined}.")

    parts = path.split(".")
    for split in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        try:
            for attr in parts[split:]:
                obj = getattr(obj, attr)
        except AttributeError:
            continue
        return obj
    raise Refused(f"Nothing called {path!r} in cellpy.")


def follow_reference(doc: str, index: list[dict] | None = None) -> tuple[str | None, str]:
    """Resolve a cross-reference in `doc` to the docstring it points at.

    This is the single biggest win in the family, and it is worth saying why.
    `CellpyCell.get_cap` takes 23 arguments, documents none of them, and spends
    its whole docstring pointing at `cellpy.readers.capacity_curves.get_cap`.
    The delegate documents 22 of its 24 in a full ``Args:`` block. `to_csv`
    (9 arguments) and `to_excel` (7) are the same shape.

    So the documentation is not missing — it is one hop away, behind a marker
    that only a docs *site* resolves. Everywhere a docstring is actually met —
    an IDE tooltip, `help()`, a chat window, an agent — the reader gets the
    pointer and not the text.

    **Two spellings, because cellpy changed one.** Up to 2.1.3 these were
    Sphinx roles: ``See :func:`cellpy.readers.capacity_curves.get_cap```. In
    2.1.3.post2 the roles were stripped to stop them leaking into the rendered
    API docs, which also stripped the module path — `get_cap`'s docstring is
    now ``See `get_cap`.`` So a bare name is resolved through the index, and
    accepted only when it lands on a *different* object with its own docstring.
    `delegates_to` is always returned alongside `delegate_doc`, so the caller
    can see exactly which call the text came from rather than trusting a guess.
    """
    import inspect

    candidates: list[str] = []
    role = _ROLE_REFERENCE.search(doc)
    if role:
        candidates.append(role.group(1))
    candidates.extend(_BARE_REFERENCE.findall(doc))

    for target in candidates:
        if "." in target:
            if target.split(".")[0] not in API_ROOTS:
                continue
            try:
                referenced = resolve_dotted(target)
            except Exception:  # noqa: BLE001 - a dead reference is not an error
                continue
            path = target
        else:
            # A bare name, and the index is the only thing that can say what it
            # means. Restricted to *module-level* functions, which is both the
            # shape cellpy's delegation actually takes — a thin method calling
            # the real implementation — and what keeps `get_cap` from matching
            # the very method whose docstring we are reading.
            matches = [
                entry
                for entry in (index or [])
                if entry["name"] == target and not _is_class_member(entry["path"])
            ]
            if len(matches) != 1:
                # Nothing, or still ambiguous. Guessing between two calls would
                # attach someone else's arguments to this one.
                continue
            path = matches[0]["path"]
            try:
                referenced = resolve_dotted(path)
            except Exception:  # noqa: BLE001
                continue

        referenced_doc = inspect.getdoc(referenced) or ""
        # A reference resolving back to the same text says nothing.
        if not referenced_doc or referenced_doc == doc:
            continue
        return path, referenced_doc

    return None, ""


def summarise(doc: str) -> str:
    """The first line of a docstring that says something.

    `CellpyCell.set_mass` opens with a bare ``Warning:``, so taking line one
    verbatim produces an index in which several unrelated calls are described
    as "Warning:". A heading is carried into the line below it instead.
    """
    lines = [line.strip() for line in doc.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    first = lines[0]
    if first.endswith(":") and len(first) < 24 and len(lines) > 1:
        return f"{first} {lines[1]}"
    return first


def build_index() -> list[dict]:
    """Every public callable in API_MODULES, one path each.

    Re-exports are the norm in cellpy: `get` is reachable as `cellpy.get` and
    `cellpy.readers.cellreader.get`, and `utils.helpers` re-exports
    `CellpyCell` — which is how the first version of this answered "get_cap"
    with `cellpy.utils.helpers.CellpyCell.get_cap`, a true path that sends the
    reader to the wrong file. So index by object identity and keep the shortest
    path, because that is the one people type, breaking ties toward the module
    that actually defines it.
    """
    import importlib
    import inspect

    best: dict[int, tuple[tuple[int, int], str, Any]] = {}

    def offer(path: str, entity: Any) -> None:
        home = getattr(entity, "__module__", "") or ""
        rank = (len(path.split(".")), 0 if path.startswith(home) else 1)
        current = best.get(id(entity))
        if current is None or rank < current[0]:
            best[id(entity)] = (rank, path, entity)

    for module_name in API_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 - a module that will not import is not an error
            continue
        for name, obj in vars(module).items():
            if name.startswith("_") or not callable(obj):
                continue
            # Anything that merely passed through from outside cellpy (pandas,
            # pathlib) is not ours to describe.
            if not (getattr(obj, "__module__", "") or "").startswith(API_ROOTS):
                continue
            offer(f"{module_name}.{name}", obj)
            if isinstance(obj, type):
                for attr in vars(obj):
                    member = getattr(obj, attr, None)
                    if not attr.startswith("_") and callable(member):
                        offer(f"{module_name}.{name}.{attr}", member)

    entries = [
        {"path": path, "name": path.rsplit(".", 1)[-1], "summary": summarise(inspect.getdoc(entity) or "")}
        for _rank, path, entity in best.values()
    ]
    entries.sort(key=lambda entry: entry["path"])
    return entries


def register(server, state) -> None:
    def index() -> list[dict]:
        if state.api_index is None:
            state.api_index = build_index()
        return state.api_index

    @server.tool()
    def search_api(query: str, limit: int = 15) -> dict:
        """Find cellpy calls by name, or by what their first docstring line says.

        Use this when you know the task but not the call — "average cycles",
        "loading", "mass". `describe_api` then gives the arguments.
        """
        if not query.strip():
            raise Refused("Give something to search for.")
        needle = query.strip().lower()
        limit = max(1, min(int(limit), 50))

        scored: list[tuple[int, dict]] = []
        for entry in index():
            name = entry["name"].lower()
            if needle == name:
                score = 0
            elif needle in name:
                score = 1
            elif needle in entry["path"].lower():
                score = 2
            elif needle in entry["summary"].lower():
                score = 3
            else:
                continue
            scored.append((score, entry))

        scored.sort(key=lambda pair: (pair[0], len(pair[1]["path"])))
        return {
            "query": query,
            "indexed": len(index()),
            "matches": [entry for _score, entry in scored[:limit]],
            "truncated": len(scored) > limit,
        }

    @server.tool()
    def describe_api(name: str, include_source: bool = False) -> dict:
        """What a cellpy call takes and what it does, from the installed package.

        `name` is a dotted path (`cellpy.get`, `cellpy.collect.collect_summary`)
        or a bare name (`get_cap`) looked up in the index.

        Read `undocumented_parameters` before answering a question about one of
        them. cellpy documents roughly half its arguments, so an argument
        missing from `doc` means the package never said what it does — not that
        it does not matter. Ask again with `include_source=True` rather than
        guessing.

        When `delegates_to` is set, the docstring pointed at another call with a
        Sphinx reference and `delegate_doc` is where the arguments are actually
        described — read it, it is usually the real documentation.
        """
        import inspect

        if "." in name:
            # A dotted path is a request to import. `resolve_dotted` is the
            # guard, so send every dotted name through it rather than falling
            # back to the index and reporting "no such cellpy call" for
            # `os.system` — true, but the wrong reason, and the wrong reason
            # teaches the caller that a different spelling might work.
            path = name
            obj = resolve_dotted(path)
        else:
            matches = [entry for entry in index() if entry["name"] == name]
            if not matches:
                hits = search_api(name, limit=5)["matches"]
                suffix = ""
                if hits:
                    suffix = " Did you mean: " + ", ".join(h["path"] for h in hits) + "?"
                raise Refused(f"No cellpy call called {name!r}.{suffix}")
            # Prefer how people actually call it. `get_cap` names both
            # `CellpyCell.get_cap` and the module-level `capacity_curves.get_cap`
            # it delegates to; someone asking about "get_cap" means the one they
            # would write as `cell.get_cap(...)`, and the delegate's arguments
            # arrive anyway through `delegates_to`.
            matches.sort(key=lambda entry: (not _is_class_member(entry["path"]), len(entry["path"])))
            path = matches[0]["path"]
            obj = resolve_dotted(path)

        doc = inspect.getdoc(obj) or ""
        delegate_path, delegate_doc = follow_reference(doc, index())
        # A parameter counts as documented if *either* docstring names it.
        searchable = doc + "\n" + delegate_doc

        if isinstance(obj, type):
            kind = "class"
        elif isinstance(obj, property):
            kind = "property"
        else:
            kind = "function"

        target = obj.fget if isinstance(obj, property) else obj
        parameters: list[dict] = []
        signature_text = None
        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            # Methods are shown as you would call them. Leaving `self` in the
            # rendered signature invites a model to pass it as an argument.
            rendered = str(signature)
            if rendered.startswith("(self, "):
                rendered = "(" + rendered[len("(self, ") :]
            elif rendered == "(self)":
                rendered = "()"
            signature_text = f"{path.rsplit('.', 1)[-1]}{rendered}"

            empty = inspect.Parameter.empty
            for pname, parameter in signature.parameters.items():
                if pname in ("self", "cls"):
                    continue
                variadic = (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
                parameters.append(
                    {
                        "name": pname,
                        "annotation": (
                            None if parameter.annotation is empty else str(parameter.annotation)
                        ),
                        "default": (
                            None if parameter.default is empty else repr(parameter.default)
                        ),
                        "required": parameter.default is empty
                        and parameter.kind not in variadic,
                        "documented": bool(re.search(rf"\b{re.escape(pname)}\b", searchable)),
                    }
                )

        result: dict[str, Any] = {
            "path": path,
            "kind": kind,
            "module": getattr(obj, "__module__", None),
            "signature": signature_text,
            "parameters": parameters,
            "doc": doc[:MAX_DOC_CHARS] + ("…" if len(doc) > MAX_DOC_CHARS else ""),
            # The trap, carried in the result rather than left to be discovered.
            "undocumented_parameters": [p["name"] for p in parameters if not p["documented"]],
        }
        if delegate_path:
            result["delegates_to"] = delegate_path
            result["delegate_doc"] = delegate_doc[:MAX_DOC_CHARS] + (
                "…" if len(delegate_doc) > MAX_DOC_CHARS else ""
            )
        if include_source:
            try:
                source = inspect.getsource(target)
            except (OSError, TypeError) as exc:
                result["source_error"] = str(exc)
            else:
                lines = source.splitlines()
                result["source"] = "\n".join(lines[:MAX_SOURCE_LINES])
                result["source_truncated"] = len(lines) > MAX_SOURCE_LINES
        return result
