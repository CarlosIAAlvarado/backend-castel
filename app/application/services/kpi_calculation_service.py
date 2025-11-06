from typing import List, Dict, Any, Optional
from datetime import date
import numpy as np
from app.application.services.data_aggregation_service import DataAggregationService


class KPICalculationService:
    """
    Servicio para calculo de KPIs (Key Performance Indicators) de agentes.

    Calcula metricas financieras:
    - ROI_1D: Retorno sobre inversion diario
    - ROI_7D: Retorno sobre inversion 7 dias
    - ROI_30D: Retorno sobre inversion 30 dias
    - Sharpe Ratio: Relacion retorno/riesgo
    - Max Drawdown: Maxima caida desde el pico
    - Volatilidad: Desviacion estandar de retornos
    """

    def __init__(self, data_aggregation_service: DataAggregationService):
        """
        Constructor con inyeccion de dependencias.

        Args:
            data_aggregation_service: Servicio de agregacion de datos
        """
        self.data_aggregation_service = data_aggregation_service

    @staticmethod
    def calculate_roi_1d(
        pnl_day: float,
        balance_previous: float
    ) -> float:
        """
        Calcula el ROI diario (1 dia).

        Formula: ROI_1D = (PnL_day / Balance_previous) * 100

        Args:
            pnl_day: Ganancia/perdida del dia
            balance_previous: Balance al cierre del dia anterior

        Returns:
            ROI en porcentaje
        """
        if balance_previous <= 0:
            return 0.0

        return (pnl_day / balance_previous) * 100

    @staticmethod
    def calculate_roi_period(
        total_pnl: float,
        balance_current: float
    ) -> float:
        """
        Calcula el ROI de un periodo (7D, 30D, etc).

        Formula: ROI_period = (Total_PnL / Balance_current) * 100

        Args:
            total_pnl: Ganancia/perdida total del periodo
            balance_current: Balance actual

        Returns:
            ROI en porcentaje
        """
        if balance_current <= 0:
            return 0.0

        return (total_pnl / balance_current) * 100

    def calculate_roi_7d(
        self,
        agent_id: str,
        target_date: date,
        balances_cache: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Calcula el ROI de los ultimos 7 dias para un agente.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo (fin del periodo)
            balances_cache: Diccionario de balances pre-cargados (opcional)

        Returns:
            Diccionario con total_pnl, balance_current, roi_7d y datos diarios
        """
        data = self.data_aggregation_service.get_agent_data_with_lookback(
            agent_id=agent_id,
            target_date=target_date,
            lookback_days=7,
            balances_cache=balances_cache
        )

        return {
            "agent_id": agent_id,
            "target_date": target_date.isoformat(),
            "total_pnl_7d": data["total_pnl"],
            "balance_current": data["balance_current"],
            "roi_7d": data["roi_period"],
            "daily_data": data["daily_data"]
        }

    def calculate_roi_30d(
        self,
        agent_id: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        Calcula el ROI de los ultimos 30 dias para un agente.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo (fin del periodo)

        Returns:
            Diccionario con total_pnl, balance_current, roi_30d y datos diarios
        """
        data = self.data_aggregation_service.get_agent_data_with_lookback(
            agent_id=agent_id,
            target_date=target_date,
            lookback_days=30
        )

        return {
            "agent_id": agent_id,
            "target_date": target_date.isoformat(),
            "total_pnl_30d": data["total_pnl"],
            "balance_current": data["balance_current"],
            "roi_30d": data["roi_period"],
            "daily_data": data["daily_data"]
        }

    @staticmethod
    def calculate_sharpe_ratio(
        daily_returns: List[float],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calcula el Sharpe Ratio (relacion retorno/riesgo ajustado).

        Formula: Sharpe = (Mean_return - Risk_free_rate) / Std_dev_returns

        Un Sharpe mayor indica mejor relacion retorno/riesgo:
        - < 1: Bajo
        - 1-2: Bueno
        - 2-3: Muy bueno
        - > 3: Excelente

        Args:
            daily_returns: Lista de retornos diarios (en porcentaje)
            risk_free_rate: Tasa libre de riesgo (default: 0.0)

        Returns:
            Sharpe Ratio
        """
        if not daily_returns or len(daily_returns) < 2:
            return 0.0

        returns_array = np.array(daily_returns)

        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array, ddof=1)

        if std_return == 0:
            return 0.0

        sharpe = (mean_return - risk_free_rate) / std_return

        return float(sharpe)

    @staticmethod
    def calculate_max_drawdown(
        cumulative_returns: List[float]
    ) -> float:
        """
        Calcula el Max Drawdown (maxima caida desde el pico).

        Mide la mayor perdida desde un punto maximo hasta un punto minimo.
        Se expresa como porcentaje negativo.

        Ejemplo:
        - Si el balance cayo de $1000 a $800, el drawdown es -20%

        Args:
            cumulative_returns: Lista de retornos acumulados

        Returns:
            Max Drawdown como porcentaje negativo
        """
        if not cumulative_returns or len(cumulative_returns) < 2:
            return 0.0

        cumulative_array = np.array(cumulative_returns)

        peak = cumulative_array[0]
        max_dd = 0.0

        for value in cumulative_array:
            if value > peak:
                peak = value

            drawdown = ((value - peak) / peak) * 100 if peak != 0 else 0.0

            if drawdown < max_dd:
                max_dd = drawdown

        return float(max_dd)

    @staticmethod
    def calculate_volatility(
        daily_returns: List[float]
    ) -> float:
        """
        Calcula la volatilidad (desviacion estandar de retornos).

        Mide la dispersion de los retornos diarios.
        Mayor volatilidad = mayor riesgo.

        Args:
            daily_returns: Lista de retornos diarios (en porcentaje)

        Returns:
            Volatilidad como desviacion estandar
        """
        if not daily_returns or len(daily_returns) < 2:
            return 0.0

        returns_array = np.array(daily_returns)
        volatility = np.std(returns_array, ddof=1)

        return float(volatility)

    def calculate_all_kpis(
        self,
        agent_id: str,
        target_date: date,
        lookback_days: int = 7
    ) -> Dict[str, Any]:
        """
        Calcula todos los KPIs para un agente en un periodo dado.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo
            lookback_days: Dias hacia atras para calcular (default: 7)

        Returns:
            Diccionario con todos los KPIs calculados
        """
        data = self.data_aggregation_service.get_agent_data_with_lookback(
            agent_id=agent_id,
            target_date=target_date,
            lookback_days=lookback_days
        )

        daily_pnls = [day["pnl"] for day in data["daily_data"]]

        balance_base = data["balance_current"] if data["balance_current"] > 0 else 1.0
        daily_returns = [(pnl / balance_base) * 100 for pnl in daily_pnls]

        cumulative_returns = []
        cumulative = 0.0
        for ret in daily_returns:
            cumulative += ret
            cumulative_returns.append(cumulative)

        roi_1d = daily_returns[-1] if daily_returns else 0.0

        sharpe = KPICalculationService.calculate_sharpe_ratio(daily_returns)
        max_dd = KPICalculationService.calculate_max_drawdown(cumulative_returns)
        volatility = KPICalculationService.calculate_volatility(daily_returns)

        return {
            "agent_id": agent_id,
            "target_date": target_date.isoformat(),
            "lookback_days": lookback_days,
            "roi_1d": roi_1d,
            "roi_period": data["roi_period"],
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "volatility": volatility,
            "total_pnl": data["total_pnl"],
            "balance_current": data["balance_current"],
            "daily_returns": daily_returns,
            "cumulative_returns": cumulative_returns
        }
