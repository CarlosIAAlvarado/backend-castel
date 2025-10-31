from abc import ABC, abstractmethod
from typing import List
from datetime import date
from app.domain.entities.top16_day import Top16Day


class Top16Repository(ABC):
    """
    Interfaz para el repositorio de ranking Top 16 diario de agentes.

    Define las operaciones de acceso a datos para el ranking de mejores
    agentes por performance en Casterly Rock.

    Esta interfaz cumple con LSP (Liskov Substitution Principle).
    """

    @abstractmethod
    def create_batch(self, top16_list: List[Top16Day]) -> List[Top16Day]:
        """
        Crea multiples registros de Top 16 para una fecha especifica.

        Pre-condiciones:
            - top16_list no debe ser None ni vacio
            - Cada elemento debe tener agent_id y date validos
            - Todos los elementos deben tener la misma fecha
            - Los ranks deben ser unicos dentro de la misma fecha

        Post-condiciones:
            - Todos los registros se persisten en la base de datos
            - Operacion atomica (todo o nada)
            - Retorna lista de registros creados con IDs asignados

        Args:
            top16_list: Lista de registros Top16Day a crear

        Returns:
            List[Top16Day]: Lista de registros creados con IDs

        Raises:
            ValueError: Si top16_list es None/vacio o contiene datos invalidos
            DatabaseError: Si hay error de conexion a base de datos
            DuplicateKeyError: Si ya existe ranking para esa fecha

        Example:
            >>> from datetime import date
            >>> top16 = [
            ...     Top16Day(agent_id="futures-001", date=date.today(), rank=1, roi_30d=0.15),
            ...     Top16Day(agent_id="futures-002", date=date.today(), rank=2, roi_30d=0.12)
            ... ]
            >>> created = repo.create_batch(top16)
            >>> assert len(created) == 2
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[Top16Day]:
        """
        Obtiene el ranking Top 16 completo de una fecha especifica.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna lista ordenada por rank ascendente
            - Retorna lista vacia si no hay ranking para esa fecha
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            List[Top16Day]: Lista ordenada por rank (puede estar vacia)

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> top16 = repo.get_by_date(date(2025, 10, 15))
            >>> for entry in top16:
            ...     print(f"#{entry.rank}: {entry.agent_id} - ROI: {entry.roi_30d:.2%}")
        """
        pass

    @abstractmethod
    def get_in_casterly_by_date(self, target_date: date) -> List[Top16Day]:
        """
        Obtiene solo agentes que estan dentro de Casterly Rock en una fecha.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna lista de agentes con is_in_casterly=True
            - Retorna lista ordenada por rank ascendente
            - Retorna lista vacia si ningun agente esta en Casterly
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            List[Top16Day]: Lista de agentes en Casterly ordenada por rank

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> in_casterly = repo.get_in_casterly_by_date(date(2025, 10, 15))
            >>> print(f"Agentes activos en Casterly: {len(in_casterly)}")
            >>> total_aum = sum(entry.aum for entry in in_casterly)
            >>> print(f"AUM total: ${total_aum}")
        """
        pass

    @abstractmethod
    def get_by_agent_range(self, agent_id: str, start_date: date, end_date: date) -> List[Top16Day]:
        """
        Obtiene el historial de ranking de un agente en un periodo especifico.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio
            - start_date debe ser una fecha valida
            - end_date debe ser una fecha valida
            - start_date <= end_date

        Post-condiciones:
            - Retorna lista de registros del agente en el periodo
            - Retorna lista ordenada por fecha ascendente
            - Retorna lista vacia si el agente no estuvo en Top 16
            - No modifica la base de datos

        Args:
            agent_id: ID del agente
            start_date: Fecha inicial (inclusiva)
            end_date: Fecha final (inclusiva)

        Returns:
            List[Top16Day]: Lista de registros ordenados por fecha

        Raises:
            ValueError: Si agent_id es None/vacio, fechas invalidas, o start_date > end_date
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date, timedelta
            >>> end = date(2025, 10, 15)
            >>> start = end - timedelta(days=30)
            >>> history = repo.get_by_agent_range("futures-001", start, end)
            >>> for entry in history:
            ...     print(f"{entry.date}: Rank #{entry.rank}, ROI: {entry.roi_30d:.2%}")
        """
        pass
