"""
Entidad SimulationStatus para rastrear el estado de simulaciones en curso.

Author: Sistema Casterly Rock
Date: 2025-11-05
Version: 1.0
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SimulationStatus(BaseModel):
    """
    Entidad que representa el estado de una simulacion en ejecucion.

    Se usa para persistir el progreso de simulaciones largas y permitir
    que multiples clientes vean el estado actual incluso despues de recargar.

    Attributes:
        status_id: Identificador unico del estado (siempre "current")
        is_running: Si hay una simulacion en curso
        current_day: Dia actual siendo procesado (1-based)
        total_days: Total de dias a procesar
        start_date: Fecha de inicio de la simulacion
        end_date: Fecha final de la simulacion
        started_at: Timestamp cuando inicio la simulacion
        updated_at: Timestamp de ultima actualizacion
        estimated_seconds_per_day: Segundos estimados por dia
        message: Mensaje descriptivo del progreso actual
    """

    status_id: str = Field(default="current", description="ID del estado (siempre 'current')")
    is_running: bool = Field(description="Si hay simulacion en curso")
    current_day: int = Field(default=0, description="Dia actual siendo procesado")
    total_days: int = Field(description="Total de dias a procesar")
    start_date: str = Field(description="Fecha de inicio (YYYY-MM-DD)")
    end_date: str = Field(description="Fecha final (YYYY-MM-DD)")
    started_at: datetime = Field(description="Timestamp de inicio")
    updated_at: datetime = Field(description="Timestamp de ultima actualizacion")
    estimated_seconds_per_day: int = Field(default=22, description="Segundos estimados por dia")
    message: Optional[str] = Field(default=None, description="Mensaje descriptivo")

    class Config:
        json_schema_extra = {
            "example": {
                "status_id": "current",
                "is_running": True,
                "current_day": 15,
                "total_days": 30,
                "start_date": "2025-09-01",
                "end_date": "2025-09-30",
                "started_at": "2025-11-05T12:00:00Z",
                "updated_at": "2025-11-05T12:05:00Z",
                "estimated_seconds_per_day": 22,
                "message": "Procesando dia 15/30..."
            }
        }
