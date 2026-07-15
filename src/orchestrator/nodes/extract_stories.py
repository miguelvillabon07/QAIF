"""
Nodo 1: Lee transcripción de Drive → extrae User Stories con LLM.
Usa CAG: si hay contexto de Jira en Redis, lo incluye en el prompt.
"""
from __future__ import annotations

import json

from src.cache.cag_manager import get_cag_manager
from src.llm.factory import get_llm
from src.orchestrator.state import AgentState
from src.schemas.user_story import Priority, UserStory
from src.utils.logging_config import get_logger
from mcp_servers.workspace.audit import log_event

logger = get_logger("node.extract_stories")

EXTRACTION_PROMPT = """
Eres un analista de negocio senior. Analiza la siguiente transcripción de reunión
y extrae todas las historias de usuario.

CONTEXTO DEL PROYECTO JIRA:
{jira_context}

TRANSCRIPCIÓN:
---
{transcription}
---

Responde ÚNICAMENTE con JSON válido (sin markdown fences):
{{
  "user_stories": [
    {{
      "title": "string imperativo máx 200 chars",
      "description": "Como [rol], quiero [acción] para [beneficio]",
      "acceptance_criteria": [
        "Given [contexto], When [acción], Then [resultado verificable]"
      ],
      "priority": "Highest|High|Medium|Low",
      "story_points": null,
      "labels": ["lista_etiquetas"],
      "confidence_score": 0.85
    }}
  ],
  "extraction_warnings": ["avisos sobre ambigüedades"]
}}

REGLAS:
- Solo extraer lo EXPLÍCITAMENTE mencionado en la transcripción
- ACs en formato Gherkin (Given/When/Then), mínimo 2 por historia
- confidence_score < 0.70 si hay ambigüedad significativa
- story_points: null o valor Fibonacci (1,2,3,5,8,13)
- Ignorar: saludos, logística, comentarios off-topic
- Mínimo 10 caracteres por AC
"""


async def extract_stories_node(state: AgentState) -> dict:
    """Nodo LangGraph: extrae User Stories de una transcripción usando LLM + CAG."""
    pipeline_id = state.get("pipeline_id", "unknown")
    log_event(
        "extract_stories", "Iniciando extracción de User Stories",
        "running", pipeline_id=pipeline_id,
        metadata={"file_id": state.get("transcription_file_id", "")},
    )

    transcription = state.get("transcription_content", "")
    if not transcription.strip():
        error = "Transcripción vacía — verifica el file_id de Drive"
        log_event("extract_stories", error, "failed", pipeline_id=pipeline_id)
        return {
            "errors": state.get("errors", []) + [error],
            "pipeline_status": "failed",
        }

    # CAG: recuperar contexto Jira si está en Redis
    cag = get_cag_manager()
    try:
        ctx = await cag.get_context("cag:jira_config")
        jira_context = ctx.get("cag:jira_config", "Sin configuración Jira disponible")
    except Exception:
        jira_context = "Redis no disponible — usando prompt sin contexto Jira"

    prompt = EXTRACTION_PROMPT.format(
        transcription=transcription[:10000],
        jira_context=jira_context[:2000],
    )

    llm = get_llm()
    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(content)

        stories: list[UserStory] = []
        file_id = state.get("transcription_file_id", "")
        for s in data.get("user_stories", []):
            try:
                # Asegurar que viene el campo requerido
                s["extracted_from_file_id"] = file_id
                story = UserStory(**s)
                stories.append(story)
            except Exception as e:
                logger.warning("UserStory inválida, saltando", error=str(e), data=str(s)[:100])

        warnings = data.get("extraction_warnings", [])
        low_conf = [s for s in stories if s.confidence_score < 0.70]
        if low_conf:
            warnings.append(f"{len(low_conf)} historia(s) con baja confianza (<70%) — revisar")

        # Convertir los warnings en Historias de Usuario para que se registren en Jira y se puedan refinar
        for w in warnings:
            try:
                stories.append(UserStory(
                    title=f"[REFINAR] {w[:100]}",
                    description=f"Se detectó una ambigüedad o deuda técnica durante la extracción automatizada:\n\n{w}\n\nEl equipo de producto debe refinar esta historia y definir las reglas de negocio/criterios de aceptación faltantes.",
                    acceptance_criteria=[
                        "Duda aclarada y validada con Stakeholders",
                        "Criterios de aceptación técnicos y de negocio definidos"
                    ],
                    priority=Priority.MEDIUM,
                    confidence_score=0.1,
                    labels=["needs_refinement", "ambiguity_warning"],
                    extracted_from_file_id=file_id,
                ))
            except Exception as e:
                logger.warning("No se pudo convertir warning a UserStory", error=str(e))

        tokens_used = 0
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})
            if usage:
                tokens_used = usage.get("total_tokens", 0)

        log_event(
            "extract_stories", f"Extraídas {len(stories)} historias",
            "success", pipeline_id=pipeline_id,
            metadata={"count": len(stories), "warnings": len(warnings)},
            tokens_used=tokens_used,
        )
        logger.info("extract_stories OK", stories=len(stories), warnings=len(warnings))

        new_status = "awaiting_review" if stories else "failed"
        next_step = "create_jira" if stories else "end"

        return {
            "user_stories": stories,
            "extraction_warnings": warnings,
            "pipeline_status": new_status,
            "current_step": next_step,
            "errors": [] if stories else ["No se extrajeron historias de la transcripción"],
        }

    except json.JSONDecodeError as e:
        msg = f"LLM retornó JSON inválido: {e}"
        log_event("extract_stories", msg, "failed", pipeline_id=pipeline_id)
        return {"errors": state.get("errors", []) + [msg], "pipeline_status": "failed"}
    except Exception as e:
        log_event("extract_stories", str(e), "failed", pipeline_id=pipeline_id)
        return {"errors": state.get("errors", []) + [str(e)], "pipeline_status": "failed"}
