"""Tests del CAG Manager — con mock de Redis para ejecutar sin infra."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Helper para crear un CAGManager con settings mockeados ─────────────────

def _make_cag_with_mock_redis(mock_redis: AsyncMock):
    """Crea un CAGManager cuyo _get_redis retorna el mock dado."""
    from src.cache.cag_manager import CAGManager

    cag = CAGManager.__new__(CAGManager)
    cag._redis = None

    # Mock settings: cag_enabled=True, ttls, redis_url
    mock_settings = MagicMock()
    mock_settings.cag_enabled = True
    mock_settings.redis_url = "redis://localhost:6379"
    mock_settings.redis_password = None
    mock_settings.cag_readme_ttl_seconds = 3600
    mock_settings.cag_api_spec_ttl_seconds = 7200
    mock_settings.cag_jira_config_ttl_seconds = 1800
    cag.settings = mock_settings

    # Parchear _get_redis para retornar nuestro mock
    async def fake_get_redis():
        return mock_redis

    cag._get_redis = fake_get_redis
    return cag


# ─── preload_readme ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preload_readme_cache_miss_reads_disk(tmp_path: Path):
    """Cache miss → lee README.md del disco y lo cachea en Redis."""
    readme = tmp_path / "README.md"
    readme.write_text("# POS API\n\nPOST /api/sales\n")

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None       # cache miss
    mock_redis.setex = AsyncMock()

    cag = _make_cag_with_mock_redis(mock_redis)
    content = await cag.preload_readme(tmp_path, "test-repo")

    assert "POS API" in content
    mock_redis.get.assert_called_once_with("cag:readme:test-repo")
    mock_redis.setex.assert_called_once()
    # Verificar que se usó el TTL correcto
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "cag:readme:test-repo"  # key
    assert call_args[0][1] == 3600                     # TTL


@pytest.mark.asyncio
async def test_preload_readme_cache_hit_returns_cached(tmp_path: Path):
    """Cache hit → retorna cached sin leer el disco."""
    # Aunque exista README en disco, no debe leerlo
    (tmp_path / "README.md").write_text("README disco — NO debe usarse")

    mock_redis = AsyncMock()
    mock_redis.get.return_value = "# README cacheado en Redis"

    cag = _make_cag_with_mock_redis(mock_redis)
    content = await cag.preload_readme(tmp_path, "cached-repo")

    assert content == "# README cacheado en Redis"
    # No debe llamar setex (ya estaba en caché)
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_preload_readme_no_readme_returns_empty(tmp_path: Path):
    """Si no hay README, retorna string vacío."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # cache miss
    mock_redis.setex = AsyncMock()

    cag = _make_cag_with_mock_redis(mock_redis)
    content = await cag.preload_readme(tmp_path, "empty-repo")

    assert content == ""
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_preload_readme_reads_readme_md_case_variants(tmp_path: Path):
    """Debe encontrar readme.md (minúsculas) si README.md no existe."""
    readme = tmp_path / "readme.md"
    readme.write_text("# Minusculas README\n\nContent aqui\n", encoding="utf-8")

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.setex = AsyncMock()

    cag = _make_cag_with_mock_redis(mock_redis)
    content = await cag.preload_readme(tmp_path, "lowercase-repo")

    assert "Minusculas README" in content


# ─── invalidate ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalidate_deletes_matching_keys():
    """invalidate() elimina todas las keys que coincidan con el patrón."""
    mock_redis = AsyncMock()
    mock_redis.keys.return_value = ["cag:readme:repo1", "cag:api_spec:repo1"]
    mock_redis.delete.return_value = 2

    cag = _make_cag_with_mock_redis(mock_redis)
    count = await cag.invalidate("cag:*")

    assert count == 2
    mock_redis.keys.assert_called_once_with("cag:*")
    mock_redis.delete.assert_called_once_with("cag:readme:repo1", "cag:api_spec:repo1")


@pytest.mark.asyncio
async def test_invalidate_no_keys_returns_zero():
    """Si no hay keys que coincidan, retorna 0."""
    mock_redis = AsyncMock()
    mock_redis.keys.return_value = []

    cag = _make_cag_with_mock_redis(mock_redis)
    count = await cag.invalidate("cag:nonexistent:*")

    assert count == 0
    mock_redis.delete.assert_not_called()


# ─── get_context ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_context_returns_available_keys():
    """get_context devuelve dict con las keys que existen en Redis."""
    mock_redis = AsyncMock()

    async def fake_get(key: str):
        data = {
            "cag:readme:repo1": "# README content",
            "cag:jira_config": '{"project": "PROJ"}',
        }
        return data.get(key)

    mock_redis.get.side_effect = fake_get

    cag = _make_cag_with_mock_redis(mock_redis)
    ctx = await cag.get_context("cag:readme:repo1", "cag:jira_config", "cag:missing:key")

    assert "cag:readme:repo1" in ctx
    assert "cag:jira_config" in ctx
    assert "cag:missing:key" not in ctx
    assert ctx["cag:readme:repo1"] == "# README content"


# ─── preload_jira_config ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preload_jira_config_stores_json():
    """preload_jira_config serializa el dict a JSON y lo guarda con TTL."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    cag = _make_cag_with_mock_redis(mock_redis)
    config = {"project_key": "PROJ", "components": ["backend", "api"]}
    await cag.preload_jira_config(config)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args[0]
    assert call_args[0] == "cag:jira_config"
    assert "PROJ" in call_args[2]  # JSON string contiene el valor


# ─── health_check ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_ok_when_redis_pings():
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    cag = _make_cag_with_mock_redis(mock_redis)
    ok, msg = await cag.health_check()

    assert ok is True
    assert "disponible" in msg.lower()


@pytest.mark.asyncio
async def test_health_check_fails_when_redis_down():
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = ConnectionError("Connection refused")

    cag = _make_cag_with_mock_redis(mock_redis)
    ok, msg = await cag.health_check()

    assert ok is False
    assert "no disponible" in msg.lower()
