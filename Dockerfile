FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
RUN pip install uv

# Copiar archivos de dependencias
COPY pyproject.toml .
COPY .env.example .

# Instalar dependencias Python
RUN uv pip install --system -e ".[dev]"

# Copiar código fuente
COPY src/ ./src/
COPY mcp_servers/ ./mcp_servers/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Crear directorios de workspace
RUN mkdir -p workspace/repos workspace/reports workspace/logs secrets

# Script de inicio que descarga el modelo Qwen si no existe
COPY scripts/pull_model.sh .
RUN chmod +x pull_model.sh

EXPOSE 8000

CMD ["python", "-m", "src.console"]
