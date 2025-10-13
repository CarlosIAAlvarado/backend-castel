from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from collections import defaultdict
from app.config.database import database_manager
from app.infrastructure.utils.data_normalizer import normalizer
import pytz


class DataProcessingService:
    """
    Servicio para procesamiento y agregacion de datos de movimientos y balances.

    Proporciona metodos para:
    - Obtener movimientos por rango de fechas
    - Agregar operaciones por dia y agente
    - Emparejar movimientos con balances
    - Calcular ROI diario
    - Obtener datos con ventana temporal (lookback)
    """

    @staticmethod
    def get_date_range(start_date: date, end_date: date) -> List[date]:
        """
        Genera una lista de fechas consecutivas entre start_date y end_date (inclusive).

        Args:
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Lista de fechas desde start_date hasta end_date
        """
        date_list = []
        current = start_date
        while current <= end_date:
            date_list.append(current)
            current += timedelta(days=1)
        return date_list

    @staticmethod
    def normalize_date_to_bogota(dt: datetime) -> datetime:
        """
        Normaliza un datetime a la zona horaria de Bogota.

        Args:
            dt: Datetime a normalizar

        Returns:
            Datetime con timezone America/Bogota
        """
        return normalizer.normalize_datetime(dt)

    @staticmethod
    def get_movements_by_date_range(
        start_date: date,
        end_date: date,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene movimientos (operaciones) de la BD filtrados por rango de fechas y agente.

        Optimizado para filtrar directamente en MongoDB.

        Args:
            start_date: Fecha inicial del rango
            end_date: Fecha final del rango
            agent_id: ID del agente (opcional). Si no se especifica, trae todos los agentes

        Returns:
            Lista de documentos de movimientos que cumplen los criterios
        """
        # Usar coleccion "movements" migrada (no mov07.10)
        collection = database_manager.get_collection("movements")

        # Usar campo 'date' (formato ISO: "2025-09-01") agregado por migracion
        query = {
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }

        # Usar 'agent_id' (no 'user') agregado por migracion
        if agent_id:
            query["agent_id"] = agent_id

        movements = list(collection.find(query))

        return movements

    @staticmethod
    def aggregate_movements_by_day_and_agent(
        movements: List[Dict[str, Any]]
    ) -> Dict[Tuple[date, str], Dict[str, Any]]:
        """
        Agrega movimientos por dia y agente, calculando P&L total y contando operaciones.

        Args:
            movements: Lista de movimientos sin procesar

        Returns:
            Diccionario con clave (fecha, agent_id) y valores agregados (pnl_total, operations_count, symbols, operations)
        """
        aggregated = defaultdict(lambda: {
            "pnl_total": 0.0,
            "operations_count": 0,
            "symbols": set(),
            "operations": []
        })

        for mov in movements:
            # Usar campos migrados: agent_id, date, closed_pnl
            agent_id = mov.get("agent_id")
            date_str = mov.get("date")

            if not agent_id or not date_str:
                continue

            # El campo 'date' ya es un string ISO "2025-09-01", convertir a date object
            try:
                operation_date = date.fromisoformat(date_str)
            except:
                continue

            # El campo closed_pnl ya es float (migrado)
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
                "time": date_str  # Usar fecha como string ISO
            })

        for key in aggregated:
            aggregated[key]["symbols"] = list(aggregated[key]["symbols"])

        return dict(aggregated)

    @staticmethod
    def get_balance_by_account_and_date(
        account_id: str,
        target_date: date
    ) -> Optional[float]:
        """
        Obtiene el balance de una cuenta especifica en una fecha determinada.

        Args:
            account_id: ID de la cuenta
            target_date: Fecha objetivo

        Returns:
            Balance normalizado o None si no se encuentra
        """
        collection = database_manager.get_collection("balances")

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(target_date, datetime.max.time()))

        balance_doc = collection.find_one({
            "userId": account_id,
            "createdAt": {
                "$gte": start_dt.isoformat(),
                "$lte": end_dt.isoformat()
            }
        })

        if not balance_doc:
            balances = list(collection.find({"userId": account_id}).sort("createdAt", -1).limit(1))
            if balances:
                balance_doc = balances[0]

        if balance_doc:
            return normalizer.normalize_balance(balance_doc.get("balance"))

        return None

    @staticmethod
    def get_all_balances_by_date(target_date: date) -> Dict[str, float]:
        """
        Obtiene todos los balances de todas las cuentas en una fecha especifica.

        Args:
            target_date: Fecha objetivo

        Returns:
            Diccionario con {account_id: balance}
        """
        collection = database_manager.get_collection("balances")

        # Usar campo 'date' agregado por migracion (formato ISO: "2025-09-01")
        date_str = target_date.isoformat()

        balances = collection.find({
            "date": date_str
        })

        result = {}
        for balance_doc in balances:
            # Usar account_id (formato futures-XXX) agregado por migracion
            account_id = balance_doc.get("account_id")
            balance_value = normalizer.normalize_balance(balance_doc.get("balance"))
            if account_id:
                result[account_id] = balance_value

        return result

    @staticmethod
    def match_movements_with_balances(
        aggregated_movements: Dict[Tuple[date, str], Dict[str, Any]],
        target_date: date
    ) -> Dict[Tuple[date, str], Dict[str, Any]]:
        """
        Empareja movimientos agregados con balances del dia anterior y calcula ROI diario.

        Formula: roi_day = (pnl_day / balance_eod_previous) * 100

        Args:
            aggregated_movements: Movimientos ya agregados por dia/agente
            target_date: Fecha objetivo para emparejar

        Returns:
            Diccionario enriquecido con balance_eod_previous y roi_day
        """
        previous_date = target_date - timedelta(days=1)
        balances = DataProcessingService.get_all_balances_by_date(previous_date)

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

    @staticmethod
    def get_agent_data_with_lookback(
        agent_id: str,
        target_date: date,
        lookback_days: int = 7,
        balances_cache: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Obtiene datos agregados de un agente con ventana temporal (lookback).

        Optimizado para aceptar balances pre-cargados y evitar queries redundantes.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo (fin del periodo)
            lookback_days: Numero de dias hacia atras (default: 7)
            balances_cache: Diccionario de balances pre-cargados (opcional)

        Returns:
            Diccionario con total_pnl, balance_current, roi_period y daily_data
        """
        start_date = target_date - timedelta(days=lookback_days - 1)

        movements = DataProcessingService.get_movements_by_date_range(
            start_date=start_date,
            end_date=target_date,
            agent_id=agent_id
        )

        aggregated = DataProcessingService.aggregate_movements_by_day_and_agent(movements)

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
            balance_current = DataProcessingService.get_all_balances_by_date(target_date).get(agent_id, 0.0)

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
