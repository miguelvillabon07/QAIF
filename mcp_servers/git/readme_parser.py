"""
Parsea README.md usando LLM para extraer:
- Comandos de setup
- Endpoints del happy path
- Dependencias
- Instrucciones de autenticación
"""
from __future__ import annotations

import json
from typing import Optional, Any

from pydantic import BaseModel

from src.llm.factory import get_llm
from src.utils.logging_config import get_logger

logger = get_logger("git.readme_parser")


class HappyPathEndpoint(BaseModel):
    method: str
    path: str
    description: str
    example_payload: Any = None
    expected_status: int = 200


class ReadmeAnalysis(BaseModel):
    setup_commands: list[str]
    base_url_hint: str = "http://localhost:8000"
    happy_path_endpoints: list[HappyPathEndpoint]
    auth_hint: str = "none"
    dependencies: list[str]
    start_command: str = ""
    health_check_path: str = "/health"
    summary: str = ""


README_ANALYSIS_PROMPT = """
Analiza este README y extrae información estructurada en JSON.
Responde SOLO con JSON válido, sin markdown fences ni texto adicional.

README:
---
{readme_content}
---

Extrae exactamente este JSON:
{{
  "setup_commands": ["lista de comandos shell para instalar dependencias y configurar el proyecto"],
  "base_url_hint": "URL base del servidor, usualmente http://localhost:PUERTO",
  "happy_path_endpoints": [
    {{
      "method": "GET|POST|PUT|DELETE|PATCH",
      "path": "/ruta/del/endpoint",
      "description": "qué hace este endpoint",
      "example_payload": null,
      "expected_status": 200
    }}
  ],
  "auth_hint": "none|bearer|api_key|basic",
  "dependencies": ["lista de dependencias principales del proyecto"],
  "start_command": "comando exacto para levantar el servidor en background",
  "health_check_path": "/health o el endpoint raíz para confirmar que está corriendo",
  "summary": "descripción de una línea del proyecto"
}}

Reglas:
- Si no puedes determinar algo con certeza, usa valores razonables por defecto.
- Para start_command, incluye el comando completo (e.g., "uvicorn main:app --port 8000").
- happy_path_endpoints: incluye los endpoints principales de negocio (no los de admin/docs).
- Responde SOLO con el JSON, sin ningún texto antes o después.
"""


async def parse_readme(readme_content: str) -> ReadmeAnalysis:
    """Usa el LLM configurado para extraer info estructurada del README."""
    if not readme_content.strip():
        logger.warning("README vacío, usando valores por defecto")
        return ReadmeAnalysis(
            setup_commands=["pip install -r requirements.txt"],
            happy_path_endpoints=[],
            dependencies=[],
        )

    llm = get_llm()
    prompt = README_ANALYSIS_PROMPT.format(readme_content=readme_content[:8000])

    from mcp_servers.workspace.audit import log_event
    log_event(
        "git_analyze",
        "Analizando README con LLM...",
        "running",
    )

    try:
       
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        # Limpiar posibles markdown fences aunque le pedimos no incluirlos
        content = content.replace("```json", "").replace("```", "").strip()

        data = json.loads(content)
        analysis = ReadmeAnalysis(**data)
        
        tokens_used = 0
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})
            if usage:
                tokens_used = usage.get("total_tokens", 0)

        logger.info(
            "README analizado",
            endpoints=len(analysis.happy_path_endpoints),
            commands=len(analysis.setup_commands),
            summary=analysis.summary[:60],
        )
        from mcp_servers.workspace.audit import log_event
        log_event(
            "git_analyze",
            f"README analizado: {len(analysis.happy_path_endpoints)} endpoints",
            "success",
            metadata={"endpoints": len(analysis.happy_path_endpoints)},
            tokens_used=tokens_used,
        )
        return analysis

    except json.JSONDecodeError as e:
        logger.error("Error parseando README", error=str(e))
        from mcp_servers.workspace.audit import log_event
        log_event(
            "git_analyze",
            f"Fallo JSON: {e}",
            "failed",
        )
        return ReadmeAnalysis(
            setup_commands=[],
            happy_path_endpoints=[],
            dependencies=[],
            summary="Error de parseo — revisar README manualmente",
        )
    except Exception as e:
        logger.error("Error LLM parse_readme", error=str(e))
        from mcp_servers.workspace.audit import log_event
        log_event(
            "git_analyze",
            f"Fallo LLM: {e}",
            "failed",
        )
        return ReadmeAnalysis(
            setup_commands=[],
            happy_path_endpoints=[],
            dependencies=[],
        )
