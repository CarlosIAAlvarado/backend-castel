from abc import ABC
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4


class DomainEvent(ABC):
    """
    Clase base para todos los eventos de dominio.

    Los eventos de dominio representan hechos que han ocurrido en el sistema
    y son inmutables (una vez creados, no pueden modificarse).

    Siguiendo DDD (Domain-Driven Design), los eventos:
    - Representan hechos pasados (uso de verbos en pasado)
    - Son inmutables
    - Contienen toda la informacion necesaria sobre el hecho ocurrido
    - Tienen un timestamp de cuando ocurrieron
    """

    def __init__(self):
        """
        Inicializa un evento de dominio con metadata comun.
        """
        self.event_id: str = str(uuid4())
        self.occurred_at: datetime = datetime.now()
        self.event_type: str = self.__class__.__name__

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el evento a diccionario para serializacion.

        Returns:
            Dict con todos los datos del evento
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            **self._get_event_data()
        }

    def _get_event_data(self) -> Dict[str, Any]:
        """
        Metodo abstracto que cada evento debe implementar
        para retornar sus datos especificos.

        Returns:
            Dict con datos especificos del evento
        """
        return {}

    def __repr__(self) -> str:
        return f"{self.event_type}(event_id={self.event_id}, occurred_at={self.occurred_at})"
