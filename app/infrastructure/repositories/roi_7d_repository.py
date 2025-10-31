"""
Repositorio para operaciones con la colección agent_roi_7d.

Esta colección es TEMPORAL y se limpia al inicio de cada nueva consulta.
Almacena el ROI calculado para ventanas de 7 días.

Author: Sistema Casterly Rock
Date: 2025-10-19
Version: 2.0
"""

import logging
from typing import List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError
from app.domain.entities.roi_7d import ROI7D

logger = logging.getLogger(__name__)


class ROI7DRepository:
    """
    Repositorio para la colección temporal agent_roi_7d.

    Esta colección almacena los cálculos de ROI de 7 días y se limpia
    completamente al inicio de cada nueva consulta.

    Attributes:
        collection: Colección MongoDB 'agent_roi_7d'
    """

    COLLECTION_NAME = "agent_roi_7d"

    def __init__(self, db: Database):
        """
        Inicializa el repositorio.

        Args:
            db: Instancia de la base de datos MongoDB
        """
        self.collection = db[self.COLLECTION_NAME]
        logger.info(f"ROI7DRepository inicializado con colección '{self.COLLECTION_NAME}'")

    async def clear_all(self) -> int:
        """
        Limpia TODOS los documentos de la colección.

        Este método se ejecuta al inicio de cada nueva consulta.

        Returns:
            Número de documentos eliminados

        Raises:
            PyMongoError: Si hay error al eliminar documentos
        """
        try:
            result = self.collection.delete_many({})
            deleted_count = result.deleted_count
            logger.info(
                f"Colección '{self.COLLECTION_NAME}' limpiada. "
                f"Eliminados: {deleted_count} documentos"
            )
            return deleted_count
        except PyMongoError as e:
            logger.error(f"Error al limpiar colección '{self.COLLECTION_NAME}': {e}")
            raise

    async def save(self, roi_7d: ROI7D) -> str:
        """
        Guarda o actualiza el cálculo de ROI de 7 días usando userId como clave.

        CAMBIO VERSION 2.1: Ahora usa UPSERT con userId + target_date como clave única.

        Args:
            roi_7d: Entidad ROI7D con los datos calculados

        Returns:
            ID del documento insertado/actualizado (como string)

        Raises:
            PyMongoError: Si hay error al guardar
            ValueError: Si roi_7d es None o userId está vacío
        """
        if roi_7d is None:
            raise ValueError("roi_7d no puede ser None")

        if not roi_7d.userId:
            raise ValueError("userId no puede estar vacío")

        try:
            roi_7d.createdAt = datetime.utcnow()
            roi_7d.updatedAt = datetime.utcnow()

            doc = roi_7d.dict(exclude_none=True)

            result = self.collection.update_one(
                {"userId": roi_7d.userId, "target_date": roi_7d.target_date},
                {"$set": doc},
                upsert=True
            )

            logger.debug(
                f"ROI 7D guardado: userId={roi_7d.userId}, "
                f"target_date={roi_7d.target_date}, roi={roi_7d.roi_7d_total:.4f}"
            )

            return str(result.upserted_id) if result.upserted_id else "updated"

        except PyMongoError as e:
            logger.error(
                f"Error al guardar ROI 7D: userId={roi_7d.userId}, "
                f"target_date={roi_7d.target_date}, error={e}"
            )
            raise

    async def find_by_agent_and_date(
        self, userId: str, target_date: str
    ) -> Optional[ROI7D]:
        """
        Busca el ROI_7D de un agente para una fecha target.

        CAMBIO VERSION 2.1: Ahora busca por userId (identificador único consistente).

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            ROI7D si existe, None si no se encuentra

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            doc = self.collection.find_one(
                {"userId": userId, "target_date": target_date}
            )

            if not doc:
                logger.debug(
                    f"ROI 7D no encontrado: userId={userId}, target_date={target_date}"
                )
                return None

            return ROI7D(**doc)

        except PyMongoError as e:
            logger.error(
                f"Error al buscar ROI 7D: userId={userId}, "
                f"target_date={target_date}, error={e}"
            )
            raise

    async def get_all_by_target_date(self, target_date: str) -> List[ROI7D]:
        """
        Obtiene ROI_7D de TODOS los agentes para una fecha target.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            Lista de ROI7D de todos los agentes

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = self.collection.find({"target_date": target_date})

            results = [ROI7D(**doc) for doc in cursor]

            logger.debug(
                f"ROIs 7D de todos los agentes: target_date={target_date}, "
                f"cantidad={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al buscar ROIs 7D por target_date: "
                f"target_date={target_date}, error={e}"
            )
            raise

    async def get_top_agents_by_roi(
        self, target_date: str, limit: int = 16
    ) -> List[ROI7D]:
        """
        Obtiene Top N agentes ordenados por ROI_7D descendente.

        Esta es la query principal para seleccionar el Top 16.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"
            limit: Número de agentes a retornar (default: 16)

        Returns:
            Lista de ROI7D de los Top N agentes ordenados por ROI

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = (
                self.collection.find({"target_date": target_date})
                .sort("roi_7d_total", -1)
                .limit(limit)
            )

            results = [ROI7D(**doc) for doc in cursor]

            logger.info(
                f"Top {limit} agentes obtenidos: target_date={target_date}, "
                f"encontrados={len(results)}"
            )

            if results:
                logger.debug(
                    f"Top 3: "
                    f"1) {results[0].userId} ({results[0].roi_7d_percentage}), "
                    f"2) {results[1].userId if len(results) > 1 else 'N/A'} "
                    f"({results[1].roi_7d_percentage if len(results) > 1 else 'N/A'}), "
                    f"3) {results[2].userId if len(results) > 2 else 'N/A'} "
                    f"({results[2].roi_7d_percentage if len(results) > 2 else 'N/A'})"
                )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al obtener top agentes: target_date={target_date}, "
                f"limit={limit}, error={e}"
            )
            raise

    async def get_agents_by_roi_range(
        self, target_date: str, min_roi: float, max_roi: float
    ) -> List[ROI7D]:
        """
        Filtra agentes por rango de ROI_7D.

        Útil para análisis de distribución de rendimiento.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"
            min_roi: ROI mínimo (ej: -0.10 para -10%)
            max_roi: ROI máximo (ej: 0.20 para 20%)

        Returns:
            Lista de ROI7D en el rango especificado, ordenados por ROI descendente

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = (
                self.collection.find(
                    {
                        "target_date": target_date,
                        "roi_7d_total": {"$gte": min_roi, "$lte": max_roi},
                    }
                )
                .sort("roi_7d_total", -1)
            )

            results = [ROI7D(**doc) for doc in cursor]

            logger.debug(
                f"Agentes en rango ROI: target_date={target_date}, "
                f"rango=[{min_roi:.2%}, {max_roi:.2%}], cantidad={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al buscar agentes por rango ROI: target_date={target_date}, "
                f"rango=[{min_roi}, {max_roi}], error={e}"
            )
            raise

    async def count_by_target_date(self, target_date: str) -> int:
        """
        Cuenta cuántos agentes tienen ROI_7D calculado para una fecha target.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            Número de documentos (agentes)

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            count = self.collection.count_documents({"target_date": target_date})
            logger.debug(
                f"Agentes con ROI 7D calculado: target_date={target_date}, count={count}"
            )
            return count

        except PyMongoError as e:
            logger.error(
                f"Error al contar ROIs 7D: target_date={target_date}, error={e}"
            )
            raise

    async def get_positive_roi_agents(self, target_date: str) -> List[ROI7D]:
        """
        Obtiene agentes con ROI_7D positivo.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            Lista de ROI7D con roi_7d_total > 0

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = (
                self.collection.find(
                    {"target_date": target_date, "roi_7d_total": {"$gt": 0}}
                )
                .sort("roi_7d_total", -1)
            )

            results = [ROI7D(**doc) for doc in cursor]

            logger.debug(
                f"Agentes con ROI positivo: target_date={target_date}, "
                f"cantidad={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al buscar agentes con ROI positivo: "
                f"target_date={target_date}, error={e}"
            )
            raise

    async def get_negative_roi_agents(self, target_date: str) -> List[ROI7D]:
        """
        Obtiene agentes con ROI_7D negativo.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            Lista de ROI7D con roi_7d_total < 0

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            cursor = (
                self.collection.find(
                    {"target_date": target_date, "roi_7d_total": {"$lt": 0}}
                )
                .sort("roi_7d_total", 1)
            )

            results = [ROI7D(**doc) for doc in cursor]

            logger.debug(
                f"Agentes con ROI negativo: target_date={target_date}, "
                f"cantidad={len(results)}"
            )

            return results

        except PyMongoError as e:
            logger.error(
                f"Error al buscar agentes con ROI negativo: "
                f"target_date={target_date}, error={e}"
            )
            raise

    async def delete_by_agent_and_date(
        self, userId: str, target_date: str
    ) -> bool:
        """
        Elimina el ROI_7D de un agente para una fecha target.

        CAMBIO VERSION 2.1: Ahora elimina por userId.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            True si se eliminó, False si no se encontró

        Raises:
            PyMongoError: Si hay error al eliminar
        """
        try:
            result = self.collection.delete_one(
                {"userId": userId, "target_date": target_date}
            )

            deleted = result.deleted_count > 0

            if deleted:
                logger.info(
                    f"ROI 7D eliminado: userId={userId}, target_date={target_date}"
                )
            else:
                logger.warning(
                    f"ROI 7D no encontrado para eliminar: "
                    f"userId={userId}, target_date={target_date}"
                )

            return deleted

        except PyMongoError as e:
            logger.error(
                f"Error al eliminar ROI 7D: userId={userId}, "
                f"target_date={target_date}, error={e}"
            )
            raise

    async def get_statistics_by_target_date(self, target_date: str) -> dict:
        """
        Obtiene estadísticas agregadas de ROI_7D para una fecha target.

        Args:
            target_date: Fecha target en formato "YYYY-MM-DD"

        Returns:
            Diccionario con estadísticas:
                - total_agents: Número total de agentes
                - avg_roi: ROI promedio
                - max_roi: ROI máximo
                - min_roi: ROI mínimo
                - positive_agents: Agentes con ROI > 0
                - negative_agents: Agentes con ROI < 0

        Raises:
            PyMongoError: Si hay error en la consulta
        """
        try:
            pipeline = [
                {"$match": {"target_date": target_date}},
                {
                    "$group": {
                        "_id": None,
                        "total_agents": {"$sum": 1},
                        "avg_roi": {"$avg": "$roi_7d_total"},
                        "max_roi": {"$max": "$roi_7d_total"},
                        "min_roi": {"$min": "$roi_7d_total"},
                        "positive_agents": {
                            "$sum": {"$cond": [{"$gt": ["$roi_7d_total", 0]}, 1, 0]}
                        },
                        "negative_agents": {
                            "$sum": {"$cond": [{"$lt": ["$roi_7d_total", 0]}, 1, 0]}
                        },
                    }
                },
            ]

            result = list(self.collection.aggregate(pipeline))

            if not result:
                return {
                    "total_agents": 0,
                    "avg_roi": 0.0,
                    "max_roi": 0.0,
                    "min_roi": 0.0,
                    "positive_agents": 0,
                    "negative_agents": 0,
                }

            stats = result[0]
            stats.pop("_id", None)

            logger.debug(
                f"Estadísticas calculadas: target_date={target_date}, stats={stats}"
            )

            return stats

        except PyMongoError as e:
            logger.error(
                f"Error al calcular estadísticas: target_date={target_date}, error={e}"
            )
            raise
