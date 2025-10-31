"""
Entidad Daily ROI - Representa el ROI calculado para un día específico.

Esta entidad almacena el resultado del cálculo de ROI diario basado en
la suma de closedPnl dividido por el balance base del día.

Fórmula: ROI_dia = sum(closedPnl_i) / balance_base

Author: Sistema Casterly Rock
Date: 2025-10-19
Version: 2.0
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TradeDetail(BaseModel):
    """
    Detalle de un trade individual dentro de un día.

    Attributes:
        symbol: Par de trading (ej: "BTCUSDT", "ETHUSDT")
        closedPnl: PnL cerrado del trade (ya convertido a float)
        roi_trade: ROI individual del trade (closedPnl / balance_base)
        createdAt: Timestamp del trade
    """

    symbol: str
    closedPnl: float
    roi_trade: float
    createdAt: datetime


class DailyROI(BaseModel):
    """
    Entidad que representa el ROI calculado para un día específico.

    Esta entidad se almacena en la colección temporal 'daily_roi_calculation'.
    La colección se limpia al inicio de cada nueva consulta para evitar data basura.

    Attributes:
        date: Fecha del día en formato "YYYY-MM-DD"
        userId: Identificador único y consistente del agente (ej: "OKX_JH1", "futures-FP1")
        agente_id: ObjectId técnico de MongoDB (opcional, puede cambiar entre días)
        balance_base: Balance del agente al inicio del día
        trades: Lista de trades ejecutados en el día
        total_pnl_day: Suma de todos los closedPnl del día
        roi_day: ROI del día (total_pnl_day / balance_base)
        n_trades: Número total de trades en el día
        createdAt: Timestamp de creación del registro
        updatedAt: Timestamp de última actualización

    Example:
        >>> trade = TradeDetail(
        ...     symbol="BTCUSDT",
        ...     closedPnl=120.50,
        ...     roi_trade=0.01205,
        ...     createdAt=datetime.now()
        ... )
        >>> daily_roi = DailyROI(
        ...     date="2025-09-07",
        ...     agente_id="68db1be91caa2dbed6764c64",
        ...     userId="OKX_JH1",
        ...     balance_base=10000.0,
        ...     trades=[trade],
        ...     total_pnl_day=120.50,
        ...     roi_day=0.01205,
        ...     n_trades=1
        ... )
    """

    date: str = Field(..., description="Fecha en formato YYYY-MM-DD")
    userId: str = Field(..., description="Identificador único del agente (ej: OKX_JH1)")
    agente_id: Optional[str] = Field(
        None, description="ObjectId técnico de MongoDB (opcional, puede cambiar entre días)"
    )
    balance_base: float = Field(..., gt=0, description="Balance base del día")
    balance_start: Optional[float] = Field(None, description="Balance al inicio del día")
    balance_end: Optional[float] = Field(None, description="Balance al final del día")
    trades: List[TradeDetail] = Field(
        default_factory=list, description="Lista de trades del día"
    )
    total_pnl_day: float = Field(
        default=0.0, description="PnL total del día (suma de closedPnl)"
    )
    roi_day: float = Field(
        default=0.0, description="ROI del día (total_pnl_day / balance_base)"
    )
    n_trades: int = Field(default=0, ge=0, description="Número de trades en el día")
    createdAt: Optional[datetime] = Field(
        default=None, description="Timestamp de creación"
    )
    updatedAt: Optional[datetime] = Field(
        default=None, description="Timestamp de actualización"
    )

    class Config:
        """Configuración de Pydantic."""

        json_encoders = {datetime: lambda v: v.isoformat()}
        schema_extra = {
            "example": {
                "date": "2025-09-07",
                "agente_id": "68db1be91caa2dbed6764c64",
                "userId": "OKX_JH1",
                "balance_base": 10000.0,
                "trades": [
                    {
                        "symbol": "BTCUSDT",
                        "closedPnl": 120.50,
                        "roi_trade": 0.01205,
                        "createdAt": "2025-09-07T10:30:00.000Z",
                    }
                ],
                "total_pnl_day": 120.50,
                "roi_day": 0.01205,
                "n_trades": 1,
            }
        }

    def calculate_roi(self) -> float:
        """
        Calcula el ROI del día.

        Returns:
            ROI como decimal (ej: 0.01205 = 1.205%)

        Raises:
            ValueError: Si balance_base es 0
        """
        if self.balance_base <= 0:
            raise ValueError("balance_base debe ser mayor a 0")

        return self.total_pnl_day / self.balance_base

    def add_trade(self, trade: TradeDetail) -> None:
        """
        Agrega un trade a la lista y actualiza métricas.

        Args:
            trade: Trade a agregar

        Note:
            Este método actualiza automáticamente total_pnl_day, roi_day y n_trades
        """
        self.trades.append(trade)
        self.total_pnl_day += trade.closedPnl
        self.n_trades = len(self.trades)
        self.roi_day = self.calculate_roi()

    def get_positive_trades_count(self) -> int:
        """
        Cuenta trades con PnL positivo.

        Returns:
            Número de trades con closedPnl > 0
        """
        return sum(1 for trade in self.trades if trade.closedPnl > 0)

    def get_negative_trades_count(self) -> int:
        """
        Cuenta trades con PnL negativo.

        Returns:
            Número de trades con closedPnl < 0
        """
        return sum(1 for trade in self.trades if trade.closedPnl < 0)

    def get_win_rate(self) -> float:
        """
        Calcula el win rate del día.

        Returns:
            Porcentaje de trades ganadores (0.0 a 1.0)
        """
        if self.n_trades == 0:
            return 0.0

        positive_trades = self.get_positive_trades_count()
        return positive_trades / self.n_trades
