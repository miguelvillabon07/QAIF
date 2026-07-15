"""Fábrica de LLM: switch entre Qwen3 local (Ollama) y Claude Sonnet 4.6 (API)."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from config.settings import get_settings
from src.utils.logging_config import get_logger

logger = get_logger("llm.factory")


def get_llm(provider: str | None = None) -> BaseChatModel:
    """
    Retorna el LLM configurado según LLM_PROVIDER en .env.

    local     → Qwen3:8b via Ollama (Docker, costo $0)
    anthropic → Claude Sonnet 4.6 via API (producción)
    """
    settings = get_settings()
    provider = provider or settings.llm_provider

    if provider == "local":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError("pip install langchain-openai para usar LLM local") from e

        logger.info(
            "LLM local inicializado",
            model=settings.local_model_name,
            base_url=settings.ollama_base_url,
        )
        return ChatOpenAI(
            model=settings.local_model_name,
            base_url=settings.ollama_base_url,
            api_key="ollama",
            temperature=0.1,
            max_tokens=4096,
            timeout=None,
            max_retries=0,
        )

    elif provider == "anthropic":
        if not settings.anthropic_configured:
            raise ValueError(
                "ANTHROPIC_API_KEY no configurada o inválida. "
                "Verifica .env o usa LLM_PROVIDER=local"
            )
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as e:
            raise ImportError("pip install langchain-anthropic para usar Claude API") from e

        logger.info(
            "LLM Anthropic API inicializado",
            model=settings.anthropic_model,
        )
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=0.1,
            max_tokens=8192,
        )

    raise ValueError(
        f"LLM_PROVIDER desconocido: '{provider}'. "
        "Valores válidos: 'local' | 'anthropic'"
    )


def switch_llm(provider: str) -> BaseChatModel:
    """Cambia el provider en runtime (usado desde la consola interactiva)."""
    import os

    os.environ["LLM_PROVIDER"] = provider
    # Reset settings singleton
    import config.settings as cfg

    cfg._settings = None
    logger.info("LLM provider cambiado", new_provider=provider)
    return get_llm(provider)
