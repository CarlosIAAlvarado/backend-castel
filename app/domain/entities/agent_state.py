from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from enum import Enum


class StateType(str, Enum):
    """
    Enumeracion de tipos de estado de un agente.

    Estados:
    - GROWTH: Crecimiento (roi_day > 0)
    - FALL: Caida (roi_day < 0)
    """
    GROWTH = "GROWTH"
    FALL = "FALL"


class AgentState(BaseModel):
    """
    Estado diario de un agente en Casterly Rock.

    Almacena la clasificacion diaria basada en ROI_day y lleva
    el contador de dias consecutivos en caida.

    Attributes:
        id: ID unico del registro
        date: Fecha del estado
        agent_id: ID del agente
        state: Estado del dia (GROWTH o FALL)
        roi_day: ROI del dia (PnL_day / Balance_base)
        pnl_day: Ganancia o perdida neta del dia
        balance_base: Balance de referencia (cierre dia anterior)
        fall_days: Contador de dias consecutivos en caida
        is_in_casterly: Si el agente esta activo en Casterly Rock
        roi_since_entry: ROI acumulado desde entrada a Casterly Rock
        entry_date: Fecha de entrada a Casterly Rock
        roi_7d: ROI de los ultimos 7 dias
        roi_30d: ROI de los ultimos 30 dias
        sharpe_ratio: Sharpe Ratio (relacion retorno/riesgo)
        max_drawdown: Max Drawdown (maxima caida desde pico)
        volatility: Volatilidad (desviacion estandar de retornos)
        createdAt: Timestamp de creacion del registro
        updatedAt: Timestamp de ultima actualizacion
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    )

    id: Optional[str] = Field(default=None, alias="_id")
    date: date
    agent_id: str
    state: StateType
    roi_day: float
    pnl_day: float
    balance_base: float
    fall_days: int = Field(default=0, ge=0)
    is_in_casterly: bool = Field(default=True)
    roi_since_entry: Optional[float] = Field(default=None)
    entry_date: Optional[date] = Field(default=None)
    roi_7d: Optional[float] = Field(default=None)
    roi_30d: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    max_drawdown: Optional[float] = Field(default=None)
    volatility: Optional[float] = Field(default=None)
    createdAt: Optional[datetime] = Field(default=None, alias="createdAt")
    updatedAt: Optional[datetime] = Field(default=None, alias="updatedAt")
