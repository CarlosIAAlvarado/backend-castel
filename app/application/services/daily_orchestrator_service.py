from typing import Dict, Any, Optional, List
from datetime import date, timedelta
import logging
from app.application.services.selection_service import SelectionService
from app.application.services.assignment_service import AssignmentService
from app.application.services.state_classification_service import StateClassificationService
from app.application.services.exit_rules_service import ExitRulesService
from app.application.services.replacement_service import ReplacementService
from app.application.services.client_accounts_simulation_service import ClientAccountsSimulationService
from app.application.services.simulation_response_builder import SimulationResponseBuilder
# RebalancingService ELIMINADO - FLUJO REAL: No hay rebalanceos programados
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.infrastructure.repositories.daily_roi_repository import DailyROIRepository
from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository
from app.domain.constants.business_rules import STOP_LOSS_THRESHOLD, CONSECUTIVE_FALL_THRESHOLD

logger = logging.getLogger(__name__)


class DailyOrchestratorService:
    """
    Servicio orquestador para la simulacion diaria completa.

    VERSION 4.0 - FLUJO REAL (SIN REBALANCEO PROGRAMADO)

    FLUJO CORRECTO:
    - window_days = KPI a evaluar (ROI_3d, ROI_5d, ROI_7d, etc.)
    - ROI con ventana deslizante: ROI_Nd = (Σ P&L últimos N días) / Balance_inicial_(t-N+1)
    - NO existe rebalanceo programado
    - Rotaciones ocurren SOLO cuando un agente es expulsado por reglas
    - Las cuentas se mantienen con sus agentes salvo expulsión

    Coordina todos los servicios para ejecutar el flujo diario:
    1. Calcular ROI con ventana deslizante (TODOS los días)
    2. Formar Top 16 actual
    3. Clasificar estados (GROWTH/FALL)
    4. Evaluar y aplicar reglas de salida:
       - 3 días consecutivos de pérdida (desde entrada al Top)
       - -10% acumulado (desde entrada al Top)
    5. Comparar Top hoy vs Top ayer
    6. Rotar SOLO las cuentas de agentes expulsados/reemplazados
    7. Actualizar asignaciones y crear snapshots
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
        client_accounts_sync_service: Optional[ClientAccountsSimulationService] = None,
        status_repo: Optional[Any] = None
    ):
        """
        Constructor con inyeccion de dependencias.

        VERSION 5.0 - FLUJO REAL: Eliminado RebalancingService

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
        self.status_repo = status_repo

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
        logger.debug(f"Processing Day One: {target_date} with window_days={window_days}")

        top16, top16_all = await self.selection_service.select_top_16(target_date, window_days=window_days)

        casterly_agent_ids = [agent["agent_id"] for agent in top16]

        logger.info(f"Top 16 selected: {len(casterly_agent_ids)} agents")

        self.selection_service.save_top16_to_database(
            target_date, top16, casterly_agent_ids, window_days=window_days
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
        trades_field = f"total_trades_{window_days}d"
        top_16_with_data = [
            {
                "userId": agent["userId"],
                roi_field: agent.get(roi_field, 0.0),  # Campo dinamico segun window_days
                "total_pnl": agent.get("total_pnl", 0.0),
                "balance": agent.get("balance_current", 0.0),
                trades_field: agent.get("total_trades_7d", 0),  # TODO: Este tambien debe ser dinamico en bulk_service
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

    def _get_current_casterly_agents(self, target_date: date) -> list[str]:
        """
        Obtiene la lista de agentes activos en Casterly.

        Returns:
            Lista de agent_ids activos
        """
        states = self.state_repo.get_by_date(target_date - timedelta(days=1))
        current_casterly_agents = list(
            {state.agent_id for state in states if state.is_in_casterly}
        )
        return current_casterly_agents

    def _get_top30_candidates(self, target_date: date) -> list[str]:
        """
        Obtiene candidatos del Top 30 del día anterior.

        Returns:
            Lista de agent_ids candidatos
        """
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
        return top30_candidates

    # TODO: Método calculate_roi_with_sliding_window() será implementado después
    # cuando se agreguen los métodos necesarios en BalanceRepository y MovementRepository

    async def _calculate_and_save_top16(
        self,
        target_date: date,
        relevant_agents: list[str],
        current_casterly_agents: list[str],
        window_days: int
    ) -> list[Dict[str, Any]]:
        """
        Calcula ROI, rankea agentes y guarda Top 16.

        Returns:
            Lista de agentes del Top 16
        """
        logger.debug(
            f"Calculating ROI for {len(relevant_agents)} relevant agents "
            f"({len(current_casterly_agents)} active + candidates)"
        )

        # USA VERSION ULTRA RAPIDA
        agents_data = await self.selection_service.calculate_all_agents_roi_7d_ULTRA_FAST(
            target_date, agent_ids=relevant_agents, window_days=window_days
        )

        ranked_agents = self.selection_service.rank_agents_by_roi_7d(agents_data, window_days=window_days)
        top16 = ranked_agents[:16]

        self.selection_service.save_top16_to_database(
            target_date, top16, current_casterly_agents, window_days=window_days
        )

        return top16

    async def _process_rotations(
        self,
        target_date: date,
        current_casterly_agents: list[str],
        window_days: int = 7
    ) -> tuple[list[Dict[str, Any]], list[str]]:
        """
        Evalúa reglas de salida y ejecuta rotaciones necesarias.

        Args:
            target_date: Fecha objetivo
            current_casterly_agents: Lista de agentes activos en Casterly
            window_days: Ventana de días para ROI (default: 7)

        Returns:
            tuple: (rotations_executed, new_agents_to_classify)
        """
        evaluation_result = self.exit_rules_service.evaluate_all_agents(target_date)

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
                replacement_agent = await self.replacement_service.find_replacement_agent(
                    target_date,
                    current_casterly_agents,
                    window_days
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
                    # Obtener ROI total acumulado correcto
                    roi_total_out = self.replacement_service.get_agent_total_roi(agent_out, target_date)

                    rotation_log = self.replacement_service.register_rotation(
                        date=target_date,
                        agent_out=agent_out,
                        agent_in=agent_in,
                        reason=reason_str,
                        window_days=window_days,
                        roi_window_out=roi_7d_out,
                        roi_total_out=roi_total_out,
                        roi_window_in=replacement_agent.get("roi_7d", 0.0),
                        n_accounts=transfer_result["n_accounts_transferred"],
                        total_aum=transfer_result["total_aum_transferred"]
                    )

                    # Usar campos dinámicos según window_days
                    roi_field = f"roi_{window_days}d"

                    replacement_result = {
                        "success": True,
                        "date": target_date.isoformat(),
                        "agent_out": agent_out,
                        "agent_in": agent_in,
                        "reason": reason_str,
                        "n_accounts_transferred": transfer_result["n_accounts_transferred"],
                        "total_aum_transferred": transfer_result["total_aum_transferred"],
                        f"agent_out_{roi_field}": roi_7d_out,  # Campo dinámico: agent_out_roi_3d, etc.
                        "agent_out_roi_total": roi_total_out,
                        f"agent_in_{roi_field}": replacement_agent.get("roi_7d", 0.0),  # Campo dinámico: agent_in_roi_3d, etc.
                        "rotation_log_id": rotation_log.id
                    }

                    rotations_executed.append(replacement_result)
                    if agent_out in current_casterly_agents:
                        current_casterly_agents.remove(agent_out)
                    current_casterly_agents.append(agent_in)
                    new_agents_to_classify.append(agent_in)

        return rotations_executed, new_agents_to_classify

    # MÉTODO _execute_rebalancing ELIMINADO - FLUJO REAL: No hay rebalanceos programados

    async def _sync_client_accounts(
        self,
        target_date: date,
        update_client_accounts: bool,
        simulation_id: Optional[str],
        window_days: int,
        dry_run: bool
    ) -> Optional[Any]:
        """
        Sincroniza cuentas de clientes si está habilitado.

        Returns:
            Resultado de sincronización o None
        """
        if not update_client_accounts:
            return None

        if not self.client_accounts_sync:
            logger.warning("update_client_accounts=True pero ClientAccountsSimulationService no esta configurado")
            return None

        if not simulation_id:
            logger.warning("update_client_accounts=True pero simulation_id no proporcionado. Saltando sincronizacion.")
            return None

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

            return client_accounts_result

        except Exception as e:
            logger.error(f"Error en sincronizacion de cuentas de clientes: {e}", exc_info=True)
            return {
                "error": str(e),
                "success": False
            }

    def _build_response_data(
        self,
        target_date: date,
        top16: list[Dict[str, Any]],
        current_casterly_agents: list[str],
        classification_result: Dict[str, Any],
        evaluation_result: Dict[str, Any],
        rotations_executed: list[Dict[str, Any]],
        client_accounts_result: Optional[Any],
        window_days: int
    ) -> Dict[str, Any]:
        """
        Construye el diccionario de respuesta final usando SimulationResponseBuilder (SRP).

        SOLID Improvement: Delegado a SimulationResponseBuilder para separar
        la responsabilidad de construcción de respuestas.

        Returns:
            Diccionario con todos los resultados del día
        """
        return SimulationResponseBuilder.build_daily_response(
            target_date=target_date,
            top16=top16,
            current_casterly_agents=current_casterly_agents,
            classification_result=classification_result,
            evaluation_result=evaluation_result,
            rotations_executed=rotations_executed,
            client_accounts_result=client_accounts_result,
            window_days=window_days
        )

    async def process_daily(
        self,
        target_date: date,
        current_day: int,
        update_client_accounts: bool = False,
        simulation_id: Optional[str] = None,
        window_days: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Procesa un dia normal de simulacion (02-Sep en adelante).

        VERSION 5.0 - FLUJO REAL (SIN REBALANCEO PROGRAMADO)

        Orden de ejecución según flujo real:
        1. Calcular ROI con ventana deslizante (TODOS los días)
        2. Seleccionar Top 16 actual y guardar
        3. Clasificar estados (GROWTH/FALL)
        4. Aplicar reglas de salida (Stop Loss desde entrada, 3 días FALL desde entrada)
        5. Comparar Top hoy vs Top ayer
        6. Rotar SOLO las cuentas de agentes expulsados/reemplazados
        7. Sincronizar cuentas de clientes

        IMPORTANTE: NO existe rebalanceo programado. Rotaciones ocurren SOLO por expulsión.

        Args:
            target_date: Fecha del dia a procesar
            current_day: Número de día en la simulación (1, 2, 3, ..., 30)
            update_client_accounts: Si True, sincroniza cuentas de clientes. Default: False
            simulation_id: ID de la simulacion (requerido si update_client_accounts=True)
            window_days: KPI a evaluar (3, 5, 7, 10, 15, 30). Default: 7
            dry_run: Si True, simula cambios sin guardar. Default: False

        Returns:
            Diccionario con resultado del dia
        """
        logger.info(f"=== PROCESANDO DÍA {current_day}: {target_date} (window={window_days}d) ===")

        # 1. Obtener agentes activos en Casterly
        current_casterly_agents = self._get_current_casterly_agents(target_date)

        if not current_casterly_agents:
            logger.warning(f"No active agents in Casterly for {target_date}")
            return {
                "success": False,
                "message": f"No hay agentes activos en Casterly para la fecha {target_date}",
            }

        # 2. Obtener candidatos del Top 30 del día anterior
        top30_candidates = self._get_top30_candidates(target_date)

        # 3. Combinar agentes activos + candidatos
        relevant_agents = list(set(current_casterly_agents + top30_candidates))

        # 4. Calcular ROI, rankear y guardar Top 16
        top16 = await self._calculate_and_save_top16(
            target_date,
            relevant_agents,
            current_casterly_agents,
            window_days
        )

        # 5. FLUJO REAL: Detectar agentes nuevos vs agentes que ya estaban
        # Obtener Top 16 del día anterior para comparar
        previous_top16_records = self.selection_service.get_top16_by_date(
            target_date - timedelta(days=1)
        )
        previous_casterly_ids = {
            record.agent_id for record in previous_top16_records
            if record.is_in_casterly
        } if previous_top16_records else set()

        # Identificar nuevos agentes que entraron hoy al Top
        current_top16_ids = {agent["agent_id"] for agent in top16}
        new_entries = current_top16_ids - previous_casterly_ids

        logger.info(
            f"[ENTRY_DETECTION] Día {current_day}: "
            f"{len(new_entries)} nuevos agentes entraron al Top 16: {list(new_entries)}"
        )

        # 6. Clasificar estados de todos los agentes activos
        # Para agentes nuevos, marcar is_new_entry=True para resetear entry_date
        classification_result = await self.state_service.classify_all_agents(
            target_date,
            current_casterly_agents
        )

        # Actualizar entry_date para nuevos agentes manualmente
        for agent_id in new_entries:
            if agent_id in current_casterly_agents:
                agent_state = self.state_repo.get_by_agent_and_date(agent_id, target_date)
                if agent_state:
                    self.state_repo.update_state(
                        agent_id,
                        target_date,
                        {
                            "entry_date": target_date.isoformat(),  # Convertir a string ISO
                            "roi_since_entry": agent_state.roi_day  # Comienza desde ROI del día de entrada
                        }
                    )
                    logger.info(
                        f"[ENTRY_RESET] {agent_id} - entry_date actualizado a {target_date.isoformat()}, "
                        f"roi_since_entry reseteo a {agent_state.roi_day:.4f}"
                    )

        # 7. Procesar rotaciones (evaluar + ejecutar)
        rotations_executed, new_agents_to_classify = await self._process_rotations(
            target_date,
            current_casterly_agents,
            window_days
        )

        # 8. Clasificar nuevos agentes que entraron por rotación
        if new_agents_to_classify:
            # Marcar estos agentes como nuevas entradas
            for agent_id in new_agents_to_classify:
                await self.state_service.classify_state(
                    agent_id,
                    target_date,
                    is_new_entry=True
                )

        # 9. FLUJO REAL: No hay verificación de días de rebalanceo
        # Las rotaciones ya se ejecutaron en paso 7 (_process_rotations)
        logger.debug(f"Día {current_day}: Rotaciones ejecutadas basadas en reglas de expulsión únicamente")

        # 10. Sincronizar cuentas de clientes (si está habilitado)
        client_accounts_result = await self._sync_client_accounts(
            target_date,
            update_client_accounts,
            simulation_id,
            window_days,
            dry_run
        )

        # 10.5. Verificar y rotar cuentas que alcanzaron stop loss individual (-10%)
        stop_loss_result = None
        if update_client_accounts and simulation_id and self.client_accounts_sync:
            logger.info(f"[STOP_LOSS_CHECK] Iniciando verificación de stop loss para cuentas de clientes")
            from datetime import datetime
            stop_loss_result = self.client_accounts_sync.client_accounts_service.check_and_rotate_stop_loss_accounts(
                simulation_id=simulation_id,
                target_date=datetime.combine(target_date, datetime.min.time()),
                window_days=window_days,
                stop_loss_threshold=-0.10
            )
            logger.info(
                f"[STOP_LOSS_CHECK] Resultado: {stop_loss_result['cuentas_con_stop_loss']} cuentas con stop loss, "
                f"{stop_loss_result['cuentas_rotadas']} rotadas exitosamente"
            )

        # 11. Construir respuesta con todos los datos del día
        # Necesitamos volver a obtener evaluation_result para la respuesta
        evaluation_result = self.exit_rules_service.evaluate_all_agents(target_date)

        result = self._build_response_data(
            target_date,
            top16,
            current_casterly_agents,
            classification_result,
            evaluation_result,
            rotations_executed,
            client_accounts_result,
            window_days
        )

        # Agregar resultado de stop loss si existe
        if stop_loss_result:
            result["stop_loss_check"] = stop_loss_result

        # FLUJO REAL: No hay información de rebalanceo programado

        logger.info(f"=== DÍA {current_day} COMPLETADO ===")

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
        logger.debug(f"[DEBUG_ORCHESTRATOR] update_client_accounts={update_client_accounts}, simulation_id={simulation_id}")
        logger.debug(f"[DEBUG_ORCHESTRATOR] self.client_accounts_sync={'presente' if self.client_accounts_sync else 'None'}")

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
        self.selection_service.save_top16_to_database(
            target_date, top16, casterly_agent_ids, window_days=window_days
        )

        # PASOS 4 y 5: Ejecutar EN PARALELO (son independientes)
        import asyncio

        assignment_task = asyncio.to_thread(
            self.assignment_service.create_initial_assignments,
            target_date, casterly_agent_ids
        )
        classification_task = self.state_service.classify_all_agents(
            target_date, casterly_agent_ids
        )

        assignment_result, classification_result = await asyncio.gather(
            assignment_task,
            classification_task
        )

        logger.info(
            f"Procesamiento completado: {assignment_result['total_assignments']} cuentas asignadas, "
            f"{classification_result['total_agents']} agentes clasificados"
        )

        # PASO 6: (NUEVO) Sincronizar cuentas de clientes
        client_accounts_result = None
        logger.debug(f"[DEBUG_SYNC] Verificando condicion: update_client_accounts={update_client_accounts}, self.client_accounts_sync={self.client_accounts_sync is not None}")
        if update_client_accounts and self.client_accounts_sync:
            logger.debug(f"[DEBUG_SYNC] Condicion CUMPLIDA - verificando simulation_id={simulation_id}")
            if not simulation_id:
                logger.debug("[DEBUG_SYNC] NO HAY simulation_id - saltando")
                logger.warning("update_client_accounts=True pero simulation_id no proporcionado. Saltando sincronizacion.")
            else:
                try:
                    logger.debug(f"[DEBUG_SYNC] INICIANDO SYNC - fecha={target_date}, window_days={window_days}")
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
            logger.debug("[DEBUG_SYNC] update_client_accounts=True PERO self.client_accounts_sync es None!")
            logger.warning("update_client_accounts=True pero ClientAccountsSimulationService no esta configurado")
        else:
            logger.debug(f"[DEBUG_SYNC] Condicion NO cumplida - update_client_accounts={update_client_accounts}")

        # Preparar datos completos del Top 16 con ROI
        # IMPORTANTE: Usar campo dinamico basado en window_days (roi_3d, roi_7d, roi_30d, etc.)
        roi_field = f"roi_{window_days}d"
        trades_field = f"total_trades_{window_days}d"
        top_16_with_data = [
            {
                "userId": agent["userId"],
                roi_field: agent.get(roi_field, 0.0),  # Campo dinamico segun window_days
                "total_pnl": agent.get("total_pnl", 0.0),
                "balance": agent.get("balance_current", 0.0),
                trades_field: agent.get("total_trades_7d", 0),  # TODO: Este tambien debe ser dinamico en bulk_service
                "rank": agent.get("rank", idx + 1)
            }
            for idx, agent in enumerate(top16)
        ]

        logger.info("=== PROCESAMIENTO COMPLETADO ===")

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
        logger.info("=" * 80)
        logger.info(f"DEBUG: run_simulation() LLAMADO CORRECTAMENTE")
        logger.info(f"DEBUG: start_date={start_date}, end_date={end_date}, window_days={window_days}")
        logger.info("=" * 80)

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

        # Calcular total de días para el progreso
        total_days = (end_date - start_date).days + 1

        logger.debug(f"Processing Day One: {current_date}")

        # Actualizar progreso: Día 1
        if self.status_repo:
            self.status_repo.update_progress(
                current_day=1,
                message=f"Procesando día 1/{total_days}: {current_date}"
            )

        day_one_result = await self.process_day_one(
            current_date,
            update_client_accounts=update_client_accounts,
            simulation_id=simulation_id,
            window_days=window_days,
            dry_run=dry_run
        )
        daily_results.append(day_one_result)

        current_date += timedelta(days=1)
        current_day = 2  # Día 1 ya fue procesado

        while current_date <= end_date:
            logger.debug(f"Processing day {current_day}: {current_date}")

            # Actualizar progreso
            if self.status_repo:
                self.status_repo.update_progress(
                    current_day=current_day,
                    message=f"Procesando día {current_day}/{total_days}: {current_date}"
                )

            daily_result = await self.process_daily(
                current_date,
                current_day=current_day,
                update_client_accounts=update_client_accounts,
                simulation_id=simulation_id,
                window_days=window_days,
                dry_run=dry_run
            )
            daily_results.append(daily_result)
            current_date += timedelta(days=1)
            current_day += 1

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

        total_days = (end_date - start_date).days + 1
        return {
            "success": True,
            "simulation_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": total_days,
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
