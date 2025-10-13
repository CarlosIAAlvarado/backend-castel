from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from app.domain.entities.agent import AgentState


class AgentDay(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    date: date
    agent_id: str
    roi_1d: float
    roi_7d: float
    roi_30d: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    volatility: Optional[float] = None
    state: AgentState
    fall_days_consecutive: int = 0
    balance_total: float
    pnl_day: float
    n_accounts: int
    total_aum: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        data = self.model_dump(by_alias=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
