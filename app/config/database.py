from pymongo import MongoClient
from pymongo.database import Database
from typing import Optional
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    client: Optional[MongoClient] = None
    db: Optional[Database] = None

    @classmethod
    def connect(cls) -> None:
        try:
            cls.client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=30000,
                connectTimeoutMS=10000
            )
            cls.db = cls.client[settings.database_name]
            cls.client.admin.command("ping")
            logger.info(f"Successfully connected to MongoDB database: {settings.database_name}")

            cls.cleanup_orphaned_simulation_status()
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise

    @classmethod
    def cleanup_orphaned_simulation_status(cls) -> None:
        """
        Limpia estados de simulacion huerfanos al reiniciar el backend.

        Marca como completada cualquier simulacion que quedo en estado
        is_running=true debido a un reinicio del servidor.
        """
        try:
            if cls.db is None:
                return

            status_collection = cls.db["simulation_status"]
            result = status_collection.find_one({"status_id": "current"})

            if result and result.get("is_running", False):
                from datetime import datetime
                logger.warning(
                    f"Estado de simulacion huerfano detectado: "
                    f"dia {result.get('current_day', 0)}/{result.get('total_days', 0)}. "
                    f"Marcando como completada..."
                )

                status_collection.update_one(
                    {"status_id": "current"},
                    {
                        "$set": {
                            "is_running": False,
                            "message": "Simulacion interrumpida por reinicio del servidor",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.info("Estado de simulacion huerfano limpiado exitosamente")
        except Exception as e:
            logger.error(f"Error al limpiar estado de simulacion huerfano: {e}")

    @classmethod
    def disconnect(cls) -> None:
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")

    @classmethod
    def get_database(cls) -> Database:
        if cls.db is None:
            raise Exception("Database not connected. Call connect() first.")
        return cls.db

    @classmethod
    def get_collection(cls, collection_name: str):
        db = cls.get_database()
        return db[collection_name]


database_manager = DatabaseManager()
