from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class AgentDistribution(BaseModel):
    """Estadisticas de un agente en un snapshot."""
    num_cuentas: int = Field(..., description="Numero de cuentas asignadas")
    balance_total: float = Field(..., description="Balance total de las cuentas")
    roi_promedio: float = Field(..., description="ROI promedio de las cuentas")

    class Config:
        populate_by_name = True


class CuentaEstado(BaseModel):
    """Estado de una cuenta en un momento especifico."""
    cuenta_id: str = Field(..., description="ID de la cuenta")
    balance: float = Field(..., description="Balance actual")
    roi: float = Field(..., description="ROI actual")
    agente: str = Field(..., description="Agente asignado")

    class Config:
        populate_by_name = True


class ClientAccountSnapshot(BaseModel):
    """
    Snapshot del estado completo de todas las cuentas en una fecha.

    Se usa para timeline y replay dia a dia de la evolucion de las cuentas.
    """
    id: Optional[str] = Field(default=None, alias="_id")
    simulation_id: str = Field(..., description="ID de la simulacion")
    target_date: str = Field(..., description="Fecha del snapshot (YYYY-MM-DD)")

    total_cuentas: int = Field(..., description="Total de cuentas activas")
    balance_total: float = Field(..., description="Suma de balances")
    roi_promedio: float = Field(..., description="ROI promedio")
    win_rate_promedio: float = Field(..., ge=0, le=1, description="Win rate promedio")

    distribucion_agentes: Dict[str, AgentDistribution] = Field(
        ...,
        description="Estadisticas por agente"
    )

    cuentas_estado: Optional[List[CuentaEstado]] = Field(
        default=None,
        description="Estado detallado de cada cuenta (opcional)"
    )

    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        """Convierte a diccionario para MongoDB."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])

        if data.get("distribucion_agentes"):
            data["distribucion_agentes"] = {
                agent_id: dist.model_dump() if isinstance(dist, AgentDistribution) else dist
                for agent_id, dist in data["distribucion_agentes"].items()
            }

        return data
