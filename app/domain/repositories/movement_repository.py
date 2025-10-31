from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.movement import Movement


class MovementRepository(ABC):
    """
    Interfaz para el repositorio de movimientos (operaciones de trading).

    Define las operaciones de acceso a datos para consultar movimientos
    de agentes en Casterly Rock.

    Esta interfaz cumple con LSP (Liskov Substitution Principle).
    """

    @abstractmethod
    def get_by_date_range(self, start_date: date, end_date: date, agent_id: Optional[str] = None) -> List[Movement]:
        """
        Obtiene movimientos en un rango de fechas, opcionalmente filtrados por agente.

        Pre-condiciones:
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date
            - agent_id puede ser None (obtiene todos los movimientos)

        Post-condiciones:
            - Retorna lista de movimientos en el rango especificado
            - Si agent_id no es None, filtra solo movimientos de ese agente
            - Retorna lista vacia si no hay movimientos
            - No modifica la base de datos

        Args:
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)
            agent_id: ID del agente para filtrar (opcional)

        Returns:
            List[Movement]: Lista de movimientos ordenados por fecha

        Raises:
            ValueError: Si fechas son invalidas o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=7)
            >>> movements = repo.get_by_date_range(start, end, agent_id="futures-001")
            >>> print(f"Total operaciones: {len(movements)}")
        """
        pass

    @abstractmethod
    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> List[Movement]:
        """
        Obtiene todos los movimientos de un agente en una fecha especifica.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna lista de movimientos del agente en esa fecha
            - Retorna lista vacia si no hay movimientos
            - No modifica la base de datos

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

        Returns:
            List[Movement]: Lista de movimientos (puede estar vacia)

        Raises:
            ValueError: Si agent_id es None/vacio o target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> movements = repo.get_by_agent_and_date("futures-001", date(2025, 10, 15))
            >>> total_pnl = sum(m.resultado for m in movements)
            >>> print(f"P&L del dia: ${total_pnl}")
        """
        pass

    @abstractmethod
    def count_by_agent_and_period(self, agent_id: str, start_date: date, end_date: date) -> int:
        """
        Cuenta el numero de operaciones de un agente en un periodo.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna el numero total de operaciones
            - Retorna 0 si no hay operaciones
            - No modifica la base de datos

        Args:
            agent_id: ID del agente
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            int: Numero de operaciones (>= 0)

        Raises:
            ValueError: Si agent_id es None/vacio, fechas invalidas, o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=30)
            >>> count = repo.count_by_agent_and_period("futures-001", start, end)
            >>> print(f"Operaciones en 30 dias: {count}")
        """
        pass
