"""
LangGraph StateGraph — Pipeline MCP QA Automation.

START → extract_stories → [interrupt human_review] → create_jira →
  run_api_tests → [conditional retry] → upload_report → END
"""
from __future__ import annotations

from config.settings import get_settings
from src.orchestrator.nodes.create_jira import create_jira_node
from src.orchestrator.nodes.extract_stories import extract_stories_node
from src.orchestrator.nodes.run_api_tests import run_api_tests_node
from src.orchestrator.nodes.upload_report import upload_report_node
from src.orchestrator.state import AgentState
from src.utils.logging_config import get_logger
from langgraph.graph import END, START, StateGraph

logger = get_logger("orchestrator.graph")


def _should_retry_tests(state: AgentState) -> str:
    """Decide si reintentar los tests o continuar al reporte."""
    settings = get_settings()
    retry_count = state.get("test_retry_count", 0)
    status = state.get("pipeline_status", "")

    if status == "failed" and retry_count < settings.pipeline_retry_max:
        errors = state.get("errors", [])
        # Reintentar solo errores de red/conexión, no de lógica de negocio
        network_keywords = ["connection", "timeout", "refused", "unreachable", "connect error"]
        is_network_error = any(
            any(kw in str(e).lower() for kw in network_keywords)
            for e in errors
        )
        if is_network_error:
            logger.info("Reintentando tests", retry=retry_count + 1, max=settings.pipeline_retry_max)
            return "retry"

    return "continue"


def _should_continue_after_extract(state: AgentState) -> str:
    """Después de extraer, va a create_jira o termina si no hay historias."""
    status = state.get("pipeline_status", "")
    if status == "failed":
        return "end"
    return "create_jira"


def create_pipeline(checkpoint_db: str | None = None):
    """
    Construye y compila el grafo LangGraph con checkpointing.
    Usa SQLite para dev (default) o puede recibir otra cadena de conexión.
    """
    settings = get_settings()
    db = checkpoint_db or settings.langgraph_checkpoint_db

    # ── Checkpointer ── (MemorySaver estable en langgraph 1.x)
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    logger.info("Checkpointer: MemorySaver")

    # ── Definir grafo ──
    graph = StateGraph(AgentState)

    # Nodos
    graph.add_node("extract_stories", extract_stories_node)
    graph.add_node("create_jira", create_jira_node)
    graph.add_node("run_api_tests", run_api_tests_node)
    graph.add_node("upload_report", upload_report_node)

    # Edges
    graph.add_edge(START, "extract_stories")

    # Después de extract: continuar o terminar si falla
    graph.add_conditional_edges(
        "extract_stories",
        _should_continue_after_extract,
        {"create_jira": "create_jira", "end": END},
    )

    graph.add_edge("create_jira", "run_api_tests")

    # Después de tests: reintentar o continuar al reporte
    graph.add_conditional_edges(
        "run_api_tests",
        _should_retry_tests,
        {"retry": "run_api_tests", "continue": "upload_report"},
    )

    graph.add_edge("upload_report", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Pipeline compilado OK")
    return compiled
