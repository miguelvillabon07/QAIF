"""Herramientas del MCP Server de Git."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import git
from mcp import types

from config.settings import get_settings
from src.utils.logging_config import get_logger

from .readme_parser import ReadmeAnalysis, parse_readme

logger = get_logger("mcp.git")

API_SPEC_CANDIDATES = [
    "openapi.yaml", "openapi.yml", "openapi.json",
    "swagger.yaml", "swagger.yml", "swagger.json",
    "docs/openapi.yaml", "docs/swagger.yaml", "api/openapi.yaml",
]


def _get_repo_path(repo_name: str) -> Path:
    settings = get_settings()
    return settings.git_workspace_path / repo_name


async def git_clone(
    repo_url: str,
    repo_name: Optional[str] = None,
    branch: Optional[str] = None,
) -> list[types.TextContent]:
    """Clona un repositorio Git en el workspace local. Si ya existe, hace pull."""
    settings = get_settings()
    name = repo_name or repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    dest = settings.git_workspace_path / name

    logger.info("git_clone", url=repo_url, dest=str(dest))
    try:
        if dest.exists():
            # Ya existe → hacer pull
            repo = git.Repo(dest)
            origin = repo.remotes.origin
            origin.pull()
            logger.info("git_pull (repo existente)", repo=name)
            return [types.TextContent(type="text", text=json.dumps({
                "status": "pulled",
                "repo_name": name,
                "path": str(dest),
                "commit": repo.head.commit.hexsha[:8],
            }))]

        # Clonar fresco
        clone_kwargs: dict = {"to_path": str(dest)}
        if branch:
            clone_kwargs["branch"] = branch
        repo = git.Repo.clone_from(repo_url, **clone_kwargs)
        logger.info("git_clone OK", repo=name, commit=repo.head.commit.hexsha[:8])
        return [types.TextContent(type="text", text=json.dumps({
            "status": "cloned",
            "repo_name": name,
            "path": str(dest),
            "commit": repo.head.commit.hexsha[:8],
            "branch": repo.active_branch.name,
        }))]
    except Exception as e:
        logger.error("git_clone FAIL", url=repo_url, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def git_pull(repo_name: str) -> list[types.TextContent]:
    """Hace git pull en un repo ya clonado."""
    dest = _get_repo_path(repo_name)
    try:
        repo = git.Repo(dest)
        origin = repo.remotes.origin
        result = origin.pull()
        commit = repo.head.commit.hexsha[:8]
        logger.info("git_pull OK", repo=repo_name, commit=commit)
        return [types.TextContent(type="text", text=json.dumps({
            "status": "pulled",
            "repo_name": repo_name,
            "commit": commit,
        }))]
    except Exception as e:
        logger.error("git_pull FAIL", repo=repo_name, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def git_read_file(
    repo_name: str,
    file_path: str,
) -> list[types.TextContent]:
    """Lee el contenido de un archivo dentro de un repo clonado."""
    dest = _get_repo_path(repo_name)
    full_path = dest / file_path
    try:
        if not full_path.exists():
            return [types.TextContent(type="text", text=json.dumps({
                "error": f"Archivo no encontrado: {file_path}",
            }))]
        content = full_path.read_text(encoding="utf-8", errors="replace")
        logger.info("git_read_file OK", repo=repo_name, file=file_path, chars=len(content))
        return [types.TextContent(type="text", text=content)]
    except Exception as e:
        logger.error("git_read_file FAIL", repo=repo_name, file=file_path, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def git_list_files(
    repo_name: str,
    pattern: str = "**/*",
    max_files: int = 100,
) -> list[types.TextContent]:
    """Lista archivos en el repo con soporte de glob pattern."""
    dest = _get_repo_path(repo_name)
    try:
        files = [
            str(p.relative_to(dest))
            for p in dest.glob(pattern)
            if p.is_file() and ".git" not in p.parts
        ][:max_files]
        logger.info("git_list_files OK", repo=repo_name, count=len(files))
        return [types.TextContent(type="text", text=json.dumps({
            "repo_name": repo_name,
            "files": files,
            "count": len(files),
        }, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error("git_list_files FAIL", repo=repo_name, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def git_analyze_readme(repo_name: str) -> list[types.TextContent]:
    """
    Analiza el README del repo usando el LLM configurado.
    Retorna ReadmeAnalysis con endpoints, comandos de setup y más.
    """
    dest = _get_repo_path(repo_name)
    logger.info("git_analyze_readme", repo=repo_name)

    # Buscar README
    readme_content = ""
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "readme.txt"]:
        p = dest / name
        if p.exists():
            readme_content = p.read_text(encoding="utf-8", errors="replace")
            break

    if not readme_content:
        logger.warning("README no encontrado", repo=repo_name)

    analysis = await parse_readme(readme_content)
    return [types.TextContent(
        type="text",
        text=analysis.model_dump_json(indent=2),
    )]


async def git_get_info(repo_name: str) -> list[types.TextContent]:
    """Retorna información del repositorio: rama, último commit, remotes."""
    dest = _get_repo_path(repo_name)
    try:
        repo = git.Repo(dest)
        info = {
            "repo_name": repo_name,
            "path": str(dest),
            "branch": repo.active_branch.name,
            "last_commit": {
                "sha": repo.head.commit.hexsha[:12],
                "message": repo.head.commit.message.strip()[:100],
                "author": str(repo.head.commit.author),
                "date": repo.head.commit.committed_datetime.isoformat(),
            },
            "remotes": [r.url for r in repo.remotes],
            "is_dirty": repo.is_dirty(),
        }
        return [types.TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error("git_get_info FAIL", repo=repo_name, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def git_detect_api_spec(repo_name: str) -> list[types.TextContent]:
    """Detecta y retorna el contenido del OpenAPI/Swagger spec del repo."""
    dest = _get_repo_path(repo_name)
    logger.info("git_detect_api_spec", repo=repo_name)
    try:
        for candidate in API_SPEC_CANDIDATES:
            spec_path = dest / candidate
            if spec_path.exists():
                content = spec_path.read_text(encoding="utf-8")
                logger.info("API spec encontrada", repo=repo_name, file=candidate)
                return [types.TextContent(type="text", text=json.dumps({
                    "found": True,
                    "file": candidate,
                    "content": content,
                }, ensure_ascii=False))]

        logger.info("API spec no encontrada", repo=repo_name)
        return [types.TextContent(type="text", text=json.dumps({
            "found": False,
            "message": "No se encontró OpenAPI/Swagger spec. Usa git_analyze_readme para inferir endpoints.",
            "searched": API_SPEC_CANDIDATES,
        }))]
    except Exception as e:
        logger.error("git_detect_api_spec FAIL", repo=repo_name, error=str(e))
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
