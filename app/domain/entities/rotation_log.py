from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class RotationReason(str, Enum):
    """
    Razones válidas de rotación según especificación.

    Hay TRES formas de salir del Top 16:
    1. THREE_DAYS_FALL: 3 días consecutivos de pérdida
    2. STOP_LOSS: ROI cayó por debajo de -10%
    3. RANKING_DISPLACEMENT: Desplazado por ranking natural (otro agente tiene mejor ROI)

    Las demás razones se mantienen para compatibilidad con datos históricos.
    """
    # REGLAS PRINCIPALES (según especificación)
    THREE_DAYS_FALL = "caida_tres_dias"
    STOP_LOSS = "stop_loss"
    RANKING_DISPLACEMENT = "desplazamiento_ranking"  # Salió por ranking natural

    # Casos especiales
    MANUAL = "manual"  # Intervención manual del usuario

    # Compatibilidad con datos históricos (NO usar en nuevas simulaciones)
    THREE_DAYS_FALL_OLD = "three_days_fall"
    STOP_LOSS_OLD = "stop_loss"
    MANUAL_OLD = "manual"
    DAILY_ROTATION_OLD = "daily_rotation"
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

    # Campos dinámicos de ROI - representan la ventana de la simulación
    window_days: Optional[int] = None  # Ventana de días usada en la simulación (ej: 7, 30)
    roi_window_out: Optional[float] = None  # ROI del agente saliente en la ventana configurada
    roi_total_out: float  # ROI total acumulado del agente saliente
    roi_window_in: Optional[float] = None  # ROI del agente entrante en la ventana configurada

    # Campos legacy para compatibilidad con datos históricos (DEPRECATED)
    roi_7d_out: Optional[float] = None  # DEPRECATED: usar roi_window_out
    roi_7d_in: Optional[float] = None  # DEPRECATED: usar roi_window_in

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
