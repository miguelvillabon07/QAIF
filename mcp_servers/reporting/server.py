"""MCP Server: Reporting (transporte stdio)."""
from __future__ import annotations

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools import reporting_generate_md, reporting_generate_pdf, reporting_get_log

server = Server("reporting-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="reporting_generate_md",
            description="Genera un reporte QA en Markdown desde un TestSuiteResult",
            inputSchema={
                "type": "object",
                "properties": {
                    "suite_result_json": {
                        "type": "string",
                        "description": "TestSuiteResult serializado como JSON",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Ruta de salida (opcional, se genera automáticamente)",
                    },
                    "pipeline_id": {"type": "string", "default": ""},
                },
                "required": ["suite_result_json"],
            },
        ),
        types.Tool(
            name="reporting_generate_pdf",
            description="Convierte un reporte .md en PDF usando reportlab",
            inputSchema={
                "type": "object",
                "properties": {
                    "md_path": {"type": "string", "description": "Ruta absoluta al archivo .md"},
                    "output_path": {"type": "string", "description": "Ruta de salida del PDF (opcional)"},
                },
                "required": ["md_path"],
            },
        ),
        types.Tool(
            name="reporting_get_log",
            description="Retorna las últimas N entradas del audit log",
            inputSchema={
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "Filtrar por pipeline ID"},
                    "last_n": {"type": "integer", "default": 50},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    dispatch = {
        "reporting_generate_md": lambda: reporting_generate_md(**arguments),
        "reporting_generate_pdf": lambda: reporting_generate_pdf(**arguments),
        "reporting_get_log": lambda: reporting_get_log(**arguments),
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
