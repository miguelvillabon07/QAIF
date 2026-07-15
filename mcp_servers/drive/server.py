"""MCP Server: Google Drive (transporte stdio)."""
from __future__ import annotations

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools import (
    drive_get_metadata,
    drive_list_files,
    drive_read_file,
    drive_search_files,
)

server = Server("google-drive-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="drive_list_files",
            description="Lista archivos en una carpeta de Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_id": {"type": "string", "description": "ID de la carpeta Drive"},
                    "name_filter": {"type": "string", "default": "", "description": "Filtro por nombre"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["folder_id"],
            },
        ),
        types.Tool(
            name="drive_read_file",
            description="Lee el contenido textual de un archivo de Drive (docs, txt, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "ID del archivo en Drive"},
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="drive_get_metadata",
            description="Obtiene metadata de un archivo (nombre, tipo, fecha, propietario)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string"},
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="drive_search_files",
            description="Busca archivos en Drive por nombre",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a buscar en el nombre"},
                    "folder_id": {"type": "string", "default": "", "description": "Limitar búsqueda a carpeta"},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    dispatch = {
        "drive_list_files": lambda: drive_list_files(**arguments),
        "drive_read_file": lambda: drive_read_file(**arguments),
        "drive_get_metadata": lambda: drive_get_metadata(**arguments),
        "drive_search_files": lambda: drive_search_files(**arguments),
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
