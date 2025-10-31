from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class SyncResult(BaseModel):
    """Resultado de sincronizacion de cuentas con simulacion."""
    target_date: date = Field(..., description="Fecha del dia sincronizado")
    cuentas_actualizadas: int = Field(..., description="Numero de cuentas actualizadas")
    cuentas_redistribuidas: int = Field(default=0, description="Cuentas redistribuidas por rotacion")
    rotaciones_procesadas: int = Field(default=0, description="Numero de rotaciones procesadas")
    snapshot_id: Optional[str] = Field(default=None, description="ID del snapshot creado")
    balance_total_antes: float = Field(..., description="Balance total antes de sincronizar")
    balance_total_despues: float = Field(..., description="Balance total despues de sincronizar")
    roi_promedio_antes: float = Field(..., description="ROI promedio antes")
    roi_promedio_despues: float = Field(..., description="ROI promedio despues")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class RotationResult(BaseModel):
    """Resultado de manejo de rotaciones."""
    fecha_rotacion: date = Field(..., description="Fecha de la rotacion")
    rotaciones_procesadas: int = Field(..., description="Numero de rotaciones")
    cuentas_redistribuidas: int = Field(..., description="Total de cuentas redistribuidas")
    detalles_rotaciones: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista con detalle de cada rotacion"
    )

    class Config:
        populate_by_name = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class UpdateResult(BaseModel):
    """Resultado de actualizacion de ROI de cuentas."""
    target_date: date = Field(..., description="Fecha objetivo")
    cuentas_actualizadas: int = Field(..., description="Numero de cuentas actualizadas")
    balance_total: float = Field(..., description="Balance total")
    roi_promedio: float = Field(..., description="ROI promedio")
    cuentas_con_ganancia: int = Field(default=0, description="Cuentas con ROI > 0")
    cuentas_con_perdida: int = Field(default=0, description="Cuentas con ROI < 0")

    class Config:
        populate_by_name = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class SnapshotResult(BaseModel):
    """Resultado de guardado de snapshot."""
    snapshot_id: str = Field(..., description="ID del snapshot creado")
    target_date: date = Field(..., description="Fecha del snapshot")
    total_cuentas: int = Field(..., description="Total de cuentas en snapshot")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class RedistributionResult(BaseModel):
    """Resultado de redistribucion de cuentas."""
    agente_out: str = Field(..., description="Agente que sale")
    agente_in: str = Field(..., description="Agente que entra")
    cuentas_movidas: int = Field(..., description="Numero de cuentas redistribuidas")
    motivo: str = Field(..., description="Razon de la redistribucion")
    fecha: date = Field(..., description="Fecha de la redistribucion")

    class Config:
        populate_by_name = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class Rotation(BaseModel):
    """Modelo de rotacion de agente."""
    agent_out: str = Field(..., description="Agente que sale del Top 16")
    agent_in: str = Field(..., description="Agente que entra al Top 16")
    reason: str = Field(..., description="Razon de la rotacion")
    rotation_date: date = Field(..., description="Fecha de la rotacion")
    rank_out: Optional[int] = Field(default=None, description="Rank final del agente saliente")
    rank_in: Optional[int] = Field(default=None, description="Rank inicial del agente entrante")

    class Config:
        populate_by_name = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }
