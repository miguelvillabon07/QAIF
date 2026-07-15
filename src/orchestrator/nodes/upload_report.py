"""
Nodo 4: Genera reporte MD + PDF y lo sube como attachment a cada issue Jira.
"""
from __future__ import annotations

import base64
from pathlib import Path

from src.orchestrator.state import AgentState
from src.utils.logging_config import get_logger
from mcp_servers.workspace.audit import log_event

logger = get_logger("node.upload_report")


async def upload_report_node(state: AgentState) -> dict:
    """Nodo LangGraph: genera MD, convierte a PDF y sube a Jira."""
    pipeline_id = state.get("pipeline_id", "unknown")
    suite = state.get("test_suite_result")
    issue_ids = state.get("jira_issue_ids", [])

    log_event(
        "upload_report", "Generando y subiendo reporte",
        "running", pipeline_id=pipeline_id,
        metadata={"issues_targets": len(issue_ids)},
    )

    if not suite:
        return {
            "errors": state.get("errors", []) + ["No hay TestSuiteResult para generar reporte"],
            "pipeline_status": "failed",
        }

    # ── Generar reporte Markdown ──
    md_path = ""
    pdf_path = ""
    try:
        from mcp_servers.reporting.tools import reporting_generate_md, reporting_generate_pdf
        import json

        md_result = await reporting_generate_md(
            suite_result_json=suite.model_dump_json(),
            pipeline_id=pipeline_id,
        )
        md_data = json.loads(md_result[0].text)
        if "error" in md_data:
            raise RuntimeError(md_data["error"])
        md_path = md_data["path"]
        logger.info("Reporte MD generado", path=md_path)
        log_event("upload_report", f"Reporte MD: {md_data['filename']}", "success",
                  pipeline_id=pipeline_id, metadata={"path": md_path})
    except Exception as e:
        logger.error("Error generando reporte MD", error=str(e))
        log_event("upload_report", f"Error MD: {e}", "failed", pipeline_id=pipeline_id)
        return {
            "errors": state.get("errors", []) + [f"Error generando reporte: {e}"],
            "pipeline_status": "failed",
        }

    # ── Convertir a PDF ──
    try:
        from mcp_servers.reporting.tools import reporting_generate_pdf
        import json

        pdf_result = await reporting_generate_pdf(md_path=md_path)
        pdf_data = json.loads(pdf_result[0].text)
        if "error" not in pdf_data:
            pdf_path = pdf_data.get("pdf_path", "")
            logger.info("PDF generado", path=pdf_path)
            log_event("upload_report", f"PDF: {pdf_data.get('filename', '')}", "success",
                      pipeline_id=pipeline_id, metadata={"path": pdf_path})
    except Exception as e:
        logger.warning("No se pudo generar PDF, continuando con solo MD", error=str(e))

    # ── Subir a Jira como attachment ──
    uploaded_to: list[str] = []
    if issue_ids:
        upload_source = pdf_path if pdf_path else md_path
        if not upload_source:
            logger.warning("No hay archivo para subir a Jira")
        else:
            source_path = Path(upload_source)
            filename = source_path.name
            try:
                content_bytes = source_path.read_bytes()
                content_b64 = base64.b64encode(content_bytes).decode("utf-8")

                from mcp_servers.jira.tools import jira_upload_attachment, jira_add_comment
                import json as json_mod

                for issue_id in issue_ids:
                    try:
                        # Subir attachment
                        att_result = await jira_upload_attachment(
                            issue_id=issue_id,
                            filename=filename,
                            content_base64=content_b64,
                        )
                        att_data = json_mod.loads(att_result[0].text)
                        if "error" not in att_data:
                            uploaded_to.append(issue_id)
                            # Agregar comentario con resumen
                            summary = (
                                f"✅ Reporte de pruebas adjunto: *{filename}*\n"
                                f"- Total: {suite.total} | Pasaron: {suite.passed} | "
                                f"Fallaron: {suite.failed}\n"
                                f"- Tasa de éxito: {suite.pass_rate:.0%}\n"
                                f"- Duración: {suite.duration_seconds:.1f}s"
                            )
                            await jira_add_comment(issue_id=issue_id, comment_body=summary)
                            log_event(
                                "upload_report", f"Reporte subido a {issue_id}",
                                "success", pipeline_id=pipeline_id,
                                metadata={"issue": issue_id, "file": filename},
                            )
                            logger.info("Attachment subido", issue=issue_id, file=filename)
                        else:
                            logger.warning("Error subiendo a Jira", issue=issue_id,
                                           error=att_data.get("error"))
                    except Exception as e:
                        logger.error("Error en upload attachment", issue=issue_id, error=str(e))
            except Exception as e:
                logger.error("Error leyendo archivo para subir", path=upload_source, error=str(e))

    # ── Finalizar pipeline ──
    from datetime import datetime, timezone
    log_event(
        "pipeline_complete",
        f"Pipeline completado — {suite.passed}/{suite.total} tests OK — "
        f"{len(uploaded_to)} issues actualizados",
        "success", pipeline_id=pipeline_id,
        metadata={
            "pass_rate": suite.pass_rate,
            "issues_updated": len(uploaded_to),
            "report_md": md_path,
            "report_pdf": pdf_path,
        },
    )

    return {
        "report_md_path": md_path,
        "report_pdf_path": pdf_path,
        "report_uploaded_to": uploaded_to,
        "pipeline_status": "completed",
        "current_step": "done",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
