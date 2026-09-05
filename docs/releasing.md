# Releasing

`cellpy-mcp` publishes to PyPI from
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml), on a tag.

The package uses **trusted publishing** (OIDC): GitHub proves the workflow's
identity to PyPI directly, so there is **no API token** to create, store,
rotate, or leak. Nothing secret is ever put in this repository. The trade is
that PyPI has to be told, once, which repository and which workflow file it
trusts.

Same arrangement as `cellpy` and `cellpy-simple-gui`, deliberately.

## One-time: let PyPI trust this repository

The project does not exist on PyPI yet, so this is registered as a **pending
publisher** — which also reserves the name without uploading anything.

1. Sign in to <https://pypi.org>.
2. Go to *Your account* → *Publishing*.
3. Under *Add a new pending publisher*, choose **GitHub** and fill in:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `cellpy-mcp` |
   | Owner | `cellpy` |
   | Repository name | `cellpy-mcp` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The owner is the **GitHub org**, not your PyPI username.

4. Repeat on <https://test.pypi.org> with environment name `testpypi`, so a
   release can be rehearsed before it is permanent.

5. In this repository: GitHub → *Settings* → *Environments* → *New environment*
   → `pypi`, and again for `testpypi`. Leaving them unprotected is fine; the
   names are what matter.

> **Why the environment name matters.** PyPI checks it. If the workflow's
> `environment:` and the pending publisher disagree, the upload is rejected with
> an OIDC error that does not say which of the two is wrong.

Both names were free when this was written (checked 2026-09-05); if the pending
publisher form says otherwise, stop and work out who owns it before renaming
anything.

## Rehearse on TestPyPI

Worth doing for the first release, because the failure modes are all one-way.

1. Actions → *Publish to PyPI* → *Run workflow*, target `testpypi`.
2. Confirm `build` and `publish (TestPyPI)` are green and `publish (PyPI)` is
   skipped.
3. Install it somewhere clean and check the thing actually runs:

   ```bash
   uv run --with cellpy-mcp --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ python -m cellpy_mcp status
   ```

   The second index is not optional: TestPyPI does not carry cellpy.

## Cutting a release

1. Bump `__version__` in [`src/cellpy_mcp/__init__.py`](../src/cellpy_mcp/__init__.py).
   It is the single source — `pyproject.toml` reads it through
   `[tool.hatch.version]`, so metadata and `__version__` cannot disagree.
2. Commit, merge to `main`.
3. Tag and push:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. Watch Actions. `build` checks that the tag matches `__version__`, runs the
   tests, then builds and inspects the wheel; `publish (PyPI)` uploads.

## What to check afterwards

- <https://pypi.org/project/cellpy-mcp/> renders the README.
- `pip install cellpy-mcp` then `python -m cellpy_mcp status` prints roots.
- With cellpy 2.2 or newer, `cellpy mcp status` reports the installed version
  rather than telling you to install it — that path is the reason the contract
  in `__init__.py` is pinned by `tests/test_contract.py`.

## Things that will bite

- **A version can never be reused.** Not after deleting the release, not after
  yanking it. A bad `0.1.0` means `0.1.1`, so rehearse on TestPyPI.
- **Renaming `publish.yml` or an environment breaks publishing**, because the
  pending publisher names both. Update PyPI in the same change.
- **The tag is the version.** `build` refuses a tag that disagrees with
  `__version__` rather than shipping a mislabelled wheel.
- **cellpy is a hard dependency.** Anyone installing this gets cellpy and its
  dependency tree; that is intended, and it is why the MCP SDK lives here rather
  than in cellpy.
