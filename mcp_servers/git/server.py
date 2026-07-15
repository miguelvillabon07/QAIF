"""MCP Server: Git operations (transporte stdio)."""
from __future__ import annotations

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools import (
    git_analyze_readme,
    git_clone,
    git_detect_api_spec,
    git_get_info,
    git_list_files,
    git_pull,
    git_read_file,
)

server = Server("git-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="git_clone",
            description="Clona un repositorio Git. Si ya existe, hace pull.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "URL del repositorio"},
                    "repo_name": {"type": "string", "description": "Nombre local (opcional)"},
                    "branch": {"type": "string", "description": "Rama a clonar (opcional)"},
                },
                "required": ["repo_url"],
            },
        ),
        types.Tool(
            name="git_pull",
            description="Actualiza un repositorio ya clonado con git pull",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="git_read_file",
            description="Lee el contenido de un archivo dentro del repositorio clonado",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string"},
                    "file_path": {"type": "string", "description": "Ruta relativa al repo (e.g., src/main.py)"},
                },
                "required": ["repo_name", "file_path"],
            },
        ),
        types.Tool(
            name="git_list_files",
            description="Lista archivos del repo con soporte de glob pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string"},
                    "pattern": {"type": "string", "default": "**/*", "description": "Glob pattern"},
                    "max_files": {"type": "integer", "default": 100},
                },
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="git_analyze_readme",
            description="Analiza el README con LLM y extrae endpoints, comandos de setup y dependencias",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="git_get_info",
            description="Obtiene información del repo: rama, último commit, remotes",
            inputSchema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
            },
        ),
        types.Tool(
            name="git_detect_api_spec",
            description="Detecta y retorna el OpenAPI/Swagger spec del repositorio si existe",
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
        "git_clone": lambda: git_clone(**arguments),
        "git_pull": lambda: git_pull(**arguments),
        "git_read_file": lambda: git_read_file(**arguments),
        "git_list_files": lambda: git_list_files(**arguments),
        "git_analyze_readme": lambda: git_analyze_readme(**arguments),
        "git_get_info": lambda: git_get_info(**arguments),
        "git_detect_api_spec": lambda: git_detect_api_spec(**arguments),
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
