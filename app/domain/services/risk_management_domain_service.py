"""
Risk Management Domain Service (Domain Layer).

Contiene lógica de negocio pura para gestión de riesgos en trading.
No depende de infraestructura (sin I/O, sin DB, sin API calls).
"""

from typing import List, Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """
    Niveles de riesgo para agentes de trading.
    """

    LOW = "low"  # Riesgo bajo: Buen performance, estable
    MEDIUM = "medium"  # Riesgo medio: Performance aceptable
    HIGH = "high"  # Riesgo alto: Performance pobre
    CRITICAL = "critical"  # Riesgo crítico: Pérdidas significativas


class RiskManagementDomainService:
    """
    Domain Service para lógica de negocio de gestión de riesgos.

    RESPONSABILIDAD ÚNICA: Cálculos de riesgo y métricas financieras.
    - ✅ Calcular nivel de riesgo de agentes
    - ✅ Calcular Sharpe Ratio
    - ✅ Calcular Maximum Drawdown
    - ✅ Evaluar diversificación de portfolio
    - ❌ NO accede a base de datos
    - ❌ NO hace I/O

    Beneficios Domain Service:
    - Lógica financiera centralizada
    - Algoritmos de riesgo testables
    - Reutilizable en diferentes contextos
    """

    # Constantes de riesgo (Business Rules)
    ROI_THRESHOLD_LOW_RISK = 0.10  # ROI > 10% = bajo riesgo
    ROI_THRESHOLD_MEDIUM_RISK = 0.05  # ROI > 5% = riesgo medio
    ROI_THRESHOLD_HIGH_RISK = -0.05  # ROI > -5% = riesgo alto
    # ROI <= -5% = riesgo crítico

    DRAWDOWN_THRESHOLD_LOW_RISK = 0.05  # Drawdown < 5%
    DRAWDOWN_THRESHOLD_MEDIUM_RISK = 0.10  # Drawdown < 10%
    DRAWDOWN_THRESHOLD_HIGH_RISK = 0.20  # Drawdown < 20%

    WIN_RATE_THRESHOLD_LOW_RISK = 0.70  # Win rate > 70%
    WIN_RATE_THRESHOLD_MEDIUM_RISK = 0.55  # Win rate > 55%

    def calculate_risk_level(
        self, agent_data: Dict[str, Any]
    ) -> tuple[RiskLevel, str]:
        """
        Calcula el nivel de riesgo de un agente.

        Lógica de negocio pura basada en múltiples métricas:
        - ROI
        - Win Rate
        - Sharpe Ratio (si disponible)
        - Días negativos

        Args:
            agent_data: Datos del agente (roi_7d, win_rate, etc.)

        Returns:
            Tuple con (RiskLevel, razón: str)

        Example:
            >>> service = RiskManagementDomainService()
            >>> risk_level, reason = service.calculate_risk_level({
            ...     "roi_7d": 0.12,
            ...     "win_rate": 0.75,
            ...     "negative_days": 1
            ... })
            >>> print(f"{risk_level.value}: {reason}")
        """
        roi = agent_data.get("roi_7d", 0.0)
        win_rate = agent_data.get("win_rate", 0.0)
        negative_days = agent_data.get("negative_days", 0)
        total_days = agent_data.get("positive_days", 0) + negative_days

        # Calcular score de riesgo (0-100, menor = mejor)
        risk_score = 0

        # Factor 1: ROI (40% del score)
        if roi >= self.ROI_THRESHOLD_LOW_RISK:
            risk_score += 0  # Excelente
        elif roi >= self.ROI_THRESHOLD_MEDIUM_RISK:
            risk_score += 15  # Bueno
        elif roi >= self.ROI_THRESHOLD_HIGH_RISK:
            risk_score += 30  # Aceptable
        else:
            risk_score += 40  # Pobre

        # Factor 2: Win Rate (30% del score)
        if win_rate >= self.WIN_RATE_THRESHOLD_LOW_RISK:
            risk_score += 0  # Excelente
        elif win_rate >= self.WIN_RATE_THRESHOLD_MEDIUM_RISK:
            risk_score += 15  # Bueno
        else:
            risk_score += 30  # Pobre

        # Factor 3: Consistencia - días negativos (30% del score)
        if total_days > 0:
            negative_ratio = negative_days / total_days
            if negative_ratio <= 0.20:  # <= 20% días negativos
                risk_score += 0  # Muy consistente
            elif negative_ratio <= 0.40:  # <= 40% días negativos
                risk_score += 10  # Consistente
            elif negative_ratio <= 0.60:  # <= 60% días negativos
                risk_score += 20  # Inconsistente
            else:
                risk_score += 30  # Muy inconsistente

        # Determinar nivel de riesgo basado en score
        if risk_score <= 20:
            risk_level = RiskLevel.LOW
            reason = f"Low risk: Excellent metrics (score: {risk_score}/100)"
        elif risk_score <= 50:
            risk_level = RiskLevel.MEDIUM
            reason = f"Medium risk: Acceptable metrics (score: {risk_score}/100)"
        elif risk_score <= 75:
            risk_level = RiskLevel.HIGH
            reason = f"High risk: Poor metrics (score: {risk_score}/100)"
        else:
            risk_level = RiskLevel.CRITICAL
            reason = f"Critical risk: Very poor metrics (score: {risk_score}/100)"

        logger.debug(
            f"[DOMAIN] Risk level calculated for {agent_data.get('userId', 'unknown')}: "
            f"{risk_level.value} ({reason})"
        )

        return risk_level, reason

    def calculate_sharpe_ratio(
        self, roi: float, volatility: float, risk_free_rate: float = 0.0
    ) -> float:
        """
        Calcula el Sharpe Ratio (medida de retorno ajustado por riesgo).

        Fórmula: Sharpe Ratio = (ROI - Risk Free Rate) / Volatility

        Args:
            roi: Return on Investment
            volatility: Volatilidad (desviación estándar de retornos)
            risk_free_rate: Tasa libre de riesgo (default 0%)

        Returns:
            float: Sharpe Ratio

        Example:
            >>> service = RiskManagementDomainService()
            >>> sharpe = service.calculate_sharpe_ratio(0.15, 0.08, 0.02)
            >>> print(f"Sharpe Ratio: {sharpe:.2f}")
        """
        if volatility == 0:
            logger.warning("[DOMAIN] Cannot calculate Sharpe Ratio: volatility is zero")
            return 0.0

        sharpe_ratio = (roi - risk_free_rate) / volatility

        logger.debug(
            f"[DOMAIN] Sharpe Ratio calculated: {sharpe_ratio:.2f} "
            f"(ROI: {roi:.2%}, Vol: {volatility:.2%}, RFR: {risk_free_rate:.2%})"
        )

        return sharpe_ratio

    def calculate_max_drawdown(self, daily_balances: List[float]) -> float:
        """
        Calcula el Maximum Drawdown (máxima pérdida desde un pico).

        Métrica clave de riesgo que mide la peor caída desde un máximo histórico.

        Args:
            daily_balances: Lista de balances diarios ordenados

        Returns:
            float: Maximum Drawdown como porcentaje negativo (ej: -0.15 = -15%)

        Example:
            >>> service = RiskManagementDomainService()
            >>> mdd = service.calculate_max_drawdown([10000, 11000, 9500, 10500])
            >>> print(f"Max Drawdown: {mdd:.2%}")
        """
        if not daily_balances or len(daily_balances) < 2:
            logger.debug("[DOMAIN] Insufficient data to calculate Max Drawdown")
            return 0.0

        max_drawdown = 0.0
        peak = daily_balances[0]

        for balance in daily_balances[1:]:
            if balance > peak:
                peak = balance
            else:
                drawdown = (balance - peak) / peak  # Siempre negativo o cero
                max_drawdown = min(max_drawdown, drawdown)

        logger.debug(f"[DOMAIN] Max Drawdown calculated: {max_drawdown:.2%}")

        return max_drawdown

    def evaluate_portfolio_diversification(
        self, agents_by_strategy: Dict[str, int]
    ) -> tuple[float, str]:
        """
        Evalúa la diversificación del portfolio por estrategia de trading.

        Usa el índice Herfindahl-Hirschman (HHI) para medir concentración.
        HHI = Σ (market_share)^2

        Args:
            agents_by_strategy: Dict con estrategia como key y número de agentes como value

        Returns:
            Tuple con (diversification_score: float 0-1, interpretación: str)
            - 0.0 = Completamente concentrado
            - 1.0 = Perfectamente diversificado

        Example:
            >>> service = RiskManagementDomainService()
            >>> score, interpretation = service.evaluate_portfolio_diversification({
            ...     "momentum": 5,
            ...     "mean_reversion": 4,
            ...     "arbitrage": 3,
            ...     "breakout": 4
            ... })
            >>> print(f"Diversification: {score:.2f} ({interpretation})")
        """
        if not agents_by_strategy:
            return 0.0, "No agents in portfolio"

        total_agents = sum(agents_by_strategy.values())

        if total_agents == 0:
            return 0.0, "No agents in portfolio"

        # Calcular HHI
        hhi = sum((count / total_agents) ** 2 for count in agents_by_strategy.values())

        # Convertir HHI a score de diversificación (invertir y normalizar)
        # HHI range: [1/n, 1] donde n = número de estrategias
        # Si HHI = 1: completamente concentrado (score = 0)
        # Si HHI = 1/n: perfectamente diversificado (score = 1)

        n_strategies = len(agents_by_strategy)
        min_hhi = 1.0 / n_strategies  # Mínimo HHI posible (perfecta diversificación)
        max_hhi = 1.0  # Máximo HHI (todo en una estrategia)

        # Normalizar: score = 1 - (HHI - min_HHI) / (max_HHI - min_HHI)
        if max_hhi - min_hhi == 0:
            diversification_score = 1.0
        else:
            diversification_score = 1.0 - (hhi - min_hhi) / (max_hhi - min_hhi)

        # Interpretación
        if diversification_score >= 0.80:
            interpretation = "Excellent diversification"
        elif diversification_score >= 0.60:
            interpretation = "Good diversification"
        elif diversification_score >= 0.40:
            interpretation = "Moderate diversification"
        else:
            interpretation = "Poor diversification (high concentration)"

        logger.info(
            f"[DOMAIN] Portfolio diversification: {diversification_score:.2f} ({interpretation}). "
            f"HHI: {hhi:.3f}, Strategies: {n_strategies}"
        )

        return diversification_score, interpretation

    def should_reduce_agent_allocation(
        self, agent_data: Dict[str, Any], risk_threshold: RiskLevel = RiskLevel.HIGH
    ) -> tuple[bool, str]:
        """
        Determina si se debe reducir la asignación de cuentas de un agente por riesgo.

        Args:
            agent_data: Datos del agente
            risk_threshold: Umbral de riesgo para reducir asignación

        Returns:
            Tuple (should_reduce: bool, razón: str)

        Example:
            >>> service = RiskManagementDomainService()
            >>> should_reduce, reason = service.should_reduce_agent_allocation(agent_data)
            >>> if should_reduce:
            ...     print(f"Reduce allocation: {reason}")
        """
        risk_level, risk_reason = self.calculate_risk_level(agent_data)

        # Comparar nivel de riesgo
        risk_levels_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]

        agent_risk_index = risk_levels_order.index(risk_level)
        threshold_risk_index = risk_levels_order.index(risk_threshold)

        if agent_risk_index >= threshold_risk_index:
            reason = (
                f"Agent risk level ({risk_level.value}) exceeds threshold ({risk_threshold.value}). "
                f"{risk_reason}"
            )
            logger.warning(f"[DOMAIN] ⚠️ Allocation reduction recommended: {reason}")
            return True, reason
        else:
            reason = f"Agent risk level ({risk_level.value}) is acceptable. {risk_reason}"
            logger.debug(f"[DOMAIN] ✅ Allocation maintained: {reason}")
            return False, reason

    def calculate_optimal_position_size(
        self, account_balance: float, risk_per_trade: float = 0.02, win_rate: float = 0.60
    ) -> float:
        """
        Calcula el tamaño óptimo de posición usando Kelly Criterion.

        Kelly Criterion: f* = (p * b - q) / b
        donde:
        - p = probabilidad de ganar (win rate)
        - q = probabilidad de perder (1 - win rate)
        - b = ratio ganancia/pérdida

        Args:
            account_balance: Balance de la cuenta
            risk_per_trade: Riesgo por trade (default 2%)
            win_rate: Tasa de éxito histórica

        Returns:
            float: Tamaño óptimo de posición en USD

        Example:
            >>> service = RiskManagementDomainService()
            >>> position_size = service.calculate_optimal_position_size(10000, 0.02, 0.65)
            >>> print(f"Optimal position: ${position_size:.2f}")
        """
        # Simplificación: usar una versión conservadora de Kelly (1/2 Kelly)
        # Asumimos ratio ganancia/pérdida = 1.5 (gana $1.5 por cada $1 perdido)

        if win_rate <= 0 or win_rate >= 1:
            logger.warning(f"[DOMAIN] Invalid win rate: {win_rate}")
            return account_balance * risk_per_trade

        b = 1.5  # Ratio ganancia/pérdida
        p = win_rate
        q = 1 - win_rate

        kelly_fraction = (p * b - q) / b

        # Aplicar fracción conservadora (1/2 Kelly)
        conservative_kelly = kelly_fraction * 0.5

        # Limitar al risk_per_trade máximo
        optimal_fraction = min(conservative_kelly, risk_per_trade)

        # Asegurar que sea positivo
        optimal_fraction = max(optimal_fraction, 0.01)

        position_size = account_balance * optimal_fraction

        logger.debug(
            f"[DOMAIN] Optimal position size: ${position_size:.2f} "
            f"({optimal_fraction:.2%} of ${account_balance:.2f})"
        )

        return position_size
