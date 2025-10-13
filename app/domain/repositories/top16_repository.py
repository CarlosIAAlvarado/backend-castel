from abc import ABC, abstractmethod
from typing import List
from datetime import date
from app.domain.entities.top16_day import Top16Day


class Top16Repository(ABC):
    """
    Interfaz para el repositorio de ranking Top 16 diario.

    Define las operaciones de acceso a datos para el ranking de agentes.
    """

    @abstractmethod
    def create_batch(self, top16_list: List[Top16Day]) -> List[Top16Day]:
        """
        Crea multiples registros de Top 16 en una fecha.

        Args:
            top16_list: Lista de Top16Day a crear

        Returns:
            Lista de Top16Day creados con IDs
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[Top16Day]:
        """
        Obtiene el ranking Top 16 de una fecha especifica.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de Top16Day ordenada por rank
        """
        pass

    @abstractmethod
    def get_in_casterly_by_date(self, target_date: date) -> List[Top16Day]:
        """
        Obtiene solo los agentes que estan dentro de Casterly Rock en una fecha.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de Top16Day donde is_in_casterly=True
        """
        pass

    @abstractmethod
    def get_by_agent_range(self, agent_id: str, start_date: date, end_date: date) -> List[Top16Day]:
        """
        Obtiene el historial de ranking de un agente en un periodo.

        Args:
            agent_id: ID del agente
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Lista de Top16Day del agente
        """
        pass
