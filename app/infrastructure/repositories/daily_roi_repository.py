"""
Repositorio para operaciones con la colección daily_roi_calculation.

Esta colección es TEMPORAL y se limpia al inicio de cada nueva consulta
para evitar acumulación de data basura.

Author: Sistema Casterly Rock
Date: 2025-10-19
Version: 2.0
"""

import logging
from typing import List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError
from app.domain.entities.daily_roi import DailyROI

logger = logging.getLogger(__name__)


class DailyROIRepository:
    """
    Repositorio para la colección temporal daily_roi_calculation.

    Esta colección almacena los cálculos de ROI diario y se limpia
    completamente al inicio de cada nueva consulta.

    Attributes:
        collection: Colección MongoDB 'daily_roi_calculation'
    """

    COLLECTION_NAME = "daily_roi_calculation"

    def __init__(self, db: Database):
        """
        Inicializa el repositorio.

        Args:
            db: Instancia de la base de datos MongoDB
        """
        self.collection = db[self.COLLECTION_NAME]
        logger.info(f"DailyROIRepository inicializado con colección '{self.COLLECTION_NAME}'")

    async def clear_all(self) -> int:
        """
        Limpia TODOS los documentos de la colección.

        Este método se ejecuta al inicio de cada nueva consulta para
        evitar acumulación de data basura.

        Returns:
            Número de documentos eliminados

        Raises:
            PyMongoError: Si hay error al eliminar documentos
        """
        try:
            result = self.collection.delete_many({})
            deleted_count = result.deleted_count
            logger.info(f"Colección '{self.COLLECTION_NAME}' limpiada. Eliminados: {deleted_count} documentos")
            return deleted_count
        except PyMongoError as e:
            logger.error(f"Error al limpiar colección '{self.COLLECTION_NAME}': {e}")
            raise

    async def save(self, daily_roi: DailyROI) -> str:
        """
        Guarda o actualiza el cálculo de ROI diario usando userId como clave.

        CAMBIO VERSION 2.1: Ahora usa UPSERT con userId + date como clave única.
        Esto garantiza que no hay duplicados para el mismo agente en el mismo día.

        Args:
            daily_roi: Entidad DailyROI con los datos calculados

        Returns:
            ID del documento insertado/actualizado (como string)

        Raises:
            PyMongoError: Si hay error al guardar
            ValueError: Si daily_roi es None o userId está vacío
        """
        if daily_roi is None:
            raise ValueError("daily_roi no puede ser None")

        if not daily_roi.userId:
            raise ValueError("userId no puede estar vacío")

        try:
            daily_roi.createdAt = datetime.utcnow()
            daily_roi.updatedAt = datetime.utcnow()

            doc = daily_roi.dict(exclude_none=True)

            result = self.collection.update_one(
                {"userId": daily_roi.userId, "date": daily_roi.date},
                {"$set": doc},
                upsert=True
            )

            logger.debug(
                f"ROI diario guardado: userId={daily_roi.userId}, "
                f"fecha={daily_roi.date}, roi={daily_roi.roi_day:.4f}"
            )

            return str(result.upserted_id) if result.upserted_id else "updated"

        except PyMongoError as e:
            logger.error(
                f"Error al guardar ROI diario: userId={daily_roi.userId}, "
                f"fecha={daily_roi.date}, error={e}"
            )
            raise

    async def find_by_agent_and_date(
        self, userId: str, target_date: str
    ) -> Optional[DailyROI]:
        """
        Busca el ROI de un agente en una fecha específica.

        CAMBIO VERSION 2.1: Ahora busca por userId (identificador único consistente).

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha en formato "YYYY-MM-DD"

        Returns:
            DailyROI si existe, None si no se encuentra

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            doc = self.collection.find_one(
                {"userId": userId, "date": target_date}
            )

            if not doc:
                logger.debug(
                    f"ROI diario no encontrado: userId={userId}, fecha={target_date}"
                )
                return None

            return DailyROI(**doc)

        except PyMongoError as e:
            logger.error(
                f"Error al buscar ROI diario: userId={userId}, "
                f"fecha={target_date}, error={e}"
            )
            raise

    async def find_by_date_range(
        self, userId: str, start_date: str, end_date: str
    ) -> List[DailyROI]:
        """
        Busca todos los ROIs de un agente en un rango de fechas.

        CAMBIO VERSION 2.1: Ahora busca por userId.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            start_date: Fecha inicio en formato "YYYY-MM-DD"
            end_date: Fecha fin en formato "YYYY-MM-DD"

        Returns:
            Lista de DailyROI ordenados por fecha ascendente

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = self.collection.find(
                {"userId": userId, "date": {"$gte": start_date, "$lte": end_date}}
            ).sort("date", 1)

            results = [DailyROI(**doc) for doc in cursor]

            logger.debug(
                f"ROIs diarios encontrados: userId={userId}, "
                f"rango=[{start_date}, {end_date}], cantidad={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al buscar ROIs por rango: userId={userId}, "
                f"rango=[{start_date}, {end_date}], error={e}"
            )
            raise

    async def find_all_by_date(self, target_date: str) -> List[DailyROI]:
        """
        Busca todos los ROIs de TODOS los agentes para una fecha.

        Útil para obtener el ranking de todos los agentes en un día específico.

        Args:
            target_date: Fecha en formato "YYYY-MM-DD"

        Returns:
            Lista de DailyROI ordenados por ROI descendente

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = self.collection.find({"date": target_date}).sort("roi_day", -1)

            results = [DailyROI(**doc) for doc in cursor]

            logger.debug(
                f"ROIs diarios de todos los agentes: fecha={target_date}, "
                f"cantidad={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al buscar ROIs de todos los agentes: fecha={target_date}, error={e}"
            )
            raise

    async def count_by_date(self, target_date: str) -> int:
        """
        Cuenta cuántos agentes tienen ROI calculado para una fecha.

        Args:
            target_date: Fecha en formato "YYYY-MM-DD"

        Returns:
            Número de documentos (agentes)

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            count = self.collection.count_documents({"date": target_date})
            logger.debug(f"Agentes con ROI calculado: fecha={target_date}, count={count}")
            return count

        except PyMongoError as e:
            logger.error(f"Error al contar ROIs por fecha: fecha={target_date}, error={e}")
            raise

    async def get_top_performers_by_date(
        self, target_date: str, limit: int = 10
    ) -> List[DailyROI]:
        """
        Obtiene los agentes con mejor ROI en una fecha específica.

        Args:
            target_date: Fecha en formato "YYYY-MM-DD"
            limit: Número máximo de resultados (default: 10)

        Returns:
            Lista de DailyROI ordenados por ROI descendente

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = (
                self.collection.find({"date": target_date})
                .sort("roi_day", -1)
                .limit(limit)
            )

            results = [DailyROI(**doc) for doc in cursor]

            logger.debug(
                f"Top performers obtenidos: fecha={target_date}, "
                f"limit={limit}, encontrados={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al obtener top performers: fecha={target_date}, error={e}"
            )
            raise

    async def delete_by_agent_and_date(
        self, userId: str, target_date: str
    ) -> bool:
        """
        Elimina el ROI de un agente en una fecha específica.

        CAMBIO VERSION 2.1: Ahora elimina por userId.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha en formato "YYYY-MM-DD"

        Returns:
            True si se eliminó, False si no se encontró

        Raises:
            PyMongoError: Si hay error al eliminar
        """
        try:
            result = self.collection.delete_one(
                {"userId": userId, "date": target_date}
            )

            deleted = result.deleted_count > 0

            if deleted:
                logger.info(
                    f"ROI diario eliminado: userId={userId}, fecha={target_date}"
                )
            else:
                logger.warning(
                    f"ROI diario no encontrado para eliminar: "
                    f"userId={userId}, fecha={target_date}"
                )

            return deleted

        except PyMongoError as e:
            logger.error(
                f"Error al eliminar ROI diario: userId={userId}, "
                f"fecha={target_date}, error={e}"
            )
            raise
