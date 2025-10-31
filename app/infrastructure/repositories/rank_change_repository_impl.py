from typing import List
from datetime import date, datetime
from app.domain.repositories.rank_change_repository import RankChangeRepository
from app.domain.entities.rank_change import RankChange
from app.config.database import database_manager


class RankChangeRepositoryImpl(RankChangeRepository):
    """
    Implementación concreta del repositorio de cambios de ranking usando MongoDB.
    """

    def __init__(self):
        self.collection_name = "rank_changes"

    def create(self, rank_change: RankChange) -> RankChange:
        """Registra un nuevo cambio de ranking."""
        collection = database_manager.get_collection(self.collection_name)

        doc = rank_change.model_dump(by_alias=True, exclude_none=True)
        if "_id" in doc:
            del doc["_id"]
        if "id" in doc:
            del doc["id"]

        # Convertir datetime a string ISO
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].isoformat()
        elif isinstance(doc.get("date"), date):
            doc["date"] = doc["date"].isoformat()

        doc["created_at"] = datetime.now()

        result = collection.insert_one(doc)
        rank_change.id = str(result.inserted_id)

        return rank_change

    def get_all(self) -> List[RankChange]:
        """Obtiene todo el historial de cambios de ranking."""
        collection = database_manager.get_collection(self.collection_name)
        docs = collection.find().sort("date", -1)
        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_date_range(self, start_date: date, end_date: date) -> List[RankChange]:
        """Obtiene cambios de ranking en un rango de fechas."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }).sort("date", -1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_agent(self, agent_id: str) -> List[RankChange]:
        """Obtiene el historial de cambios de ranking de un agente específico."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "agent_id": agent_id
        }).sort("date", -1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_significant_changes(
        self,
        start_date: date,
        end_date: date,
        min_rank_change: int = 3
    ) -> List[RankChange]:
        """Obtiene cambios significativos de ranking (>= N posiciones)."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            },
            "$expr": {
                "$gte": [
                    {"$abs": "$rank_change"},
                    min_rank_change
                ]
            }
        }).sort("date", -1)

        return [self._doc_to_entity(doc) for doc in docs]

    def _doc_to_entity(self, doc: dict) -> RankChange:
        """Convierte un documento de MongoDB a entidad RankChange."""
        # Convertir string ISO a datetime si es necesario
        date_value = doc["date"]
        if isinstance(date_value, str):
            date_value = datetime.fromisoformat(date_value)

        return RankChange(
            _id=str(doc["_id"]),
            date=date_value,
            agent_id=doc["agent_id"],
            previous_rank=doc["previous_rank"],
            current_rank=doc["current_rank"],
            rank_change=doc["rank_change"],
            previous_roi=doc["previous_roi"],
            current_roi=doc["current_roi"],
            roi_change=doc["roi_change"],
            is_in_casterly=doc["is_in_casterly"],
            created_at=doc.get("created_at")
        )
