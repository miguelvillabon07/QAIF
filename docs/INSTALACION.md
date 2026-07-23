# Instalación del prototipo QAIF

## Alcance

Esta guía documenta la preparación básica del entorno local para ejecutar el prototipo QAIF. Los comandos definitivos pueden variar según el script o módulo utilizado durante la demostración.

## Requisitos

- Git.
- Python 3.12 o superior.
- `uv` para la gestión de dependencias.
- Ollama.
- Modelo local `qwen3:8b`.
- Redis cuando el flujo requiera caché.
- Acceso a una API REST de prueba o a un proyecto con documentación técnica.

## Clonar el repositorio

```bash
git clone https://github.com/miguelvillabon07/QAIF.git
cd QAIF
```

## Instalar dependencias

```bash
uv sync
```

Las dependencias principales se encuentran declaradas en `pyproject.toml`. Las herramientas de desarrollo y pruebas se incluyen en el grupo opcional `dev`.

## Preparar Ollama

Verifique que Ollama esté instalado y en ejecución. Después, descargue el modelo configurado para la demostración:

```bash
ollama pull qwen3:8b
```

## Configurar variables del entorno

El proyecto utiliza un archivo `.env` con parámetros similares a los siguientes:

```env
PROVEEDOR_DE_LLM=local
NOMBRE_DE_MODELO_LOCAL=qwen3:8b
OLLAMA_BASE_URL=http://mcp-ollama:11434/v1
REDIS_URL=redis://mcp-redis:6379
REVISION_HUMANA_ACTIVADA=FALSO
NIVEL_DE_REGISTRO=DEPURAR
```

Los valores deben adaptarse a la infraestructura local. No se deben incluir contraseñas, tokens ni claves privadas en el repositorio.

## Verificación del entorno

Antes de iniciar el flujo, compruebe:

1. Que Python y `uv` estén disponibles.
2. Que Ollama responda correctamente.
3. Que el modelo local esté instalado.
4. Que Redis esté disponible si el módulo utilizado lo requiere.
5. Que exista documentación técnica o una API REST de prueba accesible.

## Ejecución

El repositorio contiene módulos en `src/` y scripts auxiliares en `scripts/`. La ejecución exacta debe corresponder al módulo utilizado en la demostración del prototipo.

Flujo esperado:

1. Seleccionar o analizar el proyecto objetivo.
2. Leer la documentación técnica.
3. Identificar endpoints y métodos HTTP.
4. Generar casos Happy Path.
5. Ejecutar las pruebas.
6. Consolidar resultados.
7. Crear reportes Markdown y PDF.

## Pruebas del proyecto

La configuración de `pytest` está declarada en `pyproject.toml` y utiliza la carpeta `tests/`.

```bash
uv run pytest
```

Para incluir cobertura, cuando las pruebas disponibles lo permitan:

```bash
uv run pytest --cov
```

## Consideraciones

- El prototipo se usa con fines académicos.
- Deben emplearse datos sintéticos o APIs simuladas.
- No deben utilizarse datos financieros reales.
- La documentación debe actualizarse cuando cambie el procedimiento real de ejecución.
