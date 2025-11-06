"""
Command Services (CQRS Pattern - Write Side).

Este paquete contiene servicios especializados en operaciones de ESCRITURA.
Implementa el lado Command del patrón CQRS (Command Query Responsibility Segregation).
"""

from app.application.commands.selection_commands import SelectionCommandService

__all__ = ["SelectionCommandService"]
