from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import logging
from app.application.services.selection_service import SelectionService
from app.application.services.assignment_service import AssignmentService
from app.application.services.state_classification_service import StateClassificationService
from app.application.services.exit_rules_service import ExitRulesService
from app.application.services.replacement_service import ReplacementService
from app.application.services.client_accounts_simulation_service import ClientAccountsSimulationService
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.infrastructure.repositories.daily_roi_repository import DailyROIRepository
from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository

logger = logging.getLogger(__name__)


class DailyOrchestratorService:
    """
    Servicio orquestador para la simulacion diaria completa.

    VERSION 2.0 - NUEVA LOGICA ROI
    Ahora incluye limpieza de cache al inicio y usa nueva logica de calculo ROI.

    Coordina todos los servicios para ejecutar el flujo diario:
    1. Limpiar cache temporal (daily_roi_calculation, agent_roi_7d)
    2. Calcular KPIs (ROI, ranking) con nueva logica
    3. Clasificar estados (GROWTH/FALL)
    4. Evaluar reglas de salida
    5. Ejecutar rotaciones si es necesario
    6. Actualizar asignaciones

    Periodo: 01-Sep-2025 a 07-Oct-2025
    """

    def __init__(
        self,
        selection_service: SelectionService,
        assignment_service: AssignmentService,
        state_service: StateClassificationService,
        exit_rules_service: ExitRulesService,
        replacement_service: ReplacementService,
        state_repo: AgentStateRepository,
        daily_roi_repo: DailyROIRepository,
        roi_7d_repo: ROI7DRepository,
        client_accounts_sync_service: Optional[ClientAccountsSimulationService] = None
    ):
        """
        Constructor con inyeccion de dependencias.

        VERSION 3.0: Agregado servicio de sincronizacion de client accounts

        Args:
            selection_service: Servicio de seleccion de agentes
            assignment_service: Servicio de asignacion de cuentas
            state_service: Servicio de clasificacion de estados
            exit_rules_service: Servicio de evaluacion de reglas de salida
            replacement_service: Servicio de reemplazo de agentes
            state_repo: Repositorio de estados de agentes
            daily_roi_repo: Repositorio temporal de ROI diario
            roi_7d_repo: Repositorio temporal de ROI 7D
            client_accounts_sync_service: Servicio de sincronizacion de cuentas (opcional)
        """
        self.selection_service = selection_service
        self.assignment_service = assignment_service
        self.state_service = state_service
        self.exit_rules_service = exit_rules_service
        self.replacement_service = replacement_service
        self.state_repo = state_repo
        self.daily_roi_repo = daily_roi_repo
        self.roi_7d_repo = roi_7d_repo
        self.client_accounts_sync = client_accounts_sync_service

    async def process_day_one(
        self,
        target_date: date,
        update_client_accounts: bool = False,
        simulation_id: Optional[str] = None,
        window_days: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Procesa el dia 1 (01-Sep-2025): Asignacion inicial.

        VERSION 3.0: Integrado con sincronizacion de Client Accounts

        Pasos:
        1. Seleccionar Top 16 por ROI_7D (nueva logica)
        2. Asignar cuentas aleatoriamente
        3. Guardar Top 16 en base de datos
        4. Clasificar estados iniciales
        5. (NUEVO) Sincronizar cuentas de clientes si update_client_accounts=True

        Args:
            target_date: Fecha del dia 1 (debe ser 01-Sep-2025)
            update_client_accounts: Si True, sincroniza cuentas de clientes. Default: False
            simulation_id: ID de la simulacion (requerido si update_client_accounts=True)
            window_days: Ventana de días para ROI (3, 5, 7, 10, 15, 30). Default: 7
            dry_run: Si True, simula cambios sin guardar. Default: False

        Returns:
            Diccionario con resultado del dia 1
        """
        logger.info(f"Processing Day One: {target_date}")

        top16, top16_all = await self.selection_service.select_top_16(target_date)

        casterly_agent_ids = [agent["agent_id"] for agent in top16]

        logger.info(f"Top 16 selected: {len(casterly_agent_ids)} agents")

        top16_saved = self.selection_service.save_top16_to_database(
            target_date, top16, casterly_agent_ids
        )

        assignment_result = self.assignment_service.create_initial_assignments(
            target_date, casterly_agent_ids
        )

        classification_result = await self.state_service.classify_all_agents(
            target_date, casterly_agent_ids
        )

        logger.info(
            f"Day One complete: {assignment_result['total_assignments']} accounts assigned, "
            f"{classification_result['total_agents']} agents classified"
        )

        # NUEVO: Sincronizar cuentas de clientes
        client_accounts_result = None
        if update_client_accounts and self.client_accounts_sync:
            if not simulation_id:
                logger.warning("update_client_accounts=True pero simulation_id no proporcionado. Saltando sincronizacion.")
            else:
                try:
                    logger.info("=== SINCRONIZANDO CUENTAS DE CLIENTES (DIA 1) ===")

                    client_accounts_result = await self.client_accounts_sync.sync_with_simulation_day(
                        target_date=target_date,
                        simulation_id=simulation_id,
                        window_days=window_days,
                        dry_run=dry_run
                    )

                    logger.info(
                        f"Sincronizacion de cuentas completada (Dia 1):"
                        f"\n  Cuentas actualizadas: {client_accounts_result.cuentas_actualizadas}"
                        f"\n  Cuentas redistribuidas: {client_accounts_result.cuentas_redistribuidas}"
                        f"\n  Balance total: ${client_accounts_result.balance_total_despues:,.2f}"
                        f"\n  ROI promedio: {client_accounts_result.roi_promedio_despues:.2f}%"
                    )

                except Exception as e:
                    logger.error(f"Error en sincronizacion de cuentas de clientes (Dia 1): {e}", exc_info=True)
                    client_accounts_result = {
                        "error": str(e),
                        "success": False
                    }
        elif update_client_accounts and not self.client_accounts_sync:
            logger.warning("update_client_accounts=True pero ClientAccountsSimulationService no esta configurado")

        # Preparar datos completos del Top 16 con ROI
        # IMPORTANTE: Usar campo dinamico basado en window_days (roi_3d, roi_7d, roi_30d, etc.)
        roi_field = f"roi_{window_days}d"
        top_16_with_data = [
            {
                "userId": agent["userId"],
                "roi_7d": agent.get(roi_field, 0.0),  # Mantener nombre "roi_7d" para compatibilidad con frontend
                "total_pnl": agent.get("total_pnl", 0.0),
                "balance": agent.get("balance_current", 0.0),
                "total_trades_7d": agent.get("total_trades_7d", 0),
                "rank": agent.get("rank", idx + 1)
            }
            for idx, agent in enumerate(top16)
        ]

        result = {
            "success": True,
            "date": target_date.isoformat(),
            "phase": "day_one_initialization",
            "top_16_agents": casterly_agent_ids,
            "top_16_data": top_16_with_data,
            "total_accounts_assigned": assignment_result["total_assignments"],
            "states_classified": classification_result["total_agents"],
            "growth_count": classification_result["growth_count"],
            "fall_count": classification_result["fall_count"],
        }

        # Agregar resultado de sincronizacion si existe
        if client_accounts_result:
            if isinstance(client_accounts_result, dict):
                result["client_accounts_sync"] = client_accounts_result
            else:
                result["client_accounts_sync"] = {
                    "success": True,
                    "cuentas_actualizadas": client_accounts_result.cuentas_actualizadas,
                    "cuentas_redistribuidas": client_accounts_result.cuentas_redistribuidas,
                    "rotaciones_procesadas": client_accounts_result.rotaciones_procesadas,
                    "snapshot_id": client_accounts_result.snapshot_id,
                    "balance_total_antes": client_accounts_result.balance_total_antes,
                    "balance_total_despues": client_accounts_result.balance_total_despues,
                    "roi_promedio_antes": client_accounts_result.roi_promedio_antes,
                    "roi_promedio_despues": client_accounts_result.roi_promedio_despues
                }

        return result

    async def process_daily(
        self,
        target_date: date,
        update_client_accounts: bool = False,
        simulation_id: Optional[str] = None,
        window_days: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Procesa un dia normal de simulacion (02-Sep en adelante).

        VERSION 3.0: Integrado con sincronizacion de Client Accounts

        Pasos:
        1. Calcular ROI diario y clasificar estados (nueva logica)
        2. Guardar Top 16 del dia
        3. Evaluar reglas de salida
        4. Ejecutar rotaciones si es necesario
        5. Actualizar lista de Casterly activos
        6. (NUEVO) Sincronizar cuentas de clientes si update_client_accounts=True

        Args:
            target_date: Fecha del dia a procesar
            update_client_accounts: Si True, sincroniza cuentas de clientes. Default: False
            simulation_id: ID de la simulacion (requerido si update_client_accounts=True)
            window_days: Ventana de días para ROI (3, 5, 7, 10, 15, 30). Default: 7
            dry_run: Si True, simula cambios sin guardar. Default: False

        Returns:
            Diccionario con resultado del dia
        """
        logger.info(f"Processing daily: {target_date}")

        states = self.state_repo.get_by_date(target_date - timedelta(days=1))
        current_casterly_agents = list(
            set([state.agent_id for state in states if state.is_in_casterly])
        )

        if not current_casterly_agents:
            logger.warning(f"No active agents in Casterly for {target_date}")
            return {
                "success": False,
                "message": f"No hay agentes activos en Casterly para la fecha {target_date}",
            }

        previous_top16 = self.selection_service.get_top16_by_date(
            target_date - timedelta(days=1)
        )
        if previous_top16:
            top30_candidates = (
                [t.agent_id for t in previous_top16[:30]]
                if len(previous_top16) >= 30
                else [t.agent_id for t in previous_top16]
            )
        else:
            top30_candidates = []

        relevant_agents = list(set(current_casterly_agents + top30_candidates))

        logger.debug(
            f"Calculating ROI for {len(relevant_agents)} relevant agents "
            f"({len(current_casterly_agents)} active + {len(top30_candidates)} candidates)"
        )

        # USA VERSION ULTRA RAPIDA
        agents_data = await self.selection_service.calculate_all_agents_roi_7d_ULTRA_FAST(
            target_date, agent_ids=relevant_agents, window_days=window_days
        )

        ranked_agents = self.selection_service.rank_agents_by_roi_7d(agents_data, window_days=window_days)
        top16 = ranked_agents[:16]

        top16_saved = self.selection_service.save_top16_to_database(
            target_date, top16, current_casterly_agents
        )

        classification_result = await self.state_service.classify_all_agents(
            target_date,
            current_casterly_agents
        )

        evaluation_result = self.exit_rules_service.evaluate_all_agents(
            target_date,
            fall_threshold=3,
            stop_loss_threshold=-0.10
        )

        agents_to_exit = evaluation_result["agents_to_exit"]
        rotations_executed = []
        new_agents_to_classify = []

        for agent_eval in agents_to_exit:
            agent_out = agent_eval["agent_id"]
            reasons = agent_eval["reasons"]
            reason_str = "; ".join(reasons)

            mark_result = self.exit_rules_service.mark_agent_out(
                agent_out,
                target_date,
                reason_str
            )

            if mark_result["success"]:
                replacement_agent = self.replacement_service.find_replacement_agent(
                    target_date,
                    current_casterly_agents
                )

                if replacement_agent:
                    agent_in = replacement_agent["agent_id"]

                    transfer_result = self.replacement_service.transfer_accounts(
                        agent_out,
                        agent_in,
                        target_date
                    )

                    if not transfer_result.get("success"):
                        continue

                    state_out = self.state_repo.get_by_agent_and_date(agent_out, target_date)
                    roi_7d_out = state_out.roi_day if state_out else 0.0
                    roi_total_out = state_out.roi_since_entry if state_out else 0.0

                    rotation_log = self.replacement_service.register_rotation(
                        date=target_date,
                        agent_out=agent_out,
                        agent_in=agent_in,
                        reason=reason_str,
                        roi_7d_out=roi_7d_out,
                        roi_total_out=roi_total_out,
                        roi_7d_in=replacement_agent.get("roi_7d", 0.0),
                        n_accounts=transfer_result["n_accounts_transferred"],
                        total_aum=transfer_result["total_aum_transferred"]
                    )

                    replacement_result = {
                        "success": True,
                        "date": target_date.isoformat(),
                        "agent_out": agent_out,
                        "agent_in": agent_in,
                        "reason": reason_str,
                        "n_accounts_transferred": transfer_result["n_accounts_transferred"],
                        "total_aum_transferred": transfer_result["total_aum_transferred"],
                        "agent_out_roi_7d": roi_7d_out,
                        "agent_out_roi_total": roi_total_out,
                        "agent_in_roi_7d": replacement_agent.get("roi_7d", 0.0),
                        "rotation_log_id": rotation_log.id
                    }

                    rotations_executed.append(replacement_result)
                    if agent_out in current_casterly_agents:
                        current_casterly_agents.remove(agent_out)
                    current_casterly_agents.append(agent_in)
                    new_agents_to_classify.append(agent_in)

        if new_agents_to_classify:
            new_agents_classification = await self.state_service.classify_all_agents(
                target_date,
                new_agents_to_classify
            )

        # NUEVO: Sincronizar cuentas de clientes
        client_accounts_result = None
        if update_client_accounts and self.client_accounts_sync:
            if not simulation_id:
                logger.warning("update_client_accounts=True pero simulation_id no proporcionado. Saltando sincronizacion.")
            else:
                try:
                    logger.info("=== SINCRONIZANDO CUENTAS DE CLIENTES ===")

                    client_accounts_result = await self.client_accounts_sync.sync_with_simulation_day(
                        target_date=target_date,
                        simulation_id=simulation_id,
                        window_days=window_days,
                        dry_run=dry_run
                    )

                    logger.info(
                        f"Sincronizacion de cuentas completada:"
                        f"\n  Cuentas actualizadas: {client_accounts_result.cuentas_actualizadas}"
                        f"\n  Cuentas redistribuidas: {client_accounts_result.cuentas_redistribuidas}"
                        f"\n  Rotaciones procesadas: {client_accounts_result.rotaciones_procesadas}"
                        f"\n  Balance: ${client_accounts_result.balance_total_antes:,.2f} -> ${client_accounts_result.balance_total_despues:,.2f}"
                        f"\n  ROI promedio: {client_accounts_result.roi_promedio_antes:.2f}% -> {client_accounts_result.roi_promedio_despues:.2f}%"
                    )

                except Exception as e:
                    logger.error(f"Error en sincronizacion de cuentas de clientes: {e}", exc_info=True)
                    client_accounts_result = {
                        "error": str(e),
                        "success": False
                    }
        elif update_client_accounts and not self.client_accounts_sync:
            logger.warning("update_client_accounts=True pero ClientAccountsSimulationService no esta configurado")

        # Preparar datos completos del Top 16 con ROI
        # IMPORTANTE: Usar campo dinamico basado en window_days (roi_3d, roi_7d, roi_30d, etc.)
        roi_field = f"roi_{window_days}d"
        top_16_with_data = [
            {
                "userId": agent["userId"],
                "roi_7d": agent.get(roi_field, 0.0),  # Mantener nombre "roi_7d" para compatibilidad con frontend
                "total_pnl": agent.get("total_pnl", 0.0),
                "balance": agent.get("balance_current", 0.0),
                "total_trades_7d": agent.get("total_trades_7d", 0),
                "rank": agent.get("rank", idx + 1)
            }
            for idx, agent in enumerate(top16)
        ]

        result = {
            "success": True,
            "date": target_date.isoformat(),
            "phase": "daily_processing",
            "top_16_data": top_16_with_data,
            "active_agents": len(current_casterly_agents),
            "states_classified": classification_result["total_agents"],
            "growth_count": classification_result["growth_count"],
            "fall_count": classification_result["fall_count"],
            "agents_evaluated": evaluation_result["total_active_agents"],
            "agents_exited": len(agents_to_exit),
            "rotations_executed": len(rotations_executed),
            "rotations_detail": rotations_executed,
            "current_casterly_agents": current_casterly_agents
        }

        # Agregar resultado de sincronizacion si existe
        if client_accounts_result:
            if isinstance(client_accounts_result, dict):
                result["client_accounts_sync"] = client_accounts_result
            else:
                result["client_accounts_sync"] = {
                    "success": True,
                    "cuentas_actualizadas": client_accounts_result.cuentas_actualizadas,
                    "cuentas_redistribuidas": client_accounts_result.cuentas_redistribuidas,
                    "rotaciones_procesadas": client_accounts_result.rotaciones_procesadas,
                    "snapshot_id": client_accounts_result.snapshot_id,
                    "balance_total_antes": client_accounts_result.balance_total_antes,
                    "balance_total_despues": client_accounts_result.balance_total_despues,
                    "roi_promedio_antes": client_accounts_result.roi_promedio_antes,
                    "roi_promedio_despues": client_accounts_result.roi_promedio_despues
                }

        return result

    async def process_single_date(
        self,
        target_date: date,
        skip_cache_clear: bool = False,
        window_days: int = 7,
        update_client_accounts: bool = False,
        simulation_id: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Procesa UNA SOLA FECHA para calcular ROI y seleccionar Top 16.

        VERSION 4.0 - INTEGRACION CON CLIENT ACCOUNTS
        Ahora puede sincronizar cuentas de clientes automaticamente.

        Pasos:
        1. (Opcional) Limpiar cache temporal - solo si skip_cache_clear=False
        2. Calcular ROI para todos los agentes en la fecha target
        3. Seleccionar Top 16 por ROI
        4. Asignar cuentas a Top 16
        5. Clasificar estados
        6. (NUEVO) Sincronizar cuentas de clientes si update_client_accounts=True
        7. Guardar resultados

        Args:
            target_date: Fecha para calcular ROI (ej: 07/10/2025)
            skip_cache_clear: Si True, NO limpia cache (para procesamiento batch)
            window_days: Ventana de días para ROI (3, 5, 7, 10, 15, 30). Default: 7
            update_client_accounts: Si True, sincroniza cuentas de clientes. Default: False
            simulation_id: ID de la simulacion (requerido si update_client_accounts=True)
            dry_run: Si True, simula cambios sin guardar. Default: False

        Returns:
            Diccionario con resultado del calculo
        """
        logger.info(f"=== PROCESANDO FECHA UNICA: {target_date} (VENTANA {window_days}D) ===")
        print(f"[DEBUG_ORCHESTRATOR] update_client_accounts={update_client_accounts}, simulation_id={simulation_id}")
        print(f"[DEBUG_ORCHESTRATOR] self.client_accounts_sync={'presente' if self.client_accounts_sync else 'None'}")

        deleted_daily = 0
        deleted_7d = 0

        # PASO 1: Limpiar cache temporal (SOLO si no es procesamiento batch)
        if not skip_cache_clear:
            logger.info("Limpiando cache temporal...")
            deleted_daily = await self.daily_roi_repo.clear_all()
            deleted_7d = await self.roi_7d_repo.clear_all()
            logger.info(f"Cache limpiado: {deleted_daily} ROIs diarios, {deleted_7d} ROIs 7D")

        # PASO 2: Seleccionar Top 16 (esto internamente calcula ROI para todos)
        logger.info(f"Calculando ROI_{window_days}D y seleccionando Top 16...")
        top16, top16_all = await self.selection_service.select_top_16(
            target_date, window_days=window_days
        )

        casterly_agent_ids = [agent["agent_id"] for agent in top16]
        logger.info(f"Top 16 seleccionados: {len(casterly_agent_ids)} agentes")

        # PASO 3: Guardar Top 16 en base de datos
        top16_saved = self.selection_service.save_top16_to_database(
            target_date, top16, casterly_agent_ids, window_days=window_days
        )

        # PASO 4: Asignar cuentas
        logger.info("Asignando cuentas a Top 16...")
        assignment_result = self.assignment_service.create_initial_assignments(
            target_date, casterly_agent_ids
        )

        # PASO 5: Clasificar estados
        logger.info("Clasificando estados de agentes...")
        classification_result = await self.state_service.classify_all_agents(
            target_date, casterly_agent_ids
        )

        logger.info(
            f"Procesamiento completado: {assignment_result['total_assignments']} cuentas asignadas, "
            f"{classification_result['total_agents']} agentes clasificados"
        )

        # PASO 6: (NUEVO) Sincronizar cuentas de clientes
        client_accounts_result = None
        print(f"[DEBUG_SYNC] Verificando condicion: update_client_accounts={update_client_accounts}, self.client_accounts_sync={self.client_accounts_sync is not None}")
        if update_client_accounts and self.client_accounts_sync:
            print(f"[DEBUG_SYNC] Condicion CUMPLIDA - verificando simulation_id={simulation_id}")
            if not simulation_id:
                print("[DEBUG_SYNC] NO HAY simulation_id - saltando")
                logger.warning("update_client_accounts=True pero simulation_id no proporcionado. Saltando sincronizacion.")
            else:
                try:
                    print(f"[DEBUG_SYNC] INICIANDO SYNC - fecha={target_date}, window_days={window_days}")
                    logger.info("=== SINCRONIZANDO CUENTAS DE CLIENTES ===")

                    client_accounts_result = await self.client_accounts_sync.sync_with_simulation_day(
                        target_date=target_date,
                        simulation_id=simulation_id,
                        window_days=window_days,
                        dry_run=dry_run
                    )

                    logger.info(
                        f"Sincronizacion de cuentas completada:"
                        f"\n  Cuentas actualizadas: {client_accounts_result.cuentas_actualizadas}"
                        f"\n  Cuentas redistribuidas: {client_accounts_result.cuentas_redistribuidas}"
                        f"\n  Rotaciones procesadas: {client_accounts_result.rotaciones_procesadas}"
                        f"\n  Balance: ${client_accounts_result.balance_total_antes:,.2f} -> ${client_accounts_result.balance_total_despues:,.2f}"
                        f"\n  ROI promedio: {client_accounts_result.roi_promedio_antes:.2f}% -> {client_accounts_result.roi_promedio_despues:.2f}%"
                    )

                except Exception as e:
                    logger.error(f"Error en sincronizacion de cuentas de clientes: {e}", exc_info=True)
                    # No fallar la simulacion completa por error en sincronizacion
                    client_accounts_result = {
                        "error": str(e),
                        "success": False
                    }
        elif update_client_accounts and not self.client_accounts_sync:
            print("[DEBUG_SYNC] update_client_accounts=True PERO self.client_accounts_sync es None!")
            logger.warning("update_client_accounts=True pero ClientAccountsSimulationService no esta configurado")
        else:
            print(f"[DEBUG_SYNC] Condicion NO cumplida - update_client_accounts={update_client_accounts}")

        # Preparar datos completos del Top 16 con ROI
        # IMPORTANTE: Usar campo dinamico basado en window_days (roi_3d, roi_7d, roi_30d, etc.)
        roi_field = f"roi_{window_days}d"
        top_16_with_data = [
            {
                "userId": agent["userId"],
                "roi_7d": agent.get(roi_field, 0.0),  # Mantener nombre "roi_7d" para compatibilidad con frontend
                "total_pnl": agent.get("total_pnl", 0.0),
                "balance": agent.get("balance_current", 0.0),
                "total_trades_7d": agent.get("total_trades_7d", 0),
                "rank": agent.get("rank", idx + 1)
            }
            for idx, agent in enumerate(top16)
        ]

        logger.info(f"=== PROCESAMIENTO COMPLETADO ===")

        result = {
            "success": True,
            "date": target_date.isoformat(),
            "phase": "single_date_calculation",
            "top_16_agents": casterly_agent_ids,
            "top_16_data": top_16_with_data,
            "total_accounts_assigned": assignment_result["total_assignments"],
            "states_classified": classification_result["total_agents"],
            "growth_count": classification_result["growth_count"],
            "fall_count": classification_result["fall_count"],
            "cache_cleared": {
                "daily_roi": deleted_daily,
                "roi_7d": deleted_7d
            }
        }

        # Agregar resultado de sincronizacion si existe
        if client_accounts_result:
            if isinstance(client_accounts_result, dict):
                result["client_accounts_sync"] = client_accounts_result
            else:
                result["client_accounts_sync"] = {
                    "success": True,
                    "cuentas_actualizadas": client_accounts_result.cuentas_actualizadas,
                    "cuentas_redistribuidas": client_accounts_result.cuentas_redistribuidas,
                    "rotaciones_procesadas": client_accounts_result.rotaciones_procesadas,
                    "snapshot_id": client_accounts_result.snapshot_id,
                    "balance_total_antes": client_accounts_result.balance_total_antes,
                    "balance_total_despues": client_accounts_result.balance_total_despues,
                    "roi_promedio_antes": client_accounts_result.roi_promedio_antes,
                    "roi_promedio_despues": client_accounts_result.roi_promedio_despues
                }

        return result

    async def run_simulation(
        self,
        start_date: date,
        end_date: date,
        update_client_accounts: bool = False,
        simulation_id: Optional[str] = None,
        window_days: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Ejecuta la simulacion completa para el periodo especificado.

        VERSION 3.0: INTEGRADO CON CLIENT ACCOUNTS
        - Limpia cache temporal al inicio (daily_roi_calculation, agent_roi_7d)
        - Usa nueva logica de calculo basada en closedPnl
        - Sincroniza cuentas de clientes dia a dia

        Proceso:
        1. Limpiar cache temporal (CRITICO)
        2. Dia 1: Asignacion inicial con nueva logica
        3. Dias 2-N: Procesamiento diario con rotaciones
        4. (NUEVO) Sincronizacion de cuentas de clientes cada dia

        Args:
            start_date: Fecha de inicio (debe ser 01-Sep-2025)
            end_date: Fecha de fin (debe ser 07-Oct-2025)
            update_client_accounts: Si True, sincroniza cuentas de clientes. Default: False
            simulation_id: ID de la simulacion (requerido si update_client_accounts=True)
            window_days: Ventana de días para ROI (3, 5, 7, 10, 15, 30). Default: 7
            dry_run: Si True, simula cambios sin guardar. Default: False

        Returns:
            Diccionario con resumen completo de la simulacion
        """
        if start_date > end_date:
            logger.error(
                f"Invalid date range: start_date ({start_date}) > end_date ({end_date})"
            )
            return {
                "success": False,
                "message": "start_date debe ser menor o igual que end_date",
            }

        logger.info(
            f"Starting simulation: {start_date.isoformat()} to {end_date.isoformat()}"
        )

        if update_client_accounts and not simulation_id:
            logger.warning("update_client_accounts=True pero simulation_id no proporcionado. Generando ID automaticamente.")
            simulation_id = f"sim_{window_days}d_{start_date.isoformat()}"

        logger.info("Cleaning temporal cache collections...")
        deleted_daily = await self.daily_roi_repo.clear_all()
        deleted_7d = await self.roi_7d_repo.clear_all()
        logger.info(
            f"Cache cleared: {deleted_daily} daily ROIs, {deleted_7d} 7D ROIs deleted"
        )

        daily_results = []
        current_date = start_date

        logger.info(f"Processing Day One: {current_date}")
        day_one_result = await self.process_day_one(
            current_date,
            update_client_accounts=update_client_accounts,
            simulation_id=simulation_id,
            window_days=window_days,
            dry_run=dry_run
        )
        daily_results.append(day_one_result)

        current_date += timedelta(days=1)

        while current_date <= end_date:
            logger.info(f"Processing day: {current_date}")
            daily_result = await self.process_daily(
                current_date,
                update_client_accounts=update_client_accounts,
                simulation_id=simulation_id,
                window_days=window_days,
                dry_run=dry_run
            )
            daily_results.append(daily_result)
            current_date += timedelta(days=1)

        total_rotations = sum(
            result.get("rotations_executed", 0) for result in daily_results
        )

        # Recopilar estadisticas de sincronizacion de cuentas
        total_client_accounts_syncs = 0
        final_client_accounts_sync = None
        for result in daily_results:
            if "client_accounts_sync" in result and result["client_accounts_sync"].get("success"):
                total_client_accounts_syncs += 1
                final_client_accounts_sync = result["client_accounts_sync"]

        logger.info(
            f"Simulation complete: {len(daily_results)} days processed, "
            f"{total_rotations} rotations executed"
        )

        if update_client_accounts and total_client_accounts_syncs > 0:
            logger.info(
                f"Client Accounts: {total_client_accounts_syncs} dias sincronizados"
            )
            if final_client_accounts_sync:
                logger.info(
                    f"Estado final de cuentas: Balance=${final_client_accounts_sync.get('balance_total_despues', 0):,.2f}, "
                    f"ROI={final_client_accounts_sync.get('roi_promedio_despues', 0):.2f}%"
                )

        summary = {
            "total_rotations": total_rotations,
            "final_casterly_agents": daily_results[-1].get(
                "current_casterly_agents", []
            ),
        }

        # Agregar resumen de cuentas de clientes si se sincronizaron
        if update_client_accounts and final_client_accounts_sync:
            summary["client_accounts"] = {
                "total_syncs": total_client_accounts_syncs,
                "final_balance": final_client_accounts_sync.get("balance_total_despues", 0),
                "final_roi_promedio": final_client_accounts_sync.get("roi_promedio_despues", 0),
                "total_cuentas_actualizadas": final_client_accounts_sync.get("cuentas_actualizadas", 0),
                "simulation_id": simulation_id
            }

        return {
            "success": True,
            "simulation_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": len(daily_results),
            },
            "summary": summary,
            "daily_results": daily_results,
        }

    def get_simulation_summary(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Obtiene un resumen de la simulacion sin detalles diarios.

        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin

        Returns:
            Resumen consolidado
        """
        rotation_logs = self.replacement_service.rotation_log_repo.get_by_date_range(
            start_date,
            end_date
        )

        states_final = self.state_repo.get_by_date(end_date)
        active_agents = [state.agent_id for state in states_final if state.is_in_casterly]

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_rotations": len(rotation_logs),
            "final_active_agents": len(active_agents),
            "active_agents_list": active_agents
        }
