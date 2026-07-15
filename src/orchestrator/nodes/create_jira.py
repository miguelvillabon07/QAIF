"""
Nodo 2: Crea issues en Jira para cada User Story aprobada.
Si HUMAN_REVIEW_ENABLED, el estado queda en 'awaiting_review' y el
orquestador hace interrupt; la reanudación viene con human_approved=True.
"""
from __future__ import annotations

from config.settings import get_settings
from src.orchestrator.state import AgentState
from src.utils.logging_config import get_logger
from mcp_servers.workspace.audit import log_event

logger = get_logger("node.create_jira")


async def create_jira_node(state: AgentState) -> dict:
    """Nodo LangGraph: crea issues en Jira para cada User Story."""
    settings = get_settings()
    pipeline_id = state.get("pipeline_id", "unknown")
    stories = state.get("user_stories", [])

    if not stories:
        return {
            "errors": state.get("errors", []) + ["No hay User Stories para crear en Jira"],
            "pipeline_status": "failed",
        }

    # ── Human Review (si está habilitado y aún no fue aprobado) ──
    if settings.human_review_enabled and not state.get("human_approved", False):
        logger.info("Pausando para revisión humana", stories=len(stories))
        log_event(
            "create_jira", f"Esperando aprobación humana ({len(stories)} historias)",
            "paused", pipeline_id=pipeline_id,
            metadata={"story_count": len(stories)},
        )
        return {
            "pipeline_status": "awaiting_review",
            "current_step": "human_review",
        }

    # ── Verificar que Jira esté configurado ──
    if not settings.jira_configured:
        logger.warning("Jira no configurado, saltando creación")
        log_event(
            "create_jira",
            "Jira no configurado — historias registradas pero no subidas a Jira",
            "skipped", pipeline_id=pipeline_id,
        )
        return {
            "jira_issue_ids": [],
            "jira_creation_errors": ["Jira no configurado en .env"],
            "pipeline_status": "running",
            "current_step": "run_api_tests",
        }

    # ── Crear issues ──
    log_event(
        "create_jira", f"Creando {len(stories)} issues en Jira",
        "running", pipeline_id=pipeline_id,
    )

    from mcp_servers.jira.tools import jira_create_issue
    import json

    issue_ids: list[str] = []
    errors: list[str] = []
    feedback = state.get("human_feedback", "")

    for story in stories:
        try:
            # Incorporar feedback humano en la descripción si existe
            description = story.jira_description
            if feedback:
                description = f"*Feedback del revisor:* {feedback}\n\n{description}"

            result = await jira_create_issue(
                project_key=settings.jira_project_key,
                summary=story.title,
                description=description,
                issue_type="Story",
                priority=story.priority.value,
                labels=story.labels or [],
                epic_key=story.epic_link or settings.jira_epic_key,
            )
            result_data = json.loads(result[0].text)
            if "issue_key" in result_data:
                issue_ids.append(result_data["issue_key"])
                log_event(
                    "create_jira", f"Issue creado: {result_data['issue_key']}",
                    "success", pipeline_id=pipeline_id,
                    metadata={"issue_key": result_data["issue_key"], "title": story.title[:50]},
                )
                logger.info("Issue creado", key=result_data["issue_key"], title=story.title[:50])
            else:
                errors.append(f"Error creando '{story.title[:50]}': {result_data.get('error', 'desconocido')}")
        except Exception as e:
            errors.append(f"Excepción en '{story.title[:50]}': {e}")
            logger.error("jira_create_issue FAIL", title=story.title[:50], error=str(e))

    log_event(
        "create_jira",
        f"Creación Jira completada: {len(issue_ids)}/{len(stories)} OK",
        "success" if issue_ids else "failed",
        pipeline_id=pipeline_id,
        metadata={"created": len(issue_ids), "errors": len(errors)},
    )

    return {
        "jira_issue_ids": issue_ids,
        "jira_creation_errors": errors,
        "pipeline_status": "running",
        "current_step": "run_api_tests",
        "errors": state.get("errors", []) + errors,
    }
