"""
Domain Events para Casterly Rock Simulation.

Este modulo implementa el patron Domain Events de DDD (Domain-Driven Design)
para desacoplar servicios y permitir reacciones automaticas a eventos del dominio.

Eventos disponibles:
- AgentExitedEvent: Cuando un agente sale de Casterly Rock
- AgentEnteredEvent: Cuando un agente entra a Casterly Rock
- AgentRotationCompletedEvent: Cuando se completa una rotacion
- AgentStateChangedEvent: Cuando cambia el estado de un agente
- AgentFallingConsecutiveDaysEvent: Cuando un agente lleva N dias cayendo
- AccountsAssignedEvent: Cuando se asignan cuentas
- AccountsReassignedEvent: Cuando se reasignan cuentas
- DailyProcessCompletedEvent: Cuando se completa un dia
- SimulationCompletedEvent: Cuando se completa la simulacion
"""

from app.domain.events.base import DomainEvent
from app.domain.events.event_bus import EventBus, event_bus
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

__all__ = [
    # Base
    "DomainEvent",
    "EventBus",
    "event_bus",
    # Agent Events
    "AgentExitedEvent",
    "AgentEnteredEvent",
    "AgentRotationCompletedEvent",
    "AgentStateChangedEvent",
    "AgentFallingConsecutiveDaysEvent",
    # Assignment Events
    "AccountsAssignedEvent",
    "AccountsReassignedEvent",
    # Simulation Events
    "DailyProcessCompletedEvent",
    "SimulationCompletedEvent"
]
