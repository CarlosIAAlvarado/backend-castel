from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.config.database import database_manager
from app.presentation.api import exploration_routes
from app.presentation.routes import query_routes, simulation_routes, reports_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_manager.connect()
    yield
    database_manager.disconnect()


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exploration_routes.router)
app.include_router(query_routes.router)
app.include_router(simulation_routes.router)
app.include_router(reports_routes.router)


@app.get("/")
def read_root():
    return {
        "message": settings.api_title,
        "version": settings.api_version,
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/database/test")
def test_database_connection():
    try:
        db = database_manager.get_database()
        collections = db.list_collection_names()
        return {
            "status": "connected",
            "database": settings.database_name,
            "collections": collections
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
