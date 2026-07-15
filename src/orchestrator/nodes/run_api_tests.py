"""
Nodo 3: Git-first API testing.
1. Lee análisis del README desde CAG (Redis) o estado
2. Ejecuta happy path contra la API
3. Genera sugerencias de automatización con LLM
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from src.cache.cag_manager import get_cag_manager
from src.llm.factory import get_llm
from src.orchestrator.state import AgentState
from src.utils.logging_config import get_logger
from mcp_servers.workspace.audit import log_event

logger = get_logger("node.run_api_tests")

AUTOMATION_SUGGESTIONS_PROMPT = """
Dado los resultados del happy path de esta API y la información del README,
sugiere 5-8 estrategias específicas para ampliar la cobertura de pruebas.

README Summary: {readme_summary}
Happy Path Results:
- Total: {total} pruebas
- Pasaron: {passed}
- Fallaron: {failed}
- Tasa de éxito: {pass_rate}

Responde con JSON sin markdown fences:
{{"suggestions": ["sugerencia concreta 1", "sugerencia concreta 2", ...]}}

Cada sugerencia debe ser un caso de prueba específico (no genérico).
Ejemplo: "POST /api/sales con amount=0 debe retornar 422 con mensaje de validación"
"""


async def run_api_tests_node(state: AgentState) -> dict:
    """Nodo LangGraph: ejecuta happy path de la API y genera sugerencias."""
    pipeline_id = state.get("pipeline_id", "unknown")
    repo_name = state.get("repo_name", "")
    api_base_url = state.get("api_base_url", "http://localhost:8000")

    log_event(
        "run_api_tests", f"Iniciando testing de API: {repo_name}",
        "running", pipeline_id=pipeline_id,
    )

    if not repo_name:
        return {
            "errors": state.get("errors", []) + ["repo_name no configurado en el estado"],
            "pipeline_status": "failed",
        }

    # ── Recuperar análisis del README (estado → CAG → error) ──
    readme_analysis_json = state.get("readme_analysis_json", "")
    if not readme_analysis_json:
        cag = get_cag_manager()
        try:
            ctx = await cag.get_context(f"cag:readme_analysis:{repo_name}")
            readme_analysis_json = ctx.get(f"cag:readme_analysis:{repo_name}", "")
        except Exception as e:
            logger.warning("CAG no disponible", error=str(e))

    if not readme_analysis_json:
        error = f"README no analizado para '{repo_name}'. Ejecuta 'git analyze {repo_name}' primero."
        log_event("run_api_tests", error, "failed", pipeline_id=pipeline_id)
        return {
            "errors": state.get("errors", []) + [error],
            "pipeline_status": "failed",
        }

    # ── Ejecutar happy path ──
    try:
        from mcp_servers.pos_api.tools import pos_api_run_happy_path
        from src.schemas.test_result import TestSuiteResult

        result_content = await pos_api_run_happy_path(
            repo_name=repo_name,
            base_url=api_base_url,
            readme_analysis_json=readme_analysis_json,
        )
        result_data = json.loads(result_content[0].text)

        if "error" in result_data:
            log_event("run_api_tests", result_data["error"], "failed", pipeline_id=pipeline_id)
            return {
                "errors": state.get("errors", []) + [result_data["error"]],
                "pipeline_status": "failed",
                "test_retry_count": state.get("test_retry_count", 0) + 1,
            }

        suite = TestSuiteResult.model_validate(result_data)

        # ── Generar sugerencias de automatización ──
        suggestions: list[str] = []
        tokens_used = 0
        try:
            llm = get_llm()
            from mcp_servers.git.readme_parser import ReadmeAnalysis
            readme_data = ReadmeAnalysis.model_validate_json(readme_analysis_json)
            sugg_prompt = AUTOMATION_SUGGESTIONS_PROMPT.format(
                readme_summary=readme_data.summary or "Sin descripción disponible",
                total=suite.total,
                passed=suite.passed,
                failed=suite.failed,
                pass_rate=f"{suite.pass_rate:.0%}",
            )
            sugg_response = await llm.ainvoke(sugg_prompt)
            
            if hasattr(sugg_response, "response_metadata"):
                usage = sugg_response.response_metadata.get("token_usage", {})
                if usage:
                    tokens_used = usage.get("total_tokens", 0)

            raw_content = sugg_response.content
            if isinstance(raw_content, list):
                parts = []
                for p in raw_content:
                    if isinstance(p, dict):
                        parts.append(p.get("text", ""))
                    elif isinstance(p, str):
                        parts.append(p)
                raw_content = "".join(parts)
            elif not isinstance(raw_content, str):
                raw_content = str(raw_content)

            sugg_content = (
                raw_content.strip()
                .replace("```json", "").replace("```", "").strip()
            )
            suggestions = json.loads(sugg_content).get("suggestions", [])
        except Exception as e:
            logger.warning("No se pudieron generar sugerencias LLM", error=str(e))
            suggestions = [
                "Probar endpoints con datos inválidos (status 422)",
                "Verificar respuestas de error con autenticación incorrecta (401/403)",
                "Test de carga: 10 requests simultáneos al endpoint principal",
            ]

        suite.automation_suggestions = suggestions

        log_event(
            "run_api_tests",
            f"Tests completados: {suite.passed}/{suite.total} ({suite.pass_rate:.0%})",
            "success", pipeline_id=pipeline_id,
            metadata={
                "pass_rate": suite.pass_rate,
                "total": suite.total,
                "suggestions": len(suggestions),
            },
            tokens_used=tokens_used,
        )
        logger.info(
            "run_api_tests OK",
            passed=suite.passed, total=suite.total,
            pass_rate=f"{suite.pass_rate:.0%}",
        )

        return {
            "test_suite_result": suite,
            "pipeline_status": "generating_report",
            "current_step": "upload_report",
            "test_retry_count": state.get("test_retry_count", 0),
        }

    except Exception as e:
        logger.error("run_api_tests FAIL", error=str(e))
        log_event("run_api_tests", str(e), "failed", pipeline_id=pipeline_id)
        return {
            "errors": state.get("errors", []) + [str(e)],
            "pipeline_status": "failed",
            "test_retry_count": state.get("test_retry_count", 0) + 1,
        }
