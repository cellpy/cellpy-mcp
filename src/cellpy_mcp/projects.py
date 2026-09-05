"""Batch templating — `cellpy new` for people who will not open a terminal.

`cellpy new` is the front door to the batch workflow and it is a CLI command,
which puts it behind a terminal for exactly the users who most need a template.
Wrapping it is therefore worth more than it looks — but it is a *write*
primitive that creates a directory tree and downloads a cookiecutter, so it gets
the same sandbox as `render` and `export_collection`.

**`cellpy new` cannot currently be automated**, and this is why the code below
looks the way it does. Measured against cellpy 2.1.3:
`create_project(..., no_input=True)` is *not* non-interactive. When the project
directory does not exist, `cli_api.py:1601` calls
`cookiecutter.prompt.read_user_yes_no("… Create?")` unconditionally — outside
the `no_input` guard — and a server has no stdin to answer with. Under stdio it
does not even hang usefully: it raises `ValueError: I/O operation on closed
file`.

So `new_project` creates the directory itself and then calls in, which skips
that branch and completes with no prompt at all. The upstream fix is one line
(jepegit/cellpy#990); until it lands, this workaround is the whole reason the
tool works.
"""

from __future__ import annotations

from .sandbox import Refused

__all__ = ["register"]


def register(server, sandbox) -> None:
    @server.tool()
    def list_templates() -> dict:
        """Batch templates available for `new_project`, registered and local.

        `cellpy new --list` prints this and returns nothing, so this reads the
        registry directly (jepegit/cellpy#991 asks for a library form).
        """
        from cellpy import cli_api
        from cellpy.utils.template_registry import REGISTERED_TEMPLATES

        try:
            default = str(cli_api._get_default_template())
        except Exception as exc:  # noqa: BLE001 - report it, do not fail the call
            default = f"unknown ({exc})"

        try:
            local = {
                name: str(link)
                for name, link in (cli_api._read_local_templates() or {}).items()
            }
        except Exception:  # noqa: BLE001
            local = {}

        return {
            "default": default,
            "registered": sorted(REGISTERED_TEMPLATES),
            "local": sorted(local),
        }

    @server.tool()
    def new_project(
        project: str,
        experiment: str,
        template: str | None = None,
        directory: str | None = None,
    ) -> dict:
        """Create a batch project from a template — the `cellpy new` workflow.

        `project` is the folder, `experiment` the lookup value; the template
        dates the experiment folder itself, so `experiment="exp001"` becomes
        something like `2026_09_05_exp001`. Writes inside the data directories
        only.

        Downloads the cookiecutter from GitHub on first use.
        """
        from cellpy import cli_api

        if not project.strip() or not experiment.strip():
            raise Refused("Both a project name and an experiment name are needed.")
        for value in (project, experiment):
            if "/" in value or "\\" in value or value.strip() in (".", ".."):
                raise Refused(f"{value!r} is not a folder name.")

        base = sandbox.resolve(directory) if directory else sandbox.primary
        target = sandbox.resolve(str(base / project), must_exist=False)
        existed = target.is_dir()
        # See the module docstring: creating it here is what keeps `cellpy new`
        # from asking a question the server cannot answer.
        target.mkdir(parents=True, exist_ok=True)

        before = {entry.name for entry in target.iterdir()}
        try:
            cli_api.create_project(
                template,
                directory=str(base),
                project=project,
                experiment=experiment,
                no_input=True,
            )
        except Exception as exc:  # noqa: BLE001 - the model should read the reason
            if not existed and not any(target.iterdir()):
                target.rmdir()
            raise Refused(f"Could not create the project: {type(exc).__name__}: {exc}")

        created = sorted({entry.name for entry in target.iterdir()} - before)
        notebooks = sorted(
            str(path.relative_to(target)) for path in target.rglob("*.ipynb")
        )
        return {
            "project_dir": str(target),
            "created": created,
            "notebooks": notebooks,
            "template": template or "default",
            # A chat user cannot be left with a folder and no next step.
            "next_step": f"cellpy serve --directory {target}",
        }
