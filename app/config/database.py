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
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise

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
