"""Tests unitarios de schemas Pydantic — sin dependencias externas."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.test_case import Assertion, HttpMethod, TestCase
from src.schemas.test_result import TestResult, TestStatus, TestSuiteResult
from src.schemas.user_story import ExtractionResult, Priority, UserStory


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_story(**kwargs) -> UserStory:
    defaults = {
        "title": "Procesar pago con tarjeta de crédito en POS",
        "description": "Como cajero, quiero procesar pagos para agilizar el checkout",
        "acceptance_criteria": [
            "Given una venta activa, When proceso el pago, Then confirma en menos de 3 segundos",
        ],
        "extracted_from_file_id": "file_123",
        "confidence_score": 0.90,
    }
    return UserStory(**{**defaults, **kwargs})


def make_result(status: TestStatus = TestStatus.PASS, idx: int = 0) -> TestResult:
    return TestResult(
        test_case_id=f"tc_{idx:03d}",
        test_case_name=f"Test {idx}",
        status=status,
    )


# ─── UserStory ───────────────────────────────────────────────────────────────

class TestUserStory:

    def test_valid_story_creates_successfully(self):
        story = make_story()
        assert story.title == "Procesar pago con tarjeta de crédito en POS"
        assert story.priority == Priority.MEDIUM
        assert story.confidence_score == 0.90

    def test_story_points_fibonacci_valid(self):
        for valid_sp in (1, 2, 3, 5, 8, 13):
            story = make_story(story_points=valid_sp)
            assert story.story_points == valid_sp

    def test_story_points_non_fibonacci_raises(self):
        for invalid_sp in (4, 6, 7, 9, 10, 11, 12):
            with pytest.raises(ValidationError, match="Fibonacci"):
                make_story(story_points=invalid_sp)

    def test_acceptance_criteria_too_short_raises(self):
        with pytest.raises(ValidationError, match="corto"):
            make_story(acceptance_criteria=["corto"])

    def test_acceptance_criteria_gets_stripped(self):
        story = make_story(
            acceptance_criteria=["  Given el sistema, When hago algo, Then sucede algo esperado  "]
        )
        assert not story.acceptance_criteria[0].startswith(" ")

    def test_jira_description_contains_acs_header(self):
        story = make_story()
        desc = story.jira_description
        assert "Criterios de Aceptación" in desc

    def test_jira_description_contains_description(self):
        story = make_story()
        assert "Como cajero" in story.jira_description

    def test_jira_description_contains_confidence(self):
        story = make_story(confidence_score=0.85)
        assert "85%" in story.jira_description

    def test_priority_enum_values(self):
        for prio, val in [
            (Priority.CRITICAL, "Critical"),
            (Priority.HIGH, "High"),
            (Priority.MEDIUM, "Medium"),
            (Priority.LOW, "Low"),
        ]:
            assert prio.value == val

    def test_confidence_score_bounds(self):
        make_story(confidence_score=0.0)  # OK mínimo
        make_story(confidence_score=1.0)  # OK máximo
        with pytest.raises(ValidationError):
            make_story(confidence_score=1.1)
        with pytest.raises(ValidationError):
            make_story(confidence_score=-0.1)

    def test_title_min_length_enforced(self):
        with pytest.raises(ValidationError):
            make_story(title="AB")

    def test_title_max_length_enforced(self):
        with pytest.raises(ValidationError):
            make_story(title="X" * 201)

    def test_story_has_extracted_at(self):
        story = make_story()
        assert isinstance(story.extracted_at, datetime)

    def test_story_no_epic_by_default(self):
        story = make_story()
        assert story.epic_link is None

    def test_labels_default_empty(self):
        story = make_story()
        assert story.labels == []


class TestExtractionResult:

    def test_extraction_result_valid(self):
        story = make_story()
        result = ExtractionResult(
            file_id="file_abc",
            file_name="reunion_Q2.docx",
            user_stories=[story],
        )
        assert len(result.user_stories) == 1
        assert result.total_tokens_used == 0
        assert result.extraction_warnings == []

    def test_extraction_result_with_warnings(self):
        result = ExtractionResult(
            file_id="f1",
            file_name="test.doc",
            user_stories=[],
            extraction_warnings=["Sección ambigua en minuto 15"],
            total_tokens_used=1234,
        )
        assert len(result.extraction_warnings) == 1
        assert result.total_tokens_used == 1234


# ─── TestResult ──────────────────────────────────────────────────────────────

class TestTestResult:

    def test_pass_status(self):
        r = make_result(TestStatus.PASS)
        assert r.passed is True

    def test_fail_status(self):
        r = make_result(TestStatus.FAIL)
        assert r.passed is False

    def test_error_status(self):
        r = make_result(TestStatus.ERROR)
        assert r.passed is False

    def test_optional_fields_default_none(self):
        r = make_result()
        assert r.actual_status_code is None
        assert r.response_time_ms is None
        assert r.error_message is None

    def test_executed_at_auto_set(self):
        r = make_result()
        assert isinstance(r.executed_at, datetime)


# ─── TestSuiteResult ─────────────────────────────────────────────────────────

class TestTestSuiteResult:

    def make_suite(self, pass_count: int, fail_count: int) -> TestSuiteResult:
        results = (
            [make_result(TestStatus.PASS, i) for i in range(pass_count)]
            + [make_result(TestStatus.FAIL, i + 100) for i in range(fail_count)]
        )
        return TestSuiteResult(
            suite_name="Test Suite",
            repo_name="test-repo",
            results=results,
            started_at=datetime.now(),
        )

    def test_pass_rate_all_pass(self):
        suite = self.make_suite(5, 0)
        assert suite.pass_rate == 1.0
        assert suite.passed == 5
        assert suite.failed == 0

    def test_pass_rate_all_fail(self):
        suite = self.make_suite(0, 4)
        assert suite.pass_rate == 0.0
        assert suite.passed == 0
        assert suite.failed == 4

    def test_pass_rate_mixed(self):
        suite = self.make_suite(3, 1)
        assert suite.pass_rate == 0.75
        assert suite.passed == 3
        assert suite.failed == 1
        assert suite.total == 4

    def test_empty_suite_pass_rate_zero(self):
        suite = self.make_suite(0, 0)
        assert suite.pass_rate == 0.0
        assert suite.total == 0

    def test_duration_seconds_positive(self):
        suite = self.make_suite(1, 0)
        assert suite.duration_seconds >= 0.0

    def test_automation_suggestions_default_empty(self):
        suite = self.make_suite(1, 0)
        assert suite.automation_suggestions == []


# ─── TestCase ────────────────────────────────────────────────────────────────

class TestTestCase:

    def test_valid_test_case(self):
        tc = TestCase(
            id="tc_001",
            name="GET /api/products",
            endpoint="/api/products",
            method=HttpMethod.GET,
            expected_status=200,
            tags=["happy_path"],
        )
        assert tc.method == HttpMethod.GET
        assert tc.expected_status == 200

    def test_assertion_status_code(self):
        a = Assertion(
            type="status_code",
            expected_value=201,
            description="Debe retornar 201 Created",
        )
        assert a.type == "status_code"
        assert a.expected_value == 201

    def test_assertion_response_time(self):
        a = Assertion(
            type="response_time_ms",
            threshold=3000.0,
            description="Debe responder en menos de 3 segundos",
        )
        assert a.threshold == 3000.0

    def test_http_method_enum_values(self):
        assert HttpMethod.GET.value == "GET"
        assert HttpMethod.POST.value == "POST"
        assert HttpMethod.PUT.value == "PUT"
        assert HttpMethod.DELETE.value == "DELETE"
        assert HttpMethod.PATCH.value == "PATCH"
