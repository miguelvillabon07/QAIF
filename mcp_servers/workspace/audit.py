"""Audit trail persistente en formato JSONL."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import get_settings


from datetime import timedelta

_start_times: dict[str, datetime] = {}

def log_event(
    event_type: str,
    message: str,
    status: str = "success",
    pipeline_id: str = "",
    metadata: Optional[dict] = None,
    tokens_used: int = 0,
) -> None:
    """Escribe una entrada en el audit log JSONL del día actual."""
    settings = get_settings()
    log_dir = settings.audit_log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configurar zona horaria usando el offset de los settings
    tz = timezone(timedelta(hours=settings.timezone_offset_hours))
    now_local = datetime.now(tz)
    today = now_local.strftime("%Y-%m-%d")
    log_file = log_dir / f"audit_{today}.jsonl"

    # Calcular duración si no es un evento de inicio ('running')
    duration_ms = 0
    duration_time = "0:00"
    cache_key = f"{pipeline_id}:{event_type}"
    if status == "running":
        _start_times[cache_key] = now_local
    else:
        if cache_key in _start_times:
            start_time = _start_times.pop(cache_key)
            duration_ms = int((now_local - start_time).total_seconds() * 1000)
            mins, secs = divmod(duration_ms // 1000, 60)
            duration_time = f"{mins}:{secs:02d}"

    # Asignar comando status humano
    command_status = "command running"
    if status == "success":
        command_status = "command successful"
    elif status == "failed" or status == "error":
        command_status = "command failed"

    # Determinar si fue por consola manual o por pipeline (LLM)
    exec_source = "console" if pipeline_id in ("", "manual", None) else f"llm_pipeline ({pipeline_id})"
    if metadata is None:
        metadata = {}
    metadata["execution_source"] = exec_source

    entry = {
        "timestamp": now_local.isoformat(),
        "pipeline_id": pipeline_id,
        "event_type": event_type,
        "status": status,
        "command_status": command_status,
        "message": message,
        "metadata": metadata,
        "tokens_used": tokens_used,
        "duration_ms": duration_ms,
        "duration_time": duration_time,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_log(
    last_n: int = 50,
    event_type_filter: str = "",
    pipeline_id_filter: str = "",
) -> list[dict]:
    """Recupera las últimas N entradas del audit log con filtros opcionales."""
    settings = get_settings()
    log_dir = settings.audit_log_dir

    if not log_dir.exists():
        return []

    entries: list[dict] = []
    # Iterar archivos en orden descendente (más reciente primero)
    for log_file in sorted(log_dir.glob("audit_*.jsonl"), reverse=True):
        try:
            with open(log_file, encoding="utf-8") as f:
                # Leer en reversa para obtener las más recientes primero
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if event_type_filter and entry.get("event_type") != event_type_filter:
                        continue
                    if pipeline_id_filter and entry.get("pipeline_id") != pipeline_id_filter:
                        continue
                    entries.append(entry)
                    if len(entries) >= last_n:
                        return entries
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass
    return entries


def get_pipeline_summary(pipeline_id: str) -> dict:
    """Retorna resumen agregado de todas las operaciones de un pipeline."""
    entries = get_log(last_n=500, pipeline_id_filter=pipeline_id)
    if not entries:
        return {"pipeline_id": pipeline_id, "events": [], "total": 0}

    # Ordenar cronológicamente
    entries.sort(key=lambda e: e.get("timestamp", ""))

    total_tokens = sum(e.get("tokens_used", 0) for e in entries)
    event_types = list({e["event_type"] for e in entries})
    errors = [e for e in entries if e.get("status") == "error"]

    return {
        "pipeline_id": pipeline_id,
        "total_events": len(entries),
        "total_tokens_used": total_tokens,
        "event_types": event_types,
        "error_count": len(errors),
        "started_at": entries[0]["timestamp"] if entries else None,
        "last_event_at": entries[-1]["timestamp"] if entries else None,
        "events": entries,
    }
