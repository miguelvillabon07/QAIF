"""MCP Server: Workspace management (transporte stdio)."""
from __future__ import annotations

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools import (
    workspace_cleanup,
    workspace_get_status,
    workspace_get_summary,
    workspace_list_repos,
    workspace_list_reports,
    workspace_log_event,
    workspace_read_report,
)

server = Server("workspace-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="workspace_list_repos",
            description="Lista todos los repositorios clonados en el workspace",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="workspace_get_summary",
            description="Retorna el historial completo de operaciones de un pipeline",
            inputSchema={
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "ID del pipeline a consultar"},
                },
                "required": ["pipeline_id"],
            },
        ),
        types.Tool(
            name="workspace_list_reports",
            description="Lista todos los reportes generados (MD y PDF)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "default": "*.md", "description": "Glob pattern (e.g., *.pdf)"},
                },
            },
        ),
        types.Tool(
            name="workspace_read_report",
            description="Lee el contenido de un reporte generado",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_name": {"type": "string", "description": "Nombre del archivo de reporte"},
                },
                "required": ["report_name"],
            },
        ),
        types.Tool(
            name="workspace_cleanup",
            description="Elimina archivos antiguos del workspace (logs, reportes)",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["logs", "reports", "all"],
                        "default": "logs",
                        "description": "Qué limpiar",
                    },
                    "older_than_days": {"type": "integer", "default": 30},
                },
            },
        ),
        types.Tool(
            name="workspace_get_status",
            description="Estado general del workspace: repos, reportes, Redis/CAG, integraciones",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="workspace_log_event",
            description="Registra un evento manualmente en el audit trail JSONL",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "message": {"type": "string"},
                    "pipeline_id": {"type": "string", "default": ""},
                    "status": {"type": "string", "default": "success"},
                    "metadata": {"type": "object"},
                    "tokens_used": {"type": "integer", "default": 0},
                },
                "required": ["event_type", "message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    dispatch = {
        "workspace_list_repos": lambda: workspace_list_repos(),
        "workspace_get_summary": lambda: workspace_get_summary(**arguments),
        "workspace_list_reports": lambda: workspace_list_reports(**arguments),
        "workspace_read_report": lambda: workspace_read_report(**arguments),
        "workspace_cleanup": lambda: workspace_cleanup(**arguments),
        "workspace_get_status": lambda: workspace_get_status(),
        "workspace_log_event": lambda: workspace_log_event(**arguments),
    }
    handler = dispatch.get(name)
    if not handler:
        return [types.TextContent(type="text", text=f'{{"error": "Tool desconocida: {name}"}}')] 
    return await handler()


async def main() -> None:
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
