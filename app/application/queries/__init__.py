"""
Query Services (CQRS Pattern - Read Side).

Este paquete contiene servicios especializados en operaciones de LECTURA.
Implementa el lado Query del patrón CQRS (Command Query Responsibility Segregation).
"""

from app.application.queries.selection_queries import SelectionQueryService

__all__ = ["SelectionQueryService"]
