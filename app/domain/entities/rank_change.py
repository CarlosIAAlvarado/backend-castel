from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RankChange(BaseModel):
    """
    Representa un cambio de ranking dentro del Top 16.

    A diferencia de rotation_log (que registra entradas/salidas del Top 16),
    esta entidad registra movimientos de posición DENTRO del Top 16.

    Ejemplo:
    - Agente estaba en rank 1, ahora está en rank 3
    - Agente estaba en rank 10, ahora está en rank 5
    """
    id: Optional[str] = Field(default=None, alias="_id")
    date: datetime  # Fecha del cambio
    agent_id: str  # ID del agente que cambió de posición
    previous_rank: int  # Rank anterior (1-16)
    current_rank: int  # Rank actual (1-16)
    rank_change: int  # Diferencia (negativo = bajó, positivo = subió)
    previous_roi: float  # ROI en el día anterior
    current_roi: float  # ROI en el día actual
    roi_change: float  # Diferencia de ROI
    is_in_casterly: bool  # Si el agente está activo en Casterly Rock
    created_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data

    @property
    def movement_type(self) -> str:
        """Retorna el tipo de movimiento: 'up', 'down', 'stable'"""
        if self.rank_change > 0:
            return "up"  # Subió (ej: de rank 5 a rank 3)
        elif self.rank_change < 0:
            return "down"  # Bajó (ej: de rank 3 a rank 5)
        else:
            return "stable"  # Se mantuvo igual

    @property
    def is_significant(self) -> bool:
        """Retorna True si el cambio es significativo (>= 3 posiciones)"""
        return abs(self.rank_change) >= 3
