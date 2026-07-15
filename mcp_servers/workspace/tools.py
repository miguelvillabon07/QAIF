"""Herramientas del MCP Server de Workspace."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp import types

from config.settings import get_settings
from src.utils.logging_config import get_logger

from .audit import get_log, get_pipeline_summary, log_event

logger = get_logger("mcp.workspace")


async def workspace_list_repos() -> list[types.TextContent]:
    """Lista todos los repositorios clonados en el workspace."""
    settings = get_settings()
    workspace = settings.git_workspace_path
    try:
        repos = []
        if workspace.exists():
            for d in sorted(workspace.iterdir()):
                if d.is_dir():
                    git_dir = d / ".git"
                    size_mb = sum(
                        f.stat().st_size for f in d.rglob("*") if f.is_file()
                    ) / (1024 * 1024)
                    repos.append({
                        "name": d.name,
                        "path": str(d),
                        "is_git_repo": git_dir.exists(),
                        "size_mb": round(size_mb, 2),
                    })
        logger.info("workspace_list_repos OK", count=len(repos))
        return [types.TextContent(type="text", text=json.dumps({
            "repos": repos,
            "count": len(repos),
            "workspace_path": str(workspace),
        }, indent=2))]
    except Exception as e:
        logger.error("workspace_list_repos FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def workspace_get_summary(pipeline_id: str) -> list[types.TextContent]:
    """Retorna todas las operaciones de un pipeline en orden cronológico."""
    try:
        summary = get_pipeline_summary(pipeline_id)
        logger.info(
            "workspace_get_summary OK",
            pipeline_id=pipeline_id,
            total=summary["total_events"],
        )
        return [types.TextContent(
            type="text",
            text=json.dumps(summary, ensure_ascii=False, indent=2),
        )]
    except Exception as e:
        logger.error("workspace_get_summary FAIL", pipeline_id=pipeline_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def workspace_list_reports(pattern: str = "*.md") -> list[types.TextContent]:
    """Lista todos los reportes generados en el directorio de reportes."""
    settings = get_settings()
    reports_dir = settings.report_output_dir
    try:
        reports = []
        if reports_dir.exists():
            for f in sorted(reports_dir.glob(pattern), reverse=True):
                if f.is_file():
                    stat = f.stat()
                    reports.append({
                        "name": f.name,
                        "path": str(f),
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "extension": f.suffix,
                    })
        logger.info("workspace_list_reports OK", count=len(reports))
        return [types.TextContent(type="text", text=json.dumps({
            "reports": reports,
            "count": len(reports),
            "reports_dir": str(reports_dir),
        }, indent=2))]
    except Exception as e:
        logger.error("workspace_list_reports FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def workspace_read_report(report_name: str) -> list[types.TextContent]:
    """Lee el contenido de un reporte generado."""
    settings = get_settings()
    report_path = settings.report_output_dir / report_name
    try:
        if not report_path.exists():
            # Buscar también en subdirectorios
            matches = list(settings.report_output_dir.rglob(report_name))
            if not matches:
                return [types.TextContent(type="text", text=json.dumps({
                    "error": f"Reporte '{report_name}' no encontrado en {settings.report_output_dir}",
                }))]
            report_path = matches[0]

        content = report_path.read_text(encoding="utf-8")
        logger.info("workspace_read_report OK", name=report_name, chars=len(content))
        return [types.TextContent(type="text", text=content)]
    except Exception as e:
        logger.error("workspace_read_report FAIL", name=report_name, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def workspace_cleanup(
    target: str = "logs",
    older_than_days: int = 30,
) -> list[types.TextContent]:
    """
    Limpia archivos del workspace.
    target: 'logs' | 'reports' | 'repos' | 'all'
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    deleted = []

    targets_map = {
        "logs": [settings.audit_log_dir],
        "reports": [settings.report_output_dir],
        "repos": [settings.git_workspace_path],
        "all": [settings.audit_log_dir, settings.report_output_dir],
    }
    dirs = targets_map.get(target, [])
    if not dirs:
        return [types.TextContent(type="text", text=json.dumps({
            "error": f"Target inválido: '{target}'. Usa: logs | reports | repos | all",
        }))]

    cutoff_ts = now.timestamp() - (older_than_days * 86400)
    for d in dirs:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff_ts:
                deleted.append(str(f))
                f.unlink()

    logger.info("workspace_cleanup OK", target=target, deleted=len(deleted))
    log_event(
        event_type="workspace_cleanup",
        message=f"Limpieza de {target}: {len(deleted)} archivos eliminados",
        metadata={"target": target, "older_than_days": older_than_days, "deleted": deleted},
    )
    return [types.TextContent(type="text", text=json.dumps({
        "status": "cleaned",
        "target": target,
        "files_deleted": len(deleted),
        "deleted_paths": deleted,
    }, indent=2))]


async def workspace_get_status() -> list[types.TextContent]:
    """Retorna el estado general del workspace: repos, reportes, logs y CAG."""
    settings = get_settings()

    def dir_info(path: Path) -> dict:
        if not path.exists():
            return {"exists": False, "files": 0, "size_mb": 0}
        files = list(path.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        size_bytes = sum(f.stat().st_size for f in files if f.is_file())
        return {
            "exists": True,
            "files": file_count,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "path": str(path),
        }

    # Verificar Redis
    redis_ok = False
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    status = {
        "workspace": {
            "repos": dir_info(settings.git_workspace_path),
            "reports": dir_info(settings.report_output_dir),
            "logs": dir_info(settings.audit_log_dir),
        },
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.local_model_name if settings.is_local_llm else settings.anthropic_model,
        },
        "cag": {
            "enabled": settings.cag_enabled,
            "redis_available": redis_ok,
            "redis_url": settings.redis_url,
        },
        "integrations": {
            "jira_configured": settings.jira_configured,
            "drive_configured": settings.drive_configured,
            "anthropic_configured": settings.anthropic_configured,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("workspace_get_status OK", redis=redis_ok, llm=settings.llm_provider)
    return [types.TextContent(type="text", text=json.dumps(status, indent=2))]


async def workspace_log_event(
    event_type: str,
    message: str,
    pipeline_id: str = "",
    status: str = "success",
    metadata: Optional[dict] = None,
    tokens_used: int = 0,
) -> list[types.TextContent]:
    """Registra un evento manualmente en el audit trail."""
    try:
        log_event(
            event_type=event_type,
            message=message,
            pipeline_id=pipeline_id,
            status=status,
            metadata=metadata or {},
            tokens_used=tokens_used,
        )
        return [types.TextContent(type="text", text=json.dumps({
            "status": "logged",
            "event_type": event_type,
            "pipeline_id": pipeline_id,
        }))]
    except Exception as e:
        logger.error("workspace_log_event FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
