from datetime import date
from typing import Optional, Dict, Any
from app.domain.events.base import DomainEvent


class AgentExitedEvent(DomainEvent):
    """
    Evento: Un agente ha salido de Casterly Rock.

    Este evento se dispara cuando un agente cumple las condiciones
    de salida (ej: caidas consecutivas, ROI bajo threshold).
    """

    def __init__(
        self,
        agent_id: str,
        exit_date: date,
        reason: str,
        roi_total: Optional[float] = None,
        fall_days: int = 0,
        n_accounts: int = 0,
        total_aum: float = 0.0
    ):
        super().__init__()
        self.agent_id = agent_id
        self.exit_date = exit_date
        self.reason = reason
        self.roi_total = roi_total
        self.fall_days = fall_days
        self.n_accounts = n_accounts
        self.total_aum = total_aum

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "exit_date": self.exit_date.isoformat(),
            "reason": self.reason,
            "roi_total": self.roi_total,
            "fall_days": self.fall_days,
            "n_accounts": self.n_accounts,
            "total_aum": self.total_aum
        }


class AgentEnteredEvent(DomainEvent):
    """
    Evento: Un nuevo agente ha entrado a Casterly Rock.

    Este evento se dispara cuando un agente es seleccionado
    del Top 16 para reemplazar a uno que salio.
    """

    def __init__(
        self,
        agent_id: str,
        entry_date: date,
        roi_7d: Optional[float] = None,
        n_accounts: int = 0,
        total_aum: float = 0.0,
        replaced_agent_id: Optional[str] = None
    ):
        super().__init__()
        self.agent_id = agent_id
        self.entry_date = entry_date
        self.roi_7d = roi_7d
        self.n_accounts = n_accounts
        self.total_aum = total_aum
        self.replaced_agent_id = replaced_agent_id

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "entry_date": self.entry_date.isoformat(),
            "roi_7d": self.roi_7d,
            "n_accounts": self.n_accounts,
            "total_aum": self.total_aum,
            "replaced_agent_id": self.replaced_agent_id
        }


class AgentRotationCompletedEvent(DomainEvent):
    """
    Evento: Se ha completado una rotacion (salida + entrada).

    Este evento se dispara cuando se completa el proceso completo
    de rotacion: un agente sale y otro entra en su lugar.
    """

    def __init__(
        self,
        rotation_date: date,
        agent_out: str,
        agent_in: str,
        reason: str,
        n_accounts: int = 0,
        total_aum: float = 0.0
    ):
        super().__init__()
        self.rotation_date = rotation_date
        self.agent_out = agent_out
        self.agent_in = agent_in
        self.reason = reason
        self.n_accounts = n_accounts
        self.total_aum = total_aum

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "rotation_date": self.rotation_date.isoformat(),
            "agent_out": self.agent_out,
            "agent_in": self.agent_in,
            "reason": self.reason,
            "n_accounts": self.n_accounts,
            "total_aum": self.total_aum
        }


class AgentStateChangedEvent(DomainEvent):
    """
    Evento: El estado de un agente ha cambiado (GROWTH <-> FALL).

    Este evento se dispara cuando un agente cambia de estado
    durante la clasificacion diaria.
    """

    def __init__(
        self,
        agent_id: str,
        change_date: date,
        previous_state: str,
        new_state: str,
        roi_day: float,
        pnl_day: float,
        fall_days: int = 0
    ):
        super().__init__()
        self.agent_id = agent_id
        self.change_date = change_date
        self.previous_state = previous_state
        self.new_state = new_state
        self.roi_day = roi_day
        self.pnl_day = pnl_day
        self.fall_days = fall_days

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "change_date": self.change_date.isoformat(),
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "roi_day": self.roi_day,
            "pnl_day": self.pnl_day,
            "fall_days": self.fall_days
        }


class AgentFallingConsecutiveDaysEvent(DomainEvent):
    """
    Evento: Un agente lleva N dias consecutivos cayendo.

    Este evento se dispara cuando un agente alcanza un umbral
    critico de dias consecutivos en caida (ej: 3 dias).
    """

    def __init__(
        self,
        agent_id: str,
        alert_date: date,
        fall_days: int,
        roi_since_entry: Optional[float] = None,
        cumulative_pnl: Optional[float] = None
    ):
        super().__init__()
        self.agent_id = agent_id
        self.alert_date = alert_date
        self.fall_days = fall_days
        self.roi_since_entry = roi_since_entry
        self.cumulative_pnl = cumulative_pnl

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "alert_date": self.alert_date.isoformat(),
            "fall_days": self.fall_days,
            "roi_since_entry": self.roi_since_entry,
            "cumulative_pnl": self.cumulative_pnl
        }
