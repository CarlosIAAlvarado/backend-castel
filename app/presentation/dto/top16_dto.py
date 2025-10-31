from pydantic import BaseModel, Field
from typing import Optional


class Top16ResponseDTO(BaseModel):
    """
    DTO para respuesta de ranking Top 16 en API.

    Este DTO se utiliza para datos calculados dinamicamente
    (no necesariamente desde entidad de dominio).
    """
    rank: int = Field(..., description="Posicion en el ranking", ge=1, le=100)
    agent_id: str = Field(..., description="ID del agente", min_length=1)
    roi_since_entry: float = Field(..., description="ROI acumulado desde entrada", ge=-1.0, le=50.0)
    roi_7d: float = Field(..., description="ROI ultimos 7 dias", ge=-1.0, le=10.0)
    roi_30d: Optional[float] = Field(None, description="ROI ultimos 30 dias (si hay datos)", ge=-1.0, le=50.0)
    n_accounts: int = Field(..., description="Numero de cuentas asignadas", ge=0, le=100)
    total_aum: float = Field(..., description="AUM total del agente", ge=0.0, le=100000000.0)
    is_in_casterly: bool = Field(..., description="Si el agente esta en Casterly Rock")

    @classmethod
    def from_dict(cls, data: dict):
        """
        Crea un DTO desde un diccionario de datos calculados.

        Args:
            data: Diccionario con datos del agente

        Returns:
            Top16ResponseDTO: DTO para respuesta de API
        """
        return cls(
            rank=data.get("rank", 0),
            agent_id=data.get("agent_id", ""),
            roi_since_entry=round(data.get("roi_since_entry", 0.0), 4),
            roi_7d=round(data.get("roi_7d", 0.0), 4),
            roi_30d=round(data.get("roi_30d"), 4) if data.get("roi_30d") is not None else None,
            n_accounts=data.get("n_accounts", 0),
            total_aum=round(data.get("total_aum", 0.0), 2),
            is_in_casterly=data.get("is_in_casterly", True)
        )

    class Config:
        json_schema_extra = {
            "example": {
                "rank": 1,
                "agent_id": "futures-001",
                "roi_since_entry": 0.1523,
                "roi_7d": 0.0234,
                "roi_30d": 0.0945,
                "n_accounts": 8,
                "total_aum": 400000.00,
                "is_in_casterly": True
            }
        }
