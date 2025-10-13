from abc import ABC, abstractmethod
from typing import List
from datetime import date
from app.domain.entities.rotation_log import RotationLog


class RotationLogRepository(ABC):
    """
    Interfaz para el repositorio de historial de rotaciones.

    Define las operaciones de acceso a datos para el log de rotaciones.
    """

    @abstractmethod
    def create(self, rotation: RotationLog) -> RotationLog:
        """
        Registra una nueva rotacion de agente.

        Args:
            rotation: Datos de la rotacion

        Returns:
            RotationLog creado con ID
        """
        pass

    @abstractmethod
    def get_all(self) -> List[RotationLog]:
        """
        Obtiene todo el historial de rotaciones.

        Returns:
            Lista completa de rotaciones ordenadas por fecha
        """
        pass

    @abstractmethod
    def get_by_date_range(self, start_date: date, end_date: date) -> List[RotationLog]:
        """
        Obtiene rotaciones en un rango de fechas.

        Args:
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Lista de rotaciones en el periodo
        """
        pass

    @abstractmethod
    def get_by_agent(self, agent_id: str) -> List[RotationLog]:
        """
        Obtiene el historial de rotaciones de un agente (entradas y salidas).

        Args:
            agent_id: ID del agente

        Returns:
            Lista de rotaciones donde el agente participo
        """
        pass

    @abstractmethod
    def count_rotations_by_period(self, start_date: date, end_date: date) -> int:
        """
        Cuenta el numero total de rotaciones en un periodo.

        Args:
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Numero de rotaciones
        """
        pass
