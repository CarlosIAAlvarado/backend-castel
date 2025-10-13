from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.assignment import Assignment


class AssignmentRepository(ABC):
    """
    Interfaz para el repositorio de asignaciones cuenta-agente.

    Define las operaciones de acceso a datos para asignaciones.
    """

    @abstractmethod
    def create(self, assignment: Assignment) -> Assignment:
        """
        Crea una nueva asignacion de cuenta a agente.

        Args:
            assignment: Datos de la asignacion

        Returns:
            Assignment creado con ID
        """
        pass

    @abstractmethod
    def create_batch(self, assignments: List[Assignment]) -> List[Assignment]:
        """
        Crea multiples asignaciones en lote.

        Args:
            assignments: Lista de asignaciones

        Returns:
            Lista de Assignments creados
        """
        pass

    @abstractmethod
    def get_active_assignments(self) -> List[Assignment]:
        """
        Obtiene todas las asignaciones activas del sistema.

        Returns:
            Lista de todas las asignaciones activas
        """
        pass

    @abstractmethod
    def get_active_by_agent(self, agent_id: str) -> List[Assignment]:
        """
        Obtiene todas las asignaciones activas de un agente.

        Args:
            agent_id: ID del agente

        Returns:
            Lista de asignaciones activas
        """
        pass

    @abstractmethod
    def get_active_by_account(self, account_id: str) -> Optional[Assignment]:
        """
        Obtiene la asignacion activa de una cuenta.

        Args:
            account_id: ID de la cuenta

        Returns:
            Assignment activo o None
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[Assignment]:
        """
        Obtiene todas las asignaciones de una fecha especifica.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de asignaciones
        """
        pass

    @abstractmethod
    def deactivate(self, assignment_id: str) -> Assignment:
        """
        Desactiva una asignacion (marca is_active=False y establece unassigned_at).

        Args:
            assignment_id: ID de la asignacion

        Returns:
            Assignment desactivado
        """
        pass

    @abstractmethod
    def transfer_accounts(self, from_agent: str, to_agent: str) -> int:
        """
        Transfiere todas las cuentas activas de un agente a otro.

        Args:
            from_agent: ID del agente origen
            to_agent: ID del agente destino

        Returns:
            Numero de cuentas transferidas
        """
        pass
