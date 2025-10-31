from typing import List, Dict, Any, Optional
from datetime import date
from app.domain.repositories.movement_repository import MovementRepository


class MovementQueryService:
    """
    Servicio especializado en consultas de movimientos.

    Responsabilidad unica: Obtener movimientos de la base de datos.
    Cumple con Single Responsibility Principle (SRP).
    """

    def __init__(self, movement_repo: MovementRepository):
        """
        Constructor con inyeccion de dependencias.

        Args:
            movement_repo: Repositorio de movimientos
        """
        self.movement_repo = movement_repo

    def get_movements_by_date_range(
        self,
        start_date: date,
        end_date: date,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene movimientos filtrados por rango de fechas y agente.

        Args:
            start_date: Fecha inicial del rango
            end_date: Fecha final del rango
            agent_id: ID del agente (opcional). Si no se especifica, trae todos

        Returns:
            Lista de movimientos que cumplen los criterios
        """
        from app.config.database import database_manager

        collection = database_manager.get_collection("movements")

        query = {
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }

        if agent_id:
            query["agent_id"] = agent_id

        movements = list(collection.find(query))

        return movements
