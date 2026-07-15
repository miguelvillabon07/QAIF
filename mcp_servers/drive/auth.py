"""Autenticación con Google Service Account."""
from __future__ import annotations

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config.settings import get_settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    """Retorna cliente autenticado de Google Drive vía Service Account."""
    settings = get_settings()
    if not settings.google_service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON no configurado en .env")
    creds = service_account.Credentials.from_service_account_file(
        str(settings.google_service_account_json), scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)
