from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.agent_day import AgentDay


class AgentDayRepository(ABC):
    """
    Interfaz para el repositorio de datos diarios de agentes (KPIs).

    Define las operaciones de acceso a datos para metricas diarias.
    """

    @abstractmethod
    def create(self, agent_day: AgentDay) -> AgentDay:
        """
        Crea un nuevo registro de KPIs diarios.

        Args:
            agent_day: Datos del agente del dia

        Returns:
            AgentDay creado con ID
        """
        pass

    @abstractmethod
    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> Optional[AgentDay]:
        """
        Obtiene los KPIs de un agente en una fecha especifica.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

        Returns:
            AgentDay o None si no existe
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[AgentDay]:
        """
        Obtiene los KPIs de todos los agentes en una fecha especifica.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de AgentDay
        """
        pass

    @abstractmethod
    def get_by_agent_range(self, agent_id: str, start_date: date, end_date: date) -> List[AgentDay]:
        """
        Obtiene los KPIs de un agente en un rango de fechas.

        Args:
            agent_id: ID del agente
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Lista de AgentDay ordenada por fecha
        """
        pass

    @abstractmethod
    def update(self, agent_day: AgentDay) -> AgentDay:
        """
        Actualiza un registro de KPIs diarios.

        Args:
            agent_day: Datos actualizados

        Returns:
            AgentDay actualizado
        """
        pass
