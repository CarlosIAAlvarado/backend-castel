"""
Punto de entrada principal para el servidor FastAPI
Ejecutar con: python main.py
"""

if __name__ == "__main__":
    import uvicorn
    from app.config.settings import settings

    print(f"[INICIO] Iniciando servidor FastAPI...")
    print(f"[INFO] Host: {settings.host}")
    print(f"[INFO] Puerto: {settings.port}")
    print(f"[INFO] Base de datos: {settings.database_name}")
    print(f"[INFO] Modo reload: {settings.reload}")
    print(f"[INFO] Accede a http://{settings.host}:{settings.port}/docs para ver la documentacion API")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
