from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.balance import Balance


class BalanceRepository(ABC):
    """
    Interfaz para el repositorio de balances de cuentas.

    Define las operaciones de acceso a datos para consultar balances
    diarios de cuentas en Casterly Rock.

    Esta interfaz cumple con LSP (Liskov Substitution Principle).
    """

    @abstractmethod
    def get_by_account_and_date(self, account_id: str, target_date: date) -> Optional[Balance]:
        """
        Obtiene el balance de una cuenta en una fecha especifica.

        Pre-condiciones:
            - account_id no debe ser None ni vacio
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna el balance si existe para esa cuenta y fecha
            - Retorna None si no existe balance
            - No modifica la base de datos

        Args:
            account_id: ID de la cuenta
            target_date: Fecha objetivo

        Returns:
            Optional[Balance]: Balance si existe, None en caso contrario

        Raises:
            ValueError: Si account_id es None/vacio o target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> balance = repo.get_by_account_and_date("acc-001", date(2025, 10, 15))
            >>> if balance:
            ...     print(f"Balance: ${balance.balance}")
        """
        pass

    @abstractmethod
    def get_all_by_date(self, target_date: date) -> List[Balance]:
        """
        Obtiene todos los balances de una fecha especifica.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna lista de todos los balances de esa fecha
            - Retorna lista vacia si no hay balances
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            List[Balance]: Lista de balances (puede estar vacia)

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> balances = repo.get_all_by_date(date(2025, 10, 15))
            >>> total_aum = sum(b.balance for b in balances)
            >>> print(f"AUM total: ${total_aum}")
        """
        pass

    @abstractmethod
    def get_by_account_range(self, account_id: str, start_date: date, end_date: date) -> List[Balance]:
        """
        Obtiene los balances de una cuenta en un rango de fechas.

        Pre-condiciones:
            - account_id no debe ser None ni vacio
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna lista de balances ordenados por fecha
            - Retorna lista vacia si no hay balances en el rango
            - No modifica la base de datos

        Args:
            account_id: ID de la cuenta
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            List[Balance]: Lista de balances ordenados por fecha

        Raises:
            ValueError: Si account_id es None/vacio, fechas invalidas, o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=7)
            >>> balances = repo.get_by_account_range("acc-001", start, end)
            >>> for balance in balances:
            ...     print(f"{balance.date}: ${balance.balance}")
        """
        pass

    @abstractmethod
    def get_all_by_date_range(self, start_date: date, end_date: date) -> List[Balance]:
        """
        Obtiene todos los balances de TODAS las cuentas en un rango de fechas.

        VERSION 2.2: Nuevo metodo para buscar agentes en ventana ROI_7D.

        Pre-condiciones:
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna lista de todos los balances en el rango
            - Retorna lista vacia si no hay balances
            - No modifica la base de datos

        Args:
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            List[Balance]: Lista de balances de todas las cuentas

        Raises:
            ValueError: Si fechas invalidas o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 7)
            >>> start = end - timedelta(days=7)
            >>> balances = repo.get_all_by_date_range(start, end)
            >>> unique_agents = set(b.user_id for b in balances)
            >>> print(f"Agentes activos en ventana: {len(unique_agents)}")
        """
        pass
