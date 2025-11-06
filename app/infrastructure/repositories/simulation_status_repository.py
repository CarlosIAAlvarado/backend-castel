"""
Repositorio para operaciones con la coleccion simulation_status.

Esta coleccion almacena el estado actual de la simulacion en curso.
Solo existe UN documento con _id="current".

Author: Sistema Casterly Rock
Date: 2025-11-05
Version: 1.0
"""

import logging
from typing import Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError
from app.domain.entities.simulation_status import SimulationStatus

logger = logging.getLogger(__name__)


class SimulationStatusRepository:
    """
    Repositorio para la coleccion simulation_status.

    Esta coleccion mantiene el estado actual de simulaciones en curso.
    Solo existe un documento con status_id="current".

    Attributes:
        collection: Coleccion MongoDB 'simulation_status'
    """

    COLLECTION_NAME = "simulation_status"
    CURRENT_ID = "current"

    def __init__(self, db: Database):
        """
        Inicializa el repositorio.

        Args:
            db: Instancia de la base de datos MongoDB
        """
        self.collection = db[self.COLLECTION_NAME]
        logger.info(f"SimulationStatusRepository inicializado con coleccion '{self.COLLECTION_NAME}'")

    def get_current(self) -> Optional[SimulationStatus]:
        """
        Obtiene el estado actual de la simulacion.

        Returns:
            SimulationStatus si existe, None si no hay simulacion en curso
        """
        try:
            doc = self.collection.find_one({"status_id": self.CURRENT_ID})

            if not doc:
                return None

            return SimulationStatus(**doc)

        except PyMongoError as e:
            logger.error(f"Error al obtener estado de simulacion: {e}")
            raise

    def upsert(self, status: SimulationStatus) -> None:
        """
        Crea o actualiza el estado de la simulacion.

        Args:
            status: Estado de simulacion a guardar
        """
        try:
            status.status_id = self.CURRENT_ID
            status.updated_at = datetime.utcnow()

            doc = status.model_dump(exclude_none=True)

            self.collection.update_one(
                {"status_id": self.CURRENT_ID},
                {"$set": doc},
                upsert=True
            )

            logger.debug(
                f"Estado de simulacion actualizado: day {status.current_day}/{status.total_days}"
            )

        except PyMongoError as e:
            logger.error(f"Error al guardar estado de simulacion: {e}")
            raise

    def mark_completed(self) -> None:
        """
        Marca la simulacion como completada.

        Actualiza is_running=False y current_day=total_days.
        """
        try:
            current = self.get_current()

            if not current:
                logger.warning("No hay simulacion activa para marcar como completada")
                return

            current.is_running = False
            current.current_day = current.total_days
            current.message = "Simulacion completada"
            current.updated_at = datetime.utcnow()

            self.upsert(current)

            logger.info("Simulacion marcada como completada")

        except PyMongoError as e:
            logger.error(f"Error al marcar simulacion como completada: {e}")
            raise

    def delete_current(self) -> bool:
        """
        Elimina el estado actual de simulacion.

        Returns:
            True si se elimino, False si no existia
        """
        try:
            result = self.collection.delete_one({"status_id": self.CURRENT_ID})

            deleted = result.deleted_count > 0

            if deleted:
                logger.info("Estado de simulacion eliminado")
            else:
                logger.debug("No habia estado de simulacion para eliminar")

            return deleted

        except PyMongoError as e:
            logger.error(f"Error al eliminar estado de simulacion: {e}")
            raise

    def update_progress(self, current_day: int, message: Optional[str] = None) -> None:
        """
        Actualiza solo el progreso de la simulacion.

        Args:
            current_day: Dia actual procesado
            message: Mensaje opcional a mostrar
        """
        try:
            update_data = {
                "current_day": current_day,
                "updated_at": datetime.utcnow()
            }

            if message:
                update_data["message"] = message

            self.collection.update_one(
                {"status_id": self.CURRENT_ID},
                {"$set": update_data}
            )

            logger.debug(f"Progreso actualizado: dia {current_day}")

        except PyMongoError as e:
            logger.error(f"Error al actualizar progreso: {e}")
            raise
