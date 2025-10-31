from pydantic import BaseModel, Field
from typing import Optional


class RotationLogResponseDTO(BaseModel):
    """
    DTO para respuesta de registro de rotacion en API.

    Separa la representacion de API de la entidad de dominio,
    permitiendo evolucion independiente y tipos apropiados para JSON.
    """
    date: str = Field(..., description="Fecha de rotacion en formato ISO (YYYY-MM-DD)", pattern=r'^\d{4}-\d{2}-\d{2}$')
    agent_out: Optional[str] = Field(None, description="ID del agente que sale", min_length=1)
    agent_in: Optional[str] = Field(None, description="ID del agente que entra", min_length=1)
    reason: str = Field(..., description="Razon de la rotacion", min_length=1)
    roi_7d_out: Optional[float] = Field(None, description="ROI 7 dias del agente saliente", ge=-1.0, le=10.0)
    roi_total_out: Optional[float] = Field(None, description="ROI total del agente saliente", ge=-1.0, le=50.0)
    roi_7d_in: Optional[float] = Field(None, description="ROI 7 dias del agente entrante", ge=-1.0, le=10.0)
    n_accounts: int = Field(..., description="Numero de cuentas afectadas", ge=0, le=100)
    total_aum: float = Field(..., description="AUM total afectado", ge=0.0, le=100000000.0)

    @classmethod
    def from_entity(cls, entity):
        """
        Convierte una entidad de dominio RotationLog a DTO de respuesta.

        Args:
            entity: Instancia de RotationLog del dominio

        Returns:
            RotationLogResponseDTO: DTO para respuesta de API
        """
        return cls(
            date=entity.date.isoformat() if hasattr(entity.date, 'isoformat') else str(entity.date),
            agent_out=entity.agent_out,
            agent_in=entity.agent_in,
            reason=entity.reason.value if hasattr(entity.reason, 'value') else str(entity.reason),
            roi_7d_out=round(entity.roi_7d_out, 4) if entity.roi_7d_out is not None else None,
            roi_total_out=round(entity.roi_total_out, 4) if entity.roi_total_out is not None else None,
            roi_7d_in=round(entity.roi_7d_in, 4) if entity.roi_7d_in is not None else None,
            n_accounts=entity.n_accounts,
            total_aum=round(entity.total_aum, 2)
        )

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-10-15",
                "agent_out": "futures-014",
                "agent_in": "futures-023",
                "reason": "FALL_DAYS",
                "roi_7d_out": -0.0523,
                "roi_total_out": 0.0845,
                "roi_7d_in": 0.1234,
                "n_accounts": 5,
                "total_aum": 250000.00
            }
        }
