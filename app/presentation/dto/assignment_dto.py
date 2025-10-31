from pydantic import BaseModel, Field
from typing import Optional


class AssignmentResponseDTO(BaseModel):
    """
    DTO para respuesta de asignacion de cuenta en API.

    Separa la representacion de API de la entidad de dominio,
    permitiendo evolucion independiente y tipos apropiados para JSON.
    """
    account_id: str = Field(..., description="ID de la cuenta", min_length=1)
    agent_id: str = Field(..., description="ID del agente asignado", min_length=1)
    balance: float = Field(..., description="Balance de la cuenta", ge=0.0, le=10000000.0)
    assigned_at: Optional[str] = Field(None, description="Fecha/hora de asignacion en formato ISO")
    is_active: bool = Field(..., description="Si la asignacion esta activa")
    date: str = Field(..., description="Fecha de la asignacion en formato ISO (YYYY-MM-DD)", pattern=r'^\d{4}-\d{2}-\d{2}$')

    @classmethod
    def from_entity(cls, entity):
        """
        Convierte una entidad de dominio Assignment a DTO de respuesta.

        Args:
            entity: Instancia de Assignment del dominio

        Returns:
            AssignmentResponseDTO: DTO para respuesta de API
        """
        return cls(
            account_id=entity.account_id,
            agent_id=entity.agent_id,
            balance=round(entity.balance, 2),
            assigned_at=entity.assigned_at.isoformat() if entity.assigned_at else None,
            is_active=entity.is_active,
            date=entity.date.isoformat()
        )

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": "acc-12345",
                "agent_id": "futures-001",
                "balance": 50000.00,
                "assigned_at": "2025-09-01T08:00:00",
                "is_active": True,
                "date": "2025-10-15"
            }
        }
