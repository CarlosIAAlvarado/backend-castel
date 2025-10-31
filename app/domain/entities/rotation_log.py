from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class RotationReason(str, Enum):
    # Valores antiguos (compatibilidad hacia atrás)
    THREE_DAYS_FALL_OLD = "three_days_fall"
    STOP_LOSS_OLD = "stop_loss"
    MANUAL_OLD = "manual"
    DAILY_ROTATION_OLD = "daily_rotation"

    # Valores nuevos (en español)
    THREE_DAYS_FALL = "caida_tres_dias"
    STOP_LOSS = "stop_loss"
    MANUAL = "manual"
    DAILY_ROTATION = "rotacion_diaria"
    ROI_DROPPED_BELOW_TOP16 = "roi_cayo_debajo_top16"
    BETTER_PERFORMER_AVAILABLE = "mejor_rendimiento_disponible"
    WINDOW_SHIFT_IMPACT = "impacto_ventana_movil"
    NEGATIVE_DAY_IMPACT = "impacto_dia_negativo"


class RotationLog(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    date: datetime
    agent_out: str
    agent_in: Optional[str] = None  # Puede ser None si no entra nadie (Top 16 reduce tamaño)
    reason: RotationReason
    reason_details: Optional[str] = None  # Descripción específica de la rotación
    roi_7d_out: float
    roi_total_out: float
    roi_7d_in: Optional[float] = None  # Puede ser None si agent_in es None
    n_accounts: int
    total_aum: float
    created_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
