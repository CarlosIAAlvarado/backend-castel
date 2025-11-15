"""
Punto de entrada principal para el servidor FastAPI
Ejecutar con: python main.py
"""

import sys
# FORZAR A PYTHON A NO USAR ARCHIVOS .pyc
sys.dont_write_bytecode = True

if __name__ == "__main__":
    import uvicorn
    from app.config.settings import settings
    from app.infrastructure.config.console_logger import ConsoleLogger as log

    log.separator("=", 80)
    log.success("Iniciando servidor FastAPI", context="[STARTUP]")
    log.info(f"Host: {settings.host}", context="[CONFIG]")
    log.info(f"Puerto: {settings.port}", context="[CONFIG]")
    log.info(f"Base de datos: {settings.database_name}", context="[CONFIG]")
    log.info(f"Modo reload: {settings.reload}", context="[CONFIG]")
    log.info(f"Documentación API: http://{settings.host}:{settings.port}/docs", context="[CONFIG]")
    log.separator("=", 80)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False  # DESACTIVADO TEMPORALMENTE PARA DEBUGGING
    )
