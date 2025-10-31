"""
Data Transfer Objects (DTOs) para la capa de presentacion.

Este modulo define los DTOs utilizados para comunicacion con la API REST.
Los DTOs separan las entidades de dominio de las representaciones de API,
permitiendo evolucion independiente y validaciones especificas de API.
"""

from app.presentation.dto.agent_state_dto import AgentStateResponseDTO
from app.presentation.dto.assignment_dto import AssignmentResponseDTO
from app.presentation.dto.rotation_log_dto import RotationLogResponseDTO
from app.presentation.dto.top16_dto import Top16ResponseDTO

__all__ = [
    "AgentStateResponseDTO",
    "AssignmentResponseDTO",
    "RotationLogResponseDTO",
    "Top16ResponseDTO"
]
