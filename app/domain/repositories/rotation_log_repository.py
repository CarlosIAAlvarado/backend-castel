from abc import ABC, abstractmethod
from typing import List
from datetime import date
from app.domain.entities.rotation_log import RotationLog


class RotationLogRepository(ABC):
    """
    Interfaz para el repositorio de historial de rotaciones de agentes.

    Define las operaciones de acceso a datos para el log de entradas
    y salidas de agentes en Casterly Rock.

    Esta interfaz cumple con LSP (Liskov Substitution Principle).
    """

    @abstractmethod
    def create(self, rotation: RotationLog) -> RotationLog:
        """
        Registra una nueva rotacion de agente (entrada o salida).

        Pre-condiciones:
            - rotation no debe ser None
            - rotation.rotation_date debe ser una fecha valida
            - rotation.rotation_type debe ser "IN" o "OUT"
            - rotation.agent_in o rotation.agent_out debe estar presente segun el tipo

        Post-condiciones:
            - La rotacion se persiste en la base de datos
            - Retorna el objeto con ID asignado
            - El registro queda permanente para auditoria

        Args:
            rotation: Datos de la rotacion (entrada o salida)

        Returns:
            RotationLog: Rotacion creada con ID asignado

        Raises:
            ValueError: Si rotation es None o tiene datos invalidos
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> rotation = RotationLog(
            ...     rotation_date=date.today(),
            ...     rotation_type="IN",
            ...     agent_in="futures-001",
            ...     reason="Top 16 performance"
            ... )
            >>> created = repo.create(rotation)
            >>> assert created.agent_in == "futures-001"
        """
        pass

    @abstractmethod
    def get_all(self) -> List[RotationLog]:
        """
        Obtiene todo el historial de rotaciones del sistema.

        Pre-condiciones:
            - Ninguna

        Post-condiciones:
            - Retorna lista completa de rotaciones ordenadas por fecha descendente
            - Retorna lista vacia si no hay rotaciones
            - No modifica la base de datos

        Returns:
            List[RotationLog]: Lista completa de rotaciones (puede estar vacia)

        Raises:
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> rotations = repo.get_all()
            >>> print(f"Total rotaciones historicas: {len(rotations)}")
            >>> for rot in rotations[:5]:
            ...     print(f"{rot.rotation_date}: {rot.rotation_type}")
        """
        pass

    @abstractmethod
    def get_by_date_range(self, start_date: date, end_date: date) -> List[RotationLog]:
        """
        Obtiene rotaciones en un rango de fechas especifico.

        Pre-condiciones:
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna lista de rotaciones en el periodo especificado
            - Retorna lista vacia si no hay rotaciones
            - No modifica la base de datos

        Args:
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            List[RotationLog]: Lista de rotaciones ordenadas por fecha

        Raises:
            ValueError: Si fechas son invalidas o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=30)
            >>> rotations = repo.get_by_date_range(start, end)
            >>> ins = sum(1 for r in rotations if r.rotation_type == "IN")
            >>> outs = sum(1 for r in rotations if r.rotation_type == "OUT")
            >>> print(f"Ultimos 30 dias: {ins} entradas, {outs} salidas")
        """
        pass

    @abstractmethod
    def get_by_agent(self, agent_id: str) -> List[RotationLog]:
        """
        Obtiene el historial completo de rotaciones de un agente especifico.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio

        Post-condiciones:
            - Retorna lista de rotaciones donde el agente participo (IN o OUT)
            - Retorna lista vacia si el agente no tiene historial
            - No modifica la base de datos

        Args:
            agent_id: ID del agente

        Returns:
            List[RotationLog]: Lista de rotaciones donde el agente participo

        Raises:
            ValueError: Si agent_id es None o vacio
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> rotations = repo.get_by_agent("futures-001")
            >>> print(f"Historial de futures-001:")
            >>> for rot in rotations:
            ...     print(f"{rot.rotation_date}: {rot.rotation_type} - {rot.reason}")
        """
        pass

    @abstractmethod
    def count_rotations_by_period(self, start_date: date, end_date: date) -> int:
        """
        Cuenta el numero total de rotaciones en un periodo especifico.

        Pre-condiciones:
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna el numero total de rotaciones (IN + OUT)
            - Retorna 0 si no hay rotaciones
            - No modifica la base de datos

        Args:
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            int: Numero de rotaciones (>= 0)

        Raises:
            ValueError: Si fechas son invalidas o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=90)
            >>> count = repo.count_rotations_by_period(start, end)
            >>> print(f"Rotaciones en 90 dias: {count}")
        """
        pass
