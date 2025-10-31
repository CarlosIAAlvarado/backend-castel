from pydantic import BaseModel, Field
from typing import Optional


class AgentStateResponseDTO(BaseModel):
    """
    DTO para respuesta de estado de agente en API.

    Separa la representacion de API de la entidad de dominio,
    permitiendo evolucion independiente y tipos apropiados para JSON.
    """
    agent_id: str = Field(..., description="ID del agente", min_length=1)
    date: str = Field(..., description="Fecha en formato ISO (YYYY-MM-DD)", pattern=r'^\d{4}-\d{2}-\d{2}$')
    state: str = Field(..., description="Estado del agente (GROWTH/FALL)", pattern=r'^(GROWTH|FALL)$')
    roi_day: float = Field(..., description="ROI del dia", ge=-1.0, le=10.0)
    pnl_day: float = Field(..., description="P&L del dia", ge=-1000000.0, le=1000000.0)
    balance_base: float = Field(..., description="Balance base del agente", ge=0.0)
    fall_days: int = Field(..., description="Dias consecutivos en caida", ge=0, le=365)
    is_in_casterly: bool = Field(..., description="Si el agente esta en Casterly Rock")
    roi_since_entry: Optional[float] = Field(None, description="ROI acumulado desde entrada", ge=-1.0, le=50.0)
    entry_date: Optional[str] = Field(None, description="Fecha de entrada en formato ISO", pattern=r'^\d{4}-\d{2}-\d{2}$')

    @classmethod
    def from_entity(cls, entity):
        """
        Convierte una entidad de dominio AgentState a DTO de respuesta.

        Args:
            entity: Instancia de AgentState del dominio

        Returns:
            AgentStateResponseDTO: DTO para respuesta de API
        """
        return cls(
            agent_id=entity.agent_id,
            date=entity.date.isoformat(),
            state=entity.state.value if hasattr(entity.state, 'value') else str(entity.state),
            roi_day=round(entity.roi_day, 4),
            pnl_day=round(entity.pnl_day, 2),
            balance_base=round(entity.balance_base, 2),
            fall_days=entity.fall_days,
            is_in_casterly=entity.is_in_casterly,
            roi_since_entry=round(entity.roi_since_entry, 4) if entity.roi_since_entry is not None else None,
            entry_date=entity.entry_date.isoformat() if entity.entry_date else None
        )

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "futures-001",
                "date": "2025-10-15",
                "state": "GROWTH",
                "roi_day": 0.0245,
                "pnl_day": 1250.50,
                "balance_base": 50000.00,
                "fall_days": 0,
                "is_in_casterly": True,
                "roi_since_entry": 0.1523,
                "entry_date": "2025-09-01"
            }
        }
