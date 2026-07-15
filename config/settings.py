"""Configuración centralizada con Pydantic Settings v2."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──
    llm_provider: Literal["local", "anthropic"] = "local"
    local_model_name: str = "qwen3:8b"
    ollama_base_url: str = "http://ollama:11434/v1"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # ── Google Drive ──
    google_service_account_json: Optional[Path] = None
    google_drive_folder_id: Optional[str] = None

    # ── Jira ──
    jira_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    jira_project_key: str = "PROJ"
    jira_epic_key: Optional[str] = None

    # ── Git ──
    git_workspace_path: Path = Path("/app/workspace/repos")
    git_default_branch: str = "main"

    # ── CAG + Redis ──
    cag_enabled: bool = True
    redis_url: str = "redis://redis:6379"
    redis_password: str = ""
    cag_readme_ttl_seconds: int = 3600
    cag_api_spec_ttl_seconds: int = 3600
    cag_jira_config_ttl_seconds: int = 86400

    # ── LangGraph ──
    langgraph_checkpoint_db: str = "sqlite:////app/workspace/checkpoints.db"

    # ── LangSmith ──
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "mcp_project"

    # ── Pipeline ──
    pipeline_retry_max: int = 3
    pipeline_retry_backoff_base: float = 2.0
    human_review_enabled: bool = True
    human_review_timeout_seconds: int = 300

    # ── Reports ──
    report_output_dir: Path = Path("/app/workspace/reports")
    report_company_name: str = "Mi Empresa"
    audit_log_dir: Path = Path("/app/workspace/logs")

    # ── Logging ──
    log_level: str = "INFO"
    timezone_offset_hours: int = -5  # GMT-5 (Colombia) por defecto

    @field_validator("git_workspace_path", "report_output_dir", "audit_log_dir", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_local_llm(self) -> bool:
        return self.llm_provider == "local"

    @property
    def jira_configured(self) -> bool:
        return all([self.jira_url, self.jira_email, self.jira_api_token])

    @property
    def drive_configured(self) -> bool:
        return (
            self.google_service_account_json is not None
            and self.google_drive_folder_id is not None
        )

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.startswith("sk-ant"))


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
