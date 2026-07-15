"""Schemas para casos de prueba de API."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Assertion(BaseModel):
    # kind: status_code | json_field | schema_valid | response_time_ms | header_exists
    type: str
    field_path: Optional[str] = None
    expected_value: Any = None
    threshold: Optional[float] = None
    description: str


class TestCase(BaseModel):
    id: str
    name: str
    description: str = ""
    endpoint: str
    method: HttpMethod
    headers: dict[str, str] = Field(default_factory=dict)
    payload: Any = None
    query_params: Optional[dict[str, str]] = None
    expected_status: int = Field(..., ge=100, le=599)
    expected_response_schema: Optional[dict[str, Any]] = None
    assertions: list[Assertion] = Field(default_factory=list)
    user_story_ref: Optional[str] = None
    timeout_seconds: float = 30.0
    tags: list[str] = Field(default_factory=list)
    is_happy_path: bool = True
