from abc import ABC, abstractmethod
from app.domain.entities.agent_state import AgentState


class ExitRule(ABC):
    """
    Abstraccion para reglas de salida de agentes.

    Implementa Strategy Pattern para permitir diferentes estrategias
    de evaluacion de reglas de negocio sin modificar el codigo existente.

    Cumple con Open/Closed Principle (OCP):
    - Abierto para extension: Se pueden crear nuevas reglas
    - Cerrado para modificacion: No se modifica el codigo existente
    """

    @abstractmethod
    def should_exit(self, agent_state: AgentState) -> bool:
        """
        Evalua si un agente debe salir de Casterly Rock.

        Args:
            agent_state: Estado actual del agente

        Returns:
            True si el agente debe salir, False en caso contrario
        """
        pass

    @abstractmethod
    def get_reason(self) -> str:
        """
        Retorna la razon de salida.

        Returns:
            Descripcion de la regla que se aplico
        """
        pass
