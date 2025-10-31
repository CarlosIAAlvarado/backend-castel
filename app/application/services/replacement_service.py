from typing import List, Dict, Any, Optional
from datetime import date, datetime
import pytz
from app.domain.entities.rotation_log import RotationLog, RotationReason
from app.domain.repositories.rotation_log_repository import RotationLogRepository
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.domain.repositories.top16_repository import Top16Repository
from app.application.services.selection_service import SelectionService
from app.domain.events import (
    event_bus,
    AgentExitedEvent,
    AgentEnteredEvent,
    AgentRotationCompletedEvent,
    AccountsReassignedEvent
)


class ReplacementService:
    """
    Servicio para gestion de reemplazo de agentes.

    Responsabilidades:
    - Buscar agente de reemplazo en Top 16 externo
    - Transferir cuentas del agente saliente al entrante
    - Registrar rotacion en rotation_log
    - Actualizar estado del nuevo agente
    """

    def __init__(
        self,
        rotation_log_repo: RotationLogRepository,
        assignment_repo: AssignmentRepository,
        state_repo: AgentStateRepository,
        top16_repo: Top16Repository,
        selection_service: SelectionService
    ):
        """
        Constructor con inyeccion de dependencias.

        Args:
            rotation_log_repo: Repositorio de logs de rotacion
            assignment_repo: Repositorio de asignaciones
            state_repo: Repositorio de estados de agentes
            top16_repo: Repositorio de Top16
            selection_service: Servicio de seleccion de agentes
        """
        self.rotation_log_repo = rotation_log_repo
        self.assignment_repo = assignment_repo
        self.state_repo = state_repo
        self.top16_repo = top16_repo
        self.selection_service = selection_service
        self.timezone = pytz.timezone("America/Bogota")

    def find_replacement_agent(
        self,
        target_date: date,
        current_casterly_agents: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el mejor agente de reemplazo en el Top 16 externo.

        Selecciona el agente con mayor ROI_7D que NO este en Casterly Rock.

        Args:
            target_date: Fecha objetivo
            current_casterly_agents: Lista de agent_ids actualmente en Casterly

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
            top16_sorted = sorted(top16_records, key=lambda x: x.roi_7d, reverse=True)
            external_candidates = [
                {
                    "agent_id": record.agent_id,
                    "roi_7d": record.roi_7d,
                    "total_aum": record.total_aum,
                    "n_accounts": record.n_accounts
                }
                for record in top16_sorted
                if record.agent_id not in current_casterly_agents
            ]

        if not external_candidates:
            return None

        return external_candidates[0]

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
        roi_7d_out: float = 0.0,
        roi_total_out: float = 0.0,
        roi_7d_in: float = 0.0,
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
            roi_7d_out: ROI_7D del agente saliente
            roi_total_out: ROI total del agente saliente
            roi_7d_in: ROI_7D del agente entrante
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
            roi_7d_out=roi_7d_out,
            roi_total_out=roi_total_out,
            roi_7d_in=roi_7d_in,
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
        current_casterly_agents: List[str]
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

        Returns:
            Diccionario con resultado del reemplazo
        """
        replacement_agent = self.find_replacement_agent(
            target_date,
            current_casterly_agents
        )

        if not replacement_agent:
            return {
                "success": False,
                "message": "No se encontro agente de reemplazo disponible"
            }

        agent_in = replacement_agent["agent_id"]
        agent_in_roi_7d = replacement_agent.get("roi_7d")

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
            roi_7d_out=agent_out_roi_7d,
            roi_total_out=agent_out_roi_total,
            roi_7d_in=agent_in_roi_7d if agent_in_roi_7d else 0.0,
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
            roi_7d=agent_in_roi_7d,
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
            "agent_out_roi_7d": agent_out_roi_7d,
            "agent_out_roi_total": agent_out_roi_total,
            "agent_in_roi_7d": agent_in_roi_7d,
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
