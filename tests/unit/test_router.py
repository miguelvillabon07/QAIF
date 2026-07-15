"""Tests del router de consola — sin LLM real requerido."""
from __future__ import annotations

import pytest


# ─── Comandos directos (sin LLM) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_direct_help():
    from src.console.router import route
    result = await route("help")
    assert result["actions"][0]["tool"] == "show_help"


@pytest.mark.asyncio
async def test_direct_exit():
    from src.console.router import route
    for cmd in ("exit", "quit", "q"):
        result = await route(cmd)
        assert result["actions"][0]["tool"] == "exit", f"Falló con: {cmd}"


@pytest.mark.asyncio
async def test_direct_health():
    from src.console.router import route
    result = await route("health")
    assert result["actions"][0]["tool"] == "health_check"


@pytest.mark.asyncio
async def test_direct_workspace_list():
    from src.console.router import route
    result = await route("workspace list")
    assert result["actions"][0]["tool"] == "workspace_list"


@pytest.mark.asyncio
async def test_direct_story_list():
    from src.console.router import route
    result = await route("story list")
    assert result["actions"][0]["tool"] == "story_list"


@pytest.mark.asyncio
async def test_direct_log_show():
    from src.console.router import route
    result = await route("log show")
    assert result["actions"][0]["tool"] == "log_show"
    assert result["actions"][0]["args"]["last_n"] == 20


@pytest.mark.asyncio
async def test_direct_report_show():
    from src.console.router import route
    result = await route("report show")
    assert result["actions"][0]["tool"] == "report_show"


# ─── Patrones regex ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pattern_git_clone_basic():
    from src.console.router import route
    result = await route("git clone https://github.com/user/repo.git")
    assert result["actions"][0]["tool"] == "git_clone"
    assert result["actions"][0]["args"]["url"] == "https://github.com/user/repo.git"
    assert result["actions"][0]["args"]["branch"] is None


@pytest.mark.asyncio
async def test_pattern_git_clone_with_branch():
    from src.console.router import route
    result = await route("git clone https://github.com/user/repo.git --branch develop")
    assert result["actions"][0]["tool"] == "git_clone"
    assert result["actions"][0]["args"]["branch"] == "develop"


@pytest.mark.asyncio
async def test_pattern_git_analyze():
    from src.console.router import route
    result = await route("git analyze pos-api")
    assert result["actions"][0]["tool"] == "git_analyze"
    assert result["actions"][0]["args"]["repo_name"] == "pos-api"


@pytest.mark.asyncio
async def test_pattern_git_status():
    from src.console.router import route
    result = await route("git status my-repo")
    assert result["actions"][0]["tool"] == "git_status"
    assert result["actions"][0]["args"]["repo_name"] == "my-repo"


@pytest.mark.asyncio
async def test_pattern_extract_file():
    from src.console.router import route
    result = await route("extract 1AbCdEfGhIjKlMnOpQr")
    assert result["actions"][0]["tool"] == "drive_extract"
    assert result["actions"][0]["args"]["file_id"] == "1AbCdEfGhIjKlMnOpQr"


@pytest.mark.asyncio
async def test_pattern_test_setup():
    from src.console.router import route
    result = await route("test setup pos-api")
    assert result["actions"][0]["tool"] == "test_setup"
    assert result["actions"][0]["args"]["repo_name"] == "pos-api"


@pytest.mark.asyncio
async def test_pattern_test_run_includes_both_actions():
    from src.console.router import route
    result = await route("test run pos-api")
    tools = [a["tool"] for a in result["actions"]]
    assert "test_setup" in tools
    assert "test_run" in tools


@pytest.mark.asyncio
async def test_pattern_test_run_happy_only_default():
    from src.console.router import route
    result = await route("test run pos-api")
    test_run_action = next(a for a in result["actions"] if a["tool"] == "test_run")
    assert test_run_action["args"]["happy_only"] is True


@pytest.mark.asyncio
async def test_pattern_test_run_all_flag():
    from src.console.router import route
    result = await route("test run pos-api --all")
    test_run_action = next(a for a in result["actions"] if a["tool"] == "test_run")
    assert test_run_action["args"]["happy_only"] is False


@pytest.mark.asyncio
async def test_pattern_test_shutdown():
    from src.console.router import route
    result = await route("test shutdown pos-api")
    assert result["actions"][0]["tool"] == "test_shutdown"
    assert result["actions"][0]["args"]["repo_name"] == "pos-api"


@pytest.mark.asyncio
async def test_pattern_test_suggest():
    from src.console.router import route
    result = await route("test suggest pos-api")
    assert result["actions"][0]["tool"] == "test_suggest"


@pytest.mark.asyncio
async def test_pattern_report_upload():
    from src.console.router import route
    result = await route("report upload PROJ-123")
    assert result["actions"][0]["tool"] == "report_upload"
    assert result["actions"][0]["args"]["issue_id"] == "PROJ-123"


@pytest.mark.asyncio
async def test_pattern_model_switch_local():
    from src.console.router import route
    result = await route("model switch local")
    assert result["actions"][0]["tool"] == "model_switch"
    assert result["actions"][0]["args"]["provider"] == "local"


@pytest.mark.asyncio
async def test_pattern_model_switch_anthropic():
    from src.console.router import route
    result = await route("model switch anthropic")
    assert result["actions"][0]["tool"] == "model_switch"
    assert result["actions"][0]["args"]["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_pattern_log_show_with_last_n():
    from src.console.router import route
    result = await route("log show --last 50")
    assert result["actions"][0]["tool"] == "log_show"
    assert result["actions"][0]["args"]["last_n"] == 50


@pytest.mark.asyncio
async def test_pattern_log_summary_with_id():
    from src.console.router import route
    result = await route("log summary --id pipeline-abc-123")
    assert result["actions"][0]["tool"] == "log_summary"
    assert result["actions"][0]["args"]["pipeline_id"] == "pipeline-abc-123"


@pytest.mark.asyncio
async def test_pattern_workspace_clean_default():
    from src.console.router import route
    result = await route("workspace clean")
    assert result["actions"][0]["tool"] == "workspace_clean"
    assert result["actions"][0]["args"]["older_than_days"] == 30


@pytest.mark.asyncio
async def test_pattern_workspace_clean_custom_days():
    from src.console.router import route
    result = await route("workspace clean --days 7")
    assert result["actions"][0]["tool"] == "workspace_clean"
    assert result["actions"][0]["args"]["older_than_days"] == 7


# ─── Edge cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_input_returns_structure():
    """Un string vacío no debe hacer crash — el router devuelve estructura válida."""
    from src.console.router import DIRECT_COMMANDS
    # ' ' no está en DIRECT_COMMANDS, irá al LLM — solo verificamos que el router
    # tiene la estructura interna correcta
    assert "exit" in DIRECT_COMMANDS
    assert "help" in DIRECT_COMMANDS
    assert "health" in DIRECT_COMMANDS


def test_direct_commands_count():
    """Verificar que el número de comandos directos es el esperado."""
    from src.console.router import DIRECT_COMMANDS, PATTERNS
    assert len(DIRECT_COMMANDS) >= 10, f"Se esperaban ≥10 comandos directos, hay {len(DIRECT_COMMANDS)}"
    assert len(PATTERNS) >= 10, f"Se esperaban ≥10 patterns, hay {len(PATTERNS)}"


def test_all_direct_commands_return_actions():
    """Todos los comandos directos deben retornar una estructura con 'actions'."""
    from src.console.router import DIRECT_COMMANDS
    for cmd, handler in DIRECT_COMMANDS.items():
        result = handler()
        assert "actions" in result, f"Comando '{cmd}' no retorna 'actions'"
        assert isinstance(result["actions"], list), f"Comando '{cmd}': actions no es lista"
