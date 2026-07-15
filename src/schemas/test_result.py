"""Schemas para resultados de ejecución de pruebas."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"


class AssertionResult(BaseModel):
    description: str
    passed: bool
    expected: Any = None
    actual: Any = None
    error_message: Optional[str] = None


class TestResult(BaseModel):
    test_case_id: str
    test_case_name: str
    status: TestStatus
    actual_status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    response_body: Optional[Any] = None
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    error_message: Optional[str] = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_story_ref: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == TestStatus.PASS


class TestSuiteResult(BaseModel):
    suite_name: str
    repo_name: str
    results: list[TestResult]
    started_at: datetime
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automation_suggestions: list[str] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()
