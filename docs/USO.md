# Uso del framework QAIF

## Objetivo de la guía

Esta guía resume el flujo operativo del prototipo QAIF desde la selección del proyecto objetivo hasta la generación de evidencias.

## Flujo de trabajo

### 1. Preparar el proyecto objetivo

El usuario debe disponer de una API REST o de un proyecto de prueba que incluya documentación técnica, archivos README, colecciones o especificaciones que permitan reconocer endpoints y métodos HTTP.

### 2. Iniciar QAIF

El prototipo se ejecuta desde la consola y utiliza los módulos disponibles en `src/` junto con los scripts auxiliares del repositorio.

### 3. Analizar la documentación

QAIF procesa la documentación técnica y extrae información relevante, entre ella:

- Endpoints.
- Métodos HTTP.
- Parámetros.
- Rutas.
- Respuestas esperadas.
- Dependencias entre recursos.

### 4. Generar casos de prueba

El modelo de lenguaje participa en la creación asistida de escenarios Happy Path. Cada caso debe conservar, cuando aplique:

- Identificador.
- Endpoint.
- Método HTTP.
- Datos de entrada.
- Condición previa.
- Resultado esperado.
- Criterio de aceptación.

### 5. Ejecutar las pruebas

El motor de automatización realiza las solicitudes sobre la API objetivo y registra:

- Método HTTP.
- URL.
- Código de respuesta.
- Tiempo de ejecución.
- Estado PASS o FAIL.

### 6. Interpretar resultados

Un estado FAIL no implica necesariamente una falla del framework. Puede deberse a condiciones del sistema evaluado, como recursos inexistentes, identificadores inválidos o dependencias no satisfechas.

### 7. Generar evidencias

Al finalizar, QAIF consolida los resultados y produce reportes en Markdown y PDF. Estos documentos permiten revisar el detalle de cada endpoint, los tiempos de respuesta, los estados obtenidos y una conclusión general.

## Buenas prácticas

- Usar únicamente entornos controlados.
- Mantener trazabilidad entre requisitos, casos y resultados.
- Revisar los casos generados antes de ejecutar pruebas críticas.
- No publicar credenciales ni datos sensibles.
- Conservar reportes y registros como evidencia.
- Actualizar la documentación cuando cambie el flujo real.

## Limitaciones del prototipo

- No se implementa en sistemas productivos de entidades financieras.
- No procesa datos reales de clientes.
- No sustituye la revisión de un ingeniero QA.
- No entrena modelos propios desde cero.
- Su validación corresponde a un entorno académico TRL 5.
