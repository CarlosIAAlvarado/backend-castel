from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime, date


class SimulationConfig(BaseModel):
    """Configuracion de parametros de entrada de la simulacion."""
    target_date: date
    start_date: date
    days_simulated: int
    fall_threshold: int = 3
    stop_loss_threshold: float = -0.10


class SimulationKPIs(BaseModel):
    """KPIs principales de la simulacion."""
    total_roi: float
    avg_roi: float
    volatility: float
    max_drawdown: float
    win_rate: float
    active_agents_count: int
    unique_agents_in_period: int
    sharpe_ratio: Optional[float] = None


class TopAgentSummary(BaseModel):
    """Resumen de un agente en el Top 16."""
    rank: int
    agent_id: str
    roi_7d: float
    total_aum: float
    n_accounts: int
    is_in_casterly: bool


class RotationsSummary(BaseModel):
    """Resumen de rotaciones ejecutadas."""
    total_rotations: int
    rotations_by_reason: Dict[str, int]
    agents_rotated_out: List[str]
    agents_rotated_in: List[str]


class DailyMetric(BaseModel):
    """Metrica diaria para graficos de evolucion."""
    date: date
    roi_cumulative: float
    active_agents: int
    total_pnl: float


class Simulation(BaseModel):
    """
    Entidad que representa una simulacion guardada.
    Contiene metadata, configuracion, KPIs y resumenes para comparacion.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    )

    id: Optional[str] = Field(default=None, alias="_id")
    simulation_id: str = Field(..., description="UUID unico de la simulacion")
    name: str = Field(default="Simulacion sin nombre", description="Nombre editable por usuario")
    description: Optional[str] = Field(default=None, description="Descripcion opcional")
    created_at: datetime = Field(default_factory=datetime.now, alias="createdAt")

    config: SimulationConfig
    kpis: SimulationKPIs
    top_16_final: List[TopAgentSummary]
    rotations_summary: RotationsSummary
    daily_metrics: List[DailyMetric]

    def to_dict(self) -> dict:
        """Convierte la entidad a diccionario para MongoDB."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data
