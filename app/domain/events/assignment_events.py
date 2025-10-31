from datetime import date
from typing import List, Dict, Any
from app.domain.events.base import DomainEvent


class AccountsAssignedEvent(DomainEvent):
    """
    Evento: Se han asignado cuentas a agentes.

    Este evento se dispara cuando se completa la asignacion
    inicial de cuentas a los 16 agentes de Casterly Rock.
    """

    def __init__(
        self,
        assignment_date: date,
        total_accounts: int,
        total_agents: int,
        total_aum: float,
        assignments_summary: Dict[str, Any]
    ):
        super().__init__()
        self.assignment_date = assignment_date
        self.total_accounts = total_accounts
        self.total_agents = total_agents
        self.total_aum = total_aum
        self.assignments_summary = assignments_summary

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "assignment_date": self.assignment_date.isoformat(),
            "total_accounts": self.total_accounts,
            "total_agents": self.total_agents,
            "total_aum": self.total_aum,
            "assignments_summary": self.assignments_summary
        }


class AccountsReassignedEvent(DomainEvent):
    """
    Evento: Se han reasignado cuentas de un agente a otro.

    Este evento se dispara cuando las cuentas de un agente
    que sale son transferidas al agente que entra.
    """

    def __init__(
        self,
        reassignment_date: date,
        from_agent_id: str,
        to_agent_id: str,
        account_ids: List[str],
        total_aum_transferred: float
    ):
        super().__init__()
        self.reassignment_date = reassignment_date
        self.from_agent_id = from_agent_id
        self.to_agent_id = to_agent_id
        self.account_ids = account_ids
        self.total_aum_transferred = total_aum_transferred

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "reassignment_date": self.reassignment_date.isoformat(),
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "account_ids": self.account_ids,
            "total_aum_transferred": self.total_aum_transferred,
            "accounts_count": len(self.account_ids)
        }
