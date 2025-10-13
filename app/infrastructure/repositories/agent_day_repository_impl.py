from typing import List, Optional
from datetime import date, datetime
from bson import ObjectId
from app.domain.repositories.agent_day_repository import AgentDayRepository
from app.domain.entities.agent_day import AgentDay
from app.config.database import database_manager


class AgentDayRepositoryImpl(AgentDayRepository):
    """
    Implementacion concreta del repositorio de AgentDay usando MongoDB.
    """

    def __init__(self):
        self.collection_name = "agent_day"

    def create(self, agent_day: AgentDay) -> AgentDay:
        """Crea un nuevo registro de KPIs diarios."""
        collection = database_manager.get_collection(self.collection_name)

        doc = agent_day.model_dump(by_alias=True, exclude={"_id"})
        doc["createdAt"] = datetime.now()
        doc["updatedAt"] = datetime.now()

        result = collection.insert_one(doc)
        agent_day.id = str(result.inserted_id)

        return agent_day

    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> Optional[AgentDay]:
        """Obtiene los KPIs de un agente en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        doc = collection.find_one({
            "agent_id": agent_id,
            "date": target_date.isoformat()
        })

        if doc:
            return self._doc_to_entity(doc)

        return None

    def get_by_date(self, target_date: date) -> List[AgentDay]:
        """Obtiene los KPIs de todos los agentes en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({"date": target_date.isoformat()})

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_agent_range(self, agent_id: str, start_date: date, end_date: date) -> List[AgentDay]:
        """Obtiene los KPIs de un agente en un rango de fechas."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "agent_id": agent_id,
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }).sort("date", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def update(self, agent_day: AgentDay) -> AgentDay:
        """Actualiza un registro de KPIs diarios."""
        collection = database_manager.get_collection(self.collection_name)

        doc = agent_day.model_dump(by_alias=True, exclude={"_id"})
        doc["updatedAt"] = datetime.now()

        collection.update_one(
            {"_id": ObjectId(agent_day.id)},
            {"$set": doc}
        )

        return agent_day

    def _doc_to_entity(self, doc: dict) -> AgentDay:
        """Convierte un documento de MongoDB a entidad AgentDay."""
        return AgentDay(
            _id=str(doc["_id"]),
            date=date.fromisoformat(doc["date"]),
            agent_id=doc["agent_id"],
            roi_1d=doc["roi_1d"],
            roi_7d=doc["roi_7d"],
            roi_30d=doc.get("roi_30d"),
            sharpe_ratio=doc.get("sharpe_ratio"),
            max_drawdown=doc.get("max_drawdown"),
            volatility=doc.get("volatility"),
            state=doc["state"],
            fall_days_consecutive=doc["fall_days_consecutive"],
            balance_total=doc["balance_total"],
            pnl_day=doc["pnl_day"],
            n_accounts=doc["n_accounts"],
            total_aum=doc["total_aum"],
            createdAt=doc.get("createdAt"),
            updatedAt=doc.get("updatedAt")
        )
