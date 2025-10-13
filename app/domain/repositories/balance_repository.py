from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.balance import Balance


class BalanceRepository(ABC):
    """
    Interfaz para el repositorio de balances.

    Define las operaciones de acceso a datos para balances.
    """

    @abstractmethod
    def get_by_account_and_date(self, account_id: str, target_date: date) -> Optional[Balance]:
        """
        Obtiene el balance de una cuenta en una fecha especifica.

        Args:
            account_id: ID de la cuenta
            target_date: Fecha objetivo

        Returns:
            Balance o None si no existe
        """
        pass

    @abstractmethod
    def get_all_by_date(self, target_date: date) -> List[Balance]:
        """
        Obtiene todos los balances de una fecha especifica.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de balances
        """
        pass

    @abstractmethod
    def get_by_account_range(self, account_id: str, start_date: date, end_date: date) -> List[Balance]:
        """
        Obtiene los balances de una cuenta en un rango de fechas.

        Args:
            account_id: ID de la cuenta
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Lista de balances
        """
        pass
