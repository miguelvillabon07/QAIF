"""MCP Server: POS API testing (transporte stdio)."""
from __future__ import annotations

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools import (
    pos_api_get_base_url,
    pos_api_health_check,
    pos_api_list_endpoints,
    pos_api_run_custom_test,
    pos_api_run_happy_path,
    pos_api_run_test_case,
    pos_api_setup,
    pos_api_shutdown,
)

server = Server("pos-api-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="pos_api_setup",
            description="Configura y lanza la API local desde un repo clonado (instala deps, lanza servidor)",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string"},
                    "base_url": {"type": "string", "description": "URL base (opcional, se detecta del README)"},
                },
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="pos_api_run_happy_path",
            description="Ejecuta todos los endpoints del happy path detectados en el README",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string"},
                    "base_url": {"type": "string"},
                    "readme_analysis_json": {"type": "string", "description": "JSON del ReadmeAnalysis (opcional)"},
                },
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="pos_api_run_test_case",
            description="Ejecuta un TestCase específico (JSON) contra la API",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_case_json": {"type": "string", "description": "TestCase serializado como JSON"},
                    "base_url": {"type": "string"},
                },
                "required": ["test_case_json", "base_url"],
            },
        ),
        types.Tool(
            name="pos_api_shutdown",
            description="Detiene el servidor de la API local",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="pos_api_list_endpoints",
            description="Lista los endpoints detectados en el README para un repo",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="pos_api_run_custom_test",
            description="Ejecuta un test ad-hoc contra cualquier endpoint",
            inputSchema={
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                    "base_url": {"type": "string"},
                    "payload": {"type": "object"},
                    "expected_status": {"type": "integer", "default": 200},
                    "headers": {"type": "object"},
                },
                "required": ["endpoint", "method", "base_url"],
            },
        ),
        types.Tool(
            name="pos_api_get_base_url",
            description="Retorna la base URL del servidor activo para un repo",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="pos_api_health_check",
            description="Verifica que el servidor de la API esté respondiendo",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    dispatch = {
        "pos_api_setup": lambda: pos_api_setup(**arguments),
        "pos_api_run_happy_path": lambda: pos_api_run_happy_path(**arguments),
        "pos_api_run_test_case": lambda: pos_api_run_test_case(**arguments),
        "pos_api_shutdown": lambda: pos_api_shutdown(**arguments),
        "pos_api_list_endpoints": lambda: pos_api_list_endpoints(**arguments),
        "pos_api_run_custom_test": lambda: pos_api_run_custom_test(**arguments),
        "pos_api_get_base_url": lambda: pos_api_get_base_url(**arguments),
        "pos_api_health_check": lambda: pos_api_health_check(**arguments),
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
