from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.assignment import Assignment


class AssignmentReadOps(ABC):
    """
    Interfaz segregada para operaciones de LECTURA de asignaciones.

    Cumple con ISP (Interface Segregation Principle):
    - Clientes que solo leen no dependen de metodos de escritura
    - Servicios de consulta/reporte solo necesitan esta interfaz
    - Permite permisos mas granulares (ej: usuario readonly)

    Esta interfaz define solo operaciones de consulta que NO modifican datos.
    """

    @abstractmethod
    def get_active_assignments(self) -> List[Assignment]:
        """
        Obtiene todas las asignaciones activas del sistema.

        Pre-condiciones:
            - Ninguna

        Post-condiciones:
            - Retorna lista de asignaciones con is_active=True
            - Retorna lista vacia si no hay asignaciones activas
            - No modifica la base de datos

        Returns:
            List[Assignment]: Lista de asignaciones activas

        Raises:
            DatabaseError: Si hay error de conexion

        Example:
            >>> active = repo.get_active_assignments()
            >>> print(f"Total cuentas activas: {len(active)}")
        """
        pass

    @abstractmethod
    def get_active_by_agent(self, agent_id: str) -> List[Assignment]:
        """
        Obtiene todas las asignaciones activas de un agente.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio

        Post-condiciones:
            - Retorna lista de asignaciones activas de ese agente
            - Retorna lista vacia si el agente no tiene asignaciones
            - No modifica la base de datos

        Args:
            agent_id: ID del agente

        Returns:
            List[Assignment]: Lista de asignaciones activas

        Raises:
            ValueError: Si agent_id es None o vacio
            DatabaseError: Si hay error de conexion

        Example:
            >>> assignments = repo.get_active_by_agent("futures-001")
            >>> total_aum = sum(a.balance for a in assignments)
            >>> print(f"AUM total: ${total_aum}")
        """
        pass

    @abstractmethod
    def get_active_by_account(self, account_id: str) -> Optional[Assignment]:
        """
        Obtiene la asignacion activa de una cuenta.

        Pre-condiciones:
            - account_id no debe ser None ni vacio

        Post-condiciones:
            - Retorna la asignacion activa si existe
            - Retorna None si la cuenta no tiene asignacion activa
            - No modifica la base de datos

        Args:
            account_id: ID de la cuenta

        Returns:
            Optional[Assignment]: Asignacion activa o None

        Raises:
            ValueError: Si account_id es None o vacio
            DatabaseError: Si hay error de conexion

        Example:
            >>> assignment = repo.get_active_by_account("acc-001")
            >>> if assignment:
            ...     print(f"Asignado a: {assignment.agent_id}")
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[Assignment]:
        """
        Obtiene todas las asignaciones de una fecha especifica.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna lista de asignaciones de esa fecha
            - Retorna lista vacia si no hay asignaciones
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            List[Assignment]: Lista de asignaciones

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion

        Example:
            >>> from datetime import date
            >>> assignments = repo.get_by_date(date(2025, 10, 15))
            >>> print(f"Asignaciones ese dia: {len(assignments)}")
        """
        pass
