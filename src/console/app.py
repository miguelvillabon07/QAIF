"""Consola interactiva principal con Rich."""
from __future__ import annotations

import asyncio
import json
import sys

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from config.settings import get_settings
from src.utils.logging_config import get_logger

from .prompts import BANNER
from .router import route

logger = get_logger("console.app")
console = Console()

# Estado global de la sesión
_session: dict = {
    "pipeline_id": "",
    "last_suite_json": "",
    "last_report_md": "",
    "user_stories": [],
}


async def execute_action(action: dict) -> str:
    """Despacha una acción al tool correspondiente y retorna resultado como string."""
    tool = action.get("tool", "")
    args = action.get("args", {})
    # Eliminar args None para no pasar kwargs inesperados
    args = {k: v for k, v in args.items() if v is not None}

    try:
        # ── Sistema ─────────────────────────────────────────────────────────
        if tool == "exit":
            return "__EXIT__"

        elif tool == "show_help":
            from .prompts import HELP_TEXT
            console.print(HELP_TEXT)
            return ""

        elif tool == "health_check":
            import httpx as _httpx
            import redis.asyncio as _aioredis
            from pathlib import Path as _Path
            _s = get_settings()
            _checks: list[tuple[str, bool, str]] = []
            # Ollama
            try:
                async with _httpx.AsyncClient(timeout=8.0) as _c:
                    _r = await _c.get(_s.ollama_base_url.replace("/v1", "") + "/api/tags")
                    _ms = [m["name"] for m in _r.json().get("models", [])]
                    _ok = any(_s.local_model_name in m for m in _ms)
                    _checks.append(("Ollama (GPU)", _ok, f"'{_s.local_model_name}' {'disponible' if _ok else 'NO descargado aun'}"))
            except Exception as _e:
                _checks.append(("Ollama (GPU)", False, f"No disponible: {str(_e)[:60]}"))
            # Redis
            try:
                _rc = await _aioredis.from_url(_s.redis_url, socket_timeout=3)
                await _rc.ping()
                await _rc.aclose()
                _checks.append(("Redis (CAG)", True, "Redis OK"))
            except Exception as _e:
                _checks.append(("Redis (CAG)", False, f"No disponible: {str(_e)[:60]}"))
            # Anthropic
            if getattr(_s, "anthropic_configured", False):
                try:
                    async with _httpx.AsyncClient(timeout=10.0) as _c:
                        _r = await _c.post("https://api.anthropic.com/v1/messages",
                            headers={"x-api-key": _s.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                            json={"model": _s.anthropic_model, "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]})
                        _checks.append(("Anthropic API", _r.status_code == 200, f"HTTP {_r.status_code}"))
                except Exception as _e:
                    _checks.append(("Anthropic API", False, str(_e)[:60]))
            else:
                _checks.append(("Anthropic API", False, "No configurada — ver .env"))
            # Drive SA
            _sa = getattr(_s, "google_service_account_json", None)
            _sa_ok = bool(_sa and _Path(str(_sa)).exists())
            _checks.append(("Google Drive", _sa_ok, "SA JSON encontrado" if _sa_ok else "service_account.json no encontrado"))
            # Jira
            _jira_ok = getattr(_s, "jira_configured", False)
            _checks.append(("Jira Cloud", _jira_ok, "Jira configurado" if _jira_ok else "JIRA_API_TOKEN no configurado"))
            _tbl = Table(show_header=True, header_style="bold", box=None)
            _tbl.add_column("Servicio", style="cyan", width=16)
            _tbl.add_column("Estado", width=10)
            _tbl.add_column("Detalle")
            _all_ok = True
            for _nm, _ok, _det in _checks:
                _tbl.add_row(_nm, "[green]OK[/green]" if _ok else "[red]FAIL[/red]", _det)
                if _nm in ("Ollama (GPU)", "Redis (CAG)") and not _ok:
                    _all_ok = False
            console.print(_tbl)
            if _all_ok:
                console.print("[green]Servicios criticos OK — el sistema puede ejecutarse.[/green]")
            else:
                console.print("[red]Servicios criticos no disponibles. Verifica 'docker compose up'.[/red]")
            return ""

        elif tool == "model_switch":
            provider = args.get("provider", "local")
            from src.llm.factory import switch_llm
            switch_llm(provider)
            settings = get_settings()
            model = settings.local_model_name if settings.is_local_llm else settings.anthropic_model
            console.print(f"[green]✓ Modelo cambiado a: [bold]{model}[/bold][/green]")
            return ""

        # ── Git ─────────────────────────────────────────────────────────────
        elif tool == "git_clone":
            from mcp_servers.git.tools import git_clone
            with console.status("[cyan]Clonando repositorio...[/cyan]"):
                result = await git_clone(**args)
            data = json.loads(result[0].text)
            if "error" in data:
                console.print(f"[red]✗ Error: {data['error']}[/red]")
            else:
                console.print(
                    f"[green]✓ {data.get('status', 'OK').upper()}:[/green] "
                    f"[bold]{data.get('repo_name')}[/bold] → {data.get('path')}\n"
                    f"  Commit: [dim]{data.get('commit')}[/dim]"
                )
                _session["pipeline_id"] = _session["pipeline_id"] or data.get("repo_name", "")
            return ""

        elif tool == "git_analyze":
            from mcp_servers.git.tools import git_analyze_readme
            with console.status(f"[cyan]Analizando README de {args.get('repo_name')}...[/cyan]"):
                result = await git_analyze_readme(**args)
            data = json.loads(result[0].text)
            _session["last_readme_analysis"] = result[0].text

            # Tabla de endpoints detectados
            endpoints = data.get("happy_path_endpoints", [])
            if endpoints:
                table = Table(title="Endpoints detectados", show_header=True)
                table.add_column("Método", style="bold yellow", width=8)
                table.add_column("Path", style="cyan")
                table.add_column("Descripción")
                for ep in endpoints:
                    table.add_row(ep["method"].upper(), ep["path"], ep.get("description", ""))
                console.print(table)
            console.print(
                f"\n[dim]Setup: {len(data.get('setup_commands', []))} comandos | "
                f"Auth: {data.get('auth_hint', 'none')} | "
                f"Start: [italic]{data.get('start_command', 'N/A')}[/italic][/dim]"
            )
            return ""

        elif tool == "git_status":
            from mcp_servers.git.tools import git_get_info
            result = await git_get_info(repo_name=args.get("repo_name") or "")
            data = json.loads(result[0].text)
            if "error" in data:
                console.print(f"[red]✗ {data['error']}[/red]")
            else:
                commit = data.get("last_commit", {})
                console.print(
                    f"[bold]{data['repo_name']}[/bold] "
                    f"→ [cyan]{data.get('branch')}[/cyan] | "
                    f"commit [dim]{commit.get('sha', 'N/A')[:8]}[/dim]: "
                    f"{commit.get('message', '')[:60]}"
                )
            return ""

        # ── Drive / User Stories ─────────────────────────────────────────────
        elif tool == "drive_list":
            from mcp_servers.drive.tools import drive_list_files
            settings = get_settings()
            folder_id = getattr(settings, "google_drive_folder_id", "") or ""
            with console.status("[cyan]Listando Google Drive...[/cyan]"):
                result = await drive_list_files(folder_id=folder_id)
            data = json.loads(result[0].text)
            files = data if isinstance(data, list) else data.get("files", [])
            table = Table(title="Google Drive", show_header=True)
            table.add_column("ID", style="dim", width=45)
            table.add_column("Nombre")
            table.add_column("Modificado", style="dim")
            for f in files[:20]:
                table.add_row(f.get("id", ""), f.get("name", ""), f.get("modifiedTime", "")[:10])
            console.print(table)
            return ""

        elif tool == "drive_extract":
            from mcp_servers.drive.tools import drive_read_file
            file_id = args.get("file_id", "")
            with console.status(f"[cyan]Leyendo archivo {file_id[:12]}... y extrayendo historias[/cyan]"):
                result = await drive_read_file(file_id=file_id)
                content = result[0].text

            # Extraer user stories con el nodo del orquestador
            import uuid
            from typing import cast as _cast
            from src.orchestrator.nodes.extract_stories import extract_stories_node
            from src.orchestrator.state import AgentState as _AgentState
            fake_state = {
                "pipeline_id": _session.get("pipeline_id") or str(uuid.uuid4())[:8],
                "transcription_content": content,
                "transcription_file_id": file_id,
                "errors": [],
            }
            _session["pipeline_id"] = fake_state["pipeline_id"]

            updates = await extract_stories_node(_cast(_AgentState, fake_state))
            stories = updates.get("user_stories", [])
            _session["user_stories"] = stories
            warnings = updates.get("extraction_warnings", [])

            console.print(f"\n[green]✓ {len(stories)} User Stories extraídas[/green]")
            if warnings:
                console.print(f"[yellow]⚠ {len(warnings)} avisos:[/yellow]")
                for w in warnings:
                    console.print(f"  [yellow]- {w}[/yellow]")
            for i, s in enumerate(stories[:5], 1):
                console.print(
                    f"  [bold]{i}.[/bold] [{s.priority.value if hasattr(s.priority,'value') else s.priority}] "
                    f"{s.title[:70]}"
                )
            if len(stories) > 5:
                console.print(f"  [dim]... y {len(stories)-5} más. Usa 'story list' para ver todas.[/dim]")
            return ""

        elif tool == "story_list":
            stories = _session.get("user_stories", [])
            if not stories:
                console.print("[yellow]No hay User Stories en la sesión. Usa 'extract <file_id>' primero.[/yellow]")
                return ""
            table = Table(title=f"User Stories ({len(stories)})", show_header=True)
            table.add_column("#", width=4)
            table.add_column("Prioridad", width=10)
            table.add_column("Título")
            table.add_column("ACs", width=5)
            table.add_column("Conf.", width=6)
            for i, s in enumerate(stories, 1):
                prio = s.priority.value if hasattr(s.priority, "value") else str(s.priority)
                color = {"Critical": "red", "High": "yellow", "Medium": "cyan", "Low": "dim"}.get(prio, "white")
                conf = getattr(s, "confidence_score", 1.0)
                conf_icon = "✅" if conf >= 0.7 else "⚠️"
                table.add_row(
                    str(i), f"[{color}]{prio}[/{color}]",
                    s.title[:60], str(len(s.acceptance_criteria)),
                    f"{conf_icon} {conf:.0%}",
                )
            console.print(table)
            return ""

        elif tool == "story_create":
            stories = _session.get("user_stories", [])
            if not stories:
                console.print("[yellow]No hay User Stories. Ejecuta 'extract <file_id>' primero.[/yellow]")
                return ""
            from typing import cast as _cast
            from src.orchestrator.nodes.create_jira import create_jira_node
            from src.orchestrator.state import AgentState as _AgentState
            fake_state = {
                "pipeline_id": _session.get("pipeline_id", "manual"),
                "user_stories": stories,
                "human_approved": True,  # Desde consola se considera aprobado
                "errors": [],
            }
            with console.status("[cyan]Creando issues en Jira...[/cyan]"):
                updates = await create_jira_node(_cast(_AgentState, fake_state))
            issue_ids = updates.get("jira_issue_ids", [])
            errors = updates.get("jira_creation_errors", [])
            _session["jira_issue_ids"] = issue_ids
            console.print(f"[green]✓ {len(issue_ids)}/{len(stories)} issues creados en Jira[/green]")
            for iid in issue_ids:
                console.print(f"  → [cyan]{iid}[/cyan]")
            if errors:
                for e in errors:
                    console.print(f"  [red]✗ {e}[/red]")
            return ""

        elif tool == "test_setup":
            from mcp_servers.pos_api.tools import pos_api_setup
            from mcp_servers.workspace.audit import log_event
            
            pipeline_id = _session.get("pipeline_id", "manual")
            log_event("test_setup", f"Configurando API {args.get('repo_name')}", "running", pipeline_id)
            
            with console.status(f"[cyan]Configurando API {args.get('repo_name')}...[/cyan]"):
                result = await pos_api_setup(**args)
            data = json.loads(result[0].text)
            
            if data.get("success"):
                console.print(
                    f"[green]✓ Configuración Finalizada:[/green]\n"
                    f"  {data.get('endpoints_detected', 0)} endpoints detectados.\n"
                    f"[yellow]{data.get('message', '')}[/yellow]"
                )
                _session["api_base_url"] = data.get("base_url", "")
                log_event("test_setup", "API configurada y lista", "success", pipeline_id)
            else:
                console.print(f"[red]✗ Setup falló: {data.get('message')}[/red]")
                log_event("test_setup", f"Fallo setup: {data.get('message')}", "failed", pipeline_id)
            return ""

        elif tool == "test_run":
            from mcp_servers.pos_api.tools import pos_api_run_happy_path
            from mcp_servers.workspace.audit import log_event
            
            pipeline_id = _session.get("pipeline_id", "manual")
            log_event("test_run", "Iniciando pruebas de API", "running", pipeline_id)
            
            readme_json = _session.get("last_readme_analysis", "")
            with console.status("[cyan]Ejecutando happy path...[/cyan]"):
                result = await pos_api_run_happy_path(
                    repo_name=args.get("repo_name") or "",
                    base_url=args.get("base_url") or _session.get("api_base_url"),
                    readme_analysis_json=readme_json or None,
                )
            data = json.loads(result[0].text)
            _session["last_suite_json"] = result[0].text

            if "error" in data:
                console.print(f"[red]✗ Error: {data['error']}[/red]")
                log_event("test_run", f"Error en test_run: {data['error']}", "failed", pipeline_id)
                return ""
            
            log_event(
                "test_run", 
                f"Pruebas finalizadas: {data.get('passed', 0)}/{data.get('total', 0)} exitosas", 
                "success", 
                pipeline_id,
                tokens_used=data.get("tokens_used", 0)
            )

            # Tabla de resultados
            table = Table(title="Resultados Happy Path", show_header=True)
            table.add_column("Test", style="bold")
            table.add_column("Estado", width=8)
            table.add_column("Status HTTP", width=11)
            table.add_column("Tiempo", width=8)
            for r in data.get("results", []):
                status = r.get("status", "UNKNOWN")
                icon = "✅" if status == "PASS" else "❌"
                resp_time = r.get("response_time_ms")
                resp_time_str = f"{resp_time:.0f}ms" if resp_time is not None else "N/A"
                
                status_code = str(r.get("actual_status_code", "N/A"))
                if status_code == "None":
                    status_code = "Error red"
                
                table.add_row(
                    r.get("test_case_name", "")[:50],
                    f"{icon} {status}",
                    status_code,
                    resp_time_str,
                )
            console.print(table)

            results_list = data.get("results", [])
            total = len(results_list)
            passed = sum(1 for r in results_list if r.get("status") == "PASS")
            pass_rate_float = passed / total if total > 0 else 0.0
            pass_rate_str = f"{pass_rate_float:.0%}"
            
            color = "green" if pass_rate_float >= 0.9 else "yellow" if pass_rate_float >= 0.7 else "red"
            console.print(
                f"\n[{color}]Resultado: {passed}/{total} PASS "
                f"({pass_rate_str})[/{color}]"
            )
            return ""

        elif tool == "test_suggest":
            suite_json = _session.get("last_suite_json", "")
            if not suite_json:
                console.print("[yellow]Ejecuta 'test run <repo>' primero para obtener sugerencias.[/yellow]")
                return ""
            data = json.loads(suite_json)
            suggestions = data.get("automation_suggestions", [])
            if not suggestions:
                console.print("[dim]No hay sugerencias disponibles.[/dim]")
                return ""
            console.print(Panel(
                "\n".join(f"[cyan]{i}.[/cyan] {s}" for i, s in enumerate(suggestions, 1)),
                title="💡 Sugerencias de Automatización",
                border_style="yellow",
            ))
            return ""

        elif tool == "test_shutdown":
            from mcp_servers.pos_api.tools import pos_api_shutdown
            result = await pos_api_shutdown(**args)
            data = json.loads(result[0].text)
            console.print(
                f"[green]✓ Servidor detenido[/green]" if data.get("status") == "stopped"
                else f"[yellow]⚠ No había servidor activo[/yellow]"
            )
            return ""

        # ── Reportes ─────────────────────────────────────────────────────────
        elif tool == "report_generate":
            suite_json = _session.get("last_suite_json", "")
            if not suite_json:
                console.print("[yellow]Ejecuta 'test run <repo>' primero para generar reporte.[/yellow]")
                return ""
            from mcp_servers.reporting.tools import reporting_generate_md, reporting_generate_pdf
            with console.status("[cyan]Generando reporte...[/cyan]"):
                md_result = await reporting_generate_md(
                    suite_result_json=suite_json,
                    pipeline_id=_session.get("pipeline_id", ""),
                )
            md_data = json.loads(md_result[0].text)
            _session["last_report_md"] = md_data.get("path", "")
            console.print(
                f"[green]✓ Reporte MD:[/green] [bold]{md_data.get('filename')}[/bold]\n"
                f"  {md_data.get('chars', 0)} caracteres"
            )
            # Intentar PDF
            if md_data.get("path"):
                with console.status("[cyan]Convirtiendo a PDF...[/cyan]"):
                    try:
                        pdf_result = await reporting_generate_pdf(md_path=md_data["path"])
                        pdf_data = json.loads(pdf_result[0].text)
                        if "error" not in pdf_data:
                            console.print(
                                f"[green]✓ PDF:[/green] [bold]{pdf_data.get('filename')}[/bold] "
                                f"({pdf_data.get('size_bytes', 0) // 1024}KB)"
                            )
                    except Exception as e:
                        console.print(f"[yellow]⚠ PDF no generado: {e}[/yellow]")
            return ""

        elif tool == "report_show":
            md_path = _session.get("last_report_md", "")
            if not md_path:
                # Buscar el más reciente
                from mcp_servers.workspace.tools import workspace_list_reports
                result = await workspace_list_reports(pattern="*.md")
                data = json.loads(result[0].text)
                reports = data.get("reports", [])
                if reports:
                    md_path = reports[0].get("path", "")
            if not md_path:
                console.print("[yellow]No hay reportes generados. Usa 'report generate' primero.[/yellow]")
                return ""
            from pathlib import Path
            # Asegurar que apunta al .md (no al PDF binario)
            if not md_path.endswith(".md"):
                md_path = str(Path(md_path).with_suffix(".md"))
            if not Path(md_path).exists():
                console.print(f"[yellow]Reporte MD no encontrado: {md_path}[/yellow]")
                return ""
            content = Path(md_path).read_text(encoding="utf-8")
            console.print(Panel(content[:3000] + ("..." if len(content) > 3000 else ""),
                                title=Path(md_path).name, border_style="green"))
            return ""

        elif tool == "report_upload":
            md_path = _session.get("last_report_md", "")
            if not md_path:
                # Buscar el más reciente en disco si la sesión se reinició
                from mcp_servers.workspace.tools import workspace_list_reports
                result = await workspace_list_reports(pattern="*.md")
                data = json.loads(result[0].text)
                reports = data.get("reports", [])
                if reports:
                    md_path = reports[0].get("path", "")
            if not md_path:
                console.print("[yellow]Genera un reporte primero con 'report generate'.[/yellow]")
                return ""
            from pathlib import Path
            import base64
            issue_id = args.get("issue_id", "")
            content_b64 = base64.b64encode(Path(md_path).read_bytes()).decode()
            from mcp_servers.jira.tools import jira_upload_attachment
            with console.status(f"[cyan]Subiendo a {issue_id}...[/cyan]"):
                result = await jira_upload_attachment(
                    issue_id=issue_id,
                    filename=Path(md_path).name,
                    content_base64=content_b64,
                )
            data = json.loads(result[0].text)
            if "error" in data:
                console.print(f"[red]✗ Error MD: {data['error']}[/red]")
                return ""
            console.print(f"[green]✓ Reporte MD subido a [bold]{issue_id}[/bold][/green]")
            # Subir PDF si existe
            from pathlib import Path as _Path
            _pdf = _Path(md_path).with_suffix(".pdf")
            if _pdf.exists():
                _pdf_b64 = base64.b64encode(_pdf.read_bytes()).decode()
                with console.status(f"[cyan]Subiendo PDF a {issue_id}...[/cyan]"):
                    _pr = await jira_upload_attachment(
                        issue_id=issue_id,
                        filename=_pdf.name,
                        content_base64=_pdf_b64,
                    )
                _pd = json.loads(_pr[0].text)
                if "error" not in _pd:
                    console.print(f"[green]✓ PDF subido a [bold]{issue_id}[/bold][/green]")
                else:
                    console.print(f"[yellow]⚠ PDF no subido: {_pd.get('error', '')}[/yellow]")
            return ""

        # ── Log & Workspace ──────────────────────────────────────────────────
        elif tool == "log_show":
            from mcp_servers.workspace.audit import get_log
            entries = get_log(last_n=args.get("last_n", 20))
            if not entries:
                console.print("[dim]Audit log vacío.[/dim]")
                return ""
            table = Table(title="Audit Log", show_header=True)
            table.add_column("Timestamp", style="dim", width=19)
            table.add_column("Tipo", width=22)
            table.add_column("Estado", width=10)
            table.add_column("Mensaje")
            for entry in entries:
                status_color = "green" if entry["status"] == "success" else (
                    "yellow" if entry["status"] in ("running", "paused", "skipped") else "red"
                )
                table.add_row(
                    entry["timestamp"][:19],
                    entry["event_type"],
                    f"[{status_color}]{entry['status']}[/{status_color}]",
                    entry["message"][:70],
                )
            console.print(table)
            return ""

        elif tool == "log_summary":
            pipeline_id = args.get("pipeline_id") or _session.get("pipeline_id", "")
            if not pipeline_id:
                console.print("[yellow]Especifica un pipeline ID: 'log summary --id <id>'[/yellow]")
                return ""
            from mcp_servers.workspace.audit import get_pipeline_summary
            summary = get_pipeline_summary(pipeline_id)
            console.print(Panel(
                f"Pipeline: [bold]{pipeline_id}[/bold]\n"
                f"Eventos: {summary['total_events']} | "
                f"Errores: {summary['error_count']} | "
                f"Tokens: {summary['total_tokens_used']}\n"
                f"Inicio: [dim]{summary.get('started_at', 'N/A')}[/dim]\n"
                f"Último: [dim]{summary.get('last_event_at', 'N/A')}[/dim]",
                title="Pipeline Summary", border_style="blue",
            ))
            return ""

        elif tool == "workspace_list":
            from mcp_servers.workspace.tools import workspace_list_repos, workspace_list_reports
            repos_result = await workspace_list_repos()
            reports_result = await workspace_list_reports()
            repos_data = json.loads(repos_result[0].text)
            reports_data = json.loads(reports_result[0].text)
            repos = repos_data.get("repos", [])
            reports = reports_data.get("reports", [])
            if repos:
                table = Table(title="Repositorios", show_header=True)
                table.add_column("Nombre")
                table.add_column("Git", width=5)
                table.add_column("Tamaño", width=10)
                for r in repos:
                    table.add_row(
                        r["name"],
                        "✅" if r["is_git_repo"] else "✗",
                        f"{r['size_mb']} MB",
                    )
                console.print(table)
            console.print(f"[dim]{len(reports)} reportes generados en total[/dim]")
            return ""

        elif tool == "workspace_clean":
            from mcp_servers.workspace.tools import workspace_cleanup
            with console.status("[cyan]Limpiando workspace...[/cyan]"):
                result = await workspace_cleanup(
                    target="all",
                    older_than_days=args.get("older_than_days", 30),
                )
            data = json.loads(result[0].text)
            console.print(
                f"[green]✓ Limpieza completada:[/green] "
                f"{data.get('files_deleted', 0)} archivos eliminados"
            )
            return ""

        else:
            return f"[yellow]Tool '{tool}' no implementada en la consola interactiva.[/yellow]"

    except Exception as e:
        logger.error("Error ejecutando action", tool=tool, error=str(e))
        console.print(f"[red]✗ ERROR en {tool}: {e}[/red]")
        return ""


async def run_console() -> None:
    """Loop principal de la consola interactiva."""
    settings = get_settings()
    model_display = (
        settings.local_model_name if settings.is_local_llm else settings.anthropic_model
    )

    # Banner inicial
    console.print(BANNER.format(model=model_display, status="IDLE"))
    console.print("[dim]Escribe [bold]help[/bold] para ver los comandos o [bold]exit[/bold] para salir.[/dim]\n")

    loop = asyncio.get_running_loop()

    while True:
        try:
            prompt_text = f"[bold cyan]\\[{model_display.upper()[:12]}][/bold cyan] → "
            command = await loop.run_in_executor(
                None,
                lambda: Prompt.ask(prompt_text),
            )

            if not command.strip():
                # Si el usuario presiona Enter vacío (útil al hacer docker attach)
                console.print(BANNER.format(model=model_display, status="IDLE"))
                continue

            # Routing
            routing = await route(command)

            # Clarificación requerida
            if routing.get("clarification_needed"):
                console.print(f"[yellow]❓ {routing['clarification_needed']}[/yellow]")
                continue

            # Mensaje de estado
            message = routing.get("message", "")
            if message:
                console.print(f"[dim]{message}[/dim]")

            actions = routing.get("actions", [])

            # Solo es un error si NO hay mensaje y NO hay acciones
            if not actions:
                if not message:
                    console.print(
                        "[dim]Comando no reconocido. Escribe 'help' para ver los disponibles.[/dim]"
                    )
                continue

            for action in actions:
                result = await execute_action(action)
                if result == "__EXIT__":
                    console.print("\n[bold yellow]¡Hasta luego! 👋[/bold yellow]")
                    return
                # Los resultados de texto ya son impresos dentro de execute_action

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Usa 'exit' para salir correctamente.[/yellow]")
            return
        except Exception as e:
            console.print(f"[red]Error inesperado: {e}[/red]")
            logger.error("Console loop error", error=str(e))
