from abc import ABC, abstractmethod
from typing import List
from datetime import date
from app.domain.entities.agent_state import AgentState


class AgentStateFallQueries(ABC):
    """
    Interfaz especializada para queries de agentes en caida.

    Segrega operaciones especializadas de analisis de caidas
    segun ISP (Interface Segregation Principle).

    Los clientes que solo necesitan operaciones CRUD basicas no se ven
    forzados a depender de estos metodos especializados.
    """

    @abstractmethod
    def get_agents_in_fall(
        self,
        target_date: date,
        min_fall_days: int = 3
    ) -> List[AgentState]:
        """
        Obtiene agentes en caida consecutiva por N dias o mas.

        Pre-condiciones:
            - target_date debe ser una fecha valida
            - min_fall_days debe ser mayor que 0

        Post-condiciones:
            - Retorna lista de estados que cumplen fall_days >= min_fall_days
            - Retorna lista vacia si ningun agente cumple el criterio
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo
            min_fall_days: Minimo de dias consecutivos en caida (default: 3)

        Returns:
            List[AgentState]: Lista de agentes en caida

        Raises:
            ValueError: Si target_date es invalido o min_fall_days <= 0
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> agents_in_fall = repo.get_agents_in_fall(date(2025, 10, 15), min_fall_days=3)
            >>> for agent in agents_in_fall:
            ...     print(f"{agent.agent_id}: {agent.fall_days} dias en caida")
        """
        pass

    @abstractmethod
    def get_fall_statistics(self, target_date: date) -> dict:
        """
        Obtiene estadisticas de agentes en caida.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna diccionario con estadisticas agregadas
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            dict: Diccionario con estadisticas:
                - total_in_fall: int (total de agentes en caida)
                - avg_fall_days: float (promedio de dias en caida)
                - max_fall_days: int (maximo de dias en caida)
                - agents_by_fall_range: dict (agentes agrupados por rango de dias)

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> stats = repo.get_fall_statistics(date(2025, 10, 15))
            >>> print(f"Agentes en caida: {stats['total_in_fall']}")
            >>> print(f"Promedio dias: {stats['avg_fall_days']:.1f}")
        """
        pass
