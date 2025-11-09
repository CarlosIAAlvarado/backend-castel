"""
Servicio que sincroniza las cuentas de clientes con la simulacion de agentes.

Este servicio maneja la integracion automatica entre:
- Simulacion diaria de agentes (Top 16)
- Cuentas de clientes (1000 cuentas con copytrading)

Responsabilidades:
- Actualizar ROI de cuentas basado en ROI de agentes
- Manejar rotaciones (redistribuir cuentas)
- Guardar historial de asignaciones
- Crear snapshots diarios
"""

import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from pymongo.database import Database

from app.domain.entities.client_accounts_sync_result import (
    SyncResult,
    RotationResult,
    UpdateResult,
    SnapshotResult,
    RedistributionResult,
    Rotation
)

logger = logging.getLogger(__name__)


class ClientAccountsSimulationService:
    """
    Servicio que sincroniza las cuentas de clientes con la simulacion de agentes.

    VERSION: 1.0 - Implementacion inicial del plan de integracion
    """

    def __init__(
        self,
        db: Database
    ):
        """
        Constructor con inyeccion de dependencias.

        Args:
            db: Instancia de base de datos MongoDB
        """
        self.db = db
        self.cuentas_col = db.cuentas_clientes_trading
        self.historial_col = db.historial_asignaciones_clientes
        self.snapshots_col = db.client_accounts_snapshots
        self.logger = logging.getLogger(__name__)

    async def _check_and_handle_first_day(
        self,
        target_date: date,
        simulation_id: str,
        top16_agents: List[Dict[str, Any]],
        window_days: int,
        dry_run: bool
    ) -> tuple[bool, int, int]:
        """
        Detecta y maneja el primer día de simulación.

        Args:
            target_date: Fecha de simulación
            simulation_id: ID de simulación
            top16_agents: Lista de agentes Top 16
            window_days: Ventana de días
            dry_run: Modo simulación

        Returns:
            Tupla de (es_primer_dia, cuentas_redistribuidas, rotaciones_procesadas)
        """
        cuentas_sin_agente = self.cuentas_col.count_documents({"agente_actual": "PENDING"})
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Cuentas sin agente (PENDING): {cuentas_sin_agente}")

        if cuentas_sin_agente == 0:
            return False, 0, 0

        if dry_run:
            return True, 0, 0

        logger.info("[CLIENT_ACCOUNTS_SYNC] PRIMER DIA - Redistribuyendo TODAS las cuentas al Top16")
        self.logger.info("Primer dia detectado - redistribuyendo todas las cuentas al Top16")

        # Obtener cuentas PENDING
        todas_cuentas = list(self.cuentas_col.find({"agente_actual": "PENDING", "estado": "activo"}))
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Total cuentas PENDING: {len(todas_cuentas)}")

        if not todas_cuentas:
            return True, 0, 0

        # Generar operaciones bulk
        bulk_updates, historial_entries = self._generate_first_day_bulk_ops(
            todas_cuentas, top16_agents, target_date, simulation_id, window_days
        )

        # Ejecutar operaciones
        if bulk_updates:
            result = self.cuentas_col.bulk_write(bulk_updates)
            logger.info(f"[CLIENT_ACCOUNTS_SYNC] Cuentas actualizadas: {result.modified_count}")

        if historial_entries:
            self.historial_col.insert_many(historial_entries)
            logger.info(f"[CLIENT_ACCOUNTS_SYNC] Historial creado: {len(historial_entries)} entradas")

        return True, len(bulk_updates), 0

    def _generate_first_day_bulk_ops(
        self,
        todas_cuentas: List[Dict[str, Any]],
        top16_agents: List[Dict[str, Any]],
        target_date: date,
        simulation_id: str,
        window_days: int
    ) -> tuple[List, List]:
        """
        Genera operaciones bulk para el primer día de simulación.

        Args:
            todas_cuentas: Lista de cuentas PENDING
            top16_agents: Lista de agentes Top 16
            target_date: Fecha de simulación
            simulation_id: ID de simulación
            window_days: Ventana de días

        Returns:
            Tupla de (bulk_updates, historial_entries)
        """
        from pymongo import UpdateOne
        from datetime import datetime

        # Calcular distribución
        total_cuentas = len(todas_cuentas)
        num_agents = len(top16_agents)
        cuentas_por_agente = total_cuentas // num_agents
        cuentas_restantes = total_cuentas % num_agents

        # Obtener ROIs de agentes
        agents_roi_map = {}
        roi_field = f"roi_{window_days}d"
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Obteniendo ROIs de agentes (campo: {roi_field})")

        for agent in top16_agents:
            agent_id = agent["agent_id"]
            roi_decimal = agent.get(roi_field, 0.0)
            roi_percent = roi_decimal * 100
            agents_roi_map[agent_id] = roi_percent
            logger.info(f"[CLIENT_ACCOUNTS_SYNC]   {agent_id}: {roi_decimal} -> {roi_percent}%")

        # Generar operaciones
        bulk_updates = []
        historial_entries = []
        cuenta_idx = 0
        fecha_asignacion = datetime.combine(target_date, datetime.min.time())

        for agent_idx, agent in enumerate(top16_agents):
            agent_id = agent["agent_id"]
            roi_agente = agents_roi_map.get(agent_id, 0.0)

            num_cuentas = cuentas_por_agente
            if agent_idx < cuentas_restantes:
                num_cuentas += 1

            for _ in range(num_cuentas):
                if cuenta_idx >= len(todas_cuentas):
                    break

                cuenta = todas_cuentas[cuenta_idx]
                cuenta_id = cuenta["cuenta_id"]

                bulk_updates.append(
                    UpdateOne(
                        {"_id": cuenta["_id"]},
                        {
                            "$set": {
                                "agente_actual": agent_id,
                                "fecha_asignacion_agente": fecha_asignacion,
                                "roi_agente_al_asignar": roi_agente,
                                "roi_acumulado_con_agente": 0.0,
                                "roi_historico_anterior": 0.0,
                                "updated_at": fecha_asignacion
                            }
                        }
                    )
                )

                historial_entries.append({
                    "cuenta_id": cuenta_id,
                    "nombre_cliente": cuenta["nombre_cliente"],
                    "agente_id": agent_id,
                    "simulation_id": simulation_id,
                    "fecha_inicio": fecha_asignacion,
                    "fecha_fin": None,
                    "roi_agente_inicio": roi_agente,
                    "roi_agente_fin": None,
                    "roi_cuenta_ganado": None,
                    "balance_inicio": cuenta["balance_inicial"],
                    "balance_fin": None,
                    "motivo_cambio": "inicial",
                    "dias_con_agente": None,
                    "created_at": fecha_asignacion
                })

                cuenta_idx += 1

        return bulk_updates, historial_entries

    async def _handle_rotations_if_needed(
        self,
        es_primer_dia: bool,
        target_date: date,
        simulation_id: str,
        top16_agents: List[Dict[str, Any]],
        window_days: int,
        dry_run: bool
    ) -> tuple[int, int]:
        """
        Detecta y maneja rotaciones si no es el primer día.

        Args:
            es_primer_dia: Si es el primer día
            target_date: Fecha de simulación
            simulation_id: ID de simulación
            top16_agents: Lista de agentes Top 16
            window_days: Ventana de días
            dry_run: Modo simulación

        Returns:
            Tupla de (cuentas_redistribuidas, rotaciones_procesadas)
        """
        if es_primer_dia:
            return 0, 0

        rotations = await self._detect_rotations(target_date, top16_agents, window_days)

        if not rotations or dry_run:
            return 0, 0

        rotation_result = await self.handle_rotations(
            rotations,
            target_date,
            simulation_id,
            window_days
        )

        return rotation_result.cuentas_redistribuidas, rotation_result.rotaciones_procesadas

    async def _update_roi_and_save_snapshot(
        self,
        target_date: date,
        simulation_id: str,
        window_days: int,
        dry_run: bool
    ) -> tuple[int, Optional[str]]:
        """
        Actualiza ROI de cuentas y guarda snapshot diario.

        Args:
            target_date: Fecha de simulación
            simulation_id: ID de simulación
            window_days: Ventana de días
            dry_run: Modo simulación

        Returns:
            Tupla de (cuentas_actualizadas, snapshot_id)
        """
        update_result = await self.update_all_accounts_roi(
            target_date,
            window_days,
            dry_run=dry_run
        )
        cuentas_actualizadas = update_result.cuentas_actualizadas

        snapshot_id = None
        if not dry_run:
            snapshot_result = await self.save_daily_snapshot(
                target_date,
                simulation_id
            )
            snapshot_id = snapshot_result.snapshot_id

        return cuentas_actualizadas, snapshot_id

    async def sync_with_simulation_day(
        self,
        target_date: date,
        simulation_id: str,
        window_days: int = 7,
        dry_run: bool = False
    ) -> SyncResult:
        """
        Sincroniza las cuentas con el estado de la simulacion para un dia.

        Este metodo ha sido refactorizado para reducir complejidad (13 -> ~7).
        Secciones extraídas:
        1. _check_and_handle_first_day: Detecta y maneja primer día
        2. _generate_first_day_bulk_ops: Genera operaciones del primer día
        3. _handle_rotations_if_needed: Maneja rotaciones si no es primer día
        4. _update_roi_and_save_snapshot: Actualiza ROI y guarda snapshot

        Pasos:
        1. Obtener estadisticas pre-sincronizacion
        2. Obtener Top 16 del dia
        3. Detectar y manejar primer día O rotaciones
        4. Actualizar ROI de todas las cuentas
        5. Guardar snapshot diario
        6. Obtener estadisticas post-sincronizacion

        Args:
            target_date: Fecha del dia de simulacion
            simulation_id: ID de la simulacion
            window_days: Ventana de dias para ROI (default: 7)
            dry_run: Si es True, solo simula sin guardar cambios

        Returns:
            SyncResult con estadisticas del proceso
        """
        self.logger.info(
            f"=== INICIANDO SINCRONIZACION DE CUENTAS ==="
            f"\n  Fecha: {target_date}"
            f"\n  Simulacion: {simulation_id}"
            f"\n  Ventana: {window_days}D"
            f"\n  Dry Run: {dry_run}"
        )

        # 1. Obtener estadísticas PRE-sincronización
        stats_antes = await self._get_aggregate_stats()

        # 2. Obtener Top 16 del día
        top16_agents = await self._get_top16_for_date(target_date, window_days)

        if not top16_agents:
            self.logger.warning(f"No se encontro Top 16 para {target_date}")
            return SyncResult(
                target_date=target_date,
                cuentas_actualizadas=0,
                cuentas_redistribuidas=0,
                rotaciones_procesadas=0,
                balance_total_antes=stats_antes["balance_total"],
                balance_total_despues=stats_antes["balance_total"],
                roi_promedio_antes=stats_antes["roi_promedio"],
                roi_promedio_despues=stats_antes["roi_promedio"]
            )

        # 3. Detectar y manejar primer día O rotaciones
        es_primer_dia, cuentas_redistribuidas_first, rotaciones_first = (
            await self._check_and_handle_first_day(
                target_date, simulation_id, top16_agents, window_days, dry_run
            )
        )

        cuentas_redistribuidas_rot, rotaciones_procesadas_rot = (
            await self._handle_rotations_if_needed(
                es_primer_dia, target_date, simulation_id, top16_agents, window_days, dry_run
            )
        )

        cuentas_redistribuidas = cuentas_redistribuidas_first + cuentas_redistribuidas_rot
        rotaciones_procesadas = rotaciones_first + rotaciones_procesadas_rot

        # 4. Actualizar ROI de todas las cuentas y guardar snapshot
        cuentas_actualizadas, snapshot_id = await self._update_roi_and_save_snapshot(
            target_date, simulation_id, window_days, dry_run
        )

        # 5. Obtener estadísticas POST-sincronización
        stats_despues = await self._get_aggregate_stats()

        self.logger.info(
            f"=== SINCRONIZACION COMPLETADA ==="
            f"\n  Cuentas actualizadas: {cuentas_actualizadas}"
            f"\n  Cuentas redistribuidas: {cuentas_redistribuidas}"
            f"\n  Rotaciones procesadas: {rotaciones_procesadas}"
            f"\n  Balance: ${stats_antes['balance_total']:,.2f} → ${stats_despues['balance_total']:,.2f}"
            f"\n  ROI: {stats_antes['roi_promedio']:.2f}% → {stats_despues['roi_promedio']:.2f}%"
        )

        return SyncResult(
            target_date=target_date,
            cuentas_actualizadas=cuentas_actualizadas,
            cuentas_redistribuidas=cuentas_redistribuidas,
            rotaciones_procesadas=rotaciones_procesadas,
            snapshot_id=snapshot_id,
            balance_total_antes=stats_antes["balance_total"],
            balance_total_despues=stats_despues["balance_total"],
            roi_promedio_antes=stats_antes["roi_promedio"],
            roi_promedio_despues=stats_despues["roi_promedio"]
        )

    async def handle_rotations(
        self,
        rotations: List[Rotation],
        target_date: date,
        simulation_id: str,
        window_days: int = 7
    ) -> RotationResult:
        """
        Maneja rotaciones redistribuyendo cuentas automaticamente.

        Para cada rotacion:
        1. Obtiene cuentas del agente saliente
        2. Las redistribuye al agente entrante
        3. Actualiza historial

        Args:
            rotations: Lista de rotaciones detectadas
            target_date: Fecha de la rotacion
            simulation_id: ID de la simulacion
            window_days: Ventana de dias para ROI

        Returns:
            RotationResult con detalles de la redistribucion
        """
        self.logger.info(f"Procesando {len(rotations)} rotaciones")

        total_redistribuidas = 0
        detalles_rotaciones = []

        for rotation in rotations:
            result = await self.redistribute_accounts(
                agent_out=rotation.agent_out,
                agent_in=rotation.agent_in,
                target_date=target_date,
                motivo="rotacion",
                simulation_id=simulation_id,
                window_days=window_days
            )

            total_redistribuidas += result.cuentas_movidas

            detalles_rotaciones.append({
                "agent_out": rotation.agent_out,
                "agent_in": rotation.agent_in,
                "reason": rotation.reason,
                "cuentas_movidas": result.cuentas_movidas
            })

        return RotationResult(
            fecha_rotacion=target_date,
            rotaciones_procesadas=len(rotations),
            cuentas_redistribuidas=total_redistribuidas,
            detalles_rotaciones=detalles_rotaciones
        )

    def _get_agents_roi_map(
        self,
        top16_agents: List[Dict[str, Any]],
        window_days: int
    ) -> Dict[str, float]:
        """
        Crea mapa de agent_id -> ROI en porcentaje.

        Args:
            top16_agents: Lista de agentes Top 16
            window_days: Ventana de días

        Returns:
            Diccionario de agent_id -> ROI (%)
        """
        agents_roi_map = {}
        roi_field_name = f"roi_{window_days}d"

        self.logger.info(f"DEBUG: Buscando campo '{roi_field_name}' en agentes")

        for agent in top16_agents:
            agent_id = agent["agent_id"]
            roi_decimal = agent.get(roi_field_name, 0.0)
            roi_percentage = roi_decimal * 100
            agents_roi_map[agent_id] = roi_percentage

        self.logger.info(f"DEBUG: ROI map creado con {len(agents_roi_map)} agentes")

        return agents_roi_map

    def _get_win_rate_map(
        self,
        roi_col,
        date_str: str,
        agent_ids: List[str]
    ) -> Dict[str, float]:
        """
        Obtiene win rates de los agentes.

        Args:
            roi_col: Colección de ROI
            date_str: Fecha como string
            agent_ids: Lista de IDs de agentes

        Returns:
            Diccionario de agent_id -> win_rate
        """
        roi_docs = list(roi_col.find({
            "target_date": date_str,
            "userId": {"$in": agent_ids}
        }))

        win_rate_map = {}
        for roi_doc in roi_docs:
            user_id = roi_doc.get("userId")
            positive_days = roi_doc.get("positive_days", 0)
            daily_rois = roi_doc.get("daily_rois", [])
            total_days = len(daily_rois)

            win_rate = positive_days / total_days if total_days > 0 else 0.0
            win_rate_map[user_id] = win_rate

        return win_rate_map

    def _generate_roi_update_bulk_ops(
        self,
        cuentas: List[Dict[str, Any]],
        agents_roi_map: Dict[str, float],
        win_rate_map: Dict[str, float]
    ) -> tuple[List, int, int]:
        """
        Genera operaciones bulk para actualización de ROI.

        Args:
            cuentas: Lista de cuentas activas
            agents_roi_map: Mapa de ROIs de agentes
            win_rate_map: Mapa de win rates

        Returns:
            Tupla de (bulk_operations, cuentas_con_ganancia, cuentas_con_perdida)
        """
        from pymongo import UpdateOne
        from datetime import datetime

        bulk_operations = []
        cuentas_con_ganancia = 0
        cuentas_con_perdida = 0

        for cuenta in cuentas:
            agente_id = cuenta["agente_actual"]
            roi_agente_actual = agents_roi_map.get(agente_id)

            if roi_agente_actual is None:
                self.logger.debug(f"Agente {agente_id} no encontrado en Top16 (puede haber sido expulsado)")
                continue

            roi_agente_al_asignar = cuenta["roi_agente_al_asignar"]
            roi_acumulado_con_agente = roi_agente_actual - roi_agente_al_asignar

            # CORREGIDO: Calcular balance_actual desde balance_inicial
            # roi_acumulado_con_agente ya es un valor ACUMULADO, no incremental
            # Por lo tanto, debe aplicarse sobre balance_inicial, no sobre balance_anterior
            balance_inicial = cuenta["balance_inicial"]
            balance_actual = balance_inicial * (1 + roi_acumulado_con_agente / 100)

            # Prevenir balance negativo (no se puede perder más del 100%)
            balance_actual = max(0.0, balance_actual)

            # Calcular ROI total respecto al balance inicial (para tracking)
            roi_total_nuevo = ((balance_actual / balance_inicial) - 1) * 100 if balance_inicial > 0 else 0.0

            # Guardar ROI histórico anterior para próxima rotación
            roi_historico_anterior = cuenta.get("roi_historico_anterior", 0.0)

            win_rate = win_rate_map.get(agente_id, 0.0)

            if roi_total_nuevo > 0:
                cuentas_con_ganancia += 1
            elif roi_total_nuevo < 0:
                cuentas_con_perdida += 1

            bulk_operations.append(
                UpdateOne(
                    {"_id": cuenta["_id"]},
                    {
                        "$set": {
                            "roi_acumulado_con_agente": roi_acumulado_con_agente,
                            "roi_total": roi_total_nuevo,
                            "balance_actual": balance_actual,
                            "win_rate": win_rate,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
            )

        return bulk_operations, cuentas_con_ganancia, cuentas_con_perdida

    def _execute_roi_update_bulk_ops(
        self,
        bulk_operations: List,
        dry_run: bool
    ) -> int:
        """
        Ejecuta operaciones bulk de actualización de ROI.

        Args:
            bulk_operations: Lista de operaciones UpdateOne
            dry_run: Si es True, solo simula

        Returns:
            Número de cuentas actualizadas
        """
        if not bulk_operations:
            return 0

        if not dry_run:
            result = self.cuentas_col.bulk_write(bulk_operations)
            cuentas_actualizadas = result.modified_count
            self.logger.info(f"Actualizadas {cuentas_actualizadas} cuentas en BD")
        else:
            cuentas_actualizadas = len(bulk_operations)
            self.logger.info(f"DRY RUN: {cuentas_actualizadas} cuentas se actualizarian")

        return cuentas_actualizadas

    async def update_all_accounts_roi(
        self,
        target_date: date,
        window_days: int = 7,
        dry_run: bool = False
    ) -> UpdateResult:
        """
        Actualiza el ROI de todas las cuentas basado en el ROI de sus agentes.

        Esta función ha sido refactorizada para reducir complejidad (11 -> ~7).
        Secciones extraídas:
        1. _get_agents_roi_map: Crea mapa de ROIs de agentes
        2. _get_win_rate_map: Obtiene win rates de agentes
        3. _generate_roi_update_bulk_ops: Genera operaciones bulk
        4. _execute_roi_update_bulk_ops: Ejecuta operaciones

        Formula ROI CORRECTA:
        roi_con_agente_actual = roi_agente_actual - roi_agente_al_asignar
        balance_actual = balance_inicial × (1 + roi_con_agente_actual / 100)
        roi_total = ((balance_actual / balance_inicial) - 1) × 100

        Nota: Se usa balance_inicial porque roi_con_agente_actual ya es un valor
        ACUMULADO, no incremental. Aplicarlo sobre balance_anterior causaría
        crecimiento exponencial incorrecto.

        Args:
            target_date: Fecha objetivo
            window_days: Ventana de dias para ROI
            dry_run: Si es True, solo simula sin guardar

        Returns:
            UpdateResult con estadisticas de actualizacion
        """
        self.logger.info(f"Actualizando ROI de cuentas para {target_date}")

        from app.utils.collection_names import get_top16_collection_name, get_roi_collection_name

        # 1. Obtener colecciones dinámicas y Top 16
        top16_collection_name = get_top16_collection_name(window_days)
        roi_collection_name = get_roi_collection_name(window_days)

        top16_col = self.db[top16_collection_name]
        roi_col = self.db[roi_collection_name]

        date_str = target_date.isoformat()

        top16_agents = list(top16_col.find({"date": date_str}))

        self.logger.info(f"DEBUG: Top16 encontrados: {len(top16_agents)}")

        if not top16_agents:
            self.logger.warning(f"No se encontraron agentes para {date_str}")
            return UpdateResult(
                target_date=target_date,
                cuentas_actualizadas=0,
                balance_total=0.0,
                roi_promedio=0.0
            )

        # 2. Crear mapa de ROIs de agentes
        agents_roi_map = self._get_agents_roi_map(top16_agents, window_days)

        # 3. Obtener win rates de agentes
        agent_ids = [ag["agent_id"] for ag in top16_agents]
        win_rate_map = self._get_win_rate_map(roi_col, date_str, agent_ids)

        # 4. Obtener cuentas activas
        cuentas = list(self.cuentas_col.find({"estado": "activo"}))

        self.logger.info(f"DEBUG: Cuentas activas encontradas: {len(cuentas)}")

        if not cuentas:
            self.logger.warning("No hay cuentas activas")
            return UpdateResult(
                target_date=target_date,
                cuentas_actualizadas=0,
                balance_total=0.0,
                roi_promedio=0.0
            )

        # 5. Generar operaciones bulk
        bulk_operations, cuentas_con_ganancia, cuentas_con_perdida = (
            self._generate_roi_update_bulk_ops(cuentas, agents_roi_map, win_rate_map)
        )

        # 6. Ejecutar operaciones bulk
        cuentas_actualizadas = self._execute_roi_update_bulk_ops(bulk_operations, dry_run)

        # 7. Calcular estadísticas finales
        stats = await self._get_aggregate_stats()

        self.logger.info(
            f"Actualizacion completada:"
            f"\n  Total: {cuentas_actualizadas} cuentas"
            f"\n  Con ganancia: {cuentas_con_ganancia}"
            f"\n  Con perdida: {cuentas_con_perdida}"
            f"\n  Balance total: ${stats['balance_total']:,.2f}"
            f"\n  ROI promedio: {stats['roi_promedio']:.2f}%"
        )

        return UpdateResult(
            target_date=target_date,
            cuentas_actualizadas=cuentas_actualizadas,
            balance_total=stats["balance_total"],
            roi_promedio=stats["roi_promedio"],
            cuentas_con_ganancia=cuentas_con_ganancia,
            cuentas_con_perdida=cuentas_con_perdida
        )

    async def save_daily_snapshot(
        self,
        target_date: date,
        simulation_id: str
    ) -> SnapshotResult:
        """
        Guarda un snapshot completo del estado de todas las cuentas.

        El snapshot incluye:
        - Estadisticas agregadas (balance total, ROI promedio, etc.)
        - Distribucion por agente (cuantas cuentas tiene cada uno)
        - Opcionalmente: estado detallado de cada cuenta individual

        Args:
            target_date: Fecha del snapshot
            simulation_id: ID de la simulacion

        Returns:
            SnapshotResult con ID del snapshot creado
        """
        self.logger.info(f"Guardando snapshot para {target_date}")

        # 1. Obtener todas las cuentas activas
        cuentas = list(self.cuentas_col.find({"estado": "activo"}))

        if not cuentas:
            self.logger.warning("No hay cuentas activas para snapshot")
            return SnapshotResult(
                snapshot_id="empty",
                target_date=target_date,
                total_cuentas=0
            )

        # 2. Calcular estadisticas agregadas
        total_cuentas = len(cuentas)
        balance_total = sum(c["balance_actual"] for c in cuentas)
        roi_promedio = sum(c["roi_total"] for c in cuentas) / total_cuentas
        win_rate_promedio = sum(c.get("win_rate", 0.0) for c in cuentas) / total_cuentas

        # 3. Calcular distribucion por agente
        distribucion_agentes = {}

        for cuenta in cuentas:
            agente_id = cuenta["agente_actual"]

            if agente_id not in distribucion_agentes:
                distribucion_agentes[agente_id] = {
                    "num_cuentas": 0,
                    "balance_total": 0.0,
                    "roi_sum": 0.0,
                    "cuentas": []
                }

            distribucion_agentes[agente_id]["num_cuentas"] += 1
            distribucion_agentes[agente_id]["balance_total"] += cuenta["balance_actual"]
            distribucion_agentes[agente_id]["roi_sum"] += cuenta["roi_total"]

        # Calcular ROI promedio por agente
        for agente_id, data in distribucion_agentes.items():
            num_cuentas = data["num_cuentas"]
            data["roi_promedio"] = data["roi_sum"] / num_cuentas if num_cuentas > 0 else 0.0
            del data["roi_sum"]  # No necesitamos guardar la suma
            del data["cuentas"]  # No guardar array temporal

        # 4. Crear estado detallado de cuentas (opcional, puede ser pesado)
        # Por ahora lo guardamos para tener replay completo
        cuentas_estado = [
            {
                "cuenta_id": c["cuenta_id"],
                "balance": c["balance_actual"],
                "roi": c["roi_total"],
                "agente": c["agente_actual"]
            }
            for c in cuentas
        ]

        # 5. Crear documento de snapshot
        snapshot_doc = {
            "simulation_id": simulation_id,
            "target_date": target_date.isoformat(),
            "total_cuentas": total_cuentas,
            "balance_total": balance_total,
            "roi_promedio": roi_promedio,
            "win_rate_promedio": win_rate_promedio,
            "distribucion_agentes": distribucion_agentes,
            "cuentas_estado": cuentas_estado,
            "createdAt": datetime.utcnow()
        }

        # 6. Guardar en MongoDB
        result = self.snapshots_col.insert_one(snapshot_doc)
        snapshot_id = str(result.inserted_id)

        self.logger.info(
            f"Snapshot guardado exitosamente:"
            f"\n  ID: {snapshot_id}"
            f"\n  Total cuentas: {total_cuentas}"
            f"\n  Balance total: ${balance_total:,.2f}"
            f"\n  ROI promedio: {roi_promedio:.2f}%"
            f"\n  Agentes: {len(distribucion_agentes)}"
        )

        return SnapshotResult(
            snapshot_id=snapshot_id,
            target_date=target_date,
            total_cuentas=total_cuentas
        )

    async def redistribute_accounts(
        self,
        agent_out: str,
        agent_in: str,
        target_date: date,
        motivo: str,
        simulation_id: str,
        window_days: int = 7
    ) -> RedistributionResult:
        """
        Redistribuye cuentas de un agente a otro.

        Pasos:
        1. Obtiene todas las cuentas del agente_out
        2. Para cada cuenta:
           - Cierra registro en historial (fecha_fin, roi_final, etc.)
           - Actualiza cuenta (nuevo agente, roi_al_asignar, etc.)
           - Crea nuevo registro en historial
        3. Retorna estadisticas

        Args:
            agent_out: Agente que sale
            agent_in: Agente que entra
            target_date: Fecha de la redistribucion
            motivo: Razon del cambio ('rotacion', 'rebalanceo', etc.)
            simulation_id: ID de la simulacion
            window_days: Ventana de dias para ROI

        Returns:
            RedistributionResult con detalles de cuentas movidas
        """
        self.logger.info(f"Redistribuyendo cuentas: {agent_out} → {agent_in}")

        from pymongo import UpdateOne
        from app.utils.collection_names import get_top16_collection_name

        # 1. Obtener todas las cuentas del agente saliente
        cuentas_del_agente = list(
            self.cuentas_col.find({
                "agente_actual": agent_out,
                "estado": "activo"
            })
        )

        if not cuentas_del_agente:
            self.logger.warning(f"No se encontraron cuentas para el agente {agent_out}")
            return RedistributionResult(
                agente_out=agent_out,
                agente_in=agent_in,
                cuentas_movidas=0,
                motivo=motivo,
                fecha=target_date
            )

        num_cuentas = len(cuentas_del_agente)
        self.logger.info(f"Encontradas {num_cuentas} cuentas del agente {agent_out}")

        # 2. Obtener informacion de ROI de ambos agentes
        top16_collection_name = get_top16_collection_name(window_days)
        top16_col = self.db[top16_collection_name]
        date_str = target_date.isoformat()

        # Obtener agente entrante
        agent_in_doc = top16_col.find_one({
            "date": date_str,
            "agent_id": agent_in
        })

        if not agent_in_doc:
            self.logger.error(f"Agente entrante {agent_in} no encontrado en Top16 para {date_str}")
            return RedistributionResult(
                agente_out=agent_out,
                agente_in=agent_in,
                cuentas_movidas=0,
                motivo=motivo,
                fecha=target_date
            )

        # ROI del agente entrante (convertir a porcentaje)
        roi_agente_in = agent_in_doc.get("roi_7d", 0.0) * 100

        # Obtener agente saliente (puede no estar en Top16)
        agent_out_doc = top16_col.find_one({
            "date": date_str,
            "agent_id": agent_out
        })

        roi_agente_out = 0.0
        if agent_out_doc:
            roi_agente_out = agent_out_doc.get("roi_7d", 0.0) * 100

        # 3. Preparar actualizaciones
        bulk_updates = []
        bulk_historial_updates = []  # OPTIMIZACIÓN: Bulk updates para historial
        historial_entries = []
        fecha_redistribucion = datetime.utcnow()

        for cuenta in cuentas_del_agente:
            cuenta_id = cuenta["cuenta_id"]
            dias_con_agente = (fecha_redistribucion - cuenta["fecha_asignacion_agente"]).days

            # 3.1. OPTIMIZACIÓN: Preparar actualización bulk para historial (en vez de update_one individual)
            bulk_historial_updates.append(
                UpdateOne(
                    {
                        "cuenta_id": cuenta_id,
                        "agente_id": agent_out,
                        "fecha_fin": None
                    },
                    {
                        "$set": {
                            "fecha_fin": fecha_redistribucion,
                            "roi_agente_fin": roi_agente_out,
                            "roi_cuenta_ganado": cuenta.get("roi_acumulado_con_agente", 0.0),
                            "balance_fin": cuenta["balance_actual"],
                            "dias_con_agente": dias_con_agente
                        }
                    }
                )
            )

            # 3.2. Actualizar roi_historico_anterior con el ROI ganado hasta ahora
            # Formula: roi_historico_anterior + roi_acumulado_con_agente
            roi_historico_anterior_nuevo = (
                cuenta.get("roi_historico_anterior", 0.0)
                + cuenta.get("roi_acumulado_con_agente", 0.0)
            )

            # 3.3. Crear nuevo registro en historial
            historial_entries.append({
                "cuenta_id": cuenta_id,
                "nombre_cliente": cuenta["nombre_cliente"],
                "agente_id": agent_in,
                "simulation_id": simulation_id,
                "fecha_inicio": fecha_redistribucion,
                "fecha_fin": None,
                "roi_agente_inicio": roi_agente_in,
                "roi_agente_fin": None,
                "roi_cuenta_ganado": None,
                "balance_inicio": cuenta["balance_actual"],
                "balance_fin": None,
                "motivo_cambio": motivo,
                "dias_con_agente": None,
                "created_at": fecha_redistribucion
            })

            # 3.4. Actualizar cuenta (IMPORTANTE: resetear roi_acumulado_con_agente)
            bulk_updates.append(
                UpdateOne(
                    {"_id": cuenta["_id"]},
                    {
                        "$set": {
                            "agente_actual": agent_in,
                            "fecha_asignacion_agente": fecha_redistribucion,
                            "roi_agente_al_asignar": roi_agente_in,
                            "roi_acumulado_con_agente": 0.0,  # RESET porque es nuevo agente
                            "roi_historico_anterior": roi_historico_anterior_nuevo,  # Acumular historial
                            "updated_at": fecha_redistribucion
                        },
                        "$inc": {
                            "numero_cambios_agente": 1
                        }
                    }
                )
            )

        # 4. OPTIMIZACIÓN: Ejecutar actualizaciones bulk de historial (cierre de registros)
        if bulk_historial_updates:
            result_historial = self.historial_col.bulk_write(bulk_historial_updates, ordered=False)
            self.logger.info(f"[BULK_HISTORIAL] Cerrados {result_historial.modified_count} registros en historial")

        # 5. Ejecutar actualizaciones en bulk de cuentas
        if bulk_updates:
            result = self.cuentas_col.bulk_write(bulk_updates)
            self.logger.info(f"Actualizadas {result.modified_count} cuentas")

        # 6. Insertar nuevas entradas de historial en bulk
        if historial_entries:
            self.historial_col.insert_many(historial_entries)
            self.logger.info(f"Insertadas {len(historial_entries)} entradas de historial")

        self.logger.info(
            f"Redistribucion completada:"
            f"\n  {num_cuentas} cuentas movidas"
            f"\n  De: {agent_out} (ROI: {roi_agente_out:.2f}%)"
            f"\n  A: {agent_in} (ROI: {roi_agente_in:.2f}%)"
            f"\n  Motivo: {motivo}"
        )

        return RedistributionResult(
            agente_out=agent_out,
            agente_in=agent_in,
            cuentas_movidas=num_cuentas,
            motivo=motivo,
            fecha=target_date
        )

    # ========== METODOS PRIVADOS ==========

    async def _get_aggregate_stats(self) -> Dict[str, Any]:
        """Obtiene estadisticas agregadas de todas las cuentas."""
        pipeline = [
            {"$match": {"estado": "activo"}},
            {
                "$group": {
                    "_id": None,
                    "total_cuentas": {"$sum": 1},
                    "balance_total": {"$sum": "$balance_actual"},
                    "roi_promedio": {"$avg": "$roi_total"}
                }
            }
        ]

        result = list(self.cuentas_col.aggregate(pipeline))

        if not result:
            return {
                "total_cuentas": 0,
                "balance_total": 0.0,
                "roi_promedio": 0.0
            }

        return {
            "total_cuentas": result[0]["total_cuentas"],
            "balance_total": result[0]["balance_total"],
            "roi_promedio": result[0]["roi_promedio"]
        }

    async def _get_top16_for_date(
        self,
        target_date: date,
        window_days: int
    ) -> List[Dict[str, Any]]:
        """Obtiene los Top 16 agentes de una fecha especifica."""
        from app.utils.collection_names import get_top16_collection_name

        collection_name = get_top16_collection_name(window_days)
        top16_col = self.db[collection_name]

        date_str = target_date.isoformat()

        agents = list(
            top16_col.find({
                "date": date_str,
                "is_in_casterly": True
            }).sort("rank", 1).limit(16)
        )

        return agents

    async def _detect_rotations(
        self,
        target_date: date,
        current_top16: List[Dict[str, Any]],
        window_days: int
    ) -> List[Rotation]:
        """
        Detecta rotaciones comparando Top 16 actual con el anterior.

        Args:
            target_date: Fecha actual
            current_top16: Top 16 del dia actual
            window_days: Ventana de dias

        Returns:
            Lista de rotaciones detectadas
        """
        from datetime import timedelta
        from app.utils.collection_names import get_top16_collection_name

        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Detectando rotaciones para fecha {target_date}")

        # 1. Obtener el Top 16 del dia anterior
        previous_date = target_date - timedelta(days=1)
        collection_name = get_top16_collection_name(window_days)
        top16_col = self.db[collection_name]

        previous_top16 = list(
            top16_col.find({
                "date": previous_date.isoformat(),
                "is_in_casterly": True
            }).sort("rank", 1).limit(16)
        )

        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Previous date: {previous_date.isoformat()}")
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Previous Top16 count: {len(previous_top16)}")
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Current Top16 count: {len(current_top16)}")

        # Si no hay Top 16 anterior (primer dia), no hay rotaciones
        if not previous_top16:
            logger.info("[CLIENT_ACCOUNTS_SYNC] No hay Top 16 anterior - primer dia de simulacion")
            self.logger.info("No hay Top 16 anterior - primer dia de simulacion")
            return []

        # 2. Crear sets de agent_ids para comparacion
        current_ids = {agent["agent_id"] for agent in current_top16}
        previous_ids = {agent["agent_id"] for agent in previous_top16}

        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Current IDs: {current_ids}")
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Previous IDs: {previous_ids}")

        # 3. Detectar agentes que salieron (estaban en anterior pero no en actual)
        agents_out = previous_ids - current_ids

        # 4. Detectar agentes que entraron (estan en actual pero no en anterior)
        agents_in = current_ids - previous_ids

        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Agentes que salieron: {agents_out}")
        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Agentes que entraron: {agents_in}")

        # 5. Crear rotaciones
        rotations = []

        # Para cada agente que salio, buscar cuentas asignadas a el
        for agent_out in agents_out:
            logger.info(f"[CLIENT_ACCOUNTS_SYNC] Procesando agente saliente: {agent_out}")
            # Verificar si hay cuentas con este agente
            num_cuentas = self.cuentas_col.count_documents({
                "agente_actual": agent_out,
                "estado": "activo"
            })

            logger.info(f"[CLIENT_ACCOUNTS_SYNC] Agente {agent_out} tiene {num_cuentas} cuentas")

            if num_cuentas > 0:
                # Buscar el mejor agente que entro (el de mayor rank)
                # Si hay multiples agentes nuevos, asignar al mejor
                if agents_in:
                    logger.info(f"[CLIENT_ACCOUNTS_SYNC] Buscando mejor agente entrante entre {len(agents_in)} opciones")
                    # Encontrar el agente con mejor rank en current_top16
                    best_agent_in = None
                    best_rank = 999

                    for agent in current_top16:
                        if agent["agent_id"] in agents_in and agent["rank"] < best_rank:
                            best_agent_in = agent["agent_id"]
                            best_rank = agent["rank"]

                    if best_agent_in:
                        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Rotacion creada: {agent_out} -> {best_agent_in} (rank {best_rank})")
                        self.logger.info(
                            f"Rotacion detectada: {agent_out} (salio) -> {best_agent_in} (rank {best_rank})"
                            f"\n  Cuentas afectadas: {num_cuentas}"
                        )

                        rotations.append(Rotation(
                            agent_out=agent_out,
                            agent_in=best_agent_in,
                            reason=f"Agente {agent_out} salio del Top 16 - reemplazado por {best_agent_in}",
                            rotation_date=target_date,
                            rank_in=best_rank
                        ))

                        # Remover el agente usado de agents_in para no reutilizarlo
                        agents_in.remove(best_agent_in)
                        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Agentes entrantes restantes: {len(agents_in)}")

        logger.info(f"[CLIENT_ACCOUNTS_SYNC] Total rotaciones detectadas: {len(rotations)}")
        self.logger.info(f"Total rotaciones detectadas: {len(rotations)}")

        return rotations
