"""
Strategy Pattern para criterios de ranking de agentes.

Este módulo aplica Open/Closed Principle (OCP) al permitir
extensión de criterios de ranking sin modificar código existente.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class RankingStrategy(ABC):
    """
    Estrategia base para ranking de agentes.

    Cumple con Open/Closed Principle: abierto para extensión,
    cerrado para modificación.
    """

    @abstractmethod
    def get_sort_key(self, agent_data: Dict[str, Any]) -> float:
        """
        Obtiene el valor de ordenamiento para un agente.

        Args:
            agent_data: Datos del agente

        Returns:
            Valor numérico para ordenamiento
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Obtiene el nombre de la estrategia.

        Returns:
            Nombre descriptivo de la estrategia
        """
        pass


class ROIRankingStrategy(RankingStrategy):
    """
    Estrategia de ranking basada en ROI (Return on Investment).

    Esta es la estrategia por defecto del sistema.
    """

    def __init__(self, window_days: int = 7):
        """
        Inicializa la estrategia de ROI.

        Args:
            window_days: Ventana de días para el ROI (3, 5, 7, 10, 15, 30)
        """
        self.window_days = window_days
        self.roi_field = f"roi_{window_days}d"

    def get_sort_key(self, agent_data: Dict[str, Any]) -> float:
        """
        Retorna el ROI del agente para ordenamiento.

        Args:
            agent_data: Datos del agente con ROI

        Returns:
            Valor de ROI (mayor = mejor)
        """
        return agent_data.get(self.roi_field, 0.0)

    def get_strategy_name(self) -> str:
        """Nombre de la estrategia."""
        return f"ROI {self.window_days}d"


class SharpeRatioRankingStrategy(RankingStrategy):
    """
    Estrategia de ranking basada en Sharpe Ratio.

    Sharpe Ratio = (Retorno - Tasa libre de riesgo) / Volatilidad
    Mide retorno ajustado por riesgo.
    """

    def __init__(self, risk_free_rate: float = 0.0):
        """
        Inicializa la estrategia de Sharpe Ratio.

        Args:
            risk_free_rate: Tasa libre de riesgo (default: 0.0)
        """
        self.risk_free_rate = risk_free_rate

    def get_sort_key(self, agent_data: Dict[str, Any]) -> float:
        """
        Retorna el Sharpe Ratio del agente.

        Args:
            agent_data: Datos del agente con sharpe_ratio

        Returns:
            Valor de Sharpe Ratio (mayor = mejor)
        """
        return agent_data.get("sharpe_ratio", 0.0)

    def get_strategy_name(self) -> str:
        """Nombre de la estrategia."""
        return "Sharpe Ratio"


class TotalPnLRankingStrategy(RankingStrategy):
    """
    Estrategia de ranking basada en PnL total absoluto.

    Usa ganancias/pérdidas totales sin considerar el capital invertido.
    """

    def get_sort_key(self, agent_data: Dict[str, Any]) -> float:
        """
        Retorna el PnL total del agente.

        Args:
            agent_data: Datos del agente con total_pnl

        Returns:
            Valor de PnL total (mayor = mejor)
        """
        return agent_data.get("total_pnl", 0.0)

    def get_strategy_name(self) -> str:
        """Nombre de la estrategia."""
        return "Total PnL"


class WinRateRankingStrategy(RankingStrategy):
    """
    Estrategia de ranking basada en tasa de ganancia.

    Win Rate = (Operaciones ganadoras / Total operaciones) * 100
    """

    def get_sort_key(self, agent_data: Dict[str, Any]) -> float:
        """
        Retorna la tasa de ganancia del agente.

        Args:
            agent_data: Datos del agente con win_rate

        Returns:
            Valor de Win Rate (mayor = mejor)
        """
        return agent_data.get("win_rate", 0.0)

    def get_strategy_name(self) -> str:
        """Nombre de la estrategia."""
        return "Win Rate"


class CompositeRankingStrategy(RankingStrategy):
    """
    Estrategia compuesta que combina múltiples métricas con pesos.

    Permite crear rankings personalizados combinando diferentes criterios.
    """

    def __init__(self, strategies_with_weights: Dict[RankingStrategy, float]):
        """
        Inicializa la estrategia compuesta.

        Args:
            strategies_with_weights: Diccionario de {estrategia: peso}
                Ejemplo: {
                    ROIRankingStrategy(): 0.6,
                    SharpeRatioRankingStrategy(): 0.4
                }
        """
        self.strategies_with_weights = strategies_with_weights
        total_weight = sum(strategies_with_weights.values())

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Los pesos suman {total_weight}, normalizando a 1.0")
            # Normalizar pesos
            self.strategies_with_weights = {
                strategy: weight / total_weight
                for strategy, weight in strategies_with_weights.items()
            }

    def get_sort_key(self, agent_data: Dict[str, Any]) -> float:
        """
        Retorna el score compuesto del agente.

        Args:
            agent_data: Datos del agente

        Returns:
            Score ponderado combinando todas las estrategias
        """
        total_score = 0.0
        for strategy, weight in self.strategies_with_weights.items():
            score = strategy.get_sort_key(agent_data)
            total_score += score * weight

        return total_score

    def get_strategy_name(self) -> str:
        """Nombre de la estrategia."""
        strategies_names = [
            f"{s.get_strategy_name()}({w:.2f})"
            for s, w in self.strategies_with_weights.items()
        ]
        return f"Composite({', '.join(strategies_names)})"
