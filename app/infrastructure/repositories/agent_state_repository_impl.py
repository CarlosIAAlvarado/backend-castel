from typing import List, Optional
from datetime import date, datetime, timedelta
from bson import ObjectId
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.domain.entities.agent_state import AgentState
from app.config.database import database_manager


class AgentStateRepositoryImpl(AgentStateRepository):
    """
    Implementacion concreta del repositorio de estados de agentes usando MongoDB.
    """

    def __init__(self):
        self.collection_name = "agent_states"

    def create(self, agent_state: AgentState) -> AgentState:
        """Crea un nuevo registro de estado de agente."""
        collection = database_manager.get_collection(self.collection_name)

        doc = agent_state.model_dump(by_alias=True, exclude_none=True)
        if "_id" in doc:
            del doc["_id"]
        if "id" in doc:
            del doc["id"]
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].date().isoformat()
        elif isinstance(doc.get("date"), date):
            doc["date"] = doc["date"].isoformat()
        if isinstance(doc.get("entry_date"), datetime):
            doc["entry_date"] = doc["entry_date"].date().isoformat()
        elif isinstance(doc.get("entry_date"), date):
            doc["entry_date"] = doc["entry_date"].isoformat()
        doc["createdAt"] = datetime.now()
        doc["updatedAt"] = datetime.now()

        result = collection.insert_one(doc)
        agent_state.id = str(result.inserted_id)

        return agent_state

    def create_batch(self, agent_states: List[AgentState]) -> List[AgentState]:
        """Crea multiples registros de estado en lote."""
        collection = database_manager.get_collection(self.collection_name)

        docs = []
        for agent_state in agent_states:
            doc = agent_state.model_dump(by_alias=True, exclude_none=True)
            if "_id" in doc:
                del doc["_id"]
            if "id" in doc:
                del doc["id"]
            if isinstance(doc.get("date"), datetime):
                doc["date"] = doc["date"].date().isoformat()
            elif isinstance(doc.get("date"), date):
                doc["date"] = doc["date"].isoformat()
            if isinstance(doc.get("entry_date"), datetime):
                doc["entry_date"] = doc["entry_date"].date().isoformat()
            elif isinstance(doc.get("entry_date"), date):
                doc["entry_date"] = doc["entry_date"].isoformat()
            doc["createdAt"] = datetime.now()
            doc["updatedAt"] = datetime.now()
            docs.append(doc)

        if docs:
            result = collection.insert_many(docs)
            for i, inserted_id in enumerate(result.inserted_ids):
                agent_states[i].id = str(inserted_id)

        return agent_states

    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> Optional[AgentState]:
        """Obtiene el estado de un agente en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        doc = collection.find_one({
            "agent_id": agent_id,
            "date": target_date.isoformat()
        })

        if doc:
            return self._doc_to_entity(doc)

        return None

    def get_by_date(self, target_date: date) -> List[AgentState]:
        """Obtiene todos los estados de una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({"date": target_date.isoformat()})

        return [self._doc_to_entity(doc) for doc in docs]

    def get_latest_by_agent(self, agent_id: str) -> Optional[AgentState]:
        """Obtiene el estado mas reciente de un agente."""
        collection = database_manager.get_collection(self.collection_name)

        doc = collection.find_one(
            {"agent_id": agent_id},
            sort=[("date", -1)]
        )

        if doc:
            return self._doc_to_entity(doc)

        return None

    def get_latest_by_agents_batch(self, agent_ids: List[str]) -> dict:
        """
        Obtiene los estados mas recientes de multiples agentes en una sola consulta.
        Retorna un diccionario {agent_id: AgentState}.
        """
        collection = database_manager.get_collection(self.collection_name)

        pipeline = [
            {"$match": {"agent_id": {"$in": agent_ids}}},
            {"$sort": {"date": -1}},
            {"$group": {
                "_id": "$agent_id",
                "latest_doc": {"$first": "$$ROOT"}
            }}
        ]

        results = collection.aggregate(pipeline)

        states_map = {}
        for result in results:
            agent_id = result["_id"]
            doc = result["latest_doc"]
            states_map[agent_id] = self._doc_to_entity(doc)

        return states_map

    def get_history_by_agent(self, agent_id: str, days: int = 7) -> List[AgentState]:
        """Obtiene el historial de estados de un agente."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find(
            {"agent_id": agent_id}
        ).sort("date", -1).limit(days)

        return [self._doc_to_entity(doc) for doc in docs]

    def update_state(self, agent_id: str, target_date: date, updates: dict) -> AgentState:
        """Actualiza campos de un estado existente."""
        collection = database_manager.get_collection(self.collection_name)

        updates["updatedAt"] = datetime.now()

        collection.update_one(
            {
                "agent_id": agent_id,
                "date": target_date.isoformat()
            },
            {"$set": updates}
        )

        doc = collection.find_one({
            "agent_id": agent_id,
            "date": target_date.isoformat()
        })

        return self._doc_to_entity(doc)

    def get_agents_in_fall(self, target_date: date, min_fall_days: int = 3) -> List[AgentState]:
        """Obtiene agentes en caida consecutiva por N dias o mas."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "date": target_date.isoformat(),
            "fall_days": {"$gte": min_fall_days},
            "is_in_casterly": True
        })

        return [self._doc_to_entity(doc) for doc in docs]

    def _doc_to_entity(self, doc: dict) -> AgentState:
        """Convierte un documento de MongoDB a entidad AgentState."""
        return AgentState(
            _id=str(doc["_id"]),
            date=datetime.fromisoformat(doc["date"]).date() if isinstance(doc["date"], str) else doc["date"],
            agent_id=doc["agent_id"],
            state=doc["state"],
            roi_day=doc["roi_day"],
            pnl_day=doc["pnl_day"],
            balance_base=doc["balance_base"],
            fall_days=doc.get("fall_days", 0),
            is_in_casterly=doc.get("is_in_casterly", True),
            roi_since_entry=doc.get("roi_since_entry"),
            entry_date=datetime.fromisoformat(doc["entry_date"]).date() if doc.get("entry_date") and isinstance(doc["entry_date"], str) else doc.get("entry_date"),
            createdAt=doc.get("createdAt"),
            updatedAt=doc.get("updatedAt")
        )
