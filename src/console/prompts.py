"""System prompts especializados para el router de la consola."""

CONSOLE_ROUTER_PROMPT = """\
Eres el router inteligente de MCP QA Automation.
Conviertes comandos (específicos o en lenguaje natural) en acciones JSON estructuradas.

HERRAMIENTAS DISPONIBLES:
1.  git_clone(url, branch?)          → Clonar repositorio
2.  git_analyze(repo_name)           → Analizar README con LLM
3.  git_status(repo_name)            → Ver estado del repo
4.  drive_extract(file_id)           → Extraer user stories desde Drive
5.  drive_list()                     → Listar archivos en Drive
6.  story_create(auto)               → Crear historias en Jira
7.  story_list()                     → Ver historias extraídas
8.  test_setup(repo_name)            → Instalar deps y levantar API
9.  test_run(repo_name, happy_only)  → Ejecutar happy path
10. test_suggest(repo_name)          → Sugerir pruebas adicionales
11. test_shutdown(repo_name)         → Detener servidor API
12. report_generate(pipeline_id?)    → Generar reporte MD + PDF
13. report_upload(issue_id)          → Subir reporte a Jira
14. report_show()                    → Ver último reporte
15. log_show(last_n?, event_type?)   → Ver audit trail
16. log_summary(pipeline_id?)        → Resumen de un pipeline
17. workspace_list()                 → Ver repos y reportes
18. workspace_clean(older_than_days) → Limpiar archivos viejos
19. model_switch(provider)           → Cambiar LLM (local|anthropic)
20. health_check()                   → Verificar servicios

REGLAS:
- Mapeo 1:1 → acción directa
- Múltiples pasos → lista ordenada de acciones
- Ambigüedad → pedir UNA clarificación específica
- Fuera de contexto → respuesta breve + comando más cercano
- NUNCA inventar tools inexistentes

RESPUESTA SIEMPRE EN JSON (sin markdown fences):
{
  "actions": [{"tool": "nombre_tool", "args": {}}],
  "clarification_needed": null,
  "message": "descripción breve"
}
"""

BANNER = r"""
 [bold cyan]
   ___      _    
  / _ \    / \   
  | | |   / _ \  
  | |_|  / ___ \ 
  \__\_\/_/   \_\
                                      
    A U T O M A T I O N   S Y S T E M
 [/bold cyan]

 [bold yellow]🌟 Bienvenido al Sistema Inteligente de Pruebas 🌟[/bold yellow]
 [bold green]👨‍💻 Creado por: Miguel Ángel Villabón y Diana Carolina Herrera - UNAD - PROYECTO DE GRADO [/bold green]

 [dim]────────────────────────────────────────────────────────────[/dim]
 [cyan]Modelo activo:[/cyan] {model}
 [cyan]Estado actual:[/cyan] {status}
 [dim]────────────────────────────────────────────────────────────[/dim]

 💡 Escribe [bold green]help[/bold green] para poder revisar todos los comandos disponibles.
"""

HELP_TEXT = r"""
 [dim]────────────────────────────────────────────────────────────[/dim]
 [bold]🔗 GIT[/bold]
    [cyan]git clone <url>[/cyan]           → Clonar y analizar repositorio
    [cyan]git analyze <repo>[/cyan]        → Analizar README y estructura
    [cyan]git status <repo>[/cyan]         → Ver estado del repo

 [bold]📄 DRIVE & USER STORIES[/bold]
    [cyan]extract <file_id>[/cyan]         → Extraer historias desde Drive
    [cyan]extract --list[/cyan]            → Listar archivos en Drive
    [cyan]story create [--auto][/cyan]     → Crear historias en Jira
    [cyan]story list[/cyan]                → Ver historias extraídas

 [bold]🧪 API TESTING[/bold]
    [cyan]test setup <repo>[/cyan]         → Obtener instrucciones para levantar API
    [cyan]test run <repo> [base_url=..][/cyan] → Ejecutar happy path (autogenera payloads JSON)
    [cyan]test shutdown <repo>[/cyan]      → Detener servidor API (si aplica)

 [bold]📊 REPORTES[/bold]
    [cyan]report generate[/cyan]           → Generar reporte MD + PDF
    [cyan]report upload <issue>[/cyan]     → Subir reporte a Jira
    [cyan]report show[/cyan]               → Ver último reporte generado

 [bold]🗂️ WORKSPACE & LOG[/bold]
    [cyan]log show [--last N][/cyan]       → Ver audit trail
    [cyan]log summary [--id X][/cyan]      → Resumen de un pipeline
    [cyan]workspace list[/cyan]            → Ver repos y reportes
    [cyan]workspace clean[/cyan]           → Limpiar archivos viejos

 [bold]⚙️ SISTEMA[/bold]
    [cyan]model switch <provider>[/cyan] → Cambiar modelo LLM
    [cyan]health[/cyan]                    → Verificar servicios
    [cyan]help[/cyan]                      → Esta pantalla
    [cyan]exit[/cyan]                      → Salir
 [dim]────────────────────────────────────────────────────────────[/dim]
"""
