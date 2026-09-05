"""What the server is allowed to read and write.

The caller is a language model acting on text it may have read in a file. That
is a meaningfully less trustworthy caller than a person typing a path into a
desktop app, so the boundary is not optional and every path crosses it — reads
(`load_cell`) and writes (`render`, `export_collection`, `new_project`) alike.
An unchecked write primitive would make the read check decoration.

Two things differ from the prototype this grew out of.

**Roots, plural.** The prototype had one root defaulting to `~/cellpy_mcp` —
safe, and empty, which is useless for someone whose cells are already
somewhere. But cellpy was *told* where the data is, during the setup those
users have already done. Defaulting to `config.paths` makes the server work
with no configuration at all while keeping the boundary meaningful.

**Local roots only.** `config.paths.rawdatadir` can carry a scheme — on a real
machine it is often `scp://host/…`. Containment here is `pathlib`-based and
cannot express "inside that remote share", so a root that is not a plain local
directory is dropped rather than silently treated as one.
"""

from __future__ import annotations

import os
from pathlib import Path

# Re-exported: every tool imports `Refused` from here, and the reason it is a
# `ToolError` rather than a `ValueError` is worth reading once (see `errors`).
from .errors import Refused

__all__ = ["Refused", "Sandbox", "default_roots"]


#: The `config.paths` entries a server should be able to reach. Deliberately
#: not every path cellpy knows: `filelogdir` and `db_path` are cellpy's own
#: business and nothing an agent asks for lives there.
ROOT_SETTINGS = ("rawdatadir", "cellpydatadir", "outdatadir", "notebookdir")

#: Used when cellpy has no configured paths — a fresh install, or a machine
#: where setup was never run. Not "/": a server that starts wide open and
#: relies on being configured is a server that ships wide open.
FALLBACK_ROOT = Path.home() / "cellpy_mcp"


def _is_local_dir(value: object) -> bool:
    """True when `value` names a plain local directory we can contain paths in.

    `OtherPath` stringifies to something `Path` accepts, so the check has to be
    on the *scheme*, not on whether `Path(value)` raises — it will not.
    """
    text = str(value or "").strip()
    if not text:
        return False
    # `scp://…`, `sftp://…`, `ssh://…`. A Windows drive (`C:\…`) is not a
    # scheme, hence the length guard on what precedes the colon.
    head, separator, _rest = text.partition("://")
    if separator and len(head) > 1:
        return False
    return True


def default_roots() -> list[Path]:
    """Where cellpy already keeps things, minus anything not local.

    Order is preserved and duplicates removed, because two settings routinely
    point at the same directory and a caller reading the list should not have
    to wonder whether that means something.
    """
    roots: list[Path] = []
    try:
        from cellpy import config

        paths = config.paths
    except Exception:  # noqa: BLE001 - an unconfigured cellpy is not an error here
        paths = None

    if paths is not None:
        for setting in ROOT_SETTINGS:
            value = getattr(paths, setting, None)
            if not _is_local_dir(value):
                continue
            try:
                candidate = Path(str(value)).expanduser().resolve()
            except (OSError, ValueError):
                continue
            if candidate.is_dir() and candidate not in roots:
                roots.append(candidate)

    return roots or [FALLBACK_ROOT.expanduser().resolve()]


class Sandbox:
    """A set of roots, and the only way in or out of them."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        chosen = list(roots) if roots else default_roots()
        self.roots: list[Path] = []
        for root in chosen:
            resolved = Path(root).expanduser().resolve()
            if resolved not in self.roots:
                self.roots.append(resolved)
        if not self.roots:
            raise ValueError("a sandbox needs at least one root")

    @classmethod
    def from_environment(cls, root: str | os.PathLike[str] | None = None) -> "Sandbox":
        """Roots from an explicit argument, then `CELLPY_MCP_ROOT`, then cellpy.

        `CELLPY_MCP_ROOT` takes the platform path separator, so several roots
        can be given the way `PATH` gives several.
        """
        if root:
            return cls([Path(root)])
        configured = os.environ.get("CELLPY_MCP_ROOT", "").strip()
        if configured:
            return cls([Path(part) for part in configured.split(os.pathsep) if part.strip()])
        return cls()

    @property
    def primary(self) -> Path:
        """Where something goes when the caller did not say — the first root."""
        return self.roots[0]

    def resolve(self, raw: str, *, must_exist: bool = True) -> Path:
        """Resolve a caller-supplied path inside the roots, or refuse it.

        The volume is settled from the string before any filesystem call. On
        Windows that keeps a UNC path off the network — ``Path.resolve()`` on
        ``\\\\host\\share`` asks Windows to go and find *host*, which can block
        for minutes — and a boundary that waits on a name server is one a name
        server could answer differently.
        """
        text = str(raw).strip().strip('"')
        if not text:
            raise Refused("No path given.")

        candidate = Path(text).expanduser()
        if candidate.is_absolute():
            drive = os.path.normcase(candidate.drive)
            if drive and not any(os.path.normcase(r.drive) == drive for r in self.roots):
                raise Refused(self._outside(text))
            resolved = candidate.resolve()
        else:
            # A relative path is relative to the primary root. Resolving it
            # against each root in turn would make the same string mean
            # different files depending on what happens to exist.
            resolved = (self.primary / candidate).resolve()

        if not any(resolved == root or resolved.is_relative_to(root) for root in self.roots):
            raise Refused(self._outside(text))
        if must_exist and not resolved.exists():
            raise Refused(f"{text!r} does not exist.")
        return resolved

    def _outside(self, text: str) -> str:
        """A refusal that says where the caller *could* have written instead."""
        listed = ", ".join(str(root) for root in self.roots)
        return f"{text!r} is outside the data directories. Allowed: {listed}"

    def describe(self) -> dict:
        return {"roots": [str(root) for root in self.roots]}
