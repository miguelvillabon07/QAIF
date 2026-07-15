#!/usr/bin/env python3
"""
Verifica todas las conexiones y servicios del stack MCP QA Automation.

Uso:
    uv run python scripts/health_check.py
    python scripts/health_check.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CREDENTIALS_GUIDE = "docs/credentials_guide.md"


# ── Checks individuales ──────────────────────────────────────────────────────

async def check_ollama(base_url: str, model: str) -> tuple[bool, str]:
    try:
        import httpx

        tags_url = base_url.replace("/v1", "") + "/api/tags"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(tags_url)
            r.raise_for_status()
            tags = r.json()
            models = [m["name"] for m in tags.get("models", [])]
            if any(model in m for m in models):
                return True, f"Modelo '{model}' cargado y disponible"
            else:
                return (
                    True,
                    f"Ollama OK, pero '{model}' NO descargado aún → "
                    f"docker logs mcp-model-puller",
                )
    except Exception as e:
        return (
            False,
            f"Ollama no disponible: {e} → "
            f"¿Está corriendo 'docker compose up'?",
        )


async def check_redis(url: str) -> tuple[bool, str]:
    try:
        import redis.asyncio as aioredis

        r = await aioredis.from_url(url, socket_timeout=5)
        await r.ping()
        info = await r.info("server")
        version = info.get("redis_version", "?")
        keys = await r.dbsize()
        await r.aclose()
        return True, f"Redis {version} OK | {keys} keys en cache"
    except Exception as e:
        return (
            False,
            f"Redis no disponible: {e} → "
            f"¿Está corriendo 'docker compose up redis'?",
        )


async def check_anthropic(api_key: str | None, model: str) -> tuple[bool, str]:
    if not api_key or api_key.startswith("sk-ant-api03-REEMPLAZAR"):
        return (
            False,
            f"ANTHROPIC_API_KEY no configurada → "
            f"Ver {CREDENTIALS_GUIDE} → Sección 2",
        )
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
            if r.status_code == 200:
                return True, f"Anthropic API OK | Modelo: {model}"
            elif r.status_code == 401:
                return (
                    False,
                    f"API Key inválida (401) → Regenerar en console.anthropic.com",
                )
            else:
                return False, f"Anthropic error {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return False, f"Anthropic no alcanzable: {e}"


async def check_drive(
    sa_path: Path | None, folder_id: str | None
) -> tuple[bool, str]:
    if not sa_path or not folder_id:
        return (
            False,
            f"GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_DRIVE_FOLDER_ID no configurados "
            f"→ Ver {CREDENTIALS_GUIDE} → Sección 3",
        )
    folder_placeholder = "REEMPLAZAR_CON_ID"
    if str(folder_id).startswith(folder_placeholder):
        return (
            False,
            f"GOOGLE_DRIVE_FOLDER_ID no reemplazado "
            f"→ Ver {CREDENTIALS_GUIDE} → Paso 6",
        )
    if not Path(sa_path).exists():
        return (
            False,
            f"Archivo no encontrado: {sa_path} "
            f"→ Ver {CREDENTIALS_GUIDE} → Pasos 3-4",
        )
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        result = (
            drive.files()
            .list(q=f"'{folder_id}' in parents", pageSize=5)
            .execute()
        )
        n = len(result.get("files", []))
        sa_email = creds.service_account_email
        return True, f"Drive OK | {n} archivos visibles | SA: {sa_email[:40]}"
    except Exception as e:
        err = str(e)
        if "403" in err or "forbidden" in err.lower():
            return (
                False,
                f"Sin permiso: compartir la carpeta Drive con el email del SA "
                f"→ Ver {CREDENTIALS_GUIDE} → Paso 5",
            )
        return False, f"Drive error: {err[:100]}"


async def check_jira(
    url: str | None, email: str | None, token: str | None
) -> tuple[bool, str]:
    if not all([url, email, token]):
        return (
            False,
            f"JIRA_URL, JIRA_EMAIL o JIRA_API_TOKEN no configurados "
            f"→ Ver {CREDENTIALS_GUIDE} → Sección 4",
        )
    if "REEMPLAZAR" in (token or ""):
        return (
            False,
            f"JIRA_API_TOKEN no reemplazado "
            f"→ Ver {CREDENTIALS_GUIDE} → Sección 4",
        )
    try:
        import httpx
        import base64

        auth = base64.b64encode(f"{email}:{token}".encode()).decode()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{url.rstrip('/')}/rest/api/2/myself",
                headers={"Authorization": f"Basic {auth}"},
            )
            if r.status_code == 200:
                data = r.json()
                name = data.get("displayName", data.get("name", "?"))
                return True, f"Jira OK | Autenticado como: {name}"
            elif r.status_code == 401:
                return (
                    False,
                    f"Token Jira inválido o expirado (401) "
                    f"→ Regenerar en id.atlassian.com",
                )
            else:
                return False, f"Jira error {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, f"Jira no alcanzable: {e}"


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    console.print(
        Panel(
            "[bold cyan]MCP QA Automation — Health Check[/bold cyan]\n"
            f"[dim]Guía de credenciales: {CREDENTIALS_GUIDE}[/dim]",
            border_style="cyan",
        )
    )

    try:
        from config.settings import get_settings

        s = get_settings()
    except Exception as e:
        console.print(f"\n[red]ERROR cargando .env: {e}[/red]")
        console.print(f"[dim]¿Existe el archivo .env? → cp .env.example .env[/dim]")
        sys.exit(1)

    # Definir checks con su criticidad
    checks = [
        # (nombre, coroutine, es_critico)
        ("Ollama (Qwen3)", check_ollama(s.ollama_base_url, s.local_model_name), True),
        ("Redis (CAG)", check_redis(s.redis_url), True),
        ("Anthropic API", check_anthropic(s.anthropic_api_key, s.anthropic_model), False),
        (
            "Google Drive",
            check_drive(s.google_service_account_json, s.google_drive_folder_id),
            False,
        ),
        ("Jira Cloud", check_jira(s.jira_url, s.jira_email, s.jira_api_token), False),
    ]

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Servicio", style="cyan", width=18)
    table.add_column("Estado", width=12)
    table.add_column("Critico", width=9)
    table.add_column("Detalle")

    all_critical_ok = True
    failed_optional: list[str] = []

    for name, coro, is_critical in checks:
        ok, detail = await coro
        if ok:
            status = "[green]✅ OK[/green]"
        else:
            status = "[red]❌ FAIL[/red]"
            if is_critical:
                all_critical_ok = False
            else:
                failed_optional.append(name)

        critical_badge = "[bold red]SI[/bold red]" if is_critical else "[dim]no[/dim]"
        table.add_row(name, status, critical_badge, detail)

    console.print(table)
    console.print()

    if all_critical_ok:
        console.print(
            "[green]✅ Servicios críticos OK — el sistema puede ejecutarse.[/green]"
        )
        console.print(
            "[dim]Inicia la consola con:[/dim] [bold]uv run python -m src.console[/bold]"
        )
        if failed_optional:
            console.print(
                f"\n[yellow]⚠  Servicios opcionales no configurados: "
                f"{', '.join(failed_optional)}[/yellow]"
            )
            console.print(
                f"[dim]  → Para configurarlos: ver [bold]{CREDENTIALS_GUIDE}[/bold][/dim]"
            )
    else:
        console.print(
            "[red]❌ Servicios críticos no disponibles.[/red]\n"
            "[dim]Verifica que Docker esté corriendo:[/dim] "
            "[bold]docker compose up -d[/bold]"
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
