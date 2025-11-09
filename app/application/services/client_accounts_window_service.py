"""
Servicio para calcular métricas de cuentas de clientes por ventana de tiempo.

Este servicio calcula ROI y estadísticas para períodos específicos
(3D, 5D, 7D, 10D, 15D, 30D) usando snapshots históricos.

Author: Sistema Casterly Rock
Date: 2025-11-06
Version: 1.0
"""

from typing import Dict, List, Any, Optional
from datetime import date, timedelta
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)


class ClientAccountsWindowService:
    """
    Servicio para calcular métricas de cuentas de clientes por ventana de tiempo.

    Este servicio calcula ROI y estadísticas para períodos específicos
    (3D, 5D, 7D, 10D, 15D, 30D) usando snapshots históricos.
    """

    def __init__(self, db: Database):
        """
        Inicializa el servicio.

        Args:
            db: Instancia de base de datos MongoDB
        """
        self.db = db
        self.snapshots_col = db.client_accounts_snapshots

    def get_window_stats(
        self,
        simulation_id: str,
        window_days: int,
        target_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calcula estadísticas de cuentas para una ventana específica.

        Args:
            simulation_id: ID de la simulación
            window_days: Ventana de días (3, 5, 7, 10, 15, 30)

        Returns:
            Dict con estadísticas agregadas de la ventana
        """
        logger.info(
            f"Calculando stats para ventana {window_days}D, simulation_id={simulation_id}, target_date={target_date}"
        )

        # 1. Determinar la fecha de referencia (target_date)
        if target_date:
            # Usar la fecha proporcionada
            target_date_obj = date.fromisoformat(target_date)
            target_date_str = target_date
            logger.info(f"Usando target_date proporcionada: {target_date_str}")
        else:
            # Buscar el snapshot más reciente
            latest_snapshot = self.snapshots_col.find_one(
                {"simulation_id": simulation_id},
                sort=[("target_date", -1)]
            )

            if not latest_snapshot:
                logger.error(f"No se encontraron snapshots para simulation_id: {simulation_id}")
                raise ValueError(
                    f"No se encontraron snapshots para la simulación '{simulation_id}'. "
                    f"Verifica que la simulación existe y tiene datos guardados. "
                    f"Ejecuta una simulación primero o verifica el ID."
                )

            target_date_str = latest_snapshot["target_date"]
            target_date_obj = date.fromisoformat(target_date_str)
            logger.info(f"Usando snapshot más reciente: {target_date_str}")

        start_date = target_date_obj - timedelta(days=window_days - 1)

        logger.info(
            f"Ventana de cálculo: {start_date.isoformat()} -> {target_date_str}"
        )

        # 2. Obtener snapshots del período
        snapshots = list(self.snapshots_col.find({
            "simulation_id": simulation_id,
            "target_date": {
                "$gte": start_date.isoformat(),
                "$lte": target_date_str
            }
        }).sort("target_date", 1))

        if not snapshots:
            logger.error(
                f"No hay snapshots en la ventana {window_days}D "
                f"({start_date.isoformat()} -> {target_date_str}) "
                f"para simulation_id: {simulation_id}"
            )
            raise ValueError(
                f"No hay datos disponibles en la ventana de {window_days} días "
                f"({start_date.isoformat()} a {target_date_str}) "
                f"para la simulación '{simulation_id}'. "
                f"La simulación debe tener al menos {window_days} días de datos."
            )

        logger.info(f"Snapshots encontrados en ventana: {len(snapshots)}")

        # 3. Calcular ROI por cuenta en la ventana
        accounts_data = self._calculate_accounts_window_roi(snapshots)

        # 4. Calcular estadísticas agregadas
        stats = self._calculate_aggregated_stats(
            accounts_data,
            simulation_id,
            window_days,
            start_date.isoformat(),
            target_date_str
        )

        logger.info(
            f"Stats calculadas: {stats['total_cuentas']} cuentas, "
            f"ROI promedio: {stats['roi_promedio']}%"
        )

        return stats

    def _calculate_accounts_window_roi(
        self,
        snapshots: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calcula ROI de cada cuenta en la ventana.

        Fórmula: ROI_ventana = ((Balance_final - Balance_inicial) / Balance_inicial) * 100

        Args:
            snapshots: Lista de snapshots del período ordenados por fecha

        Returns:
            Dict con ROI, balance inicial/final por cuenta
        """
        accounts = {}

        # Primer snapshot: balance inicial
        first_snapshot = snapshots[0]
        for cuenta in first_snapshot.get("cuentas_estado", []):
            cuenta_id = cuenta["cuenta_id"]
            accounts[cuenta_id] = {
                "balance_inicio": cuenta["balance"],
                "balance_fin": cuenta["balance"],
                "roi_inicio": cuenta.get("roi", 0.0),
                "roi_fin": cuenta.get("roi", 0.0),
                "agente_actual": cuenta["agente"],
                "win_rate": 0.0  # Se actualiza con el último snapshot
            }

        # Último snapshot: balance final
        last_snapshot = snapshots[-1]
        for cuenta in last_snapshot.get("cuentas_estado", []):
            cuenta_id = cuenta["cuenta_id"]
            if cuenta_id in accounts:
                accounts[cuenta_id]["balance_fin"] = cuenta["balance"]
                accounts[cuenta_id]["roi_fin"] = cuenta.get("roi", 0.0)
                accounts[cuenta_id]["agente_actual"] = cuenta["agente"]

        # Calcular ROI de la ventana para cada cuenta
        for cuenta_id, data in accounts.items():
            balance_inicio = data["balance_inicio"]
            balance_fin = data["balance_fin"]

            if balance_inicio > 0:
                roi_ventana = ((balance_fin - balance_inicio) / balance_inicio) * 100
            else:
                roi_ventana = 0.0

            data["roi_ventana"] = roi_ventana

        logger.debug(f"ROI calculado para {len(accounts)} cuentas")

        return accounts

    def _calculate_aggregated_stats(
        self,
        accounts: Dict[str, Dict[str, float]],
        simulation_id: str,
        window_days: int,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Calcula estadísticas agregadas de todas las cuentas.

        Args:
            accounts: Dict con datos de cada cuenta
            simulation_id: ID de simulación
            window_days: Ventana de días
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)

        Returns:
            Dict con estadísticas agregadas
        """
        if not accounts:
            return self._empty_stats(simulation_id, window_days)

        total_cuentas = len(accounts)
        balance_total = sum(a["balance_fin"] for a in accounts.values())
        roi_promedio = sum(a["roi_ventana"] for a in accounts.values()) / total_cuentas

        # Calcular win rate promedio (% de cuentas con ganancia)
        cuentas_ganadoras = sum(1 for a in accounts.values() if a["roi_ventana"] > 0)
        win_rate_promedio = (cuentas_ganadoras / total_cuentas) * 100 if total_cuentas > 0 else 0.0

        return {
            "simulation_id": simulation_id,
            "window_days": window_days,
            "start_date": start_date,
            "end_date": end_date,
            "total_cuentas": total_cuentas,
            "balance_total": round(balance_total, 2),
            "roi_promedio": round(roi_promedio, 2),
            "win_rate_promedio": round(win_rate_promedio, 2)
        }

    def _empty_stats(self, simulation_id: str, window_days: int) -> Dict[str, Any]:
        """
        Retorna estadísticas vacías cuando no hay datos.

        Args:
            simulation_id: ID de simulación
            window_days: Ventana de días

        Returns:
            Dict con valores por defecto
        """
        return {
            "simulation_id": simulation_id,
            "window_days": window_days,
            "total_cuentas": 0,
            "balance_total": 0.0,
            "roi_promedio": 0.0,
            "win_rate_promedio": 0.0
        }

    def get_accounts_list_with_window(
        self,
        simulation_id: str,
        window_days: int,
        skip: int = 0,
        limit: int = 1000,
        agente_id: Optional[str] = None,
        search: Optional[str] = None,
        target_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene lista de cuentas con ROI calculado para la ventana.

        Args:
            simulation_id: ID de simulación
            window_days: Ventana de días (3-30)
            skip: Registros a omitir (paginación)
            limit: Límite de registros
            agente_id: Filtro opcional por agente
            search: Término de búsqueda (cuenta_id o agente)

        Returns:
            Dict con lista de cuentas y total
        """
        logger.info(
            f"Obteniendo cuentas con ventana {window_days}D: "
            f"skip={skip}, limit={limit}, agente={agente_id}, search={search}, target_date={target_date}"
        )

        # 1. Determinar la fecha de referencia (target_date)
        if target_date:
            # Usar la fecha proporcionada
            target_date_obj = date.fromisoformat(target_date)
            target_date_str = target_date
            logger.info(f"Usando target_date proporcionada: {target_date_str}")
        else:
            # Buscar el snapshot más reciente
            latest_snapshot = self.snapshots_col.find_one(
                {"simulation_id": simulation_id},
                sort=[("target_date", -1)]
            )

            if not latest_snapshot:
                logger.error(f"No se encontraron snapshots para simulation_id: {simulation_id}")
                raise ValueError(
                    f"No se encontraron snapshots para la simulación '{simulation_id}'. "
                    f"Verifica que la simulación existe y tiene datos guardados. "
                    f"Ejecuta una simulación primero o verifica el ID."
                )

            target_date_str = latest_snapshot["target_date"]
            target_date_obj = date.fromisoformat(target_date_str)
            logger.info(f"Usando snapshot más reciente: {target_date_str}")

        start_date = target_date_obj - timedelta(days=window_days - 1)

        # 2. Obtener snapshots del período
        snapshots = list(self.snapshots_col.find({
            "simulation_id": simulation_id,
            "target_date": {
                "$gte": start_date.isoformat(),
                "$lte": target_date_str
            }
        }).sort("target_date", 1))

        if not snapshots:
            logger.error(
                f"No hay snapshots en la ventana {window_days}D "
                f"({start_date.isoformat()} -> {target_date_str}) "
                f"para simulation_id: {simulation_id}"
            )
            raise ValueError(
                f"No hay datos disponibles en la ventana de {window_days} días "
                f"({start_date.isoformat()} a {target_date_str}) "
                f"para la simulación '{simulation_id}'. "
                f"La simulación debe tener al menos {window_days} días de datos."
            )

        logger.info(f"Procesando {len(snapshots)} snapshots para lista de cuentas")

        # 3. Calcular ROI por cuenta
        accounts_data = self._calculate_accounts_window_roi(snapshots)

        # 4. Convertir a lista y aplicar filtros
        accounts_list = []
        for cuenta_id, data in accounts_data.items():
            # Filtro por agente
            if agente_id and data["agente_actual"] != agente_id:
                continue

            # Filtro por búsqueda (case-insensitive)
            if search:
                search_lower = search.lower()
                if (search_lower not in cuenta_id.lower() and
                    search_lower not in data["agente_actual"].lower()):
                    continue

            # Calcular número de cambios de agente (simplificado por ahora)
            # TODO: Calcular desde historial_agentes si es necesario
            numero_cambios_agente = 0

            accounts_list.append({
                "account_id": cuenta_id,
                "cuenta_id": cuenta_id,
                "nombre_cliente": f"Cliente {cuenta_id[-4:]}",  # Nombre generado
                "balance_actual": round(data["balance_fin"], 2),
                "balance_inicial": round(data["balance_inicio"], 2),
                "roi_total": round(data["roi_ventana"], 2),
                "win_rate": data["win_rate"],
                "agente_actual": data["agente_actual"],
                "fecha_asignacion_agente": target_date_str,  # Última fecha de la ventana
                "roi_agente_al_asignar": 0.0,  # TODO: Obtener del historial
                "roi_acumulado_con_agente": round(data["roi_ventana"], 2),
                "numero_cambios_agente": numero_cambios_agente,
                "estado": "activo"
            })

        # 5. Ordenar por ROI descendente
        accounts_list.sort(key=lambda x: x["roi_total"], reverse=True)

        # 6. Total antes de paginar
        total = len(accounts_list)

        # 7. Aplicar paginación
        accounts_list = accounts_list[skip:skip + limit]

        logger.info(
            f"Lista de cuentas generada: {total} total, "
            f"retornando {len(accounts_list)} (skip={skip}, limit={limit})"
        )

        return {
            "accounts": accounts_list,
            "total": total,
            "skip": skip,
            "limit": limit
        }
