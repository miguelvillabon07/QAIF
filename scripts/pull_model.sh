#!/bin/bash
# Descarga Qwen3:8b en Ollama si no está disponible
MODEL=${LOCAL_MODEL_NAME:-qwen3:8b}
echo "Verificando modelo: $MODEL"
if curl -s http://ollama:11434/api/tags | grep -q "$MODEL"; then
    echo "Modelo $MODEL ya disponible"
else
    echo "Descargando $MODEL (puede tomar varios minutos)..."
    curl -X POST http://ollama:11434/api/pull \
         -H "Content-Type: application/json" \
         -d "{\"name\": \"$MODEL\"}"
    echo "Modelo $MODEL descargado"
fi
