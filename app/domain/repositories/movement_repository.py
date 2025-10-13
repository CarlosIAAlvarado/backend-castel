from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.movement import Movement


class MovementRepository(ABC):
    """
    Interfaz para el repositorio de movimientos (operaciones).

    Define las operaciones de acceso a datos para movimientos.
    """

    @abstractmethod
    def get_by_date_range(self, start_date: date, end_date: date, agent_id: Optional[str] = None) -> List[Movement]:
        """
        Obtiene movimientos en un rango de fechas, opcionalmente filtrados por agente.

        Args:
            start_date: Fecha inicial
            end_date: Fecha final
            agent_id: ID del agente (opcional)

        Returns:
            Lista de movimientos
        """
        pass

    @abstractmethod
    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> List[Movement]:
        """
        Obtiene todos los movimientos de un agente en una fecha especifica.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

        Returns:
            Lista de movimientos
        """
        pass

    @abstractmethod
    def count_by_agent_and_period(self, agent_id: str, start_date: date, end_date: date) -> int:
        """
        Cuenta el numero de operaciones de un agente en un periodo.

        Args:
            agent_id: ID del agente
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Numero de operaciones
        """
        pass
