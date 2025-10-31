"""
Servicio para calcular el ROI diario de un agente.

Implementa la NUEVA LÓGICA:
1. Obtener balance del día
2. JOIN con movements del mismo día (usando agente_id, userId, createdAt)
3. Sumar todos los closedPnl
4. Calcular ROI = total_pnl / balance

Fórmula: ROI_dia = sum(closedPnl_i) / balance_base

Author: Sistema Casterly Rock
Date: 2025-10-19
Version: 2.0
"""

import logging
from typing import List, Dict, Optional
from datetime import date, datetime, time, timedelta
from pymongo.database import Database
from pymongo.errors import PyMongoError
from pydantic import ValidationError
import pytz
from app.domain.entities.daily_roi import DailyROI, TradeDetail
from app.infrastructure.repositories.daily_roi_repository import DailyROIRepository

logger = logging.getLogger(__name__)


class DailyROICalculationService:
    """
    Servicio para calcular el ROI diario de un agente.

    Este servicio ejecuta una query de agregación MongoDB que hace JOIN
    entre las colecciones 'balances' y 'mov07.10' usando tres llaves foráneas:
    - agente_id
    - userId
    - DATE(createdAt)

    Attributes:
        daily_roi_repo: Repositorio para guardar resultados
        db: Base de datos MongoDB
        balances_collection: Colección de balances
        movements_collection: Colección de movements (mov07.10)
    """

    def __init__(self, daily_roi_repo: DailyROIRepository, db: Database):
        """
        Inicializa el servicio.

        Args:
            daily_roi_repo: Repositorio DailyROI para guardar resultados
            db: Instancia de la base de datos MongoDB
        """
        self.daily_roi_repo = daily_roi_repo
        self.db = db
        self.balances_collection = db["balances"]
        self.movements_collection = db["mov07.10"]
        logger.info("DailyROICalculationService inicializado")

    async def calculate_roi_for_day(
        self, userId: str, target_date: date
    ) -> Optional[DailyROI]:
        """
        Calcula el ROI de un agente para un día específico.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador único.

        Este método:
        1. Verifica si ya existe en caché (busca por userId)
        2. Si no existe, ejecuta query de agregación MongoDB
        3. Guarda resultado en repositorio (caché)

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha del día a calcular

        Returns:
            DailyROI con el resultado, o None si no hay datos

        Raises:
            ValueError: Si userId es None o vacío
            PyMongoError: Si hay error en MongoDB
        """
        if not userId:
            raise ValueError("userId no puede ser None o vacío")

        target_date_str = target_date.isoformat()

        logger.debug(f"Calculando ROI diario: userId={userId}, fecha={target_date_str}")

        # Verificar si ya existe en caché (BUSCA POR userId)
        cached = await self.daily_roi_repo.find_by_agent_and_date(
            userId, target_date_str
        )
        if cached:
            logger.debug(
                f"ROI diario encontrado en caché: userId={userId}, "
                f"fecha={target_date_str}, roi={cached.roi_day:.4f}"
            )
            return cached

        # Ejecutar query de agregación
        result = await self._execute_aggregation_query(userId, target_date)

        if not result:
            logger.warning(
                f"No se encontraron datos para calcular ROI: "
                f"userId={userId}, fecha={target_date_str}"
            )
            return None

        # Convertir resultado a entidad DailyROI con protección contra balance=0
        try:
            daily_roi = self._build_daily_roi_entity(result)
        except ValidationError as e:
            # Verificar si el error es específicamente por balance_base
            error_str = str(e)
            if "balance_base" in error_str and ("greater than" in error_str or "gt" in error_str):
                balance_value = result.get("balance_base", "N/A")
                logger.warning(
                    f"Agente {userId} tiene balance invalido ({balance_value}) en {target_date_str}. "
                    f"No se puede calcular ROI. Este agente sera omitido en los calculos."
                )
                return None
            else:
                # Si es otro error de validación, propagarlo
                logger.error(
                    f"Error de validacion inesperado para userId={userId}, "
                    f"fecha={target_date_str}: {e}"
                )
                raise

        # Guardar en repositorio (caché)
        await self.daily_roi_repo.save(daily_roi)

        logger.info(
            f"ROI diario calculado y guardado: userId={userId}, "
            f"fecha={target_date_str}, roi={daily_roi.roi_day:.4f}, "
            f"pnl={daily_roi.total_pnl_day:.2f}, n_trades={daily_roi.n_trades}"
        )

        return daily_roi

    async def _execute_aggregation_query(
        self, userId: str, target_date: date
    ) -> Optional[Dict]:
        """
        Ejecuta la query de agregación MongoDB para obtener datos del día.

        CAMBIO VERSION 2.1: Ahora filtra por userId como identificador único.

        Esta query hace el JOIN entre balances y mov07.10 usando:
        - userId (principal, consistente entre días)
        - agente_id (secundario, para precisión en el JOIN)
        - DATE(createdAt)

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha objetivo

        Returns:
            Diccionario con datos agregados, o None si no hay resultados

        Raises:
            PyMongoError: Si hay error en la query
        """
        # Crear rango de fechas para el día completo (COMO STRINGS ISO)
        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, time.min))
        end_dt = tz.localize(datetime.combine(target_date, time.max))

        pipeline = [
            # PASO 1: Filtrar balance del día POR USERID Y BALANCE > 0
            {
                "$match": {
                    "userId": userId,
                    "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()},
                    "balance": {"$gt": 0}  # NUEVO: Filtrar balances <= 0 para evitar división por cero
                }
            },
            # PASO 2: JOIN con movements del mismo día
            {
                "$lookup": {
                    "from": "mov07.10",
                    "let": {
                        "bal_agente_id": "$agente_id",
                        "bal_userId": "$userId",
                        "bal_date": {"$substr": ["$createdAt", 0, 10]},
                    },
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$agente_id", "$$bal_agente_id"]},
                                        {"$eq": ["$userId", "$$bal_userId"]},
                                        {
                                            "$eq": [
                                                {"$substr": ["$createdAt", 0, 10]},
                                                "$$bal_date",
                                            ]
                                        },
                                    ]
                                }
                            }
                        },
                        {"$project": {"symbol": 1, "closedPnl": 1, "createdAt": 1}},
                    ],
                    "as": "trades",
                }
            },
            # PASO 3: Convertir closedPnl de String a Float
            {
                "$project": {
                    "agente_id": 1,
                    "userId": 1,
                    "balance": 1,
                    "date": {"$substr": ["$createdAt", 0, 10]},
                    "trades": {
                        "$map": {
                            "input": "$trades",
                            "as": "trade",
                            "in": {
                                "symbol": "$$trade.symbol",
                                "closedPnl": {
                                    "$toDouble": {
                                        "$replaceAll": {
                                            "input": "$$trade.closedPnl",
                                            "find": ",",
                                            "replacement": ".",
                                        }
                                    }
                                },
                                "createdAt": "$$trade.createdAt",
                            },
                        }
                    },
                }
            },
            # PASO 4: Calcular total_pnl y n_trades
            {
                "$addFields": {
                    "total_pnl_day": {"$sum": "$trades.closedPnl"},
                    "n_trades": {"$size": "$trades"},
                }
            },
            # PASO 5: Calcular ROI del día
            {
                "$addFields": {
                    "roi_day": {
                        "$cond": {
                            "if": {"$gt": ["$balance", 0]},
                            "then": {"$divide": ["$total_pnl_day", "$balance"]},
                            "else": 0,
                        }
                    }
                }
            },
            # PASO 6: Formatear trades con roi_trade
            {
                "$project": {
                    "date": 1,
                    "agente_id": 1,
                    "userId": 1,
                    "balance_base": "$balance",
                    "trades": {
                        "$map": {
                            "input": "$trades",
                            "as": "trade",
                            "in": {
                                "symbol": "$$trade.symbol",
                                "closedPnl": "$$trade.closedPnl",
                                "roi_trade": {
                                    "$divide": ["$$trade.closedPnl", "$balance"]
                                },
                                "createdAt": "$$trade.createdAt",
                            },
                        }
                    },
                    "total_pnl_day": 1,
                    "roi_day": 1,
                    "n_trades": 1,
                }
            },
        ]

        try:
            cursor = self.balances_collection.aggregate(pipeline)
            results = list(cursor)

            if not results:
                logger.debug(
                    f"Query de agregación sin resultados: userId={userId}, "
                    f"fecha={target_date.isoformat()}"
                )
                return None

            logger.debug(
                f"Query de agregación exitosa: userId={userId}, "
                f"fecha={target_date.isoformat()}, trades={results[0].get('n_trades', 0)}"
            )

            return results[0]

        except PyMongoError as e:
            logger.error(
                f"Error en query de agregación: userId={userId}, "
                f"fecha={target_date.isoformat()}, error={e}"
            )
            raise

    def _build_daily_roi_entity(self, query_result: Dict) -> DailyROI:
        """
        Convierte el resultado de la query en una entidad DailyROI.

        Args:
            query_result: Resultado de la query de agregación

        Returns:
            Entidad DailyROI construida

        Raises:
            ValueError: Si faltan campos requeridos
        """
        try:
            trades = [
                TradeDetail(
                    symbol=t["symbol"],
                    closedPnl=t["closedPnl"],
                    roi_trade=t["roi_trade"],
                    createdAt=t["createdAt"],
                )
                for t in query_result.get("trades", [])
            ]

            # Calcular balance_start y balance_end
            balance_base_value = query_result["balance_base"]
            total_pnl = query_result["total_pnl_day"]

            return DailyROI(
                date=query_result["date"],
                agente_id=query_result["agente_id"],
                userId=query_result["userId"],
                balance_base=balance_base_value,
                balance_start=balance_base_value,
                balance_end=balance_base_value + total_pnl,
                trades=trades,
                total_pnl_day=total_pnl,
                roi_day=query_result["roi_day"],
                n_trades=query_result["n_trades"],
            )

        except KeyError as e:
            logger.error(
                f"Error al construir DailyROI: falta campo {e}, "
                f"query_result={query_result}"
            )
            raise ValueError(f"Falta campo requerido en query result: {e}")

    async def calculate_for_multiple_days(
        self, userId: str, start_date: date, end_date: date
    ) -> List[DailyROI]:
        """
        Calcula ROI diario para múltiples días consecutivos.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador.

        Este método itera sobre cada día en el rango y calcula su ROI.
        Los resultados se guardan en caché automáticamente.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            start_date: Fecha inicio del rango
            end_date: Fecha fin del rango

        Returns:
            Lista de DailyROI para cada día en el rango (solo días con datos)

        Raises:
            ValueError: Si start_date > end_date
        """
        if start_date > end_date:
            raise ValueError(
                f"start_date ({start_date}) debe ser <= end_date ({end_date})"
            )

        logger.info(
            f"Calculando ROI para múltiples días: userId={userId}, "
            f"rango=[{start_date.isoformat()}, {end_date.isoformat()}]"
        )

        results = []
        current_date = start_date
        days_processed = 0
        days_with_data = 0

        while current_date <= end_date:
            daily_roi = await self.calculate_roi_for_day(userId, current_date)
            days_processed += 1

            if daily_roi:
                results.append(daily_roi)
                days_with_data += 1

            current_date += timedelta(days=1)

        logger.info(
            f"ROI múltiples días completado: userId={userId}, "
            f"días_procesados={days_processed}, días_con_datos={days_with_data}"
        )

        return results

    async def calculate_for_multiple_agents(
        self, agent_ids: List[str], target_date: date
    ) -> List[DailyROI]:
        """
        Calcula ROI diario para múltiples agentes en una fecha.

        Args:
            agent_ids: Lista de IDs de agentes
            target_date: Fecha objetivo

        Returns:
            Lista de DailyROI (solo agentes con datos)

        Raises:
            ValueError: Si agent_ids está vacía
        """
        if not agent_ids:
            raise ValueError("agent_ids no puede estar vacía")

        logger.info(
            f"Calculando ROI para múltiples agentes: "
            f"fecha={target_date.isoformat()}, n_agentes={len(agent_ids)}"
        )

        results = []
        agents_with_data = 0

        for agent_id in agent_ids:
            daily_roi = await self.calculate_roi_for_day(agent_id, target_date)

            if daily_roi:
                results.append(daily_roi)
                agents_with_data += 1

        logger.info(
            f"ROI múltiples agentes completado: fecha={target_date.isoformat()}, "
            f"agentes_procesados={len(agent_ids)}, agentes_con_datos={agents_with_data}"
        )

        return results
