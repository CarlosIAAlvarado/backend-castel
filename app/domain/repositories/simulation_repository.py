from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.entities.simulation import Simulation


class SimulationRepository(ABC):
    """
    Interfaz para el repositorio de simulaciones guardadas.

    Define las operaciones de acceso a datos para simulaciones
    guardadas que pueden ser consultadas y comparadas.
    """

    @abstractmethod
    def create(self, simulation: Simulation) -> Simulation:
        """
        Crea una nueva simulacion en la base de datos.

        Args:
            simulation: Entidad Simulation a crear

        Returns:
            Simulation: Simulacion creada con ID asignado

        Raises:
            ValueError: Si simulation es None o datos invalidos
            DatabaseError: Si hay error de conexion
        """
        pass

    @abstractmethod
    def get_all(self, limit: int = 50) -> List[Simulation]:
        """
        Obtiene todas las simulaciones guardadas ordenadas por fecha descendente.

        Args:
            limit: Numero maximo de simulaciones a retornar (default: 50)

        Returns:
            List[Simulation]: Lista de simulaciones ordenadas por created_at desc
        """
        pass

    @abstractmethod
    def get_by_id(self, simulation_id: str) -> Optional[Simulation]:
        """
        Obtiene una simulacion por su simulation_id.

        Args:
            simulation_id: UUID de la simulacion

        Returns:
            Optional[Simulation]: Simulacion encontrada o None
        """
        pass

    @abstractmethod
    def update(self, simulation_id: str, name: str, description: Optional[str] = None) -> bool:
        """
        Actualiza el nombre y descripcion de una simulacion.

        Args:
            simulation_id: UUID de la simulacion
            name: Nuevo nombre
            description: Nueva descripcion (opcional)

        Returns:
            bool: True si se actualizo, False si no se encontro
        """
        pass

    @abstractmethod
    def delete(self, simulation_id: str) -> bool:
        """
        Elimina una simulacion por su simulation_id.

        Args:
            simulation_id: UUID de la simulacion

        Returns:
            bool: True si se elimino, False si no se encontro
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Cuenta el total de simulaciones guardadas.

        Returns:
            int: Numero total de simulaciones
        """
        pass

    @abstractmethod
    def get_by_ids(self, simulation_ids: List[str]) -> List[Simulation]:
        """
        Obtiene multiples simulaciones por sus IDs para comparacion.

        Args:
            simulation_ids: Lista de UUIDs de simulaciones (max 5)

        Returns:
            List[Simulation]: Lista de simulaciones encontradas
        """
        pass
