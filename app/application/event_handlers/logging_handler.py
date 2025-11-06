import logging
from app.domain.events.agent_events import (
    AgentExitedEvent,
    AgentEnteredEvent,
    AgentRotationCompletedEvent,
    AgentStateChangedEvent,
    AgentFallingConsecutiveDaysEvent
)
from app.domain.events.assignment_events import (
    AccountsAssignedEvent,
    AccountsReassignedEvent
)
from app.domain.events.simulation_events import (
    DailyProcessCompletedEvent,
    SimulationCompletedEvent
)

logger = logging.getLogger(__name__)


class LoggingEventHandler:
    """
    Handler que registra todos los eventos en los logs.

    Este handler es util para auditoria y debugging,
    manteniendo un registro completo de todos los eventos
    que ocurren en el sistema.
    """

    @staticmethod
    def handle_agent_exited(event: AgentExitedEvent) -> None:
        """Registra cuando un agente sale de Casterly Rock"""
        logger.info(
            f"[EVENT] AgentExited: {event.agent_id} exited on {event.exit_date} "
            f"(reason: {event.reason}, ROI: {event.roi_total}, fall_days: {event.fall_days})"
        )

    @staticmethod
    def handle_agent_entered(event: AgentEnteredEvent) -> None:
        """Registra cuando un agente entra a Casterly Rock"""
        logger.info(
            f"[EVENT] AgentEntered: {event.agent_id} entered on {event.entry_date} "
            f"(ROI 7D: {event.roi_7d}, AUM: ${event.total_aum:,.2f}, "
            f"replaced: {event.replaced_agent_id})"
        )

    @staticmethod
    def handle_rotation_completed(event: AgentRotationCompletedEvent) -> None:
        """Registra cuando se completa una rotacion"""
        logger.info(
            f"[EVENT] RotationCompleted: {event.agent_out} -> {event.agent_in} "
            f"on {event.rotation_date} (reason: {event.reason}, "
            f"accounts: {event.n_accounts}, AUM: ${event.total_aum:,.2f})"
        )

    @staticmethod
    def handle_state_changed(event: AgentStateChangedEvent) -> None:
        """Registra cuando cambia el estado de un agente"""
        logger.info(
            f"[EVENT] StateChanged: {event.agent_id} changed from {event.previous_state} "
            f"to {event.new_state} on {event.change_date} "
            f"(ROI: {event.roi_day:.4f}, P&L: ${event.pnl_day:,.2f})"
        )

    @staticmethod
    def handle_falling_consecutive_days(event: AgentFallingConsecutiveDaysEvent) -> None:
        """Registra alertas de caidas consecutivas"""
        logger.warning(
            f"[EVENT] FallingConsecutiveDays: {event.agent_id} has been falling for "
            f"{event.fall_days} consecutive days (ROI since entry: {event.roi_since_entry})"
        )

    @staticmethod
    def handle_accounts_assigned(event: AccountsAssignedEvent) -> None:
        """Registra asignacion de cuentas"""
        logger.info(
            f"[EVENT] AccountsAssigned: {event.total_accounts} accounts assigned to "
            f"{event.total_agents} agents on {event.assignment_date} "
            f"(Total AUM: ${event.total_aum:,.2f})"
        )

    @staticmethod
    def handle_accounts_reassigned(event: AccountsReassignedEvent) -> None:
        """Registra reasignacion de cuentas"""
        logger.info(
            f"[EVENT] AccountsReassigned: {len(event.account_ids)} accounts "
            f"from {event.from_agent_id} to {event.to_agent_id} "
            f"(AUM: ${event.total_aum_transferred:,.2f})"
        )

    @staticmethod
    def handle_daily_process_completed(event: DailyProcessCompletedEvent) -> None:
        """Registra completacion de proceso diario"""
        logger.info(
            f"[EVENT] DailyProcessCompleted: {event.process_date} - "
            f"{event.agents_in_casterly} agents in Casterly, "
            f"{event.rotations_count} rotations, "
            f"Growth: {event.growth_agents}, Fall: {event.fall_agents} "
            f"(Processing time: {event.processing_time_ms:.2f}ms)"
        )

    @staticmethod
    def handle_simulation_completed(event: SimulationCompletedEvent) -> None:
        """Registra completacion de simulacion"""
        logger.info(
            f"[EVENT] SimulationCompleted: {event.start_date} to {event.end_date} - "
            f"{event.total_days} days processed, {event.total_rotations} rotations, "
            f"Final agents: {event.final_agents_count}, Final AUM: ${event.final_aum:,.2f} "
            f"(Duration: {event.simulation_duration_seconds:.2f}s, Success: {event.success})"
        )
        if not event.success:
            logger.error(f"Simulation completed with {len(event.errors)} errors: {event.errors}")
