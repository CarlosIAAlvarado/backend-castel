from typing import List, Callable, Dict, Type
from app.domain.events.base import DomainEvent
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Event Bus para publicar y suscribirse a eventos de dominio.

    Implementa el patron Publisher/Subscriber (Pub/Sub) para
    desacoplar emisores de eventos de sus handlers.

    Ejemplo de uso:
        # Registrar un handler
        event_bus.subscribe(AgentExitedEvent, log_agent_exit)

        # Publicar un evento
        event = AgentExitedEvent(agent_id="futures-001", ...)
        event_bus.publish(event)

        # El handler se ejecuta automaticamente
    """

    def __init__(self):
        """
        Inicializa el Event Bus con un registro vacio de handlers.
        """
        self._handlers: Dict[Type[DomainEvent], List[Callable]] = {}

    def subscribe(self, event_type: Type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """
        Registra un handler para un tipo de evento especifico.

        Args:
            event_type: Clase del evento a escuchar
            handler: Funcion que se ejecutara cuando ocurra el evento

        Example:
            >>> def on_agent_exited(event: AgentExitedEvent):
            ...     print(f"Agent {event.agent_id} exited")
            >>> event_bus.subscribe(AgentExitedEvent, on_agent_exited)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)
        logger.info(f"Handler registered for {event_type.__name__}: {handler.__name__}")

    def unsubscribe(self, event_type: Type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """
        Elimina un handler registrado para un tipo de evento.

        Args:
            event_type: Clase del evento
            handler: Funcion handler a eliminar
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.info(f"Handler unregistered for {event_type.__name__}: {handler.__name__}")

    def publish(self, event: DomainEvent) -> None:
        """
        Publica un evento, ejecutando todos los handlers registrados.

        Los handlers se ejecutan sincronicamente en el orden de registro.
        Si un handler falla, se registra el error pero continua con los demas.

        Args:
            event: Instancia del evento a publicar

        Example:
            >>> event = AgentExitedEvent(agent_id="futures-001", ...)
            >>> event_bus.publish(event)
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        logger.debug(f"Publishing {event_type.__name__} (event_id={event.event_id})")

        if not handlers:
            logger.warning(f"No handlers registered for {event_type.__name__}")
            return

        for handler in handlers:
            try:
                handler(event)
                logger.debug(f"Handler {handler.__name__} executed successfully for {event_type.__name__}")
            except Exception as e:
                logger.error(
                    f"Error executing handler {handler.__name__} for {event_type.__name__}: {str(e)}",
                    exc_info=True
                )

    def clear_handlers(self, event_type: Type[DomainEvent] = None) -> None:
        """
        Limpia handlers registrados.

        Args:
            event_type: Si se especifica, solo limpia handlers de ese tipo.
                       Si es None, limpia todos los handlers.
        """
        if event_type:
            self._handlers[event_type] = []
            logger.info(f"Handlers cleared for {event_type.__name__}")
        else:
            self._handlers.clear()
            logger.info("All handlers cleared")

    def get_handlers_count(self, event_type: Type[DomainEvent]) -> int:
        """
        Retorna el numero de handlers registrados para un tipo de evento.

        Args:
            event_type: Clase del evento

        Returns:
            Numero de handlers registrados
        """
        return len(self._handlers.get(event_type, []))


# Singleton global del Event Bus
event_bus = EventBus()
