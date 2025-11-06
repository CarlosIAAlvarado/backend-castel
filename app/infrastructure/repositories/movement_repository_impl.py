from typing import List, Optional
from datetime import date
from app.domain.repositories.movement_repository import MovementRepository
from app.domain.entities.movement import Movement
from app.config.database import database_manager
from app.infrastructure.utils.data_normalizer import normalizer


class MovementRepositoryImpl(MovementRepository):
    """
    Implementacion concreta del repositorio de movimientos usando MongoDB.
    """

    def __init__(self):
        # Usar coleccion real mov07.10 con datos de produccion
        self.collection_name = "mov07.10"

    def get_by_date_range(self, start_date: date, end_date: date, agent_id: Optional[str] = None) -> List[Movement]:
        """Obtiene movimientos en un rango de fechas, opcionalmente filtrados por agente."""
        collection = database_manager.get_collection(self.collection_name)

        # Convertir dates a formato ISO string para comparar con createdAt
        start_datetime = f"{start_date.isoformat()}T00:00:00.000Z"
        end_datetime = f"{end_date.isoformat()}T23:59:59.999Z"

        # Usar createdAt para filtrar por fecha (estructura real de mov07.10)
        query = {
            "createdAt": {
                "$gte": start_datetime,
                "$lte": end_datetime
            }
        }

        # Usar 'agente_id' (estructura real de mov07.10)
        if agent_id:
            query["agente_id"] = agent_id

        docs = list(collection.find(query))

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> List[Movement]:
        """Obtiene todos los movimientos de un agente en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        # Buscar por agente_id (estructura real) y rango de fecha en createdAt
        start_datetime = f"{target_date.isoformat()}T00:00:00.000Z"
        end_datetime = f"{target_date.isoformat()}T23:59:59.999Z"

        docs = list(collection.find({
            "agente_id": agent_id,
            "createdAt": {
                "$gte": start_datetime,
                "$lte": end_datetime
            }
        }))

        return [self._doc_to_entity(doc) for doc in docs]

    def count_by_agent_and_period(self, agent_id: str, start_date: date, end_date: date) -> int:
        """Cuenta el numero de operaciones de un agente en un periodo."""
        movements = self.get_by_date_range(start_date, end_date, agent_id)
        return len(movements)

    def _doc_to_entity(self, doc: dict) -> Movement:
        """Convierte un documento de MongoDB a entidad Movement."""
        # Soportar ambos formatos: closedPnl (original) y closed_pnl (migrado)
        closed_pnl = doc.get("closed_pnl") if "closed_pnl" in doc else doc.get("closedPnl")

        return Movement(
            _id=str(doc["_id"]),
            user=doc.get("user", doc.get("account_id", "")),
            userId=doc.get("userId", ""),
            createdTime=doc.get("createdTime", doc.get("created_at", "")),
            updatedTime=doc.get("updatedTime", doc.get("updated_at", "")),
            symbol=normalizer.normalize_symbol(doc.get("symbol")),
            side=doc.get("side", ""),
            leverage=doc.get("leverage", 0),
            qty=doc.get("qty", ""),
            closedPnl=closed_pnl if isinstance(closed_pnl, (int, float)) else normalizer.normalize_pnl(closed_pnl),
            avgEntryPrice=doc.get("avgEntryPrice", ""),
            avgExitPrice=doc.get("avgExitPrice", ""),
            createdAt=normalizer.normalize_datetime(doc.get("createdAt")),
            updatedAt=normalizer.normalize_datetime(doc.get("updatedAt"))
        )
