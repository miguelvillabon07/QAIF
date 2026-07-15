# Architecture Decision Records (ADRs)

> Registro de decisiones arquitecturales del sistema MCP QA Automation.
> Formato: contexto → decisión → alternativas → consecuencias.

---

## ADR-001: Qwen3:8b como modelo de IA local

**Estado**: Aceptado | **Fecha**: 2026-05 | **Autor**: Jhonattan Gonzalez

### Contexto

El sistema requiere inferencia LLM frecuente para:
- Extraer User Stories de transcripciones (~800-2000 tokens de input)
- Analizar READMEs y detectar endpoints (~1000-4000 tokens)
- Rutear comandos en lenguaje natural (~200 tokens)

La infraestructura disponible incluye una **NVIDIA RTX 3050 Laptop GPU con 6GB VRAM** y acceso a la **Anthropic API** (costo variable).

### Decisión

**Usar Qwen3:8b Q4_K_M como modelo local primario, con Claude API como fallback.**

- Cuantización Q4_K_M ocupa ~5.0GB → encaja en 6GB VRAM con margen
- Flash Attention 2 reduce VRAM adicional ~20% y acelera prefill
- Velocidad de generación: **25-35 tok/s** en GPU (vs 3-8 tok/s en CPU)

### Alternativas consideradas

| Modelo | VRAM | Velocidad | Calidad | Decisión |
|---|---|---|---|---|
| **Qwen3:8b Q4_K_M** | 5.0GB | 25-35 tok/s | ★★★★ | ✅ ELEGIDO |
| Llama3.1:8b | 5.5GB | 22-30 tok/s | ★★★★ | Descartado (menor contexto español) |
| Mistral:7b | 4.8GB | 28-35 tok/s | ★★★ | Descartado (menor coherencia larga) |
| Gemma2:9b | 6.2GB | 18-25 tok/s | ★★★★ | Descartado (no cabe en 6GB) |
| Phi3:14b | >8GB | N/A | ★★★★★ | Descartado (no cabe en VRAM) |

### Consecuencias

**Positivas:**
- $0/mes en inferencia local
- Sin dependencia de internet para pipeline principal
- Datos sensibles no salen del equipo

**Negativas:**
- Contexto máximo 8K tokens (transcripciones muy largas deben truncarse)
- Cold start de ~8s al cargar el modelo en VRAM
- Solo 1 request simultáneo con 6GB VRAM

**Mitigación:**
- Transcripciones truncadas a 10K chars (suficiente para 90% de casos)
- `OLLAMA_KEEP_ALIVE=5m` mantiene el modelo cargado entre requests
- Switch a Claude API (`model switch anthropic`) para casos excepcionales

---


## ADR-002: MCP Servers custom vs servidores oficiales

**Estado**: Aceptado | **Fecha**: 2026-05

### Contexto

Existen servidores MCP oficiales o de la comunidad para algunos servicios:
- `mcp-atlassian` → Jira oficial
- `mcp-server-gdrive` → Google Drive
- `mcp-github` → GitHub

### Decisión

**Construir MCP servers custom para todos los servicios.**

### Justificación

| Criterio | Servers oficiales | Custom (este sistema) |
|---|---|---|
| **Control del schema** | Limitado | Total — exactamente los campos que necesitamos |
| **Autenticación** | OAuth genérico | Service Account + API Token según caso |
| **Error handling** | Genérico | Con `async_retry`, logging structlog, audit trail |
| **Integración CAG** | Ninguna | Integrada en git y pos_api |
| **Rate limiting** | No siempre | Configurable por server |
| **Testeabilidad** | Caja negra | Tests unitarios directos |

### Cuándo usar servidores oficiales

- Para **demos rápidas** o pruebas de concepto
- Cuando las herramientas necesarias ya existen exactamente como se necesitan
- Para servicios que cambian su API frecuentemente (menor mantenimiento)

### Consecuencias

- Mayor código a mantener (~1500 líneas en mcp_servers/)
- Mayor control sobre el comportamiento
- Fácil agregar nuevas herramientas (solo añadir función en tools.py)

---

## ADR-003: LangGraph como orquestador del pipeline

**Estado**: Aceptado | **Fecha**: 2026-05

### Contexto

El pipeline de QA tiene múltiples pasos secuenciales con:
- Estado compartido entre nodos
- Posibilidad de retry en errores de red
- Human-in-the-loop (aprobación antes de crear en Jira)
- Checkpointing para resumir pipelines interrumpidos

### Decisión

**Usar LangGraph `StateGraph` como orquestador.**

---

## ADR-004: Git-First para API Testing

**Estado**: Aceptado | **Fecha**: 2026-05

### Contexto

El sistema debe probar APIs que pueden no tener documentación previa, o cuya documentación puede estar desactualizada. El repositorio Git siempre es la fuente de verdad.

### Decisión

**El flujo de testing siempre parte del repositorio Git.**

```
git clone → README analizado con LLM → endpoints detectados →
API levantada localmente → happy path ejecutado → suggestions generadas
```

### Por qué no API-first

Si empezáramos por la URL de la API:
- La API puede no estar corriendo
- No tendríamos contexto de cómo levantarla
- No sabríamos las credenciales necesarias
- No podríamos generar tests de setup/teardown

### Flujo Git-First en detalle

```
1. git_clone()          → Código fuente local
2. git_analyze_readme() → LLM extrae: endpoints, setup_cmds, start_command, auth_hint
3. pos_api_setup()      → Ejecuta setup_cmds, lanza start_command en background
4. health_check()       → Verifica que la API responde en /health o /api
5. pos_api_run_happy_path() → HTTP requests a cada endpoint detectado
6. LLM suggestions      → Basadas en resultado del happy path
```

### Consecuencias

- Puede analizar APIs **sin documentación externa** (solo README)
- Funciona con cualquier framework (FastAPI, Django, Express, Spring)
- Si el README tiene errores → el análisis LLM puede compensar (baja confianza)

---

## ADR-005: Carpetas individuales por MCP Server

**Estado**: Aceptado | **Fecha**: 2026-05

### Contexto

Hay dos formas de organizar los MCP servers:
1. **Monolito**: Un solo directorio `mcp_servers/` con todos los tools en archivos por dominio
2. **Carpetas individuales**: Cada server en su propia carpeta con `config.json`, `server.py`, `tools.py`, `auth.py`

### Decisión

**Carpeta individual por server.**

```
mcp_servers/
├── drive/       (Drive MCP — carpeta independiente)
├── jira/        (Jira MCP — carpeta independiente)
├── git/         (Git MCP — carpeta independiente)
├── pos_api/     (POS API MCP — carpeta independiente)
├── reporting/   (Reporting MCP — carpeta independiente)
└── workspace/   (Workspace MCP — carpeta independiente)
```

### Justificación

| Criterio | Monolito | Carpetas individuales |
|---|---|---|
| **Dockerización** | Un solo contenedor | Cada server puede ser su propio contenedor |
| **Despliegue independiente** | No | Sí — actualizar Jira sin tocar Drive |
| **Dependencias** | Compartidas (conflictos) | Cada carpeta tiene su `requirements.txt` |
| **Testing** | Mock de todo el sistema | Tests aislados por server |
| **Legibilidad** | Archivos grandes | Archivos pequeños y enfocados |
| **`config.json`** | No aplicable | Estándar MCP: metadata + tools list |

### Cuándo consolidar

Si los servers comparten >80% del código (auth, schemas, logging) sin divergir, considerar consolidar para reducir duplicación.

### Consecuencias

- Cada server es un **proceso MCP independiente** que puede correr en su propio contenedor
- `config.json` sigue el estándar MCP para ser compatible con cualquier host MCP
- Fácil agregar un nuevo server: copiar estructura, implementar `tools.py`
- `workspace/` sirve de server "utilitario" compartido (logs, repos, reports)

---

## ADR-006: Ejecución Híbrida de API Testing (Agente en Docker, API en Host)

**Estado**: Aceptado | **Fecha**: 2026-05

### Contexto

El Agente MCP corre dentro de un contenedor Docker `python:3.12-slim` para garantizar portabilidad. Sin embargo, en el pipeline de QA necesitamos ejecutar pruebas contra APIs locales que tienen sus propias dependencias pesadas (ej: Java JDK, Node.js, Spring Boot, NestJS).

Originalmente se pensaba descargar dependencias (ej. Maven/Gradle) e iniciar la API (`bootRun`) _dentro_ del contenedor del agente pero fallaba porque el contenedor no posee un entorno universal (ej. `JAVA_HOME not set`).

### Decisión

**Delegar la ejecución de la API objetivo a la máquina anfitriona (Host) y usar el agente Docker únicamente como orquestador de pruebas mediante `host.docker.internal`.**

### Flujo Híbrido Actualizado

1. `test setup` → El agente lee el README y proporciona las instrucciones manuales.
2. **Humano** → Levanta el servicio en una terminal del Host (`cd workspace/repos/... && ./gradlew bootRun`).
3. `test run base_url=http://host.docker.internal:8000` → El agente Docker dispara peticiones HTTP hacia el Host.

### Consecuencias

**Positivas:**
- El contenedor del agente se mantiene ligero (sin instalar SDKs de Java, Node, Go, etc.).
- Cero problemas de compilación o variables de entorno ajenas al agente.
- Mayor control humano sobre la inicialización de la API (visualización de logs nativos).

**Negativas:**
- Se pierde la automatización E2E del 100% (requiere que un humano o script del host inicie el servicio).
- Dependencia del hostname especial `host.docker.internal`, el cual requiere configuración adicional en Linux (nativo en Docker Desktop para Windows/Mac).

---

*Estos ADRs deben actualizarse cuando las decisiones cambien.*
*Seguir formato: Contexto → Decisión → Alternativas → Consecuencias.*
