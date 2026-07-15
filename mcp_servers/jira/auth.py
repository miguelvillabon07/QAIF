"""Autenticación con Jira Cloud vía API Token."""
from __future__ import annotations

from atlassian import Jira

from config.settings import get_settings

_jira_client: Jira | None = None


def get_jira_client() -> Jira:
    """Retorna cliente Jira singleton (lazy init)."""
    global _jira_client
    if _jira_client is None:
        s = get_settings()
        if not s.jira_configured:
            raise ValueError(
                "Credenciales Jira no configuradas. "
                "Verifica JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN en .env"
            )
        _jira_client = Jira(
            url=s.jira_url,
            username=s.jira_email,
            password=s.jira_api_token,
            cloud=True,
        )
    return _jira_client
