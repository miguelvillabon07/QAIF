"""Herramientas del MCP Server de Jira con retry para rate limiting."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Optional

from mcp import types

from src.utils.logging_config import get_logger
from src.utils.retry import async_retry

from .auth import get_jira_client

logger = get_logger("mcp.jira")


@async_retry(max_attempts=3, base_delay=1.0, exceptions=(Exception,))
async def jira_create_issue(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Story",
    priority: str = "Medium",
    labels: Optional[list] = None,
    epic_key: Optional[str] = None,
) -> list[types.TextContent]:
    """Crea un issue en Jira (Story, Bug, Task, etc.)."""
    logger.info("jira_create_issue", project=project_key, summary=summary[:50])
    try:
        jira = get_jira_client()
        fields: dict = {
            "project": {"key": project_key},
            "summary": summary[:255],
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
        if labels:
            fields["labels"] = labels

        issue = jira.create_issue(fields=fields)
        issue_key = issue["key"]

        # Intentar vincular al epic (no disponible en todos los planes)
        if epic_key:
            try:
                jira.create_issue_link(
                    type="Epic Link",
                    inwardIssue=issue_key,
                    outwardIssue=epic_key,
                )
            except Exception:
                logger.warning("Epic link no disponible", issue=issue_key, epic=epic_key)

        logger.info("jira_create_issue OK", issue_key=issue_key)
        return [types.TextContent(type="text", text=json.dumps({
            "issue_key": issue_key,
            "url": f"{jira.url}/browse/{issue_key}",
        }))]
    except Exception as e:
        logger.error("jira_create_issue FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_get_issue(issue_id: str) -> list[types.TextContent]:
    """Obtiene un issue completo de Jira."""
    try:
        jira = get_jira_client()
        issue = jira.issue(issue_id)
        return [types.TextContent(
            type="text",
            text=json.dumps(issue, ensure_ascii=False, indent=2),
        )]
    except Exception as e:
        logger.error("jira_get_issue FAIL", issue_id=issue_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_update_issue(
    issue_id: str,
    fields: dict,
) -> list[types.TextContent]:
    """Actualiza campos de un issue existente."""
    try:
        jira = get_jira_client()
        jira.update_issue_field(key=issue_id, fields=fields)
        logger.info("jira_update_issue OK", issue_id=issue_id, fields=list(fields.keys()))
        return [types.TextContent(type="text", text=json.dumps({
            "status": "updated",
            "issue": issue_id,
            "fields_updated": list(fields.keys()),
        }))]
    except Exception as e:
        logger.error("jira_update_issue FAIL", issue_id=issue_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_add_comment(
    issue_id: str,
    comment_body: str,
) -> list[types.TextContent]:
    """Agrega un comentario a un issue."""
    try:
        jira = get_jira_client()
        comment = jira.add_comment(issue_id, comment_body)
        logger.info("jira_add_comment OK", issue_id=issue_id)
        return [types.TextContent(type="text", text=json.dumps({
            "comment_id": comment["id"],
            "issue": issue_id,
        }))]
    except Exception as e:
        logger.error("jira_add_comment FAIL", issue_id=issue_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_upload_attachment(
    issue_id: str,
    filename: str,
    content_base64: str,
) -> list[types.TextContent]:
    """Sube un archivo como attachment. content_base64 = contenido codificado en base64."""
    import tempfile
    import os
    try:
        jira = get_jira_client()
        content_bytes = base64.b64decode(content_base64)
        
        # atlassian-python-api requiere un archivo físico en el disco
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name
            
        try:
            jira.add_attachment(issue_key=issue_id, filename=tmp_path)
            logger.info("jira_upload_attachment OK", issue=issue_id, file=filename, size=len(content_bytes))
            return [types.TextContent(type="text", text=json.dumps({
                "status": "uploaded",
                "filename": filename,
                "issue": issue_id,
                "size_bytes": len(content_bytes),
            }))]
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        logger.error("jira_upload_attachment FAIL", issue_id=issue_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_transition_issue(
    issue_id: str,
    transition_name: str,
) -> list[types.TextContent]:
    """Transiciona un issue a un nuevo estado (e.g., 'In Progress', 'Done')."""
    try:
        jira = get_jira_client()
        transitions = jira.get_issue_transitions(issue_id)
        target = next(
            (t for t in transitions if t["name"].lower() == transition_name.lower()),
            None,
        )
        if not target:
            available = [t["name"] for t in transitions]
            return [types.TextContent(type="text", text=json.dumps({
                "error": f"Transición '{transition_name}' no encontrada.",
                "available_transitions": available,
            }))]
        jira.transition_issue(issue_id, target["id"])
        logger.info("jira_transition_issue OK", issue=issue_id, to=transition_name)
        return [types.TextContent(type="text", text=json.dumps({
            "status": "transitioned",
            "issue": issue_id,
            "to": transition_name,
        }))]
    except Exception as e:
        logger.error("jira_transition_issue FAIL", issue_id=issue_id, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_link_issues(
    source_id: str,
    target_id: str,
    link_type: str = "Relates",
) -> list[types.TextContent]:
    """Crea un enlace entre dos issues."""
    try:
        jira = get_jira_client()
        jira.create_issue_link(
            type=link_type,
            inwardIssue=source_id,
            outwardIssue=target_id,
        )
        logger.info("jira_link_issues OK", source=source_id, target=target_id)
        return [types.TextContent(type="text", text=json.dumps({
            "status": "linked",
            "source": source_id,
            "target": target_id,
            "link_type": link_type,
        }))]
    except Exception as e:
        logger.error("jira_link_issues FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def jira_search_issues(
    jql: str,
    max_results: int = 50,
) -> list[types.TextContent]:
    """Busca issues usando JQL (Jira Query Language)."""
    try:
        jira = get_jira_client()
        results = jira.jql(jql, limit=max_results)
        issues = [
            {
                "key": i["key"],
                "summary": i["fields"]["summary"],
                "status": i["fields"]["status"]["name"],
                "priority": i["fields"].get("priority", {}).get("name", "N/A"),
                "assignee": (i["fields"].get("assignee") or {}).get("displayName", "Unassigned"),
            }
            for i in results.get("issues", [])
        ]
        logger.info("jira_search_issues OK", jql=jql[:60], count=len(issues))
        return [types.TextContent(
            type="text",
            text=json.dumps({"total": len(issues), "issues": issues}, ensure_ascii=False, indent=2),
        )]
    except Exception as e:
        logger.error("jira_search_issues FAIL", jql=jql[:60], error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
