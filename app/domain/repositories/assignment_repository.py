from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.assignment import Assignment


class AssignmentRepository(ABC):
    """
    Interfaz para el repositorio de asignaciones cuenta-agente.

    Define las operaciones de acceso a datos para asignaciones de cuentas
    a agentes en Casterly Rock.

    Esta interfaz cumple con LSP (Liskov Substitution Principle).
    """

    @abstractmethod
    def create(self, assignment: Assignment) -> Assignment:
        """
        Crea una nueva asignacion de cuenta a agente.

        Pre-condiciones:
            - assignment no debe ser None
            - assignment.account_id no debe estar vacio
            - assignment.agent_id no debe estar vacio
            - assignment.balance debe ser mayor o igual a 0

        Post-condiciones:
            - La asignacion se persiste en la base de datos
            - Retorna el objeto con posible ID asignado

        Args:
            assignment: Datos de la asignacion

        Returns:
            Assignment: Asignacion creada

        Raises:
            ValueError: Si assignment es None o tiene datos invalidos
            DatabaseError: Si hay error de conexion
            DuplicateKeyError: Si la cuenta ya tiene asignacion activa

        Example:
            >>> from datetime import date
            >>> assignment = Assignment(account_id="acc-001", agent_id="futures-001", balance=10000)
            >>> created = repo.create(assignment)
            >>> assert created.account_id == "acc-001"
        """
        pass

    @abstractmethod
    def create_batch(self, assignments: List[Assignment]) -> List[Assignment]:
        """
        Crea multiples asignaciones en lote.

        Pre-condiciones:
            - assignments no debe ser None ni vacio
            - Cada elemento debe cumplir pre-condiciones de create()

        Post-condiciones:
            - Todas las asignaciones se persisten
            - Operacion atomica segun implementacion

        Args:
            assignments: Lista de asignaciones

        Returns:
            List[Assignment]: Lista de asignaciones creadas

        Raises:
            ValueError: Si assignments es None/vacio o contiene datos invalidos
            DatabaseError: Si hay error de conexion

        Example:
            >>> assignments = [Assignment(account_id=f"acc-{i}", agent_id="futures-001") for i in range(10)]
            >>> created = repo.create_batch(assignments)
            >>> assert len(created) == 10
        """
        pass

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

    @abstractmethod
    def deactivate(self, assignment_id: str) -> Assignment:
        """
        Desactiva una asignacion (marca is_active=False y establece unassigned_at).

        Pre-condiciones:
            - assignment_id no debe ser None ni vacio
            - Debe existir la asignacion

        Post-condiciones:
            - is_active se marca como False
            - unassigned_at se establece con timestamp actual
            - Se persiste en la base de datos

        Args:
            assignment_id: ID de la asignacion

        Returns:
            Assignment: Asignacion desactivada

        Raises:
            ValueError: Si assignment_id es None o vacio
            NotFoundError: Si no existe la asignacion
            DatabaseError: Si hay error de conexion

        Example:
            >>> deactivated = repo.deactivate("assignment-123")
            >>> assert deactivated.is_active == False
            >>> assert deactivated.unassigned_at is not None
        """
        pass

    @abstractmethod
    def transfer_accounts(self, from_agent: str, to_agent: str) -> int:
        """
        Transfiere todas las cuentas activas de un agente a otro.

        Pre-condiciones:
            - from_agent no debe ser None ni vacio
            - to_agent no debe ser None ni vacio
            - from_agent != to_agent

        Post-condiciones:
            - Todas las asignaciones activas de from_agent se desactivan
            - Se crean nuevas asignaciones activas para to_agent
            - Retorna el numero de cuentas transferidas

        Args:
            from_agent: ID del agente origen
            to_agent: ID del agente destino

        Returns:
            int: Numero de cuentas transferidas

        Raises:
            ValueError: Si parametros son None/vacios o iguales
            DatabaseError: Si hay error de conexion

        Example:
            >>> count = repo.transfer_accounts("futures-001", "futures-002")
            >>> print(f"Transferidas {count} cuentas")
        """
        pass
