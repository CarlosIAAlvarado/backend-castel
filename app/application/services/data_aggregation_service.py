from typing import List, Dict, Any, Tuple, Optional, TYPE_CHECKING
from datetime import date, timedelta
from collections import defaultdict
import logging

if TYPE_CHECKING:
    from app.application.services.movement_query_service import MovementQueryService
    from app.application.services.balance_query_service import BalanceQueryService

logger = logging.getLogger(__name__)


class DataAggregationService:
    """
    Servicio especializado en agregacion y procesamiento de datos.

    Responsabilidad unica: Agregar movimientos y calcular metricas.
    Cumple con Single Responsibility Principle (SRP).
    """

    def __init__(
        self,
        movement_query_service: 'MovementQueryService',
        balance_query_service: 'BalanceQueryService'
    ):
        """
        Constructor con inyeccion de dependencias.

        Args:
            movement_query_service: Servicio de consultas de movimientos
            balance_query_service: Servicio de consultas de balances
        """
        self.movement_query_service = movement_query_service
        self.balance_query_service = balance_query_service

    @staticmethod
    def aggregate_movements_by_day_and_agent(
        movements: List[Dict[str, Any]]
    ) -> Dict[Tuple[date, str], Dict[str, Any]]:
        """
        Agrega movimientos por dia y agente.

        Args:
            movements: Lista de movimientos

        Returns:
            Diccionario agregado con clave (fecha, agent_id)
        """
        aggregated = defaultdict(lambda: {
            "pnl_total": 0.0,
            "operations_count": 0,
            "symbols": set(),
            "operations": []
        })

        for mov in movements:
            agent_id = mov.get("agent_id")
            date_str = mov.get("date")

            if not agent_id or not date_str:
                continue

            try:
                operation_date = date.fromisoformat(date_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid date format for date_str '{date_str}': {e}")
                continue

            pnl = mov.get("closed_pnl", 0.0)
            key = (operation_date, agent_id)

            aggregated[key]["pnl_total"] += pnl
            aggregated[key]["operations_count"] += 1
            aggregated[key]["symbols"].add(mov.get("symbol", ""))
            aggregated[key]["operations"].append({
                "symbol": mov.get("symbol"),
                "side": mov.get("side"),
                "pnl": pnl,
                "qty": mov.get("qty"),
                "time": date_str
            })

        for key in aggregated:
            aggregated[key]["symbols"] = list(aggregated[key]["symbols"])

        return dict(aggregated)

    def match_movements_with_balances(
        self,
        aggregated_movements: Dict[Tuple[date, str], Dict[str, Any]],
        target_date: date
    ) -> Dict[Tuple[date, str], Dict[str, Any]]:
        """
        Empareja movimientos con balances y calcula ROI.

        Args:
            aggregated_movements: Movimientos agregados
            target_date: Fecha objetivo

        Returns:
            Movimientos enriquecidos con ROI
        """
        previous_date = target_date - timedelta(days=1)
        balances = self.balance_query_service.get_all_balances_by_date(previous_date)

        enriched_data = {}

        for (operation_date, agent_id), data in aggregated_movements.items():
            if operation_date != target_date:
                continue

            balance_eod = balances.get(agent_id, 0.0)

            roi_day = 0.0
            if balance_eod > 0:
                roi_day = (data["pnl_total"] / balance_eod) * 100

            enriched_data[(operation_date, agent_id)] = {
                **data,
                "balance_eod_previous": balance_eod,
                "roi_day": roi_day
            }

        return enriched_data

    def get_agent_data_with_lookback(
        self,
        agent_id: str,
        target_date: date,
        lookback_days: int = 7,
        balances_cache: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Obtiene datos agregados de un agente con ventana temporal.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo
            lookback_days: Dias hacia atras
            balances_cache: Cache de balances pre-cargados

        Returns:
            Diccionario con total_pnl, balance_current, roi_period y daily_data
        """
        start_date = target_date - timedelta(days=lookback_days - 1)

        movements = self.movement_query_service.get_movements_by_date_range(
            start_date=start_date,
            end_date=target_date,
            agent_id=agent_id
        )

        aggregated = self.aggregate_movements_by_day_and_agent(movements)

        total_pnl = 0.0
        daily_data = []

        for day_offset in range(lookback_days):
            current_date = start_date + timedelta(days=day_offset)
            key = (current_date, agent_id)

            if key in aggregated:
                pnl_day = aggregated[key]["pnl_total"]
                total_pnl += pnl_day
                daily_data.append({
                    "date": current_date.isoformat(),
                    "pnl": pnl_day,
                    "operations": aggregated[key]["operations_count"]
                })
            else:
                daily_data.append({
                    "date": current_date.isoformat(),
                    "pnl": 0.0,
                    "operations": 0
                })

        if balances_cache is not None:
            balance_current = balances_cache.get(agent_id, 0.0)
        else:
            balance_current = self.balance_query_service.get_all_balances_by_date(target_date).get(agent_id, 0.0)

        roi_period = 0.0
        if balance_current > 0:
            roi_period = (total_pnl / balance_current) * 100

        return {
            "agent_id": agent_id,
            "target_date": target_date.isoformat(),
            "lookback_days": lookback_days,
            "total_pnl": total_pnl,
            "balance_current": balance_current,
            "roi_period": roi_period,
            "daily_data": daily_data
        }
