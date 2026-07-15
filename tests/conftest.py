"""Fixtures compartidas para todos los tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Asegurar que el root del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_transcription() -> str:
    return """
    María comentó que los cajeros necesitan poder aplicar descuentos hasta el 30%.
    El sistema debe registrar quién aplicó el descuento y cuándo lo hizo.
    Juan agregó que también se necesita un reporte diario de descuentos aplicados.
    Todos están de acuerdo en que la prioridad es alta para esta funcionalidad.
    También se discutió que el sistema debe validar que el descuento no supere el límite.
    """


@pytest.fixture
def sample_readme() -> str:
    return """
    # POS API Validation Suite
    ## Setup
    pip install -r requirements.txt
    ## Run
    uvicorn main:app --port 8000
    ## Endpoints
    POST /api/v1/sales     - Crear venta
    GET  /api/v1/products  - Listar productos
    POST /api/v1/payments  - Procesar pago
    GET  /api/v1/health    - Health check
    """


@pytest.fixture
def sample_user_story():
    from src.schemas.user_story import UserStory
    return UserStory(
        title="Procesar pago con tarjeta de crédito",
        description="Como cajero, quiero procesar pagos para agilizar el checkout",
        acceptance_criteria=[
            "Given una venta activa, When proceso el pago, Then confirma en menos de 3 segundos",
            "Given un pago rechazado, When reintento, Then el sistema muestra el motivo del rechazo",
        ],
        extracted_from_file_id="file_test_123",
        confidence_score=0.90,
    )
