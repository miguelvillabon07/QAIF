# Resultados y validación del prototipo QAIF

## Contexto de la demostración

La validación del prototipo se realizó en un entorno académico y controlado, utilizando un proyecto de prueba y datos no sensibles. El objetivo fue evidenciar el flujo completo de análisis, generación, ejecución y reporte.

## Resultados observados

Durante la demostración se ejecutaron siete pruebas correspondientes al flujo Happy Path.

| Indicador | Resultado |
|---|---:|
| Casos ejecutados | 7 |
| Casos exitosos | 2 |
| Respuestas HTTP 404 | 5 |
| Reportes generados | Markdown y PDF |

## Interpretación

Las respuestas HTTP 404 no se interpretan automáticamente como un fallo del framework. En el proyecto evaluado, algunos endpoints requieren recursos creados previamente o identificadores válidos antes de ejecutar determinadas operaciones.

El prototipo registró para cada solicitud:

- Método HTTP.
- URL evaluada.
- Código de respuesta.
- Tiempo de ejecución.
- Estado PASS o FAIL.

## Evidencias generadas

QAIF consolida los resultados en dos formatos:

1. Reporte Markdown para consulta técnica rápida y control de versiones.
2. Reporte PDF para presentación y conservación formal de la evidencia.

Los reportes incluyen un resumen ejecutivo, el detalle de los endpoints evaluados, tiempos de respuesta, estados obtenidos y una conclusión general.

## Relación con TRL 5

La demostración aporta evidencia de validación tecnológica en un entorno relevante simulado o controlado:

- Existe un prototipo funcional.
- Los componentes principales se encuentran integrados.
- El sistema ejecuta pruebas sobre una API REST.
- Se obtienen resultados verificables.
- Se generan evidencias técnicas.
- El funcionamiento se presenta mediante un video demostrativo.

## Enlaces

- Video demostrativo: https://youtu.be/fBCzXiYRcgg?si=q_tsTtbEC8QkuFle
- Repositorio público: https://github.com/miguelvillabon07/QAIF

## Trabajo pendiente

La validación debe seguir fortaleciéndose con:

- Mayor variedad de escenarios.
- Casos negativos y de borde.
- Métricas consolidadas de cobertura y tiempos.
- Comparación entre ejecución manual y asistida.
- Revisión final de coherencia con el documento maestro.
