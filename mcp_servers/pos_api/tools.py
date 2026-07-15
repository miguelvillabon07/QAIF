"""Herramientas del MCP Server POS API."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from mcp import types

from config.settings import get_settings
from src.schemas.test_case import Assertion, HttpMethod, TestCase
from src.schemas.test_result import TestSuiteResult
from src.utils.logging_config import get_logger

from .api_launcher import get_base_url, list_running, setup_and_launch, shutdown
from .runner import run_test_case

logger = get_logger("mcp.pos_api")


async def pos_api_setup(
    repo_name: str,
    base_url: Optional[str] = None,
) -> list[types.TextContent]:
    """
    Configura y levanta la API local:
    1. Lee el análisis del README desde Redis (CAG) o lo genera en el momento
    2. Ejecuta setup_commands
    3. Lanza el servidor y espera health check
    """
    settings = get_settings()
    repo_path = settings.git_workspace_path / repo_name
    logger.info("pos_api_setup", repo=repo_name, path=str(repo_path))

    if not repo_path.exists():
        return [types.TextContent(type="text", text=json.dumps({
            "error": f"Repo '{repo_name}' no encontrado en {repo_path}. Usa git_clone primero.",
        }))]

    # Intentar leer análisis del README desde CAG (Redis)
    readme_analysis_json: Optional[str] = None
    if settings.cag_enabled:
        try:
            from src.cache.cag_manager import get_cag_manager
            cag = get_cag_manager()
            ctx = await cag.get_context(f"cag:readme_analysis:{repo_name}")
            readme_analysis_json = ctx.get(f"cag:readme_analysis:{repo_name}")
        except Exception:
            pass

    # Si no está en caché, analizar ahora
    if not readme_analysis_json:
        logger.info("README no en caché, analizando", repo=repo_name)
        from mcp_servers.git.readme_parser import ReadmeAnalysis, parse_readme
        readme_path = None
        for name in ["README.md", "readme.md", "README.rst"]:
            p = repo_path / name
            if p.exists():
                readme_path = p
                break

        content = readme_path.read_text(encoding="utf-8") if readme_path else ""
        analysis = await parse_readme(content)

        # Guardar en CAG para próximas llamadas
        if settings.cag_enabled:
            try:
                from src.cache.cag_manager import get_cag_manager
                import redis.asyncio as aioredis
                r = await aioredis.from_url(settings.redis_url)
                await r.setex(
                    f"cag:readme_analysis:{repo_name}",
                    settings.cag_readme_ttl_seconds,
                    analysis.model_dump_json(),
                )
                await r.aclose()
            except Exception as e:
                logger.warning("No se pudo cachear en CAG", error=str(e))
    else:
        from mcp_servers.git.readme_parser import ReadmeAnalysis
        analysis = ReadmeAnalysis.model_validate_json(readme_analysis_json)
        logger.info("README analysis desde CAG", repo=repo_name)

    # Resolver base_url
    resolved_base_url = base_url or analysis.base_url_hint or "http://localhost:8000"
    suggested_base_url = resolved_base_url.replace("localhost", "host.docker.internal")

    # Deshabilitado por problemas de entorno Docker vs Host (Java JDK, Node, etc.)
    # ok, message = await setup_and_launch(...)
    
    ok = True
    message = (
        f"Por favor, abre otra consola en tu máquina local y ejecuta:\n"
        f"  cd workspace/repos/{repo_name}\n"
        f"  {analysis.start_command or './gradlew bootRun'}\n\n"
        f"Valida en qué puerto arranca el servidor.\n"
        f"Luego ejecuta en esta consola: test run {repo_name} base_url={suggested_base_url}"
    )

    return [types.TextContent(type="text", text=json.dumps({
        "success": ok,
        "message": message,
        "repo_name": repo_name,
        "base_url": resolved_base_url,
        "endpoints_detected": len(analysis.happy_path_endpoints),
        "start_command": analysis.start_command,
    }))]


async def pos_api_run_happy_path(
    repo_name: str,
    base_url: Optional[str] = None,
    readme_analysis_json: Optional[str] = None,
) -> list[types.TextContent]:
    """
    Ejecuta el happy path completo:
    1. Lee endpoints desde readme_analysis o CAG
    2. Crea y ejecuta TestCase para cada endpoint
    3. Genera automation_suggestions via LLM
    4. Retorna TestSuiteResult como JSON
    """
    settings = get_settings()
    resolved_base_url = base_url or get_base_url(repo_name) or "http://localhost:8000"
    logger.info("pos_api_run_happy_path", repo=repo_name, base_url=resolved_base_url)

    # Obtener análisis del README
    if readme_analysis_json:
        from mcp_servers.git.readme_parser import ReadmeAnalysis
        analysis = ReadmeAnalysis.model_validate_json(readme_analysis_json)
    else:
        # Intentar desde CAG
        analysis = None
        if settings.cag_enabled:
            try:
                from src.cache.cag_manager import get_cag_manager
                cag = get_cag_manager()
                ctx = await cag.get_context(f"cag:readme_analysis:{repo_name}")
                cached = ctx.get(f"cag:readme_analysis:{repo_name}")
                if cached:
                    from mcp_servers.git.readme_parser import ReadmeAnalysis
                    analysis = ReadmeAnalysis.model_validate_json(cached)
            except Exception:
                pass

        if analysis is None:
            return [types.TextContent(type="text", text=json.dumps({
                "error": "No hay análisis del README disponible. Ejecuta pos_api_setup primero.",
            }))]

    if not analysis.happy_path_endpoints:
        return [types.TextContent(type="text", text=json.dumps({
            "warning": "No se detectaron endpoints en el README. Verifica el análisis.",
            "base_url": resolved_base_url,
        }))]

    # --- INYECCIÓN DE PAYLOADS POSTMAN-LIKE ---
    from pathlib import Path
    import os
    test_data_dir = Path(settings.git_workspace_path).parent / "test_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    payloads_file = test_data_dir / f"{repo_name}_payloads.json"
    
    custom_payloads = {}
    if payloads_file.exists():
        with open(payloads_file, "r", encoding="utf-8") as f:
            custom_payloads = json.load(f)
    else:
        # Generar payloads automáticamente con LLM analizando el DTO (si es posible) o infiriendo
        try:
            from src.llm.factory import get_llm
            llm = get_llm()
            # Tratar de leer algún Controller o DTO si existe para dar más contexto
            repo_path = Path(settings.git_workspace_path) / repo_name
            context_files = ""
            if repo_path.exists():
                java_files = list(repo_path.rglob("*.java")) + list(repo_path.rglob("*.ts"))
                # Priorizar archivos que suenen a esquemas o controladores
                def file_score(f):
                    name = f.as_posix().lower()
                    if "test" in name: return -1
                    score = 0
                    if "dto" in name or "model" in name or "request" in name or "response" in name: score += 2
                    if "controller" in name or "api" in name: score += 1
                    return score
                    
                target_files = sorted([f for f in java_files if file_score(f) >= 0], key=file_score, reverse=True)[:20]
                for tf in target_files:
                    context_files += f"\n--- {tf.name} ---\n{tf.read_text(encoding='utf-8')[:2500]}\n"
            
            endpoints_list = "\n".join([f"- {ep.method} {ep.path}: {ep.description}" for ep in analysis.happy_path_endpoints])
            prompt = f"""Eres un ingeniero QA creando una colección Postman.
El API en '{repo_name}' tiene estos endpoints:
{endpoints_list}

Aquí hay contexto de los modelos/código (si está vacío, infiere lógicamente):
{context_files}

Genera un JSON válido con esta estructura exacta para inyectar en los tests del happy path:
{{
    "/ruta/del/endpoint": {{
        "path": "/ruta/resuelta/si/habia/variables",
        "method": "POST",
        "headers": {{"Content-Type": "application/json"}},
        "payload": {{"clave": "valor_valido"}}
    }}
}}
Responde SOLO con el JSON válido, sin markdown ni explicaciones."""
            
            response = await llm.ainvoke(prompt)
            raw_json = response.content.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:-3]
            elif raw_json.startswith("```"):
                raw_json = raw_json[3:-3]
            
            custom_payloads_raw = json.loads(raw_json)
            # Manejar caso en el que el LLM devuelva una lista de diccionarios en lugar de un diccionario
            if isinstance(custom_payloads_raw, list):
                custom_payloads = {}
                for item in custom_payloads_raw:
                    custom_payloads.update(item)
            else:
                custom_payloads = custom_payloads_raw
                
            with open(payloads_file, "w", encoding="utf-8") as f:
                json.dump(custom_payloads, f, indent=2)
            logger.info("Payloads autogenerados via LLM", file=str(payloads_file))
        except Exception as e:
            logger.error("Error autogenerando payloads", error=str(e))
    # --- FIN INYECCIÓN ---

    # Crear TestCases para cada endpoint
    test_cases: list[TestCase] = []
    for i, ep in enumerate(analysis.happy_path_endpoints):
        assertions = [
            Assertion(
                type="status_code",
                expected_value=ep.expected_status,
                description=f"Status code es {ep.expected_status}",
            ),
            Assertion(
                type="response_time_ms",
                threshold=3000.0,
                description="Respuesta en menos de 3 segundos",
            ),
        ]
        if ep.method.upper() in ("POST", "PUT"):
            assertions.append(Assertion(
                type="schema_valid",
                description="Response body es válido",
            ))

        custom_data = custom_payloads.get(ep.path, {})
        final_endpoint = custom_data.get("path", ep.path)
        final_method = HttpMethod(custom_data.get("method", ep.method).upper())
        final_payload = custom_data.get("payload", ep.example_payload)
        final_headers = custom_data.get("headers", {})

        test_cases.append(TestCase(
            id=f"hp_{repo_name}_{i:03d}",
            name=f"[HP] {ep.method.upper()} {ep.path}",
            description=ep.description,
            endpoint=final_endpoint,
            method=final_method,
            headers=final_headers,
            payload=final_payload,
            expected_status=ep.expected_status,
            assertions=assertions,
            is_happy_path=True,
            tags=["happy_path", "auto_generated"],
        ))

    # Ejecutar tests
    started_at = datetime.now(timezone.utc)
    results = []
    for tc in test_cases:
        result = await run_test_case(tc, resolved_base_url)
        results.append(result)

    # Generar automation_suggestions via LLM
    suggestions: list[str] = []
    failed_endpoints = [r for r in results if not r.passed]
    if failed_endpoints or True:  # Siempre generamos sugerencias
        try:
            from src.llm.factory import get_llm
            llm = get_llm()
            results_summary = "\n".join(
                f"- {r.test_case_name}: {r.status.value} "
                f"(status={r.actual_status_code}, time={r.response_time_ms}ms)"
                for r in results
            )
            prompt = f"""Eres un QA engineer experto. Basándote en estos resultados de pruebas de la API '{repo_name}':

{results_summary}

Sugiere 3-5 casos de prueba adicionales que cubran edge cases, validaciones de error y escenarios negativos.
Responde SOLO con una lista numerada, sin explicaciones adicionales."""
            response = await llm.ainvoke(prompt)
            raw = response.content.strip()
            suggestions = [
                line.lstrip("0123456789.-) ").strip()
                for line in raw.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ][:5]
        except Exception as e:
            logger.warning("No se pudieron generar sugerencias LLM", error=str(e))
            suggestions = ["Probar con datos inválidos", "Verificar autenticación", "Test de carga básico"]

    suite = TestSuiteResult(
        suite_name=f"Happy Path — {repo_name}",
        repo_name=repo_name,
        results=results,
        started_at=started_at,
        automation_suggestions=suggestions,
    )

    logger.info(
        "pos_api_run_happy_path OK",
        repo=repo_name,
        total=suite.total,
        passed=suite.passed,
        pass_rate=f"{suite.pass_rate:.0%}",
    )
    return [types.TextContent(type="text", text=suite.model_dump_json(indent=2))]


async def pos_api_run_test_case(test_case_json: str, base_url: str) -> list[types.TextContent]:
    """Ejecuta un único TestCase (como JSON) contra base_url."""
    try:
        tc = TestCase.model_validate_json(test_case_json)
        result = await run_test_case(tc, base_url)
        return [types.TextContent(type="text", text=result.model_dump_json(indent=2))]
    except Exception as e:
        logger.error("pos_api_run_test_case FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def pos_api_shutdown(repo_name: str) -> list[types.TextContent]:
    """Detiene el servidor de la API."""
    ok = shutdown(repo_name)
    return [types.TextContent(type="text", text=json.dumps({
        "status": "stopped" if ok else "not_running",
        "repo_name": repo_name,
    }))]


async def pos_api_list_endpoints(repo_name: str) -> list[types.TextContent]:
    """Lista los endpoints disponibles según el análisis del README."""
    settings = get_settings()
    try:
        if settings.cag_enabled:
            from src.cache.cag_manager import get_cag_manager
            cag = get_cag_manager()
            ctx = await cag.get_context(f"cag:readme_analysis:{repo_name}")
            cached = ctx.get(f"cag:readme_analysis:{repo_name}")
            if cached:
                from mcp_servers.git.readme_parser import ReadmeAnalysis
                analysis = ReadmeAnalysis.model_validate_json(cached)
                return [types.TextContent(type="text", text=json.dumps({
                    "repo_name": repo_name,
                    "endpoints": [ep.model_dump() for ep in analysis.happy_path_endpoints],
                    "source": "cache",
                }, indent=2))]
        return [types.TextContent(type="text", text=json.dumps({
            "message": "Análisis no disponible. Ejecuta pos_api_setup primero.",
        }))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def pos_api_run_custom_test(
    endpoint: str,
    method: str,
    base_url: str,
    payload: Optional[dict] = None,
    expected_status: int = 200,
    headers: Optional[dict] = None,
) -> list[types.TextContent]:
    """Ejecuta un test ad-hoc sin necesidad de TestCase pre-configurado."""
    tc = TestCase(
        id=f"custom_{uuid.uuid4().hex[:8]}",
        name=f"Custom: {method.upper()} {endpoint}",
        endpoint=endpoint,
        method=HttpMethod(method.upper()),
        payload=payload,
        expected_status=expected_status,
        headers=headers or {},
        assertions=[
            Assertion(type="status_code", expected_value=expected_status,
                      description=f"Status code es {expected_status}"),
            Assertion(type="response_time_ms", threshold=5000.0,
                      description="Tiempo de respuesta < 5s"),
        ],
        is_happy_path=False,
        tags=["custom", "ad_hoc"],
    )
    result = await run_test_case(tc, base_url)
    return [types.TextContent(type="text", text=result.model_dump_json(indent=2))]


async def pos_api_get_base_url(repo_name: str) -> list[types.TextContent]:
    """Retorna la base URL del servidor activo para el repo."""
    url = get_base_url(repo_name)
    running = list_running()
    return [types.TextContent(type="text", text=json.dumps({
        "repo_name": repo_name,
        "base_url": url,
        "is_running": url is not None,
        "all_running": running,
    }))]


async def pos_api_health_check(repo_name: str) -> list[types.TextContent]:
    """Verifica que el servidor de la API esté respondiendo."""
    base_url = get_base_url(repo_name)
    if not base_url:
        return [types.TextContent(type="text", text=json.dumps({
            "healthy": False,
            "message": f"No hay servidor activo para '{repo_name}'",
        }))]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(base_url)
            healthy = r.status_code < 500
            return [types.TextContent(type="text", text=json.dumps({
                "healthy": healthy,
                "status_code": r.status_code,
                "base_url": base_url,
                "repo_name": repo_name,
            }))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({
            "healthy": False,
            "error": str(e),
            "base_url": base_url,
        }))]
