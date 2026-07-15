"""Implementación de las herramientas del MCP Server de Drive."""
from __future__ import annotations

import json

from mcp import types

from src.utils.logging_config import get_logger

from .auth import get_drive_service

logger = get_logger("mcp.drive")

SUPPORTED_EXPORT_MIMES: dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


async def drive_list_files(
    folder_id: str,
    name_filter: str = "",
    max_results: int = 20,
) -> list[types.TextContent]:
    """Lista archivos en una carpeta de Google Drive."""
    logger.info("drive_list_files", folder_id=folder_id, filter=name_filter)
    try:
        drive = get_drive_service()
        query = f"'{folder_id}' in parents and trashed=false"
        if name_filter:
            query += f" and name contains '{name_filter}'"
        result = drive.files().list(
            q=query,
            pageSize=min(max_results, 100),
            fields="files(id,name,mimeType,modifiedTime,size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = result.get("files", [])
        logger.info("drive_list_files OK", count=len(files))
        return [types.TextContent(type="text", text=json.dumps(files, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error("drive_list_files FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def drive_read_file(file_id: str) -> list[types.TextContent]:
    """Lee el contenido de un archivo de Google Drive."""
    logger.info("drive_read_file", file_id=file_id)
    try:
        drive = get_drive_service()
        meta = drive.files().get(
            fileId=file_id, fields="mimeType,name,size", supportsAllDrives=True
        ).execute()
        mime = meta.get("mimeType", "")
        name = meta.get("name", file_id)
        size = int(meta.get("size", 0))

        if size > MAX_FILE_SIZE_BYTES:
            return [types.TextContent(type="text", text=json.dumps({
                "warning": f"Archivo '{name}' ({size // 1024}KB) supera límite de 5MB",
            }))]

        if mime in SUPPORTED_EXPORT_MIMES:
            content = drive.files().export(
                fileId=file_id,
                mimeType=SUPPORTED_EXPORT_MIMES[mime],
            ).execute()
        else:
            content = drive.files().get_media(
                fileId=file_id, supportsAllDrives=True
            ).execute()

        text = content.decode("utf-8") if isinstance(content, bytes) else str(content)
        logger.info("drive_read_file OK", name=name, chars=len(text))
        return [types.TextContent(type="text", text=text)]
    except Exception as e:
        logger.error("drive_read_file FAIL", file_id=file_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def drive_get_metadata(file_id: str) -> list[types.TextContent]:
    """Obtiene metadata completa de un archivo de Drive."""
    try:
        drive = get_drive_service()
        meta = drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType,size,modifiedTime,createdTime,owners,webViewLink",
            supportsAllDrives=True,
        ).execute()
        return [types.TextContent(type="text", text=json.dumps(meta, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error("drive_get_metadata FAIL", file_id=file_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def drive_search_files(
    query: str,
    folder_id: str = "",
) -> list[types.TextContent]:
    """Busca archivos en Google Drive por nombre."""
    try:
        drive = get_drive_service()
        q = f"name contains '{query}' and trashed=false"
        if folder_id:
            q += f" and '{folder_id}' in parents"
        result = drive.files().list(
            q=q,
            pageSize=20,
            fields="files(id,name,mimeType,modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return [types.TextContent(
            type="text",
            text=json.dumps(result.get("files", []), ensure_ascii=False, indent=2),
        )]
    except Exception as e:
        logger.error("drive_search_files FAIL", query=query, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
