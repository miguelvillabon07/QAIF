"""Router LLM para interpretar comandos de la consola."""
from __future__ import annotations

import json
import re

from src.llm.factory import get_llm
from src.utils.logging_config import get_logger

from .prompts import CONSOLE_ROUTER_PROMPT

logger = get_logger("console.router")


# ── Comandos directos que NO necesitan LLM ──────────────────────────────────
DIRECT_COMMANDS: dict[str, callable] = {
    "exit": lambda: {"actions": [{"tool": "exit", "args": {}}], "message": "Saliendo..."},
    "quit": lambda: {"actions": [{"tool": "exit", "args": {}}], "message": "Saliendo..."},
    "q": lambda: {"actions": [{"tool": "exit", "args": {}}], "message": "Saliendo..."},
    "help": lambda: {"actions": [{"tool": "show_help", "args": {}}], "message": ""},
    "h": lambda: {"actions": [{"tool": "show_help", "args": {}}], "message": ""},
    "health": lambda: {"actions": [{"tool": "health_check", "args": {}}], "message": "Verificando servicios..."},
    "workspace list": lambda: {"actions": [{"tool": "workspace_list", "args": {}}], "message": ""},
    "extract --list": lambda: {"actions": [{"tool": "drive_list", "args": {}}], "message": "Listando Drive..."},
    "drive list": lambda: {"actions": [{"tool": "drive_list", "args": {}}], "message": "Listando Drive..."},
    "story list": lambda: {"actions": [{"tool": "story_list", "args": {}}], "message": ""},
    "story create": lambda: {"actions": [{"tool": "story_create", "args": {"auto": False}}], "message": ""},
    "story create --auto": lambda: {"actions": [{"tool": "story_create", "args": {"auto": True}}], "message": ""},
    "report show": lambda: {"actions": [{"tool": "report_show", "args": {}}], "message": ""},
    "report generate": lambda: {"actions": [{"tool": "report_generate", "args": {}}], "message": "Generando reporte..."},
    "log show": lambda: {"actions": [{"tool": "log_show", "args": {"last_n": 20}}], "message": ""},
    "log summary": lambda: {"actions": [{"tool": "log_summary", "args": {}}], "message": ""},
    "workspace clean": lambda: {"actions": [{"tool": "workspace_clean", "args": {"older_than_days": 30}}], "message": ""},
}

# ── Patrones regex (sin LLM) ─────────────────────────────────────────────────
PATTERNS: list[tuple[str, callable]] = [
    # git clone <url> [--branch <branch>]
    (
        r"^git clone (.+?)(?:\s+--branch\s+(\S+))?$",
        lambda m: {
            "actions": [{"tool": "git_clone", "args": {
                "repo_url": m.group(1).strip(),
                "branch": m.group(2),
            }}],
            "message": f"Clonando {m.group(1).strip()}...",
        },
    ),
    # git analyze <repo>
    (
        r"^git analyze (.+)$",
        lambda m: {
            "actions": [{"tool": "git_analyze", "args": {"repo_name": m.group(1).strip()}}],
            "message": f"Analizando README de {m.group(1).strip()}...",
        },
    ),
    # git status <repo>
    (
        r"^git status (.+)$",
        lambda m: {
            "actions": [{"tool": "git_status", "args": {"repo_name": m.group(1).strip()}}],
            "message": "",
        },
    ),
    # extract <file_id>
    (
        r"^extract\s+([A-Za-z0-9_\-]+)$",
        lambda m: {
            "actions": [{"tool": "drive_extract", "args": {"file_id": m.group(1).strip()}}],
            "message": "Extrayendo user stories desde Drive...",
        },
    ),
    # test setup <repo> [base_url=<url>]
    (
        r"^test setup ([^\s]+)(?:\s+base_url=(\S+))?$",
        lambda m: {
            "actions": [{"tool": "test_setup", "args": {"repo_name": m.group(1).strip(), "base_url": m.group(2)}}],
            "message": f"Configurando API: {m.group(1).strip()}...",
        },
    ),
    # test run <repo> [base_url=<url>] [--all]
    (
        r"^test run ([^\s]+)(?:\s+base_url=(\S+))?(?:\s+--all)?$",
        lambda m: {
            "actions": [
                {"tool": "test_setup", "args": {"repo_name": m.group(1).strip(), "base_url": m.group(2)}},
                {"tool": "test_run", "args": {
                    "repo_name": m.group(1).strip(),
                    "base_url": m.group(2),
                    "happy_only": "--all" not in m.string,
                }},
            ],
            "message": f"Ejecutando tests en {m.group(1).strip()}...",
        },
    ),
    # test suggest <repo>
    (
        r"^test suggest (.+)$",
        lambda m: {
            "actions": [{"tool": "test_suggest", "args": {"repo_name": m.group(1).strip()}}],
            "message": "",
        },
    ),
    # test shutdown <repo>
    (
        r"^test shutdown (.+)$",
        lambda m: {
            "actions": [{"tool": "test_shutdown", "args": {"repo_name": m.group(1).strip()}}],
            "message": f"Deteniendo servidor {m.group(1).strip()}...",
        },
    ),
    # report upload <issue_id>
    (
        r"^report upload (.+)$",
        lambda m: {
            "actions": [{"tool": "report_upload", "args": {"issue_id": m.group(1).strip()}}],
            "message": f"Subiendo reporte a {m.group(1).strip()}...",
        },
    ),
    # model switch <local|anthropic>
    (
        r"^model switch (local|anthropic)$",
        lambda m: {
            "actions": [{"tool": "model_switch", "args": {"provider": m.group(1)}}],
            "message": f"Cambiando a {m.group(1)}...",
        },
    ),
    # log show [--last N]
    (
        r"^log show(?:\s+--last\s+(\d+))?$",
        lambda m: {
            "actions": [{"tool": "log_show", "args": {"last_n": int(m.group(1) or 20)}}],
            "message": "",
        },
    ),
    # log summary [--id <pipeline_id>]
    (
        r"^log summary(?:\s+--id\s+(\S+))?$",
        lambda m: {
            "actions": [{"tool": "log_summary", "args": {"pipeline_id": m.group(1) or ""}}],
            "message": "",
        },
    ),
    # workspace clean [--days N]
    (
        r"^workspace clean(?:\s+--days\s+(\d+))?$",
        lambda m: {
            "actions": [{"tool": "workspace_clean", "args": {
                "older_than_days": int(m.group(1) or 30),
            }}],
            "message": "Limpiando workspace...",
        },
    ),
]


async def route(command: str) -> dict:
    """Interpreta un comando y retorna la acción JSON a ejecutar."""
    cmd_stripped = command.strip()
    cmd_lower = cmd_stripped.lower()

    # Comandos exactos (sin LLM)
    if cmd_lower in DIRECT_COMMANDS:
        return DIRECT_COMMANDS[cmd_lower]()

    # Patrones regex directos (sin LLM)
    for pattern, handler in PATTERNS:
        m = re.match(pattern, cmd_stripped, re.IGNORECASE)
        if m:
            return handler(m)

    # Fallback: LLM para lenguaje natural y comandos complejos
    logger.info("Routing via LLM", command=cmd_stripped[:100])
    llm = get_llm()
    try:
        messages = [
            {"role": "system", "content": CONSOLE_ROUTER_PROMPT},
            {"role": "user", "content": cmd_stripped},
        ]
        response = await llm.ainvoke(messages)
        content = (
            response.content.strip()
            .replace("```json", "").replace("```", "").strip()
        )
        result = json.loads(content)
        # Asegurar que siempre tiene la estructura esperada
        result.setdefault("actions", [])
        result.setdefault("message", "")
        result.setdefault("clarification_needed", None)
        return result
    except json.JSONDecodeError as e:
        logger.warning("Router LLM retornó JSON inválido", error=str(e))
        return {
            "actions": [],
            "message": "No pude interpretar el comando. Escribe 'help' para ver los disponibles.",
            "clarification_needed": None,
        }
    except Exception as e:
        logger.error("Router LLM error", error=str(e))
        return {
            "actions": [],
            "message": f"Error del router: {e}. Escribe 'help' para los comandos.",
            "clarification_needed": None,
        }
