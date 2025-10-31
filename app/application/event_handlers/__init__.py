"""
Event Handlers para reaccionar a Domain Events.

Los handlers se registran al Event Bus y se ejecutan automaticamente
cuando ocurren los eventos correspondientes.
"""

from app.application.event_handlers.logging_handler import LoggingEventHandler
from app.application.event_handlers.agent_event_handlers import AgentEventHandlers
from app.application.event_handlers.setup import (
    register_event_handlers,
    unregister_all_handlers
)

__all__ = [
    "LoggingEventHandler",
    "AgentEventHandlers",
    "register_event_handlers",
    "unregister_all_handlers"
]
