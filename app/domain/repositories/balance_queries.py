from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import date


class BalanceAggregationQueries(ABC):
    """
    Interfaz especializada para agregaciones avanzadas de balances.

    Segrega operaciones especializadas de analisis agregado
    segun ISP (Interface Segregation Principle).

    Los clientes que solo necesitan consultas basicas de balances no se ven
    forzados a depender de estos metodos especializados de agregacion.
    """

    @abstractmethod
    def get_total_aum_by_date(self, target_date: date) -> float:
        """
        Obtiene el AUM (Assets Under Management) total de todas las cuentas en una fecha.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna suma de todos los balances
            - Retorna 0.0 si no hay balances
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            float: AUM total (>= 0)

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> aum = repo.get_total_aum_by_date(date(2025, 10, 15))
            >>> print(f"AUM total: ${aum:,.2f}")
        """
        pass

    @abstractmethod
    def get_aum_evolution(
        self,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, any]]:
        """
        Obtiene la evolucion del AUM total en un rango de fechas.

        Pre-condiciones:
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna lista ordenada por fecha ascendente
            - Cada elemento contiene fecha y AUM total
            - Retorna lista vacia si no hay datos
            - No modifica la base de datos

        Args:
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            List[Dict]: Lista de diccionarios con formato:
                [{"date": date, "aum": float}, ...]

        Raises:
            ValueError: Si fechas invalidas o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=30)
            >>> evolution = repo.get_aum_evolution(start, end)
            >>> for entry in evolution:
            ...     print(f"{entry['date']}: ${entry['aum']:,.2f}")
        """
        pass
