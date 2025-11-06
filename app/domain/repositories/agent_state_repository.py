from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from app.domain.entities.agent_state import AgentState


class AgentStateRepository(ABC):
    """
    Interfaz base para el repositorio de estados de agentes.

    Define las operaciones CRUD basicas y de consulta de historial
    para el estado diario de los agentes en Casterly Rock.

    Esta interfaz sigue el patron Repository y cumple con:
    - LSP (Liskov Substitution Principle): Contratos bien definidos
    - ISP (Interface Segregation Principle): Solo operaciones basicas,
      sin metodos especializados que no todos los clientes necesitan

    Para operaciones especializadas (ej: analisis de caidas),
    ver AgentStateFallQueries.
    """

    @abstractmethod
    def create(self, agent_state: AgentState) -> AgentState:
        """
        Crea un nuevo registro de estado de agente en la base de datos.

        Pre-condiciones:
            - agent_state no debe ser None
            - agent_state.agent_id no debe estar vacio
            - agent_state.date debe ser una fecha valida
            - agent_state.state debe ser un AgentStateEnum valido

        Post-condiciones:
            - El estado se persiste en la base de datos
            - El estado creado puede tener un ID asignado (dependiendo de la implementacion)
            - Retorna el mismo objeto con posibles campos actualizados

        Args:
            agent_state: Estado del agente a crear

        Returns:
            AgentState: El estado creado, potencialmente con ID asignado

        Raises:
            ValueError: Si agent_state es None o tiene datos invalidos
            DatabaseError: Si hay error de conexion a base de datos
            DuplicateKeyError: Si ya existe un estado para ese agente/fecha

        Example:
            >>> from datetime import date
            >>> repo = AgentStateRepositoryImpl()
            >>> state = AgentState(agent_id="futures-001", date=date.today())
            >>> created = repo.create(state)
            >>> assert created.agent_id == "futures-001"
        """
        pass

    @abstractmethod
    def create_batch(self, agent_states: List[AgentState]) -> List[AgentState]:
        """
        Crea multiples registros de estado en lote (operacion optimizada).

        Pre-condiciones:
            - agent_states no debe ser None
            - agent_states no debe estar vacio
            - Cada elemento debe cumplir las pre-condiciones de create()

        Post-condiciones:
            - Todos los estados se persisten en la base de datos
            - La operacion es atomica (todo o nada segun la implementacion)
            - Retorna la lista de estados creados

        Args:
            agent_states: Lista de estados a crear

        Returns:
            List[AgentState]: Lista de estados creados

        Raises:
            ValueError: Si agent_states es None, vacio o contiene datos invalidos
            DatabaseError: Si hay error de conexion a base de datos
            DuplicateKeyError: Si alguno de los estados ya existe

        Example:
            >>> states = [AgentState(agent_id=f"futures-{i}", date=date.today()) for i in range(10)]
            >>> created = repo.create_batch(states)
            >>> assert len(created) == 10
        """
        pass

    @abstractmethod
    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> Optional[AgentState]:
        """
        Obtiene el estado de un agente en una fecha especifica.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna el estado si existe
            - Retorna None si no existe
            - No modifica la base de datos

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

        Returns:
            Optional[AgentState]: AgentState si existe, None en caso contrario

        Raises:
            ValueError: Si agent_id es None/vacio o target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> state = repo.get_by_agent_and_date("futures-001", date(2025, 10, 15))
            >>> if state:
            ...     print(f"ROI: {state.roi_day}")
        """
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[AgentState]:
        """
        Obtiene todos los estados de una fecha especifica.

        Pre-condiciones:
            - target_date debe ser una fecha valida

        Post-condiciones:
            - Retorna lista de todos los estados de esa fecha
            - Retorna lista vacia si no hay estados
            - No modifica la base de datos

        Args:
            target_date: Fecha objetivo

        Returns:
            List[AgentState]: Lista de estados (puede estar vacia)

        Raises:
            ValueError: Si target_date es invalido
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> states = repo.get_by_date(date(2025, 10, 15))
            >>> print(f"Agentes activos: {len(states)}")
        """
        pass

    @abstractmethod
    def get_latest_by_agent(self, agent_id: str) -> Optional[AgentState]:
        """
        Obtiene el estado mas reciente de un agente.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio

        Post-condiciones:
            - Retorna el estado con la fecha mas reciente
            - Retorna None si el agente no tiene estados
            - No modifica la base de datos

        Args:
            agent_id: ID del agente

        Returns:
            Optional[AgentState]: Estado mas reciente o None

        Raises:
            ValueError: Si agent_id es None o vacio
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> latest = repo.get_latest_by_agent("futures-001")
            >>> if latest:
            ...     print(f"Ultima actualizacion: {latest.date}")
        """
        pass

    @abstractmethod
    def get_history_by_agent(self, agent_id: str, days: int = 7) -> List[AgentState]:
        """
        Obtiene el historial de estados de un agente en los ultimos N dias.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio
            - days debe ser mayor que 0

        Post-condiciones:
            - Retorna lista ordenada por fecha descendente (mas reciente primero)
            - Retorna lista vacia si no hay historial
            - No modifica la base de datos

        Args:
            agent_id: ID del agente
            days: Numero de dias hacia atras (default: 7)

        Returns:
            List[AgentState]: Lista de estados ordenados por fecha desc

        Raises:
            ValueError: Si agent_id es None/vacio o days <= 0
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> history = repo.get_history_by_agent("futures-001", days=30)
            >>> for state in history:
            ...     print(f"{state.date}: ROI {state.roi_day}")
        """
        pass

    @abstractmethod
    def update_state(self, agent_id: str, target_date: date, updates: dict) -> AgentState:
        """
        Actualiza campos especificos de un estado existente.

        Pre-condiciones:
            - agent_id no debe ser None ni vacio
            - target_date debe ser una fecha valida
            - updates no debe ser None ni vacio
            - Debe existir un estado para ese agent_id y target_date

        Post-condiciones:
            - El estado se actualiza en la base de datos
            - Solo se modifican los campos especificados en updates
            - Retorna el estado actualizado

        Args:
            agent_id: ID del agente
            target_date: Fecha del estado
            updates: Diccionario con campos a actualizar

        Returns:
            AgentState: Estado actualizado

        Raises:
            ValueError: Si parametros son None/vacios/invalidos
            NotFoundError: Si no existe el estado
            DatabaseError: Si hay error de conexion a base de datos

        Example:
            >>> from datetime import date
            >>> updated = repo.update_state(
            ...     "futures-001",
            ...     date(2025, 10, 15),
            ...     {"is_in_casterly": False}
            ... )
            >>> assert updated.is_in_casterly == False
        """
        pass
