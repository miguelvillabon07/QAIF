"""Herramientas del MCP Server de Reporting."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp import types

from config.settings import get_settings
from src.schemas.test_result import TestSuiteResult
from src.utils.logging_config import get_logger

logger = get_logger("mcp.reporting")

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_jinja_env():
    from jinja2 import Environment, FileSystemLoader
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )


async def reporting_generate_md(
    suite_result_json: str,
    output_path: Optional[str] = None,
    pipeline_id: str = "",
) -> list[types.TextContent]:
    """
    Renderiza el template Jinja2 con el TestSuiteResult y guarda el reporte .md.
    Retorna la ruta del archivo generado y un preview de las primeras líneas.
    """
    logger.info("reporting_generate_md", pipeline_id=pipeline_id)
    try:
        suite = TestSuiteResult.model_validate_json(suite_result_json)
        settings = get_settings()

        # Calcular avg response time
        times = [r.response_time_ms for r in suite.results if r.response_time_ms is not None]
        avg_response_time = sum(times) / len(times) if times else None

        # Renderizar template
        env = _get_jinja_env()
        template = env.get_template("report_full.md.j2")
        content = template.render(
            suite=suite,
            now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            company_name=settings.report_company_name,
            avg_response_time=avg_response_time,
        )

        # Determinar ruta de salida
        if output_path:
            out_file = Path(output_path)
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"report_{suite.repo_name}_{timestamp}.md"
            out_file = settings.report_output_dir / filename

        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(content, encoding="utf-8")
        logger.info("Reporte MD generado", path=str(out_file), chars=len(content))

        # Log en audit trail
        try:
            from mcp_servers.workspace.audit import log_event
            log_event(
                event_type="report_generated",
                message=f"Reporte MD: {out_file.name}",
                status="success",
                pipeline_id=pipeline_id,
                metadata={
                    "path": str(out_file),
                    "repo": suite.repo_name,
                    "total": suite.total,
                    "passed": suite.passed,
                    "pass_rate": f"{suite.pass_rate:.0%}",
                },
            )
        except Exception:
            pass

        return [types.TextContent(type="text", text=json.dumps({
            "status": "generated",
            "path": str(out_file),
            "filename": out_file.name,
            "chars": len(content),
            "suite_summary": {
                "total": suite.total,
                "passed": suite.passed,
                "failed": suite.failed,
                "pass_rate": f"{suite.pass_rate:.1%}",
            },
        }))]
    except Exception as e:
        logger.error("reporting_generate_md FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def reporting_generate_pdf(
    md_path: str,
    output_path: Optional[str] = None,
) -> list[types.TextContent]:
    """
    Convierte un reporte Markdown a PDF usando reportlab.
    Estrategia: MD → texto simple → PDF con reportlab Platypus.
    """
    logger.info("reporting_generate_pdf", md_path=md_path)
    try:
        md_file = Path(md_path)
        if not md_file.exists():
            return [types.TextContent(type="text", text=json.dumps({
                "error": f"Archivo MD no encontrado: {md_path}",
            }))]

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.platypus import HRFlowable

        if output_path:
            pdf_path = Path(output_path)
        else:
            pdf_path = md_file.with_suffix(".pdf")

        # Leer contenido MD
        md_content = md_file.read_text(encoding="utf-8")

        # Construir PDF
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        story = []

        # Procesar líneas del MD
        for line in md_content.split("\n"):
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 6))
                continue

            if stripped.startswith("# "):
                story.append(Paragraph(stripped[2:], styles["Title"]))
                story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
                story.append(Spacer(1, 12))
            elif stripped.startswith("## "):
                story.append(Spacer(1, 8))
                story.append(Paragraph(stripped[3:], styles["Heading2"]))
            elif stripped.startswith("### "):
                story.append(Paragraph(stripped[4:], styles["Heading3"]))
            elif stripped.startswith("| "):
                # Saltar líneas de tabla (las procesamos por bloque)
                pass
            elif stripped.startswith("> "):
                quote_style = ParagraphStyle(
                    "Quote", parent=styles["Normal"],
                    leftIndent=20, textColor=colors.darkgrey,
                    fontSize=10,
                )
                story.append(Paragraph(stripped[2:], quote_style))
            elif stripped.startswith("- ") or stripped.startswith("* "):
                story.append(Paragraph(f"• {stripped[2:]}", styles["Normal"]))
            elif stripped.startswith("_") and stripped.endswith("_"):
                italic_style = ParagraphStyle(
                    "Italic", parent=styles["Normal"],
                    textColor=colors.grey, fontSize=9,
                )
                story.append(Paragraph(stripped.strip("_"), italic_style))
            elif stripped == "---":
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
                story.append(Spacer(1, 6))
            else:
                story.append(Paragraph(stripped, styles["Normal"]))

        doc.build(story)
        logger.info("PDF generado", path=str(pdf_path))

        return [types.TextContent(type="text", text=json.dumps({
            "status": "generated",
            "pdf_path": str(pdf_path),
            "filename": pdf_path.name,
            "size_bytes": pdf_path.stat().st_size,
        }))]
    except Exception as e:
        logger.error("reporting_generate_pdf FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def reporting_get_log(
    pipeline_id: Optional[str] = None,
    last_n: int = 50,
) -> list[types.TextContent]:
    """Lee el audit log y retorna las últimas N entradas."""
    try:
        from mcp_servers.workspace.audit import get_log
        entries = get_log(
            last_n=last_n,
            pipeline_id_filter=pipeline_id or "",
        )
        return [types.TextContent(type="text", text=json.dumps({
            "entries": entries,
            "count": len(entries),
            "pipeline_id": pipeline_id,
        }, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error("reporting_get_log FAIL", error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
