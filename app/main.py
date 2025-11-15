from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.config.database import database_manager
from app.presentation.routes import simulation_routes, reports_routes, simulations_routes, client_accounts_routes
# rebalancing_routes ELIMINADO - FLUJO REAL: No hay rebalanceos programados
from app.infrastructure.config.logging_config import setup_logging
from app.infrastructure.config.console_logger import ConsoleLogger as log
import os

logger = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_to_file=True
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.success("Iniciando aplicación FastAPI", context="[STARTUP]")
    logger.info(f"Configuración - Database: {settings.database_name}")
    logger.info(f"Configuración - CORS Origins: {settings.cors_origins}")
    database_manager.connect()
    log.success("Base de datos conectada exitosamente", context="[DATABASE]")
    yield
    log.info("Cerrando conexión a base de datos", context="[SHUTDOWN]")
    database_manager.disconnect()
    log.success("Aplicación finalizada correctamente", context="[SHUTDOWN]")


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

if settings.cors_origins == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in settings.cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation_routes.router)
app.include_router(reports_routes.router)
app.include_router(simulations_routes.router)
app.include_router(client_accounts_routes.router)
# rebalancing_routes.router ELIMINADO - FLUJO REAL: No hay endpoints de rebalanceo


@app.get("/")
def read_root() -> dict:
    return {
        "message": settings.api_title,
        "version": settings.api_version,
        "status": "running"
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "healthy"}


@app.get("/database/test")
def test_database_connection() -> dict:
    try:
        db = database_manager.get_database()
        collections = db.list_collection_names()
        logger.info(f"Test de conexión exitoso - {len(collections)} colecciones encontradas")
        return {
            "status": "connected",
            "database": settings.database_name,
            "collections": collections
        }
    except Exception as e:
        logger.error(f"Error en test de conexión: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
