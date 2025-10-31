from abc import ABC, abstractmethod
from typing import List
from app.domain.entities.assignment import Assignment


class AssignmentWriteOps(ABC):
    """
    Interfaz segregada para operaciones de ESCRITURA de asignaciones.

    Cumple con ISP (Interface Segregation Principle):
    - Clientes que solo escriben no dependen de metodos de lectura
    - Servicios de orquestacion/mutacion solo necesitan esta interfaz
    - Permite permisos mas granulares (ej: servicio de escritura separado)

    Esta interfaz define solo operaciones que MODIFICAN datos.
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
