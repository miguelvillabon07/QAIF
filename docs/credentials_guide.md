# Guía de Credenciales — MCP QA Automation

> Esta guía explica **qué credencial necesitas**, **cuándo configurarla**, **cómo obtenerla paso a paso** y **cómo verificar que funciona**.

---

## Mapa de Funcionalidades vs Credenciales

```
FUNCIONALIDAD                     CREDENCIAL REQUERIDA
─────────────────────────────────────────────────────────────
docker compose up                → (ninguna — solo Docker)
model switch local               → (ninguna — Ollama local)
git clone / git analyze          → (ninguna — repo público)
─────────────────────────────────────────────────────────────
extract <file_id>                → GOOGLE_SERVICE_ACCOUNT_JSON
story create                     → JIRA_URL + JIRA_EMAIL +
                                   JIRA_API_TOKEN + JIRA_PROJECT_KEY
report upload <issue>            → (mismas de Jira)
model switch anthropic           → ANTHROPIC_API_KEY
─────────────────────────────────────────────────────────────
```

---

## Archivo `.env` — Punto Central de Configuración

Todas las credenciales van en un único archivo `.env` en la raíz del proyecto.

```bash
# Crear el archivo si no existe
cp .env.example .env
# o simplemente crear:
notepad .env   # Windows
```

> [!CAUTION]
> El archivo `.env` está en `.gitignore`. **NUNCA** lo subas a Git ni lo compartas. Contiene claves que dan acceso a tus servicios.

---

## 1. 🤖 IA Local — Ollama + Qwen3:8b

**Cuándo**: Siempre. Es el modo por defecto. No requiere cuenta ni internet.

**Variables en `.env`**:
```bash
LLM_PROVIDER=local
LOCAL_MODEL_NAME=qwen3:8b
OLLAMA_BASE_URL=http://ollama:11434/v1
```

> [!NOTE]
> **Conexión Docker vs. Python Local:**
> - Si usas **Docker** (recomendado), usa `OLLAMA_BASE_URL=http://ollama:11434/v1` porque "ollama" es el nombre del contenedor en la red interna.
> - Si ejecutas tu código Python **fuera de Docker** directamente en tu Windows (pero Ollama corre en Docker o en tu PC), debes cambiarlo a `OLLAMA_BASE_URL=http://localhost:11434/v1`.

> [!TIP]
> **GPU vs CPU:**
> El entorno está configurado nativamente para aprovechar tu tarjeta gráfica (GPU). Sin embargo, si deseas ejecutar Ollama solo con el procesador (CPU), puedes eliminar o comentar las líneas relacionadas con `deploy`, `resources` y `CUDA_VISIBLE_DEVICES` en tu archivo `docker-compose.yml`. Al usar CPU el procesamiento será significativamente más lento.

> [!WARNING]
> **Versiones de Qwen3 y consumo de RAM/VRAM:**
> Actualmente usas `qwen3:8b`, que funciona excelente con 6GB de VRAM (como en la RTX 3050).
> Si en algún momento necesitas reducir drásticamente el consumo de memoria, puedes cambiar en `.env` a versiones más ligeras como `qwen3:4b` o `qwen3:1.5b`.
> *⚠️ Ten en cuenta que al usar versiones más pequeñas, comprometes la capacidad de razonamiento lógico de la IA y la calidad de los datos procesados.*

**Cómo funciona**:
1. `docker compose up` descarga el modelo seleccionado automáticamente (primera vez, solo una vez).
2. El modelo se guarda en el volumen Docker `ollama_models` → persiste entre reinicios.
3. El agente llama a Ollama por HTTP → sin API key.

**Cuándo cambiar `LOCAL_MODEL_NAME`**:
- Si quieres probar otro modelo disponible en Ollama.
- Modelos probados con 6GB VRAM: `qwen3:8b`, `llama3.1:8b`, `mistral:7b`.
- Para ver modelos disponibles: `docker exec mcp-ollama ollama list`.

**Verificar que funciona**:
```bash
# Nota para Windows (PowerShell): Usa "curl.exe" en lugar de "curl"
curl.exe http://localhost:11434/api/tags

# Para verificar qué modelos están descargados y listos:
docker exec mcp-ollama ollama list
```

> [!TIP]
> **Troubleshooting de conexión:**
> 1. **Logs**: Verifica el estado general y errores con `docker compose logs -f`.
> 2. **Servicio detenido**: Revisa si el contenedor está corriendo con `docker compose ps`. Si no está activo, inícialo con `docker compose up -d --build`.
> 3. **Modelo vacío en la lista**: Si al ejecutar `ollama list` no aparece `qwen3:8b`, significa que aún se está descargando en segundo plano (pesa ~5GB). Puedes ver el progreso ejecutando: `docker compose logs -f mcp-model-puller`.
> 4. **Conectividad**: Valida que el puerto 11434 no esté bloqueado y que tu variable `OLLAMA_BASE_URL` en el archivo `.env` coincida con tu entorno (Docker o Local).

---

## 2. 🧠 IA en la Nube — Anthropic Claude

**Cuándo usar**: Cuando necesites procesar documentos muy largos (>8K tokens), o como respaldo si Ollama no está disponible.

**Variable en `.env`**:
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-sonnet-4-5
```

### Cómo obtener la API Key

1. Ir a [console.anthropic.com](https://console.anthropic.com)
2. Iniciar sesión o crear cuenta (requiere verificación de tarjeta)
3. En el menú lateral: **API Keys**
4. Click en **"Create Key"**
5. Nombrarla (ej: `mcp-qa-automation`)
6. Copiar la clave — **solo se muestra una vez**
7. Pegarla en `.env`: `ANTHROPIC_API_KEY=sk-ant-api03-XXXX`

### Cuándo cambiarla

- Si la clave fue comprometida: revocarla en la consola y crear una nueva
- Si cambias de cuenta de facturación

### Costos aproximados con Claude Sonnet 4

| Operación | Tokens aprox. | Costo |
|---|---|---|
| Extraer User Stories de transcripción | ~3,000 | ~$0.009 |
| Analizar README | ~2,000 | ~$0.006 |
| Pipeline completo (extracción + tests) | ~8,000 | ~$0.024 |

> **Recomendación**: Usa `LLM_PROVIDER=local` para desarrollo y pruebas. Cambia a `anthropic` solo para documentos muy grandes o demos de producción.

**Verificar en la consola**:
```bash
[QWEN3:8B] → model switch anthropic
# Debe responder: ✓ Modelo cambiado a: claude-sonnet-4-5
```

---

## 3. 📄 Google Drive — Leer Transcripciones

**Cuándo**: Al usar `extract <file_id>` para leer actas de reunión desde Drive.

**Variables en `.env`**:
```bash
GOOGLE_SERVICE_ACCOUNT_JSON=secrets/service_account.json
GOOGLE_DRIVE_FOLDER_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs
```

### Cómo obtener el Service Account JSON — Paso a Paso

#### Paso 1: Crear el proyecto en Google Cloud

1. Ir a [console.cloud.google.com](https://console.cloud.google.com)
2. Click en el selector de proyecto (arriba izquierda) → **"Nuevo proyecto"**
3. Nombre: `mcp-qa-automation` → **Crear**

#### Paso 2: Habilitar la API de Drive

1. En el menú lateral: **APIs y servicios → Biblioteca**
2. Buscar: `Google Drive API`
3. Click en el resultado → **Habilitar**

#### Paso 3: Crear Service Account

1. Menú: **APIs y servicios → Credenciales**
2. Click **"+ Crear credenciales" → "Cuenta de servicio"**
3. Nombre: `mcp-qa-reader`
4. Descripción: `Lectura de transcripciones para QA automation`
5. Click **"Crear y continuar"**
6. En "Rol": buscar y seleccionar **"Visualizador"** (Viewer)
7. Click **"Continuar" → "Listo"**

#### Paso 4: Descargar el JSON de credenciales

1. En la lista de Service Accounts, click en `mcp-qa-reader@...`
2. Tab **"Claves"**
3. Click **"Agregar clave" → "Crear clave nueva"**
4. Formato: **JSON** → **Crear**
5. Se descarga automáticamente un archivo `mcp-qa-automation-XXXX.json`
6. **Moverlo** a: `MCP_Project/secrets/service_account.json`

```bash
# En Windows (PowerShell):
Move-Item "$env:USERPROFILE\Downloads\mcp-qa-automation-*.json" "secrets\service_account.json"
```

#### Paso 5: Compartir las carpetas de Drive con el Service Account

> Este paso es crítico — sin él, el service account no puede leer los archivos.

1. Abrir [drive.google.com](https://drive.google.com)
2. Click derecho en la carpeta que contiene las transcripciones → **"Compartir"**
3. En el campo de email: pegar el email del service account
   - Se encuentra en el JSON descargado: campo `"client_email"`
   - Ejemplo: `mcp-qa-reader@mcp-qa-automation.iam.gserviceaccount.com`
4. Permisos: **"Lector"** (no necesita editar)
5. Click **"Compartir"**

#### Paso 6: Obtener el `GOOGLE_DRIVE_FOLDER_ID`

1. Abrir la carpeta en Drive
2. La URL será: `https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs`
3. El ID es la última parte: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs`
4. Copiar en `.env`: `GOOGLE_DRIVE_FOLDER_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs`

**Verificar que funciona**:
```bash
[QWEN3:8B] → extract --list
# Debe mostrar una tabla con los archivos de tu carpeta Drive
```

**Errores comunes**:
| Error | Causa | Solución |
|---|---|---|
| `403 Forbidden` | Service account sin acceso | Compartir la carpeta Drive con el email del SA |
| `File not found` | `file_id` incorrecto | Verificar el ID en la URL de Drive |
| `JSON decode error` | JSON del SA corrupto | Re-descargar el archivo de credenciales |

---

## 4. 🎫 Jira — Crear Issues y Subir Reportes

**Cuándo**: Al usar `story create` (crear User Stories) o `report upload <issue>`.

**Variables en `.env`**:
```bash
JIRA_URL=https://tu-empresa.atlassian.net
JIRA_EMAIL=tu@email.com
JIRA_API_TOKEN=ATATT3xFfGF...
JIRA_PROJECT_KEY=PROJ
JIRA_EPIC_KEY=PROJ-1
```

### Cómo obtener el API Token de Jira

1. Ir a [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
   - O desde Jira: click en tu **avatar** (arriba derecha) → **"Profile"** → **"Security"** → **"API token"**
2. Click **"Create API token"**
3. Etiqueta: `mcp-qa-automation`
4. Click **"Create"**
5. **Copiar el token** — solo se muestra una vez
6. Pegarlo en `.env`: `JIRA_API_TOKEN=ATATT3xFfGF...`

### Cómo obtener los demás valores

| Variable | Dónde encontrarla |
|---|---|
| `JIRA_URL` | La URL de tu Jira: `https://miempresa.atlassian.net` |
| `JIRA_EMAIL` | Tu email de login en Jira |
| `JIRA_PROJECT_KEY` | En Jira → elige tu proyecto → la clave aparece en la URL y en los issue IDs (ej: `PROJ` en `PROJ-123`) |
| `JIRA_EPIC_KEY` | Opcional. El issue ID de un Epic padre (ej: `PROJ-1`). Si no tienes, dejarlo vacío |

### Permisos necesarios en Jira

El usuario cuyo token usas debe tener en el proyecto:
- ✅ **Create Issues**
- ✅ **Edit Issues**
- ✅ **Add Comments**
- ✅ **Create Attachments**

> Si usas Jira Cloud con plan Free, estos permisos están disponibles para cualquier miembro del proyecto.

**Verificar que funciona**:
```bash
# Luego de story create exitoso, debe mostrar:
# ✓ 3/3 issues creados en Jira
# → PROJ-101
# → PROJ-102
```

**Errores comunes**:
| Error | Causa | Solución |
|---|---|---|
| `401 Unauthorized` | Token incorrecto o expirado | Generar nuevo token en Atlassian |
| `403 Forbidden` | Sin permiso para crear issues | Pedir acceso al admin del proyecto |
| `404 Not Found` | `JIRA_PROJECT_KEY` incorrecto | Verificar la clave exacta en la URL del proyecto |

---

## 5. 🔄 Cuándo Rotar/Cambiar Credenciales

### Rotación recomendada

| Credencial | Cuándo rotar | Acción |
|---|---|---|
| `ANTHROPIC_API_KEY` | Si fue expuesta o cada 90 días | Revocar en console.anthropic.com + crear nueva |
| `JIRA_API_TOKEN` | Si fue expuesta o cada 6 meses | Revocar en id.atlassian.com + crear nuevo |
| `service_account.json` | Si fue expuesta | Eliminar la clave en Google Cloud + descargar nueva |

### Si una credencial fue comprometida

**1. Revocar INMEDIATAMENTE:**
- Anthropic: [console.anthropic.com](https://console.anthropic.com) → API Keys → Revocar
- Jira: [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) → Delete
- Google: [console.cloud.google.com](https://console.cloud.google.com) → IAM → Service Accounts → Eliminar clave

**2. Crear nueva y actualizar `.env`**

**3. Verificar que no hubo acceso no autorizado** en los logs del servicio

---

## 6. Estructura Final del `.env`

```bash
# ════════════════════════════════════════════════════
# MCP QA AUTOMATION — Configuración de entorno
# ════════════════════════════════════════════════════
# ⚠  Este archivo es PRIVADO. NO subir a Git.
# ════════════════════════════════════════════════════

# ── LLM Principal ────────────────────────────────────
# "local"      = Qwen3:8b via Ollama (GPU, gratis)
# "anthropic"  = Claude Sonnet 4 (API de pago)
LLM_PROVIDER=local

LOCAL_MODEL_NAME=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434/v1

# ── Anthropic (solo si LLM_PROVIDER=anthropic) ───────
# Obtener en: https://console.anthropic.com/api-keys
ANTHROPIC_API_KEY=sk-ant-api03-REEMPLAZAR
ANTHROPIC_MODEL=claude-sonnet-4-5

# ── Google Drive ──────────────────────────────────────
# Guía: docs/credentials_guide.md → Sección 3
GOOGLE_SERVICE_ACCOUNT_JSON=secrets/service_account.json
GOOGLE_DRIVE_FOLDER_ID=REEMPLAZAR_CON_ID_DE_TU_CARPETA

# ── Jira Cloud ────────────────────────────────────────
# Token: https://id.atlassian.com/manage-profile/security/api-tokens
JIRA_URL=https://TU-EMPRESA.atlassian.net
JIRA_EMAIL=tu@email.com
JIRA_API_TOKEN=ATATT3x-REEMPLAZAR
JIRA_PROJECT_KEY=PROJ
JIRA_EPIC_KEY=

# ── Redis / CAG ───────────────────────────────────────
# Redis corre en Docker — no requiere credenciales externas
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=
CAG_ENABLED=true
CAG_README_TTL_SECONDS=3600
CAG_API_SPEC_TTL_SECONDS=7200
CAG_JIRA_CONFIG_TTL_SECONDS=1800

# ── Pipeline ──────────────────────────────────────────
HUMAN_REVIEW_ENABLED=false
PIPELINE_RETRY_MAX=3
LANGGRAPH_CHECKPOINT_DB=sqlite:///checkpoints.db

# ── Reportes ──────────────────────────────────────────
REPORT_OUTPUT_DIR=workspace/reports
REPORT_COMPANY_NAME=Mi Empresa S.A.

# ── Workspace / Git ───────────────────────────────────
GIT_WORKSPACE_PATH=workspace/repos
AUDIT_LOG_DIR=workspace/logs
```

---

## 7. Checklist de Configuración Inicial

Marca cada paso cuando lo completes:

```
☐ 1. Crear archivo .env en la raíz del proyecto
☐ 2. docker compose up  (verificar que Redis y Ollama arrancan)
☐ 3. Esperar descarga de Qwen3:8b (ver: docker logs mcp-model-puller -f)
☐ 4. Probar consola: uv run python -m src.console → escribir "health"

-- Si usas Drive: --
☐ 5. Crear proyecto en Google Cloud
☐ 6. Habilitar Google Drive API
☐ 7. Crear Service Account y descargar JSON
☐ 8. Mover JSON a secrets/service_account.json
☐ 9. Compartir carpeta Drive con el email del Service Account
☐ 10. Copiar folder_id en GOOGLE_DRIVE_FOLDER_ID
☐ 11. Verificar: extract --list (debe mostrar archivos)

-- Si usas Jira: --
☐ 12. Crear API Token en id.atlassian.com
☐ 13. Completar JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY
☐ 14. Verificar permisos de tu usuario en el proyecto Jira
☐ 15. Verificar: story create (con al menos 1 historia extraída)

-- Si usas Anthropic: --
☐ 16. Crear API Key en console.anthropic.com
☐ 17. Completar ANTHROPIC_API_KEY
☐ 18. Verificar: model switch anthropic → escribir "hello" (prueba básica)
```

---

> Cuando hayas completado los pasos que necesitas, escríbeme **"credenciales configuradas"** y continuamos con el pipeline E2E completo.

*Última actualización: 2026-05 | Autor: Jhonattan Gonzalez*
