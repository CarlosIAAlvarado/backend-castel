from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date


class Top16Day(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        },
        extra="allow"  # Permitir campos adicionales como roi_3d, roi_14d, etc.
    )

    id: Optional[str] = Field(default=None, alias="_id")
    date: date
    rank: int
    agent_id: str
    # Campos de ROI para diferentes ventanas (todos opcionales para flexibilidad)
    roi_3d: Optional[float] = Field(default=None)
    roi_5d: Optional[float] = Field(default=None)
    roi_7d: Optional[float] = Field(default=None)
    roi_10d: Optional[float] = Field(default=None)
    roi_14d: Optional[float] = Field(default=None)
    roi_15d: Optional[float] = Field(default=None)
    roi_30d: Optional[float] = Field(default=None)
    n_accounts: int
    total_aum: float
    is_in_casterly: bool = False
    window_days: Optional[int] = Field(default=None, description="Ventana de días usada para calcular ROI")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
