from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.config.database import database_manager
from app.presentation.routes import simulation_routes, reports_routes, simulations_routes, client_accounts_routes


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
