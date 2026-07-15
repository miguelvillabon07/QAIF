"""MCP Server: Jira Cloud (transporte stdio)."""
from __future__ import annotations

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools import (
    jira_add_comment,
    jira_create_issue,
    jira_get_issue,
    jira_link_issues,
    jira_search_issues,
    jira_transition_issue,
    jira_update_issue,
    jira_upload_attachment,
)

server = Server("jira-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="jira_create_issue",
            description="Crea un issue en Jira (Story, Bug, Task)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string"},
                    "summary": {"type": "string"},
                    "description": {"type": "string"},
                    "issue_type": {"type": "string", "default": "Story"},
                    "priority": {"type": "string", "default": "Medium"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "epic_key": {"type": "string"},
                },
                "required": ["project_key", "summary", "description"],
            },
        ),
        types.Tool(
            name="jira_get_issue",
            description="Obtiene un issue completo por su key (e.g., PROJ-42)",
            inputSchema={
                "type": "object",
                "properties": {"issue_id": {"type": "string"}},
                "required": ["issue_id"],
            },
        ),
        types.Tool(
            name="jira_update_issue",
            description="Actualiza campos de un issue existente",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "fields": {"type": "object", "description": "Dict de campos a actualizar"},
                },
                "required": ["issue_id", "fields"],
            },
        ),
        types.Tool(
            name="jira_add_comment",
            description="Agrega un comentario a un issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "comment_body": {"type": "string"},
                },
                "required": ["issue_id", "comment_body"],
            },
        ),
        types.Tool(
            name="jira_upload_attachment",
            description="Sube un archivo como attachment (PDF de reporte, etc.). Contenido en base64.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "filename": {"type": "string"},
                    "content_base64": {"type": "string"},
                },
                "required": ["issue_id", "filename", "content_base64"],
            },
        ),
        types.Tool(
            name="jira_transition_issue",
            description="Cambia el estado de un issue (To Do → In Progress → Done)",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "transition_name": {"type": "string", "description": "Nombre del estado destino"},
                },
                "required": ["issue_id", "transition_name"],
            },
        ),
        types.Tool(
            name="jira_link_issues",
            description="Crea un enlace entre dos issues (Relates, Blocks, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "link_type": {"type": "string", "default": "Relates"},
                },
                "required": ["source_id", "target_id"],
            },
        ),
        types.Tool(
            name="jira_search_issues",
            description="Busca issues con JQL (Jira Query Language)",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {"type": "string", "description": "Query JQL"},
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["jql"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    dispatch = {
        "jira_create_issue": lambda: jira_create_issue(**arguments),
        "jira_get_issue": lambda: jira_get_issue(**arguments),
        "jira_update_issue": lambda: jira_update_issue(**arguments),
        "jira_add_comment": lambda: jira_add_comment(**arguments),
        "jira_upload_attachment": lambda: jira_upload_attachment(**arguments),
        "jira_transition_issue": lambda: jira_transition_issue(**arguments),
        "jira_link_issues": lambda: jira_link_issues(**arguments),
        "jira_search_issues": lambda: jira_search_issues(**arguments),
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
