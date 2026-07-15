"""HTTP test runner con assertion engine completo."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from src.schemas.test_case import Assertion, TestCase
from src.schemas.test_result import AssertionResult, TestResult, TestStatus
from src.utils.logging_config import get_logger

logger = get_logger("pos_api.runner")


def _resolve_field(obj: Any, path: str) -> Any:
    """Resuelve un field path tipo 'data.user.id' en un dict/list anidado."""
    if not path:
        return obj
    parts = path.split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
    return current


def _evaluate_assertion(
    assertion: Assertion,
    actual_status: int,
    response_body: Any,
    response_time_ms: float,
    response_headers: dict,
) -> AssertionResult:
    """Evalúa una assertion y retorna el resultado."""
    try:
        if assertion.type == "status_code":
            passed = actual_status == assertion.expected_value
            return AssertionResult(
                description=assertion.description,
                passed=passed,
                expected=assertion.expected_value,
                actual=actual_status,
            )

        elif assertion.type == "json_field":
            actual = _resolve_field(response_body, assertion.field_path or "")
            passed = actual == assertion.expected_value
            return AssertionResult(
                description=assertion.description,
                passed=passed,
                expected=assertion.expected_value,
                actual=actual,
            )

        elif assertion.type == "exists":
            actual = _resolve_field(response_body, assertion.field_path or "")
            passed = actual is not None
            return AssertionResult(
                description=assertion.description,
                passed=passed,
                expected="field exists",
                actual=str(actual),
            )

        elif assertion.type == "response_time_ms":
            threshold = assertion.threshold or 5000.0
            passed = response_time_ms <= threshold
            return AssertionResult(
                description=assertion.description,
                passed=passed,
                expected=f"<= {threshold}ms",
                actual=f"{response_time_ms:.1f}ms",
            )

        elif assertion.type == "header_exists":
            header_key = (assertion.field_path or "").lower()
            passed = header_key in {k.lower() for k in response_headers}
            return AssertionResult(
                description=assertion.description,
                passed=passed,
                expected=f"Header '{header_key}' presente",
                actual="presente" if passed else "ausente",
            )

        elif assertion.type == "schema_valid":
            # Validación básica de que la respuesta sea un objeto/lista no vacío
            passed = response_body is not None and response_body != {}
            return AssertionResult(
                description=assertion.description,
                passed=passed,
                expected="response non-empty",
                actual=type(response_body).__name__,
            )

        else:
            return AssertionResult(
                description=assertion.description,
                passed=False,
                error_message=f"Tipo de assertion desconocido: '{assertion.type}'",
            )

    except Exception as e:
        return AssertionResult(
            description=assertion.description,
            passed=False,
            error_message=f"Error evaluando assertion: {e}",
        )


async def run_test_case(test: TestCase, base_url: str) -> TestResult:
    """Ejecuta un TestCase HTTP completo y retorna TestResult."""
    url = f"{base_url.rstrip('/')}{test.endpoint}"
    logger.info("run_test_case inicio", name=test.name, method=test.method.value, url=url)

    start_ms = time.perf_counter() * 1000
    try:
        async with httpx.AsyncClient(timeout=test.timeout_seconds) as client:
            request_kwargs: dict = {
                "method": test.method.value,
                "url": url,
                "headers": test.headers,
                "params": test.query_params,
            }
            if test.payload and test.method.value in ("POST", "PUT", "PATCH"):
                request_kwargs["json"] = test.payload

            response = await client.request(**request_kwargs)
            response_time_ms = time.perf_counter() * 1000 - start_ms

            # Parsear body
            try:
                body = response.json()
            except Exception:
                body = {"raw_text": response.text[:2000]}

            # Evaluar todas las assertions
            assertion_results = [
                _evaluate_assertion(a, response.status_code, body, response_time_ms, dict(response.headers))
                for a in test.assertions
            ]

            # Assertion implícita: status code esperado
            status_ok = response.status_code == test.expected_status
            all_assertions_pass = all(ar.passed for ar in assertion_results)
            final_status = TestStatus.PASS if (status_ok and all_assertions_pass) else TestStatus.FAIL

            logger.info(
                "run_test_case OK",
                name=test.name,
                status=final_status.value,
                http_status=response.status_code,
                time_ms=round(response_time_ms, 1),
            )

            return TestResult(
                test_case_id=test.id,
                test_case_name=test.name,
                status=final_status,
                actual_status_code=response.status_code,
                response_time_ms=round(response_time_ms, 1),
                response_body=body,
                assertion_results=assertion_results,
                user_story_ref=test.user_story_ref,
                error_message=None if status_ok else f"Status {response.status_code} != {test.expected_status}",
            )

    except httpx.TimeoutException:
        elapsed = time.perf_counter() * 1000 - start_ms
        logger.error("run_test_case TIMEOUT", name=test.name, timeout=test.timeout_seconds)
        return TestResult(
            test_case_id=test.id,
            test_case_name=test.name,
            status=TestStatus.ERROR,
            response_time_ms=round(elapsed, 1),
            error_message=f"Timeout después de {test.timeout_seconds}s",
        )
    except Exception as e:
        logger.error("run_test_case ERROR", name=test.name, error=str(e))
        return TestResult(
            test_case_id=test.id,
            test_case_name=test.name,
            status=TestStatus.ERROR,
            error_message=str(e),
        )
