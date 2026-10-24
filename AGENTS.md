<!-- BEGIN issue-flow (managed: do not edit this block) -->
# Issue-flow

This project tracks GitHub issues with issue-flow. Each `iflow-*` skill holds its own instructions; read a skill only when it is invoked.

## Running Python

Follow the project's documented toolchain (README, `AGENTS.md`, `pyproject.toml`, `environment.yml`, CI). Never call bare `python`: use the project's runner (`uv run …` by default, `conda run -n <env> …` for conda projects, `poetry run …` for poetry). In a uv project, manage dependencies with `uv add` / `uv remove` / `uv sync`, not `pip`.

## Tracking layout

Under `.issueflows/`:

- `00-tools/` — reusable helper scripts; `README.md` is the index. Check it before writing a one-off helper, and add useful tools back.
- `01-current-issues/` — the focus issue only: `issue<N>_original.md`, `issue<N>_plan.md`, `issue<N>_status.md`.
- `02-partly-solved-issues/` — parked work. `03-solved-issues/` — finished work.
- `04-designs-and-guides/` — durable design docs; `this-project.md` is the project brief.
- `05-epics/` — staged epic plans (`epic<N>_plan.md`).

- After each iteration, update `issue<N>_status.md` (done, current state, remaining work) with an explicit checkbox: `- [x] Done` when fully resolved, `- [ ] Done` otherwise. Other steps route files by that checkbox.
- Finished issues move to `03-solved-issues/`, unfinished ones to `02-partly-solved-issues/`.
- Before planning or building, read `04-designs-and-guides/this-project.md` if present and skim `04-designs-and-guides/` for relevant docs. Record non-trivial design decisions there (context, decision, alternatives, issue link).

## Commands

Invoke as `/iflow-<step>` or in chat as `iflow <step> [args]` (also `iflow-<step>` or `/iflow <step>`). A message that **starts with** one of these forms invokes the `iflow-<step>` skill with the trailing text as its arguments; plain `iflow` runs the dispatcher. Mid-sentence mentions are not invocations.

| Command | Purpose |
|---|---|
| `iflow` | Dispatcher: run the next of capture / plan / build / close. |
| `iflow-setup` | Get a project ready (uv, git, GitHub, scaffold). |
| `iflow-pick` | Choose an issue, branch, and capture it. |
| `iflow-plan` | Write the plan and stop for approval. |
| `iflow-build` | Implement the approved plan. |
| `iflow-pause` | Park unfinished work with resume notes. |
| `iflow-close` | Tests, bump, changelog trailers, commit, push, PR. |
| `iflow-cleanup` | After merge: default branch, pull, delete landed branches. |
| `iflow-run` | Hands-off runs under one up-front confirm. |
| `iflow-issue` | Create and shape GitHub issues. |
| `iflow-status` | Read-only overview of every issue. |
The core loop is `pick → plan → build → close → cleanup`. `/iflow` detects the focus issue's state and dispatches to the next of capture / plan / build / close; it never dispatches to any other command. Never skip the plan confirmation in `/iflow-plan` unless a hands-off mode was confirmed.

Issue labels can route `/iflow-pick`: `yolo` → `/iflow-run yolo`, `ops` → no-PR close (ops wins over yolo). A `publish` label makes `/iflow-close` bump the version and release after merge.

## Branch hygiene

- Work on an issue branch `<N>-<short-slug>`, never on the default branch.
- Before continuing a branch, run `git fetch --prune` and check ahead/behind against `origin/<default>`. PRs are **squash**-merged, so a merged branch looks "ahead" and is stale.
- After a PR merges, remind the user to run `/iflow-cleanup`. Do not run it automatically.
- An issue already under `02-partly-solved-issues/` or `03-solved-issues/` has a stale branch. Re-open it only on purpose with `/iflow-pick <N>`.

## Multi-repo workspaces

When the workspace holds several repos with their own `.issueflows/`, resolve the target repo first (`root:` / `repo:` hints, then `issue-flow agent resolve`, then the `issueflow-workspace.toml` default); ask when ambiguous. Pass `--repo <owner/repo>` to every `gh` call. Lifecycle state is per repository.

## Optional skills

- **caveman** — terse response style. Off until the user asks ("caveman", "be terse"). Off with "stop caveman" / "normal mode". Code, commits, PRs, security warnings, and destructive-action confirmations are always normal prose.
- **grill-me** — relentless one-question-at-a-time planning interview. Off until the user asks ("grill me"). Off with "stop grilling".

## Knowledge graph

If `graphify-out/GRAPH_REPORT.md` exists, skim it before grepping. Run `graphify query` / `path` / `explain` only when `graphify-out/graph.json` exists. `/iflow-status graph` rebuilds the graph; nothing runs it automatically.


<!-- END issue-flow (managed) -->
