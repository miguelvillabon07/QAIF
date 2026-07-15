"""Estado del pipeline LangGraph — todos los campos compartidos entre nodos."""
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.schemas.test_case import TestCase
from src.schemas.test_result import TestSuiteResult
from src.schemas.user_story import ExtractionResult, UserStory


class AgentState(TypedDict):
    # ── Identificación del pipeline ──
    pipeline_id: str
    started_at: str
    completed_at: Optional[str]

    # ── Input ──
    transcription_file_id: str
    transcription_file_name: str
    transcription_content: str

    # ── Repo Git / API ──
    repo_url: str
    repo_name: str
    repo_local_path: str
    readme_analysis_json: str        # JSON del ReadmeAnalysis
    api_base_url: str

    # ── Fase 1: Extracción User Stories ──
    extraction_result: Optional[ExtractionResult]
    user_stories: list[UserStory]
    extraction_warnings: list[str]

    # ── Human Review ──
    human_approved: bool
    human_feedback: Optional[str]

    # ── Fase 2: Jira ──
    jira_issue_ids: list[str]
    jira_creation_errors: list[str]

    # ── Fase 3: Testing ──
    test_cases: list[TestCase]
    test_suite_result: Optional[TestSuiteResult]
    test_retry_count: int

    # ── Fase 4: Reporte ──
    report_md_path: str
    report_pdf_path: str
    report_uploaded_to: list[str]    # Lista de issue_ids donde se subió

    # ── Control ──
    pipeline_status: str             # idle|running|paused|completed|failed
    current_step: str
    errors: list[str]
    total_tokens_used: int

    # ── Mensajes LangGraph ──
    messages: Annotated[list[BaseMessage], add_messages]
