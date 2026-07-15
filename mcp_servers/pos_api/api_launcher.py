"""
Levanta el servidor de la API localmente desde su carpeta de repo.
Detecta el framework (FastAPI, Flask, Express, etc.) y el comando de inicio.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import httpx

from src.utils.logging_config import get_logger

logger = get_logger("pos_api.launcher")

# Registro global de procesos levantados (repo_name → Popen)
_running_processes: dict[str, subprocess.Popen] = {}
# Registro de base_urls (repo_name → base_url)
_base_urls: dict[str, str] = {}


async def setup_and_launch(
    repo_path: Path,
    setup_commands: list[str],
    start_command: str,
    base_url: str,
    health_path: str = "/health",
) -> tuple[bool, str]:
    """
    1. Instala dependencias (setup_commands)
    2. Lanza el servidor (start_command en background)
    3. Espera hasta que health check responda (máx 30s)
    """
    repo_name = repo_path.name
    logger.info("setup_and_launch inicio", repo=repo_name, commands=len(setup_commands))

    # Ejecutar comandos de setup secuencialmente
    for cmd in setup_commands:
        logger.info("Ejecutando setup", cmd=cmd)
        try:
            print(f"\n[INFO] Ejecutando: {cmd}")
            proc = subprocess.Popen(
                cmd, shell=True, cwd=str(repo_path),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    print(f"  {line.rstrip()}")
            
            if proc.returncode != 0:
                logger.error("Setup falló", cmd=cmd)
                return False, f"Setup falló en '{cmd}'"
            logger.info("Setup OK", cmd=cmd)
        except Exception as e:
            return False, f"Excepción en comando {cmd}: {e}"

    if not start_command:
        return False, "No se detectó comando de inicio. Verifica el README."

    # Lanzar servidor en background
    try:
        proc = subprocess.Popen(
            start_command, shell=True, cwd=str(repo_path),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        _running_processes[repo_name] = proc
        _base_urls[repo_name] = base_url
        logger.info("Servidor iniciado", repo=repo_name, pid=proc.pid, cmd=start_command)
    except Exception as e:
        return False, f"Error lanzando servidor: {e}"

    # Esperar health check (máx 300s, poll cada 1s)
    health_url = f"{base_url.rstrip('/')}{health_path}"
    print(f"\n[INFO] Servidor iniciando en background (PID {proc.pid}). Esperando health check en {health_url}...")
    print(f"[INFO] (La primera vez puede tardar varios minutos si está descargando dependencias)")
    
    for attempt in range(300):
        if attempt > 0 and attempt % 10 == 0:
            print(f"  ... esperando (intento {attempt}/300)")
            
        await asyncio.sleep(1)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(health_url)
                if r.status_code < 500:
                    logger.info(
                        "API disponible", url=health_url,
                        status=r.status_code, attempt=attempt + 1,
                    )
                    return True, f"Servidor disponible en {base_url} (intento {attempt + 1})"
        except (httpx.ConnectError, httpx.TimeoutException):
            pass  # Aún no está listo

        # Verificar si el proceso murió prematuramente
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            return False, f"El servidor terminó inesperadamente:\n{stderr[:500]}"

    return False, f"Servidor no respondió en 300s. Health URL: {health_url}"


def shutdown(repo_name: str) -> bool:
    """Termina el proceso del servidor."""
    proc = _running_processes.pop(repo_name, None)
    _base_urls.pop(repo_name, None)
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        logger.info("Servidor detenido", repo=repo_name)
        return True
    logger.warning("No hay proceso activo para detener", repo=repo_name)
    return False


def get_base_url(repo_name: str) -> Optional[str]:
    """Retorna la base URL del servidor activo para un repo."""
    return _base_urls.get(repo_name)


def list_running() -> list[dict]:
    """Lista todos los servidores activos."""
    return [
        {
            "repo_name": name,
            "pid": proc.pid,
            "base_url": _base_urls.get(name, ""),
            "running": proc.poll() is None,
        }
        for name, proc in _running_processes.items()
    ]
