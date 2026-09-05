"""Writing into someone else's configuration file.

The file holds the caller's other MCP servers. Everything here is about not
losing them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cellpy_mcp import clients

pytestmark = pytest.mark.essential


@pytest.fixture()
def target(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "client" / "claude_desktop_config.json"
    monkeypatch.setattr(clients, "config_path", lambda client=None: path)
    return path


def test_it_creates_the_file_when_there_is_none(target, tmp_path):
    written = clients.install([tmp_path])
    assert Path(written) == target
    config = json.loads(target.read_text(encoding="utf-8"))
    assert set(config["mcpServers"]) == {"cellpy"}


def test_other_servers_survive(target, tmp_path):
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "mcpServers": {"filesystem": {"command": "npx", "args": ["-y", "fs"]}},
                "theme": "dark",
            }
        ),
        encoding="utf-8",
    )

    clients.install([tmp_path])
    config = json.loads(target.read_text(encoding="utf-8"))

    assert config["mcpServers"]["filesystem"] == {"command": "npx", "args": ["-y", "fs"]}
    assert config["theme"] == "dark", "unrelated keys are not ours to drop"
    assert "cellpy" in config["mcpServers"]


def test_installing_twice_replaces_rather_than_duplicates(target, tmp_path):
    clients.install([tmp_path])
    clients.install([tmp_path / "elsewhere"])
    config = json.loads(target.read_text(encoding="utf-8"))
    assert list(config["mcpServers"]) == ["cellpy"]
    assert "elsewhere" in config["mcpServers"]["cellpy"]["env"]["CELLPY_MCP_ROOT"]


def test_an_unparseable_config_is_refused_not_overwritten(target, tmp_path):
    """The whole point of refusing: we cannot even read what we would destroy."""
    target.parent.mkdir(parents=True)
    target.write_text("{ this is not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        clients.install([tmp_path])

    assert target.read_text(encoding="utf-8") == "{ this is not json"


def test_a_dry_run_writes_nothing(target, tmp_path):
    assert clients.install([tmp_path], dry_run=True) == str(target)
    assert not target.exists()


def test_no_temporary_file_is_left_behind(target, tmp_path):
    clients.install([tmp_path])
    assert [p.name for p in target.parent.iterdir()] == [target.name]


def test_an_unknown_client_says_which_ones_it_knows():
    with pytest.raises(ValueError, match="claude-desktop"):
        clients.config_path("emacs")


def test_the_entry_names_this_interpreter(tmp_path):
    """A chat client activates no environment, so PATH cannot be relied on."""
    entry = clients.server_entry([tmp_path])
    assert entry["command"] == sys.executable
    assert entry["args"] == ["-m", "cellpy_mcp"]


def test_several_roots_travel_as_one_environment_variable(tmp_path):
    import os

    entry = clients.server_entry([tmp_path / "a", tmp_path / "b"])
    assert entry["env"]["CELLPY_MCP_ROOT"].count(os.pathsep) == 1


# -- more than one client (#1) ---------------------------------------------------


@pytest.mark.parametrize("client", sorted(clients.CLIENTS))
def test_every_client_resolves_to_a_plausible_path(client):
    """A path that is relative, or lands on `/`, would write somewhere strange."""
    path = clients.config_path(client)
    assert path.is_absolute()
    assert path.suffix == ".json"
    assert path.parent != path.anchor


def test_vscode_uses_its_own_key(tmp_path, monkeypatch):
    """The trap that fails silently.

    VS Code reads `servers`; everyone else reads `mcpServers`. Writing the
    wrong one produces a file that parses, saves, and does nothing — no error
    anywhere, and the user is left believing they registered.
    """
    target = tmp_path / "vscode" / "mcp.json"
    monkeypatch.setattr(clients, "config_path", lambda client=None: target)

    clients.install([tmp_path], client="vscode")
    config = json.loads(target.read_text(encoding="utf-8"))

    assert "servers" in config
    assert "cellpy" in config["servers"]
    assert "mcpServers" not in config


def test_the_others_use_mcpservers(tmp_path, monkeypatch):
    for client in ("claude-desktop", "cursor"):
        target = tmp_path / client / "config.json"
        monkeypatch.setattr(clients, "config_path", lambda client=None, t=target: t)
        clients.install([tmp_path], client=client)
        config = json.loads(target.read_text(encoding="utf-8"))
        assert "cellpy" in config["mcpServers"], client
        assert "servers" not in config, client


def test_an_existing_vscode_file_keeps_its_other_servers(tmp_path, monkeypatch):
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps({"servers": {"playwright": {"command": "npx"}}, "inputs": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(clients, "config_path", lambda client=None: target)

    clients.install([tmp_path], client="vscode")
    config = json.loads(target.read_text(encoding="utf-8"))

    assert config["servers"]["playwright"] == {"command": "npx"}
    assert config["inputs"] == []
    assert "cellpy" in config["servers"]


def test_claude_code_is_not_written_to_but_is_answered(tmp_path):
    """Its servers share a file with the sign-in session and trust decisions.

    Refusing to edit that is the point — but a refusal that does not say what
    to do instead just moves the problem, so the message carries the command.
    """
    with pytest.raises(ValueError) as raised:
        clients.config_path("claude-code")

    message = str(raised.value)
    assert "claude mcp add" in message

    command = clients.command_for("claude-code", [tmp_path])
    assert command.startswith("claude mcp add cellpy")
    assert "CELLPY_MCP_ROOT=" in command
    assert "-m cellpy_mcp" in command


def test_installing_into_one_client_does_not_touch_another(tmp_path, monkeypatch):
    """Each client has its own file; registering with Cursor is not a VS Code edit."""
    cursor = tmp_path / "cursor.json"
    vscode = tmp_path / "vscode.json"
    paths = {"cursor": cursor, "vscode": vscode}
    monkeypatch.setattr(clients, "config_path", lambda client=None: paths[client])

    clients.install([tmp_path], client="cursor")

    assert cursor.exists()
    assert not vscode.exists()
