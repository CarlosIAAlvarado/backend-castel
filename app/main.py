from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.config.database import database_manager
from app.core.cache import cache_service
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

    # Inicializar cache Redis (falla graciosamente si Redis no está disponible)
    cache_service.connect()
    if cache_service.is_enabled():
        log.success("Cache Redis conectado exitosamente", context="[CACHE]")
    else:
        log.warning("Cache Redis no disponible - ejecutando sin cache", context="[CACHE]")

    yield

    log.info("Cerrando conexión a base de datos", context="[SHUTDOWN]")
    database_manager.disconnect()

    log.info("Cerrando conexión a cache Redis", context="[SHUTDOWN]")
    cache_service.disconnect()

    log.success("Aplicación finalizada correctamente", context="[SHUTDOWN]")


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

if settings.cors_origins == "*":
    origins = ["*"]
    allow_credentials = False  # SEGURIDAD: No permitir credentials con origen *
    logger.warning(
        "CORS configurado con origen '*' - credentials deshabilitados por seguridad. "
        "Para produccion, especifica dominios en CORS_ORIGINS"
    )
else:
    origins = [origin.strip() for origin in settings.cors_origins.split(",")]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PERFORMANCE: Add GZip compression for responses > 1KB
# Expected improvement: 60-80% reduction in response size for large payloads
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)

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


# NOTA: Para ejecutar el servidor, usa: python main.py (desde backend/)
# Este archivo define la aplicación FastAPI y es importado por uvicorn
# NO debe ejecutarse directamente
