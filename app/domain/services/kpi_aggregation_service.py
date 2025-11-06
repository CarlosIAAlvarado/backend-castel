"""
KPI Aggregation Service (Domain Layer).

Servicio de dominio para recalcular KPIs de simulaciones existentes
con diferentes ventanas de tiempo sin necesidad de re-ejecutar la simulacion.

Responsabilidades:
- Recalcular KPIs para ventanas de 3, 5, 10, 15, 30 dias desde datos almacenados
- Filtrar daily_rois por rangos de fechas especificos
- Calcular metricas: ROI total, promedio, volatilidad, drawdown, win rate, Sharpe ratio
- Obtener Top16 filtrado por ventana
- Calcular metricas diarias para graficos

NO depende de infraestructura directamente (recibe db como parametro).
"""

from typing import List, Dict, Any, Optional
from datetime import date, timedelta
import logging

from app.domain.entities.simulation import (
    SimulationKPIs,
    TopAgentSummary,
    DailyMetric
)

logger = logging.getLogger(__name__)


class KPIAggregationService:
    """
    Servicio de dominio para agregacion y recalculo de KPIs.

    Permite analizar simulaciones existentes con diferentes ventanas temporales
    sin necesidad de re-ejecutar toda la simulacion.
    """

    def __init__(self, db):
        """
        Inicializa el servicio con acceso a la base de datos.

        Args:
            db: Instancia de base de datos MongoDB
        """
        self.db = db

    def get_filtered_kpis(
        self,
        simulation_id: str,
        window_days: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Obtiene KPIs recalculados para una ventana de tiempo especifica.

        Args:
            simulation_id: ID de la simulacion
            window_days: Ventana de dias para calcular KPIs (3, 5, 10, 15, 30)
            start_date: Fecha inicial de la ventana
            end_date: Fecha final de la ventana (target_date)

        Returns:
            Dict con kpis, top_16_final y daily_metrics recalculados

        Raises:
            ValueError: Si los parametros no son validos
        """
        # Validar ventana
        if window_days not in [3, 5, 10, 15, 30]:
            raise ValueError(f"window_days debe ser 3, 5, 10, 15 o 30. Recibido: {window_days}")

        # Validar rango de fechas
        total_days = (end_date - start_date).days + 1
        if total_days != window_days:
            raise ValueError(
                f"El rango de fechas ({total_days} dias) no coincide con window_days ({window_days})"
            )

        logger.info(
            f"Recalculando KPIs para simulation_id={simulation_id}, "
            f"window_days={window_days}, start_date={start_date}, end_date={end_date}"
        )

        # 1. Obtener Top16 para la ventana especifica
        top16_data = self._get_top16_for_window(end_date, window_days)
        top16_agent_ids = [agent.agent_id for agent in top16_data]

        # 2. Calcular KPIs desde la coleccion ROI dinamica
        kpis_data = self._calculate_kpis_from_roi_collection(
            end_date=end_date,
            top16_agent_ids=top16_agent_ids,
            window_days=window_days,
            start_date=start_date
        )

        # 3. Calcular metricas diarias
        daily_metrics_data = self._calculate_daily_metrics_for_window(
            start_date=start_date,
            end_date=end_date,
            top16_agent_ids=top16_agent_ids,
            window_days=window_days
        )

        return {
            "success": True,
            "simulation_id": simulation_id,
            "window_days": window_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "kpis": kpis_data.model_dump(),
            "top_16_final": [agent.model_dump() for agent in top16_data],
            "daily_metrics": [metric.model_dump() for metric in daily_metrics_data]
        }

    def _get_top16_for_window(self, end_date: date, window_days: int) -> List[TopAgentSummary]:
        """
        Obtiene el Top 16 desde la coleccion dinamica top16_XD.

        Args:
            end_date: Fecha objetivo (target_date)
            window_days: Ventana de dias (determina la coleccion: top16_3d, top16_5d, etc.)

        Returns:
            Lista de TopAgentSummary ordenados por rank
        """
        from app.utils.collection_names import get_top16_collection_name

        top16_collection_name = get_top16_collection_name(window_days)
        top16_collection = self.db[top16_collection_name]

        logger.info(f"Obteniendo Top16 desde: {top16_collection_name} para fecha: {end_date}")

        top16_docs = list(top16_collection.find({
            "date": end_date.isoformat()
        }).sort("rank", 1))

        if not top16_docs:
            logger.warning(
                f"No se encontraron datos en {top16_collection_name} para fecha {end_date}"
            )
            return []

        roi_field = f"roi_{window_days}d"
        return [
            TopAgentSummary(
                rank=doc.get("rank"),
                agent_id=doc.get("agent_id"),
                roi_7d=doc.get(roi_field, 0.0),
                total_aum=doc.get("total_aum", 0.0),
                n_accounts=doc.get("n_accounts", 0),
                is_in_casterly=doc.get("is_in_casterly", False)
            )
            for doc in top16_docs
        ]

    def _calculate_kpis_from_roi_collection(
        self,
        end_date: date,
        top16_agent_ids: List[str],
        window_days: int,
        start_date: date
    ) -> SimulationKPIs:
        """
        Calcula KPIs desde la coleccion ROI dinamica (agent_roi_XD).

        Args:
            end_date: Fecha objetivo
            top16_agent_ids: Lista de IDs de agentes Top16
            window_days: Ventana de dias
            start_date: Fecha inicial (para filtrar daily_rois correctamente)

        Returns:
            SimulationKPIs con metricas calculadas
        """
        from app.utils.collection_names import get_roi_collection_name

        roi_collection_name = get_roi_collection_name(window_days)
        roi_collection = self.db[roi_collection_name]

        logger.info(f"Calculando KPIs desde: {roi_collection_name}")

        # Obtener documentos ROI de los Top16 agentes
        roi_docs = list(roi_collection.find({
            "target_date": end_date.isoformat(),
            "userId": {"$in": top16_agent_ids}
        }))

        if not roi_docs:
            logger.warning(f"No se encontraron datos ROI para los Top16 agentes en {roi_collection_name}")
            return SimulationKPIs(
                total_roi=0.0,
                avg_roi=0.0,
                volatility=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                active_agents_count=0,
                unique_agents_in_period=0,
                sharpe_ratio=None
            )

        # Filtrar daily_rois para el rango especifico
        filtered_roi_docs = self._filter_roi_docs_by_date_range(
            roi_docs, start_date, end_date, window_days
        )

        # Calcular metricas
        total_agents = len(filtered_roi_docs)
        total_roi = sum(doc.get("filtered_roi_total", 0.0) for doc in filtered_roi_docs)
        avg_roi = total_roi / total_agents if total_agents > 0 else 0.0

        # Volatilidad
        all_daily_rois = []
        for doc in filtered_roi_docs:
            daily_rois_list = doc.get("filtered_daily_rois", [])
            for day in daily_rois_list:
                roi = day.get("roi", 0.0)
                if roi != 0:
                    all_daily_rois.append(roi)

        if len(all_daily_rois) > 1:
            mean_roi = sum(all_daily_rois) / len(all_daily_rois)
            variance = sum((x - mean_roi) ** 2 for x in all_daily_rois) / len(all_daily_rois)
            volatility = variance ** 0.5
        else:
            volatility = 0.0

        # Max Drawdown
        max_drawdown = 0.0
        for doc in filtered_roi_docs:
            daily_rois_list = doc.get("filtered_daily_rois", [])
            if len(daily_rois_list) >= 2:
                cumulative = [1.0]
                for day in daily_rois_list:
                    roi = day.get("roi", 0)
                    cumulative.append(cumulative[-1] * (1 + roi))

                peak = cumulative[0]
                for value in cumulative:
                    if value > peak:
                        peak = value
                    drawdown = (value - peak) / peak if peak > 0 else 0
                    if drawdown < max_drawdown:
                        max_drawdown = drawdown

        # Win Rate
        positive_agents = sum(1 for doc in filtered_roi_docs if doc.get("filtered_roi_total", 0.0) > 0)
        win_rate = positive_agents / total_agents if total_agents > 0 else 0.0

        # Sharpe Ratio
        sharpe_ratio = None
        if volatility > 0:
            sharpe_ratio = avg_roi / volatility

        return SimulationKPIs(
            total_roi=total_roi,
            avg_roi=avg_roi,
            volatility=volatility,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            active_agents_count=len(filtered_roi_docs),
            unique_agents_in_period=total_agents,
            sharpe_ratio=sharpe_ratio
        )

    def _filter_roi_docs_by_date_range(
        self,
        roi_docs: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        window_days: int
    ) -> List[Dict[str, Any]]:
        """
        Filtra los daily_rois de cada documento ROI para incluir solo los dias en el rango.

        Args:
            roi_docs: Documentos ROI desde MongoDB
            start_date: Fecha inicial del rango
            end_date: Fecha final del rango
            window_days: Ventana de dias

        Returns:
            Lista de documentos ROI con daily_rois filtrados y roi_total recalculado
        """
        filtered_docs = []

        for doc in roi_docs:
            daily_rois_list = doc.get("daily_rois", [])

            # Calcular el indice de inicio basado en window_days y el rango deseado
            # Los daily_rois tienen window_days elementos, y queremos filtrar desde start_date hasta end_date
            total_days_in_range = (end_date - start_date).days + 1

            # Asumimos que daily_rois[0] corresponde a (end_date - window_days + 1)
            # y daily_rois[-1] corresponde a end_date

            # Calcular offset: cuantos dias hay desde el inicio de daily_rois hasta start_date
            base_start_date = end_date - timedelta(days=window_days - 1)
            offset = (start_date - base_start_date).days

            if offset < 0:
                offset = 0

            # Extraer los dias relevantes
            filtered_daily_rois = daily_rois_list[offset:offset + total_days_in_range]

            # Recalcular ROI total para el rango filtrado
            filtered_roi_total = sum(day.get("roi", 0.0) for day in filtered_daily_rois)

            filtered_doc = doc.copy()
            filtered_doc["filtered_daily_rois"] = filtered_daily_rois
            filtered_doc["filtered_roi_total"] = filtered_roi_total

            filtered_docs.append(filtered_doc)

        return filtered_docs

    def _calculate_daily_metrics_for_window(
        self,
        start_date: date,
        end_date: date,
        top16_agent_ids: List[str],
        window_days: int
    ) -> List[DailyMetric]:
        """
        Calcula metricas diarias para graficos de evolucion.

        Args:
            start_date: Fecha inicial
            end_date: Fecha final
            top16_agent_ids: Lista de IDs de agentes Top16
            window_days: Ventana de dias

        Returns:
            Lista de DailyMetric para cada dia en el rango
        """
        from app.utils.collection_names import get_roi_collection_name

        roi_collection_name = get_roi_collection_name(window_days)
        agent_roi_collection = self.db[roi_collection_name]

        logger.info(f"Calculando daily_metrics desde: {roi_collection_name}")

        # Obtener documentos ROI
        roi_docs = list(agent_roi_collection.find({
            "userId": {"$in": top16_agent_ids},
            "target_date": end_date.isoformat()
        }))

        if not roi_docs:
            logger.warning(f"No se encontraron datos para calcular daily_metrics")
            return []

        # Filtrar daily_rois
        filtered_roi_docs = self._filter_roi_docs_by_date_range(
            roi_docs, start_date, end_date, window_days
        )

        # Calcular metricas por dia
        num_days = (end_date - start_date).days + 1
        daily_metrics = []
        cumulative_roi = 0.0

        for day_index in range(num_days):
            current_date = start_date + timedelta(days=day_index)

            daily_roi_sum = 0.0
            active_agents = 0
            total_pnl = 0.0

            for doc in filtered_roi_docs:
                daily_rois_list = doc.get("filtered_daily_rois", [])

                if day_index < len(daily_rois_list):
                    day_data = daily_rois_list[day_index]
                    roi = day_data.get("roi", 0.0)
                    pnl = day_data.get("pnl", 0.0)

                    daily_roi_sum += roi
                    total_pnl += pnl

                    if roi != 0.0:
                        active_agents += 1

            cumulative_roi += daily_roi_sum

            daily_metrics.append(DailyMetric(
                date=current_date,
                roi_cumulative=cumulative_roi,
                active_agents=active_agents,
                total_pnl=total_pnl
            ))

        logger.info(f"daily_metrics generados: {len(daily_metrics)} dias")
        return daily_metrics
