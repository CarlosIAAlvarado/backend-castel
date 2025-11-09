from typing import List, Dict, Any, Optional
from datetime import date, datetime
import pytz
from app.domain.entities.rotation_log import RotationLog, RotationReason
from app.domain.repositories.rotation_log_repository import RotationLogRepository
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.domain.repositories.top16_repository import Top16Repository
from app.application.services.selection_service import SelectionService
from app.infrastructure.repositories.daily_roi_repository import DailyROIRepository
from app.domain.events import (
    event_bus,
    AgentExitedEvent,
    AgentEnteredEvent,
    AgentRotationCompletedEvent,
    AccountsReassignedEvent
)
from app.domain.constants.business_rules import STOP_LOSS_THRESHOLD


class ReplacementService:
    """
    Servicio para gestion de reemplazo de agentes.

    Responsabilidades:
    - Buscar agente de reemplazo en Top 16 externo
    - Transferir cuentas del agente saliente al entrante
    - Registrar rotacion en rotation_log
    - Actualizar estado del nuevo agente
    """

    def _get_roi_field_name(self, window_days: int) -> str:
        """
        Retorna el nombre del campo de ROI según la ventana de días.

        Args:
            window_days: Ventana de días (3, 5, 7, 10, 14, 15, 30)

        Returns:
            Nombre del campo (ej: 'roi_7d', 'roi_30d')
        """
        return f"roi_{window_days}d"

    def _get_roi_from_record(self, record, window_days: int) -> float:
        """
        Obtiene el ROI del registro según la ventana de días.

        Args:
            record: Registro de Top16Day o diccionario
            window_days: Ventana de días

        Returns:
            ROI de la ventana especificada, o 0.0 si no existe
        """
        field_name = self._get_roi_field_name(window_days)

        if hasattr(record, field_name):
            return getattr(record, field_name, 0.0)
        elif isinstance(record, dict):
            return record.get(field_name, 0.0)
        else:
            # Fallback a roi_7d si no existe el campo
            return getattr(record, 'roi_7d', 0.0) if hasattr(record, 'roi_7d') else record.get('roi_7d', 0.0)

    def __init__(
        self,
        rotation_log_repo: RotationLogRepository,
        assignment_repo: AssignmentRepository,
        state_repo: AgentStateRepository,
        top16_repo: Top16Repository,
        selection_service: SelectionService,
        daily_roi_repo: DailyROIRepository
    ):
        """
        Constructor con inyeccion de dependencias.

        Args:
            rotation_log_repo: Repositorio de logs de rotacion
            assignment_repo: Repositorio de asignaciones
            state_repo: Repositorio de estados de agentes
            top16_repo: Repositorio de Top16
            selection_service: Servicio de seleccion de agentes
            daily_roi_repo: Repositorio de ROI diario
        """
        self.rotation_log_repo = rotation_log_repo
        self.assignment_repo = assignment_repo
        self.state_repo = state_repo
        self.top16_repo = top16_repo
        self.selection_service = selection_service
        self.daily_roi_repo = daily_roi_repo
        self.timezone = pytz.timezone("America/Bogota")

    def get_agent_total_roi(self, agent_id: str, target_date: date) -> float:
        """
        Obtiene el ROI total acumulado de un agente hasta una fecha específica.

        Calcula la suma de todos los ROIs diarios desde el inicio hasta target_date.

        Args:
            agent_id: ID del agente
            target_date: Fecha hasta la cual calcular el ROI total

        Returns:
            ROI total acumulado (suma de ROIs diarios)
        """
        # Obtener todos los ROIs diarios del agente hasta la fecha objetivo
        daily_rois = self.daily_roi_repo.get_by_user_id_and_date_range(
            agent_id,
            start_date=None,  # Desde el inicio
            end_date=target_date
        )

        if not daily_rois:
            return 0.0

        # Sumar todos los ROIs diarios
        total_roi = sum(roi.roi_day for roi in daily_rois)
        return total_roi

    def find_replacement_agent(
        self,
        target_date: date,
        current_casterly_agents: List[str],
        window_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el mejor agente de reemplazo en el Top 16 externo.

        SEGÚN ESPECIFICACIÓN (Sección 4):
        Criterios de Selección (en orden de prioridad):
        1. Mejor ROI: El agente debe tener el ROI más alto disponible
        2. Historial limpio:
           a) NO tiene 3 días consecutivos de pérdida
           b) Tiene ROI acumulado >= -10% (Stop Loss)

        Args:
            target_date: Fecha objetivo
            current_casterly_agents: Lista de agent_ids actualmente en Casterly
            window_days: Ventana de días para evaluar ROI (default: 7)

        Returns:
            Diccionario con informacion del agente de reemplazo o None
        """
        top16_records = self.top16_repo.get_by_date(target_date)

        if not top16_records:
            top16, _ = self.selection_service.select_top_16(target_date)
            external_candidates = [
                agent for agent in top16
                if agent["agent_id"] not in current_casterly_agents
            ]
        else:
            # Ordenar por ROI dinámico según window_days
            top16_sorted = sorted(
                top16_records,
                key=lambda x: self._get_roi_from_record(x, window_days),
                reverse=True
            )
            external_candidates = [
                {
                    "agent_id": record.agent_id,
                    "roi_window": self._get_roi_from_record(record, window_days),
                    "total_aum": record.total_aum,
                    "n_accounts": record.n_accounts
                }
                for record in top16_sorted
                if record.agent_id not in current_casterly_agents
            ]

        if not external_candidates:
            return None

        # Filtrar candidatos que cumplen con los criterios de la especificación
        from app.utils.logging_config import logger

        logger.info(f"[REPLACEMENT_START] Buscando reemplazo en fecha {target_date}. Total candidatos externos: {len(external_candidates)}")

        valid_candidates = []
        excluded_by_stop_loss = []
        excluded_by_three_days = []
        excluded_by_negative_roi = []

        for candidate in external_candidates:
            agent_id = candidate["agent_id"]
            roi_window = candidate.get("roi_window", 0.0)

            # Obtener ROI acumulado total del agente
            roi_total = self.get_agent_total_roi(agent_id, target_date)

            # CRITERIO 1: ROI acumulado positivo (según especificación sección 4.2.b)
            if roi_total <= 0:
                excluded_by_negative_roi.append(
                    f"{agent_id} (ROI total: {roi_total * 100:.2f}%, ROI {window_days}D: {roi_window * 100:.2f}%)"
                )
                continue  # Agente no tiene ROI acumulado positivo

            # CRITERIO 2: ROI >= -10% (Stop Loss)
            if roi_window < STOP_LOSS_THRESHOLD:
                excluded_by_stop_loss.append(
                    f"{agent_id} (ROI {window_days}D: {roi_window * 100:.2f}%)"
                )
                continue  # Agente viola Stop Loss, no puede entrar

            # CRITERIO 3: NO tiene 3 días consecutivos de pérdida
            has_three_consecutive_losses = self.selection_service._check_three_consecutive_losses(
                agent_id, target_date
            )
            if has_three_consecutive_losses:
                excluded_by_three_days.append(
                    f"{agent_id} (ROI {window_days}D: {roi_window * 100:.2f}%)"
                )
                continue  # Agente tiene 3 días consecutivos negativos, no puede entrar

            # Si pasa todos los criterios, es un candidato válido
            valid_candidates.append(candidate)

        # Log de candidatos excluidos
        if excluded_by_negative_roi:
            logger.warning(f"[REPLACEMENT] Candidatos excluidos por ROI acumulado NO positivo: {excluded_by_negative_roi}")
        if excluded_by_stop_loss:
            logger.warning(f"[REPLACEMENT] Candidatos excluidos por Stop Loss: {excluded_by_stop_loss}")
        if excluded_by_three_days:
            logger.warning(f"[REPLACEMENT] Candidatos excluidos por 3 días consecutivos: {excluded_by_three_days}")

        if not valid_candidates:
            # No hay candidatos que cumplan los criterios
            fallback_roi = external_candidates[0].get('roi_window', 0.0)
            logger.error(
                f"[REPLACEMENT] NO hay candidatos válidos. Total candidatos: {len(external_candidates)}. "
                f"Usando fallback: {external_candidates[0]['agent_id']} con ROI {window_days}D: {fallback_roi * 100:.2f}%"
            )
            # Fallback: retornar el mejor disponible (aunque no cumpla todos los criterios)
            return external_candidates[0]

        # Retornar el candidato con mejor ROI que cumple todos los criterios
        selected = valid_candidates[0]
        selected_roi = selected.get('roi_window', 0.0)
        logger.info(
            f"[REPLACEMENT] Candidato seleccionado: {selected['agent_id']} con ROI {window_days}D: {selected_roi * 100:.2f}%. "
            f"Total válidos: {len(valid_candidates)}/{len(external_candidates)}"
        )
        return selected

    def transfer_accounts(
        self,
        agent_out: str,
        agent_in: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        Transfiere todas las cuentas de un agente saliente a uno entrante.

        Proceso:
        1. Desactiva asignaciones del agente saliente
        2. Crea nuevas asignaciones para el agente entrante
        3. Calcula totales de cuentas y AUM transferido

        Args:
            agent_out: ID del agente saliente
            agent_in: ID del agente entrante
            target_date: Fecha de la transferencia

        Returns:
            Diccionario con resultado de la transferencia
        """
        assignments_out = self.assignment_repo.get_active_by_agent(agent_out)

        if not assignments_out:
            return {
                "success": False,
                "message": f"No se encontraron cuentas activas para agente {agent_out}"
            }

        n_accounts_transferred = self.assignment_repo.transfer_accounts(agent_out, agent_in)

        total_aum_transferred = sum(assignment.balance for assignment in assignments_out)

        return {
            "success": True,
            "agent_out": agent_out,
            "agent_in": agent_in,
            "n_accounts_transferred": n_accounts_transferred,
            "total_aum_transferred": total_aum_transferred,
            "date": target_date.isoformat()
        }

    def register_rotation(
        self,
        date: date,
        agent_out: str,
        agent_in: str,
        reason: str,
        window_days: int,
        roi_window_out: float = 0.0,
        roi_total_out: float = 0.0,
        roi_window_in: float = 0.0,
        n_accounts: int = 0,
        total_aum: float = 0.0
    ) -> RotationLog:
        """
        Registra una rotacion en rotation_log.

        Args:
            date: Fecha de la rotacion
            agent_out: ID del agente saliente
            agent_in: ID del agente entrante
            reason: Motivo de la rotacion (debe ser: three_days_fall, stop_loss o manual)
            window_days: Ventana de días de la simulación (ej: 7, 30)
            roi_window_out: ROI del agente saliente en la ventana configurada
            roi_total_out: ROI total del agente saliente
            roi_window_in: ROI del agente entrante en la ventana configurada
            n_accounts: Numero de cuentas transferidas
            total_aum: AUM total transferido

        Returns:
            RotationLog creado
        """
        if isinstance(reason, str):
            if reason == "three_days_fall":
                reason_enum = RotationReason.THREE_DAYS_FALL
            elif reason == "stop_loss":
                reason_enum = RotationReason.STOP_LOSS
            else:
                reason_enum = RotationReason.MANUAL
        else:
            reason_enum = reason

        rotation_log = RotationLog(
            date=datetime.combine(date, datetime.min.time()),
            agent_out=agent_out,
            agent_in=agent_in,
            reason=reason_enum,
            window_days=window_days,
            roi_window_out=roi_window_out,
            roi_total_out=roi_total_out,
            roi_window_in=roi_window_in,
            # Compatibilidad legacy
            roi_7d_out=roi_window_out,
            roi_7d_in=roi_window_in,
            n_accounts=n_accounts,
            total_aum=total_aum
        )

        saved_log = self.rotation_log_repo.create(rotation_log)

        return saved_log

    def execute_replacement(
        self,
        agent_out: str,
        target_date: date,
        reason: str,
        current_casterly_agents: List[str],
        window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Ejecuta el proceso completo de reemplazo de un agente.

        Proceso:
        1. Busca agente de reemplazo en Top 16 externo
        2. Transfiere cuentas del saliente al entrante
        3. Registra rotacion en rotation_log
        4. Actualiza estado del agente saliente

        Args:
            agent_out: ID del agente saliente
            target_date: Fecha de la rotacion
            reason: Motivo de la rotacion
            current_casterly_agents: Lista de agentes actualmente en Casterly
            window_days: Ventana de días para ROI (default: 7)

        Returns:
            Diccionario con resultado del reemplazo
        """
        replacement_agent = self.find_replacement_agent(
            target_date,
            current_casterly_agents,
            window_days
        )

        if not replacement_agent:
            return {
                "success": False,
                "message": "No se encontro agente de reemplazo disponible"
            }

        agent_in = replacement_agent["agent_id"]
        agent_in_roi_window = replacement_agent.get("roi_window", 0.0)

        agent_out_state = self.state_repo.get_by_agent_and_date(agent_out, target_date)
        agent_out_roi_7d = agent_out_state.roi_day if agent_out_state else 0.0
        agent_out_roi_total = agent_out_state.roi_since_entry if agent_out_state else 0.0

        transfer_result = self.transfer_accounts(agent_out, agent_in, target_date)

        if not transfer_result["success"]:
            return transfer_result

        rotation_log = self.register_rotation(
            date=target_date,
            agent_out=agent_out,
            agent_in=agent_in,
            reason=reason,
            window_days=window_days,
            roi_window_out=agent_out_roi_7d,
            roi_total_out=agent_out_roi_total,
            roi_window_in=agent_in_roi_window,
            n_accounts=transfer_result["n_accounts_transferred"],
            total_aum=transfer_result["total_aum_transferred"]
        )

        # Publicar eventos de dominio
        # 1. Evento: Agente ha salido
        exit_event = AgentExitedEvent(
            agent_id=agent_out,
            exit_date=target_date,
            reason=reason,
            roi_total=agent_out_roi_total,
            fall_days=agent_out_state.fall_days if agent_out_state else 0,
            n_accounts=transfer_result["n_accounts_transferred"],
            total_aum=transfer_result["total_aum_transferred"]
        )
        event_bus.publish(exit_event)

        # 2. Evento: Nuevo agente ha entrado
        enter_event = AgentEnteredEvent(
            agent_id=agent_in,
            entry_date=target_date,
            roi_7d=agent_in_roi_window,
            n_accounts=transfer_result["n_accounts_transferred"],
            total_aum=transfer_result["total_aum_transferred"],
            replaced_agent_id=agent_out
        )
        event_bus.publish(enter_event)

        # 3. Evento: Rotacion completada
        rotation_event = AgentRotationCompletedEvent(
            rotation_date=target_date,
            agent_out=agent_out,
            agent_in=agent_in,
            reason=reason,
            n_accounts=transfer_result["n_accounts_transferred"],
            total_aum=transfer_result["total_aum_transferred"]
        )
        event_bus.publish(rotation_event)

        # 4. Evento: Cuentas reasignadas
        assignments_out = self.assignment_repo.get_active_by_agent(agent_in)
        account_ids = [assignment.account_id for assignment in assignments_out]

        reassignment_event = AccountsReassignedEvent(
            reassignment_date=target_date,
            from_agent_id=agent_out,
            to_agent_id=agent_in,
            account_ids=account_ids,
            total_aum_transferred=transfer_result["total_aum_transferred"]
        )
        event_bus.publish(reassignment_event)

        return {
            "success": True,
            "date": target_date.isoformat(),
            "agent_out": agent_out,
            "agent_in": agent_in,
            "reason": reason,
            "n_accounts_transferred": transfer_result["n_accounts_transferred"],
            "total_aum_transferred": transfer_result["total_aum_transferred"],
            "agent_out_roi_window": agent_out_roi_7d,
            "agent_out_roi_total": agent_out_roi_total,
            "agent_in_roi_window": agent_in_roi_window,
            "rotation_log_id": rotation_log.id
        }

    def get_rotation_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de rotaciones.

        Args:
            start_date: Fecha inicial (opcional)
            end_date: Fecha final (opcional)
            agent_id: Filtrar por agente especifico (opcional)

        Returns:
            Lista de rotaciones
        """
        if start_date and end_date:
            rotation_logs = self.rotation_log_repo.get_by_date_range(start_date, end_date)
        elif agent_id:
            rotation_logs = self.rotation_log_repo.get_by_agent(agent_id)
        else:
            rotation_logs = self.rotation_log_repo.get_all()

        return [
            {
                "id": log.id,
                "date": log.date.isoformat() if hasattr(log.date, 'isoformat') else str(log.date),
                "agent_out": log.agent_out,
                "agent_in": log.agent_in,
                "reason": log.reason,
                "n_accounts": log.n_accounts,
                "total_aum": log.total_aum
            }
            for log in rotation_logs
        ]
