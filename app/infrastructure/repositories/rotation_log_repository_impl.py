from typing import List
from datetime import date, datetime
from app.domain.repositories.rotation_log_repository import RotationLogRepository
from app.domain.entities.rotation_log import RotationLog
from app.config.database import database_manager


class RotationLogRepositoryImpl(RotationLogRepository):
    """
    Implementacion concreta del repositorio de historial de rotaciones usando MongoDB.
    """

    def __init__(self):
        self.collection_name = "rotation_log"

    def create(self, rotation: RotationLog) -> RotationLog:
        """Registra una nueva rotacion de agente."""
        collection = database_manager.get_collection(self.collection_name)

        doc = rotation.model_dump(by_alias=True, exclude_none=True)
        if "_id" in doc:
            del doc["_id"]
        if "id" in doc:
            del doc["id"]
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].isoformat()
        elif isinstance(doc.get("date"), date):
            doc["date"] = doc["date"].isoformat()
        doc["createdAt"] = datetime.now()

        result = collection.insert_one(doc)
        rotation.id = str(result.inserted_id)

        return rotation

    def get_all(self) -> List[RotationLog]:
        """Obtiene todo el historial de rotaciones."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find().sort("date", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_date_range(self, start_date: date, end_date: date) -> List[RotationLog]:
        """Obtiene rotaciones en un rango de fechas."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }).sort("date", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_agent(self, agent_id: str) -> List[RotationLog]:
        """Obtiene el historial de rotaciones de un agente."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "$or": [
                {"agent_out": agent_id},
                {"agent_in": agent_id}
            ]
        }).sort("date", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def count_rotations_by_period(self, start_date: date, end_date: date) -> int:
        """Cuenta el numero total de rotaciones en un periodo."""
        collection = database_manager.get_collection(self.collection_name)

        count = collection.count_documents({
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        })

        return count

    def _doc_to_entity(self, doc: dict) -> RotationLog:
        """Convierte un documento de MongoDB a entidad RotationLog."""
        return RotationLog(
            _id=str(doc["_id"]),
            date=datetime.fromisoformat(doc["date"]) if isinstance(doc["date"], str) else doc["date"],
            agent_out=doc["agent_out"],
            agent_in=doc["agent_in"],
            reason=doc["reason"],
            roi_7d_out=doc["roi_7d_out"],
            roi_total_out=doc["roi_total_out"],
            roi_7d_in=doc["roi_7d_in"],
            n_accounts=doc["n_accounts"],
            total_aum=doc["total_aum"],
            createdAt=doc.get("createdAt")
        )
