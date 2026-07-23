# Trazabilidad del proyecto QAIF

## Propósito

Este documento relaciona los objetivos específicos, las fases CDIO, las historias de usuario, las funcionalidades implementadas y las evidencias disponibles en el repositorio.

## Matriz de trazabilidad

| Objetivo específico | Fase CDIO | Funcionalidad relacionada | Evidencia |
|---|---|---|---|
| Identificar herramientas de IA aplicables al aseguramiento de la calidad | Conceive | Selección de LLM, MCP y herramientas de automatización | Documento maestro, configuración y dependencias |
| Evaluar la pertinencia técnica y funcional de las herramientas | Conceive | Integración de modelo local, orquestación, caché y validación | Arquitectura y módulos del proyecto |
| Diseñar la arquitectura del framework QAIF | Design | Separación de análisis, generación, ejecución y reporte | `docs/ARQUITECTURA.md` y diagramas Mermaid |
| Implementar un prototipo funcional | Implement | Análisis de documentación, identificación de endpoints y generación de casos | Código fuente, scripts, pruebas y video |
| Validar el desempeño del framework | Operate | Ejecución de pruebas, métricas y reportes | `docs/RESULTADOS.md`, Markdown, PDF y video |

## Historias de usuario y evidencias

| Historia funcional | Resultado esperado | Evidencia del repositorio |
|---|---|---|
| Analizar documentación técnica | Identificación de información útil para pruebas | Módulos de análisis y flujo descrito en el README |
| Identificar endpoints | Extracción de rutas y métodos HTTP | Consola, scripts y demostración |
| Generar casos Happy Path con IA | Casos estructurados para ejecución | Modelo local, orquestación y resultados del video |
| Ejecutar pruebas sobre APIs REST | Registro de códigos, tiempos y estados | Carpeta `tests/`, registros y reportes |
| Generar reportes técnicos | Evidencia en Markdown y PDF | Documentación de resultados y video |
| Mantener trazabilidad | Relación entre objetivos, funciones y evidencias | README y este documento |

## Coherencia con Scrum

| Artefacto Scrum | Aplicación en QAIF |
|---|---|
| Product Backlog | Requisitos priorizados del framework |
| Historias de usuario | Necesidades del ingeniero QA y del proceso de automatización |
| Sprint Backlog | Actividades seleccionadas para cada incremento |
| Incremento | Componentes funcionales integrados al prototipo |
| Sprint Review | Revisión de funcionamiento y evidencias |
| Sprint Retrospective | Ajustes técnicos y documentales identificados |

## Criterio de actualización

Esta matriz debe revisarse cuando se modifiquen:

- Los objetivos específicos.
- Las historias de usuario.
- La arquitectura.
- Las funcionalidades implementadas.
- Las evidencias o resultados de validación.
