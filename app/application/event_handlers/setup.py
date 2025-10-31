"""
Setup para registro automatico de Event Handlers.

Este modulo registra todos los handlers al Event Bus al iniciar la aplicacion.
Debe ser importado en el startup de la aplicacion (main.py o __init__.py).
"""

import logging
from app.domain.events import (
    event_bus,
    AgentExitedEvent,
    AgentEnteredEvent,
    AgentRotationCompletedEvent,
    AgentStateChangedEvent,
    AgentFallingConsecutiveDaysEvent,
    AccountsAssignedEvent,
    AccountsReassignedEvent,
    DailyProcessCompletedEvent,
    SimulationCompletedEvent
)
from app.application.event_handlers.logging_handler import LoggingEventHandler
from app.application.event_handlers.agent_event_handlers import AgentEventHandlers

logger = logging.getLogger(__name__)


def register_event_handlers(rotation_log_repo=None):
    """
    Registra todos los event handlers al Event Bus.

    Esta funcion debe ser llamada al iniciar la aplicacion,
    idealmente en el startup de FastAPI o en __init__.py.

    Args:
        rotation_log_repo: Repositorio opcional para AgentEventHandlers
    """
    # Instanciar handlers
    logging_handler = LoggingEventHandler()
    agent_handlers = AgentEventHandlers(rotation_log_repo=rotation_log_repo)

    # === Registrar Logging Handlers (para todos los eventos) ===

    # Agent Events
    event_bus.subscribe(AgentExitedEvent, logging_handler.handle_agent_exited)
    event_bus.subscribe(AgentEnteredEvent, logging_handler.handle_agent_entered)
    event_bus.subscribe(AgentRotationCompletedEvent, logging_handler.handle_rotation_completed)
    event_bus.subscribe(AgentStateChangedEvent, logging_handler.handle_state_changed)
    event_bus.subscribe(AgentFallingConsecutiveDaysEvent, logging_handler.handle_falling_days)

    # Assignment Events
    event_bus.subscribe(AccountsAssignedEvent, logging_handler.handle_accounts_assigned)
    event_bus.subscribe(AccountsReassignedEvent, logging_handler.handle_accounts_reassigned)

    # Simulation Events
    event_bus.subscribe(DailyProcessCompletedEvent, logging_handler.handle_daily_process_completed)
    event_bus.subscribe(SimulationCompletedEvent, logging_handler.handle_simulation_completed)

    # === Registrar Specialized Agent Handlers ===

    event_bus.subscribe(AgentExitedEvent, agent_handlers.handle_agent_exited)
    event_bus.subscribe(AgentEnteredEvent, agent_handlers.handle_agent_entered)
    event_bus.subscribe(AgentRotationCompletedEvent, agent_handlers.handle_rotation_completed)
    event_bus.subscribe(AgentFallingConsecutiveDaysEvent, agent_handlers.handle_falling_consecutive_days)

    logger.info("Event handlers registered successfully")
    logger.debug(f"AgentExitedEvent handlers: {event_bus.get_handlers_count(AgentExitedEvent)}")
    logger.debug(f"AgentEnteredEvent handlers: {event_bus.get_handlers_count(AgentEnteredEvent)}")
    logger.debug(f"AgentRotationCompletedEvent handlers: {event_bus.get_handlers_count(AgentRotationCompletedEvent)}")


def unregister_all_handlers():
    """
    Elimina todos los handlers del Event Bus.

    Util para testing o para shutdown limpio de la aplicacion.
    """
    event_bus.clear_handlers()
    logger.info("All event handlers unregistered")
