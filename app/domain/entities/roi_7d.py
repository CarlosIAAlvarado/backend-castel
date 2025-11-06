"""
Entidad ROI 7D - Representa el ROI calculado para una ventana de 7 días.

Esta entidad almacena el resultado de sumar los ROIs diarios de una ventana
de 8 días (fecha_target - 7 días hasta fecha_target).

Fórmula: ROI_7D = sum(ROI_dia_1, ROI_dia_2, ..., ROI_dia_8)

Author: Sistema Casterly Rock
Date: 2025-10-19
Version: 2.0
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DailyROISummary(BaseModel):
    """
    Resumen de ROI de un día dentro de la ventana de 7 días.

    Attributes:
        date: Fecha del día en formato "YYYY-MM-DD"
        roi: ROI calculado para ese día
        pnl: PnL total del día
        n_trades: Número de trades en el día
    """

    date: str
    roi: float
    pnl: float
    n_trades: int


class ROI7D(BaseModel):
    """
    Entidad que representa el ROI calculado para una ventana de 7 días.

    Esta entidad se almacena en la colección temporal 'agent_roi_7d'.
    La colección se limpia al inicio de cada nueva consulta.

    La ventana de 7 días incluye 8 días de datos:
    [target_date - 7 días, target_date]

    Attributes:
        target_date: Fecha final de la ventana (formato "YYYY-MM-DD")
        userId: Identificador único y consistente del agente (ej: "OKX_JH1")
        agente_id: ObjectId técnico de MongoDB (opcional, puede cambiar entre días)
        window_start: Fecha inicio de la ventana (target_date - 7)
        window_end: Fecha fin de la ventana (target_date)
        daily_rois: Lista de ROIs diarios en la ventana
        roi_7d_total: Suma de todos los ROIs diarios
        roi_7d_percentage: ROI total en formato porcentaje
        total_pnl_7d: Suma de PnL de todos los días
        total_trades_7d: Número total de trades en la ventana
        avg_roi_per_day: Promedio de ROI por día
        positive_days: Número de días con ROI positivo
        negative_days: Número de días con ROI negativo
        createdAt: Timestamp de creación
        updatedAt: Timestamp de actualización

    Example:
        >>> roi_7d = ROI7D(
        ...     target_date="2025-09-14",
        ...     agente_id="68db1be91caa2dbed6764c64",
        ...     userId="OKX_JH1",
        ...     window_start="2025-09-07",
        ...     window_end="2025-09-14",
        ...     daily_rois=[
        ...         DailyROISummary(date="2025-09-07", roi=0.0176, pnl=176.0, n_trades=3),
        ...         DailyROISummary(date="2025-09-08", roi=0.0234, pnl=234.0, n_trades=2),
        ...     ],
        ...     roi_7d_total=0.0820,
        ...     total_trades_7d=18
        ... )
    """

    target_date: str = Field(..., description="Fecha final de la ventana YYYY-MM-DD")
    userId: str = Field(..., description="Identificador único del agente (ej: OKX_JH1)")
    agente_id: Optional[str] = Field(
        None, description="ObjectId técnico de MongoDB (opcional, puede cambiar entre días)"
    )
    window_start: str = Field(
        ..., description="Fecha inicio de ventana (target - 7 días)"
    )
    window_end: str = Field(..., description="Fecha fin de ventana (target)")
    daily_rois: List[DailyROISummary] = Field(
        default_factory=list, description="ROIs diarios en la ventana"
    )
    roi_7d_total: float = Field(
        default=0.0, description="ROI total de 7 días (suma de ROIs diarios)"
    )
    roi_7d_percentage: str = Field(
        default="0.00%", description="ROI total en formato porcentaje"
    )
    total_pnl_7d: float = Field(default=0.0, description="PnL total de 7 días")
    total_trades_7d: int = Field(
        default=0, ge=0, description="Total de trades en la ventana"
    )
    avg_roi_per_day: float = Field(
        default=0.0, description="Promedio de ROI por día"
    )
    positive_days: int = Field(
        default=0, ge=0, description="Número de días con ROI > 0"
    )
    negative_days: int = Field(
        default=0, ge=0, description="Número de días con ROI < 0"
    )
    createdAt: Optional[datetime] = Field(
        default=None, description="Timestamp de creación"
    )
    updatedAt: Optional[datetime] = Field(
        default=None, description="Timestamp de actualización"
    )

    class Config:
        """Configuración de Pydantic."""

        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "example": {
                "target_date": "2025-09-14",
                "agente_id": "68db1be91caa2dbed6764c64",
                "userId": "OKX_JH1",
                "window_start": "2025-09-07",
                "window_end": "2025-09-14",
                "daily_rois": [
                    {"date": "2025-09-07", "roi": 0.0176, "pnl": 176.0, "n_trades": 3},
                    {"date": "2025-09-08", "roi": 0.0234, "pnl": 234.0, "n_trades": 2},
                ],
                "roi_7d_total": 0.0820,
                "roi_7d_percentage": "8.20%",
                "total_trades_7d": 18,
                "positive_days": 6,
                "negative_days": 2,
            }
        }

    def calculate_total_roi(self) -> float:
        """
        Calcula el ROI total sumando todos los ROIs diarios.

        Returns:
            ROI total como decimal
        """
        return sum(day.roi for day in self.daily_rois)

    def calculate_total_pnl(self) -> float:
        """
        Calcula el PnL total sumando todos los PnLs diarios.

        Returns:
            PnL total
        """
        return sum(day.pnl for day in self.daily_rois)

    def calculate_total_trades(self) -> int:
        """
        Calcula el número total de trades en la ventana.

        Returns:
            Número total de trades
        """
        return sum(day.n_trades for day in self.daily_rois)

    def calculate_avg_roi_per_day(self) -> float:
        """
        Calcula el ROI promedio por día.

        Returns:
            Promedio de ROI diario
        """
        if not self.daily_rois:
            return 0.0

        return self.roi_7d_total / len(self.daily_rois)

    def count_positive_days(self) -> int:
        """
        Cuenta días con ROI positivo.

        Returns:
            Número de días con roi > 0
        """
        return sum(1 for day in self.daily_rois if day.roi > 0)

    def count_negative_days(self) -> int:
        """
        Cuenta días con ROI negativo.

        Returns:
            Número de días con roi < 0
        """
        return sum(1 for day in self.daily_rois if day.roi < 0)

    def format_roi_as_percentage(self) -> str:
        """
        Formatea el ROI total como porcentaje.

        Returns:
            String en formato "X.XX%"

        Example:
            >>> roi_7d.roi_7d_total = 0.0820
            >>> roi_7d.format_roi_as_percentage()
            "8.20%"
        """
        return f"{self.roi_7d_total * 100:.2f}%"

    def get_best_day(self) -> Optional[DailyROISummary]:
        """
        Obtiene el día con mejor ROI en la ventana.

        Returns:
            DailyROISummary del mejor día, o None si no hay datos
        """
        if not self.daily_rois:
            return None

        return max(self.daily_rois, key=lambda day: day.roi)

    def get_worst_day(self) -> Optional[DailyROISummary]:
        """
        Obtiene el día con peor ROI en la ventana.

        Returns:
            DailyROISummary del peor día, o None si no hay datos
        """
        if not self.daily_rois:
            return None

        return min(self.daily_rois, key=lambda day: day.roi)

    def is_complete_window(self) -> bool:
        """
        Verifica si la ventana tiene los 8 días completos.

        Returns:
            True si tiene 8 días de datos, False si no
        """
        return len(self.daily_rois) == 8

    def get_volatility(self) -> float:
        """
        Calcula la volatilidad (desviación estándar) de los ROIs diarios.

        Returns:
            Desviación estándar de los ROIs

        Note:
            Requiere numpy para cálculo preciso. Esta es una aproximación.
        """
        if not self.daily_rois:
            return 0.0

        rois = [day.roi for day in self.daily_rois]
        mean_roi = sum(rois) / len(rois)
        variance = sum((roi - mean_roi) ** 2 for roi in rois) / len(rois)
        return variance**0.5
