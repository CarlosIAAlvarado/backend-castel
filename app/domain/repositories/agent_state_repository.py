from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.agent_state import AgentState


class AgentStateRepository(ABC):
    """
    Interfaz para el repositorio de estados de agentes.

    Define las operaciones de acceso a datos para el estado diario
    de los agentes en Casterly Rock.
    """

    @abstractmethod
    def create(self, agent_state: AgentState) -> AgentState:
        """
        Crea un nuevo registro de estado de agente.

        Args:
            agent_state: Datos del estado

        Returns:
            AgentState creado con ID
        """
        pass

    @abstractmethod
    def create_batch(self, agent_states: List[AgentState]) -> List[AgentState]:
        """
        Crea multiples registros de estado en lote.

        Args:
            agent_states: Lista de estados

        Returns:
            Lista de AgentStates creados
        """
        pass

    @abstractmethod
    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> Optional[AgentState]:
        """
        Obtiene el estado de un agente en una fecha especifica.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

        Returns:
            AgentState o None si no existe
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[AgentState]:
        """
        Obtiene todos los estados de una fecha especifica.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de estados de todos los agentes
        """
        pass

    @abstractmethod
    def get_latest_by_agent(self, agent_id: str) -> Optional[AgentState]:
        """
        Obtiene el estado mas reciente de un agente.

        Args:
            agent_id: ID del agente

        Returns:
            AgentState mas reciente o None
        """
        pass

    @abstractmethod
    def get_history_by_agent(self, agent_id: str, days: int = 7) -> List[AgentState]:
        """
        Obtiene el historial de estados de un agente.

        Args:
            agent_id: ID del agente
            days: Numero de dias hacia atras

        Returns:
            Lista de estados ordenados por fecha descendente
        """
        pass

    @abstractmethod
    def update_state(self, agent_id: str, target_date: date, updates: dict) -> AgentState:
        """
        Actualiza campos de un estado existente.

        Args:
            agent_id: ID del agente
            target_date: Fecha del estado
            updates: Diccionario con campos a actualizar

        Returns:
            AgentState actualizado
        """
        pass

    @abstractmethod
    def get_agents_in_fall(self, target_date: date, min_fall_days: int = 3) -> List[AgentState]:
        """
        Obtiene agentes en caida consecutiva por N dias o mas.

        Args:
            target_date: Fecha objetivo
            min_fall_days: Minimo de dias consecutivos en caida

        Returns:
            Lista de agentes que cumplen el criterio
        """
        pass
