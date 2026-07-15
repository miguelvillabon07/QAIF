# Reporte de Pruebas — Happy Path — task-crud-api

**Fecha:** 2026-07-04 23:04 UTC
**Repositorio:** task-crud-api
**Empresa:** Mi Empresa

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total de pruebas | 7 |
| Pasaron | 2 ✅ |
| Fallaron | 5 ❌ |
| Tasa de éxito | 28.6% |
| Duración total | 145.4s |
| Tiempo promedio de respuesta | 33.0ms |


> ❌ **Estado: NO APTO** — Demasiados fallos críticos. Bloquear deployment.


---

## Resultados por Endpoint


### 1. [HP] GET /api/health — ✅ PASS

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_000` |
| Status HTTP | 200 |
| Tiempo de respuesta | 75.1ms |




**Assertions:**


- ✅ **Status code es 200**


- ✅ **Respuesta en menos de 3 segundos**



---

### 2. [HP] POST /api/tasks — ❌ FAIL

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_001` |
| Status HTTP | 200 |
| Tiempo de respuesta | 34.2ms |

| Error | `Status 200 != 201` |


**Assertions:**


- ❌ **Status code es 201** — esperado: `201`, actual: `200`


- ✅ **Respuesta en menos de 3 segundos**


- ✅ **Response body es válido**



---

### 3. [HP] GET /api/tasks — ✅ PASS

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_002` |
| Status HTTP | 200 |
| Tiempo de respuesta | 28.1ms |




**Assertions:**


- ✅ **Status code es 200**


- ✅ **Respuesta en menos de 3 segundos**



---

### 4. [HP] GET /api/tasks/<id> — ❌ FAIL

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_003` |
| Status HTTP | 404 |
| Tiempo de respuesta | 28.2ms |

| Error | `Status 404 != 200` |


**Assertions:**


- ❌ **Status code es 200** — esperado: `200`, actual: `404`


- ✅ **Respuesta en menos de 3 segundos**



---

### 5. [HP] PUT /api/tasks/<id> — ❌ FAIL

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_004` |
| Status HTTP | 404 |
| Tiempo de respuesta | 24.2ms |

| Error | `Status 404 != 200` |


**Assertions:**


- ❌ **Status code es 200** — esperado: `200`, actual: `404`


- ✅ **Respuesta en menos de 3 segundos**


- ✅ **Response body es válido**



---

### 6. [HP] PATCH /api/tasks/<id> — ❌ FAIL

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_005` |
| Status HTTP | 404 |
| Tiempo de respuesta | 20.6ms |

| Error | `Status 404 != 200` |


**Assertions:**


- ❌ **Status code es 200** — esperado: `200`, actual: `404`


- ✅ **Respuesta en menos de 3 segundos**



---

### 7. [HP] DELETE /api/tasks/<id> — ❌ FAIL

| Campo | Valor |
|-------|-------|
| Endpoint ID | `hp_task-crud-api_006` |
| Status HTTP | 404 |
| Tiempo de respuesta | 20.8ms |

| Error | `Status 404 != 200` |


**Assertions:**


- ❌ **Status code es 200** — esperado: `200`, actual: `404`


- ✅ **Respuesta en menos de 3 segundos**



---


## Sugerencias de Automatización Adicional



1. Crear una tarea con datos inválidos (ej. campo obligatorio faltante) y verificar código de error 400.

2. Intentar recuperar una tarea con ID inválido (ej. cadena en lugar de número) y verificar código 404.

3. Intentar actualizar una tarea con ID inexistente y verificar código 404.

4. Intentar eliminar una tarea con ID inexistente y verificar código 404.

5. Crear múltiples tareas con el mismo ID y verificar que se devuelva un error 400 o 409.



---

## Información de Ejecución

| Campo | Valor |
|-------|-------|
| Inicio | 2026-07-04 22:48:56.546518+00:00 |
| Fin | 2026-07-04 22:51:21.971356+00:00 |
| Pipeline | Automatizado por MCP QA Automation |

_Reporte generado automáticamente · No modificar manualmente_