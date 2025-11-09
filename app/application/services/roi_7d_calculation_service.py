"""
Servicio para calcular el ROI de 7 días de un agente.

Implementa la NUEVA LÓGICA (compuesta):
1. Calcular ROI diario para cada día en la ventana [T-7, T]
2. Agregar usando fórmula compuesta (multiplicativa)
3. Guardar resultado en agent_roi_7d

Fórmula (financieramente correcta):
ROI_7D = (1 + ROI_día_1) * (1 + ROI_día_2) * ... * (1 + ROI_día_N) - 1

Author: Sistema Casterly Rock
Date: 2025-10-19
Version: 2.1
"""

import logging
from typing import List, Optional
from datetime import date, timedelta
from app.domain.entities.roi_7d import ROI7D, DailyROISummary
from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository
from app.application.services.daily_roi_calculation_service import (
    DailyROICalculationService,
)

logger = logging.getLogger(__name__)


class ROI7DCalculationService:
    """
    Servicio para calcular el ROI de 7 días de un agente.

    Este servicio:
    1. Usa DailyROICalculationService para obtener ROIs diarios
    2. Suma los ROIs diarios de la ventana [target_date - 7, target_date]
    3. Guarda el resultado en agent_roi_7d (caché)

    La ventana de 7 días incluye 8 días de datos:
    [target_date - 7 días, target_date]

    Attributes:
        roi_7d_repo: Repositorio para guardar resultados
        daily_roi_service: Servicio para calcular ROIs diarios
    """

    WINDOW_SIZE_DAYS = 7

    def __init__(
        self,
        roi_7d_repo: ROI7DRepository,
        daily_roi_service: DailyROICalculationService,
    ):
        """
        Inicializa el servicio.

        Args:
            roi_7d_repo: Repositorio ROI7D
            daily_roi_service: Servicio para calcular ROIs diarios
        """
        self.roi_7d_repo = roi_7d_repo
        self.daily_roi_service = daily_roi_service
        logger.info("ROI7DCalculationService inicializado")

    async def calculate_roi_7d(
        self, userId: str, target_date: date
    ) -> Optional[ROI7D]:
        """
        Calcula el ROI de 7 días para un agente.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador único.

        Ventana: [target_date - 7 días, target_date] (8 días totales)

        Este método:
        1. Verifica si ya existe en caché (busca por userId)
        2. Si no existe, calcula ROI diario para cada día de la ventana
        3. Suma todos los ROIs diarios
        4. Guarda resultado en repositorio

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha final de la ventana

        Returns:
            ROI7D con el resultado calculado, o None si no hay suficientes datos

        Raises:
            ValueError: Si userId es None o vacío
        """
        if not userId:
            raise ValueError("userId no puede ser None o vacío")

        target_date_str = target_date.isoformat()

        logger.debug(
            f"Calculando ROI 7D: userId={userId}, target_date={target_date_str}"
        )

        # Verificar si ya existe en caché (BUSCA POR userId)
        cached = await self.roi_7d_repo.find_by_agent_and_date(
            userId, target_date_str
        )
        if cached:
            logger.debug(
                f"ROI 7D encontrado en caché: userId={userId}, "
                f"target_date={target_date_str}, roi={cached.roi_7d_total:.4f}"
            )
            return cached

        # Definir ventana de 7 días
        window_start = target_date - timedelta(days=self.WINDOW_SIZE_DAYS)
        window_end = target_date

        logger.debug(
            f"Ventana 7D: [{window_start.isoformat()}, {window_end.isoformat()}]"
        )

        # Calcular ROI diario para cada día (USANDO userId)
        daily_rois = await self.daily_roi_service.calculate_for_multiple_days(
            userId, window_start, window_end
        )

        if not daily_rois:
            logger.warning(
                f"No se encontraron datos para calcular ROI 7D: "
                f"userId={userId}, target_date={target_date_str}"
            )
            return None

        # Validar que tengamos ventana completa (8 días)
        if len(daily_rois) < 8:
            logger.warning(
                f"Ventana incompleta para ROI 7D: userId={userId}, "
                f"target_date={target_date_str}, días_encontrados={len(daily_rois)}/8"
            )

        # Calcular métricas agregadas
        roi_7d = self._calculate_aggregated_metrics(
            userId,
            target_date_str,
            window_start.isoformat(),
            window_end.isoformat(),
            daily_rois,
        )

        # Guardar en repositorio
        await self.roi_7d_repo.save(roi_7d)

        logger.info(
            f"ROI 7D calculado y guardado: userId={userId}, "
            f"target_date={target_date_str}, roi={roi_7d.roi_7d_total:.4f} "
            f"({roi_7d.roi_7d_percentage}), días={len(daily_rois)}, "
            f"trades={roi_7d.total_trades_7d}"
        )

        return roi_7d

    def _calculate_aggregated_metrics(
        self,
        userId: str,
        target_date: str,
        window_start: str,
        window_end: str,
        daily_rois: List,
    ) -> ROI7D:
        """
        Calcula las métricas agregadas a partir de los ROIs diarios.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha target
            window_start: Fecha inicio ventana
            window_end: Fecha fin ventana
            daily_rois: Lista de DailyROI de la ventana

        Returns:
            Entidad ROI7D con métricas calculadas
        """
        # Crear resúmenes diarios
        daily_roi_summaries = [
            DailyROISummary(
                date=dr.date, roi=dr.roi_day, pnl=dr.total_pnl_day, n_trades=dr.n_trades
            )
            for dr in daily_rois
        ]

        # Calcular ROI total usando fórmula compuesta (multiplicativa)
        roi_compound = 1.0
        for dr in daily_rois:
            roi_compound *= (1.0 + dr.roi_day)
        roi_7d_total = roi_compound - 1.0
        total_pnl_7d = sum(dr.total_pnl_day for dr in daily_rois)
        total_trades_7d = sum(dr.n_trades for dr in daily_rois)

        # Calcular métricas adicionales
        n_days = len(daily_rois)
        avg_roi_per_day = roi_7d_total / n_days if n_days > 0 else 0.0
        positive_days = sum(1 for dr in daily_rois if dr.roi_day > 0)
        negative_days = sum(1 for dr in daily_rois if dr.roi_day < 0)

        # Formatear porcentaje
        roi_7d_percentage = f"{roi_7d_total * 100:.2f}%"

        # Obtener agente_id del primer DailyROI (opcional, para referencia)
        agente_id = daily_rois[0].agente_id if daily_rois else None

        logger.debug(
            f"Métricas calculadas: userId={userId}, roi_total={roi_7d_total:.4f}, "
            f"pnl_total={total_pnl_7d:.2f}, trades={total_trades_7d}, "
            f"días_positivos={positive_days}, días_negativos={negative_days}"
        )

        return ROI7D(
            target_date=target_date,
            userId=userId,
            agente_id=agente_id,
            window_start=window_start,
            window_end=window_end,
            daily_rois=daily_roi_summaries,
            roi_7d_total=roi_7d_total,
            roi_7d_percentage=roi_7d_percentage,
            total_pnl_7d=total_pnl_7d,
            total_trades_7d=total_trades_7d,
            avg_roi_per_day=avg_roi_per_day,
            positive_days=positive_days,
            negative_days=negative_days,
        )

    async def calculate_for_all_agents(
        self, agent_ids: List[str], target_date: date
    ) -> List[ROI7D]:
        """
        Calcula ROI_7D para una lista de agentes.

        Este método procesa todos los agentes en paralelo conceptualmente
        (aunque Python asyncio no es verdadero paralelismo).

        Args:
            agent_ids: Lista de IDs de agentes
            target_date: Fecha target para la ventana

        Returns:
            Lista de ROI7D para cada agente (solo agentes con datos)

        Raises:
            ValueError: Si agent_ids está vacía
        """
        if not agent_ids:
            raise ValueError("agent_ids no puede estar vacía")

        logger.info(
            f"Calculando ROI 7D para múltiples agentes: "
            f"target_date={target_date.isoformat()}, n_agentes={len(agent_ids)}"
        )

        results = []
        agents_with_data = 0

        for agent_id in agent_ids:
            roi_7d = await self.calculate_roi_7d(agent_id, target_date)

            if roi_7d:
                results.append(roi_7d)
                agents_with_data += 1

        logger.info(
            f"ROI 7D para múltiples agentes completado: "
            f"target_date={target_date.isoformat()}, "
            f"agentes_procesados={len(agent_ids)}, agentes_con_datos={agents_with_data}"
        )

        return results

    async def get_top_agents(
        self, target_date: date, limit: int = 16
    ) -> List[ROI7D]:
        """
        Obtiene los Top N agentes por ROI_7D.

        Este método asume que los ROI_7D ya fueron calculados previamente
        y solo consulta el repositorio.

        Args:
            target_date: Fecha target
            limit: Número de agentes a retornar (default: 16)

        Returns:
            Lista de ROI7D ordenados por ROI descendente

        Raises:
            ValueError: Si limit <= 0
        """
        if limit <= 0:
            raise ValueError("limit debe ser mayor a 0")

        target_date_str = target_date.isoformat()

        logger.debug(
            f"Obteniendo top {limit} agentes: target_date={target_date_str}"
        )

        top_agents = await self.roi_7d_repo.get_top_agents_by_roi(
            target_date_str, limit
        )

        logger.info(
            f"Top {limit} agentes obtenidos: target_date={target_date_str}, "
            f"encontrados={len(top_agents)}"
        )

        return top_agents

    async def get_performance_distribution(
        self, target_date: date
    ) -> dict:
        """
        Obtiene la distribución de rendimiento de agentes.

        Returns:
            Diccionario con:
                - total_agents: Total de agentes
                - positive_roi: Agentes con ROI > 0
                - negative_roi: Agentes con ROI < 0
                - neutral_roi: Agentes con ROI = 0
                - avg_roi: ROI promedio
                - max_roi: ROI máximo
                - min_roi: ROI mínimo
        """
        target_date_str = target_date.isoformat()

        logger.debug(
            f"Calculando distribución de rendimiento: target_date={target_date_str}"
        )

        stats = await self.roi_7d_repo.get_statistics_by_target_date(target_date_str)

        neutral_agents = stats["total_agents"] - (
            stats["positive_agents"] + stats["negative_agents"]
        )

        distribution = {
            "target_date": target_date_str,
            "total_agents": stats["total_agents"],
            "positive_roi": stats["positive_agents"],
            "negative_roi": stats["negative_agents"],
            "neutral_roi": neutral_agents,
            "avg_roi": stats["avg_roi"],
            "max_roi": stats["max_roi"],
            "min_roi": stats["min_roi"],
        }

        logger.info(
            f"Distribución calculada: target_date={target_date_str}, "
            f"total={distribution['total_agents']}, "
            f"pos={distribution['positive_roi']}, "
            f"neg={distribution['negative_roi']}"
        )

        return distribution

    async def validate_complete_window(
        self, userId: str, target_date: date
    ) -> bool:
        """
        Valida si un agente tiene una ventana completa de 7 días.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha target

        Returns:
            True si tiene 8 días completos, False si no
        """
        roi_7d = await self.calculate_roi_7d(userId, target_date)

        if not roi_7d:
            return False

        return roi_7d.is_complete_window()
