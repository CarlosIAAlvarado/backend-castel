from abc import ABC, abstractmethod
from typing import List
from datetime import date
from app.domain.entities.rank_change import RankChange


class RankChangeRepository(ABC):
    """
    Interfaz para el repositorio de cambios de ranking dentro del Top 16.

    Define las operaciones de acceso a datos para el historial de movimientos
    de posición de agentes DENTRO del Top 16.

    A diferencia de RotationLogRepository (entradas/salidas), este repositorio
    maneja cambios de posición internos (ej: del rank 1 al rank 3).
    """

    @abstractmethod
    def create(self, rank_change: RankChange) -> RankChange:
        """
        Registra un nuevo cambio de ranking.

        Args:
            rank_change: Datos del cambio de ranking

        Returns:
            RankChange: Cambio creado con ID asignado

        Raises:
            ValueError: Si rank_change es None o tiene datos inválidos
            DatabaseError: Si hay error de conexión a base de datos
        """
        pass

    @abstractmethod
    def get_all(self) -> List[RankChange]:
        """
        Obtiene todo el historial de cambios de ranking.

        Returns:
            List[RankChange]: Lista completa ordenada por fecha descendente
        """
        pass

    @abstractmethod
    def get_by_date_range(self, start_date: date, end_date: date) -> List[RankChange]:
        """
        Obtiene cambios de ranking en un rango de fechas.

        Args:
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            List[RankChange]: Lista de cambios en el periodo
        """
        pass

    @abstractmethod
    def get_by_agent(self, agent_id: str) -> List[RankChange]:
        """
        Obtiene el historial de cambios de ranking de un agente específico.

        Args:
            agent_id: ID del agente

        Returns:
            List[RankChange]: Lista de cambios de ese agente
        """
        pass

    @abstractmethod
    def get_significant_changes(self, start_date: date, end_date: date, min_rank_change: int = 3) -> List[RankChange]:
        """
        Obtiene cambios significativos de ranking (>= N posiciones).

        Args:
            start_date: Fecha inicial
            end_date: Fecha final
            min_rank_change: Mínimo cambio de posiciones (default: 3)

        Returns:
            List[RankChange]: Lista de cambios significativos
        """
        pass
