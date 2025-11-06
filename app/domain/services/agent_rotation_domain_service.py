"""
Agent Rotation Domain Service (Domain Layer).

Contiene lógica de negocio pura para rotaciones de agentes.
No depende de infraestructura (sin I/O, sin DB, sin API calls).
"""

from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RotationEligibility(Enum):
    """
    Estados de elegibilidad para rotación de agentes.
    """

    ELIGIBLE = "eligible"  # Elegible para rotación
    NOT_ELIGIBLE_PERFORMANCE = "not_eligible_performance"  # No elegible: buen performance
    NOT_ELIGIBLE_NEW_AGENT = "not_eligible_new_agent"  # No elegible: agente nuevo
    NOT_ELIGIBLE_LOCKED = "not_eligible_locked"  # No elegible: agente bloqueado
    NOT_ELIGIBLE_MINIMUM_TIME = "not_eligible_minimum_time"  # No elegible: tiempo mínimo no cumplido


class AgentRotationDomainService:
    """
    Domain Service para lógica de negocio de rotaciones de agentes.

    RESPONSABILIDAD ÚNICA: Lógica de negocio pura sobre rotaciones.
    - ✅ Determinar si un agente puede ser rotado
    - ✅ Calcular tiempo mínimo de permanencia
    - ✅ Evaluar criterios de performance
    - ✅ Calcular penalizaciones por rotación
    - ❌ NO accede a base de datos (eso es responsabilidad de Application Services)
    - ❌ NO hace I/O (sin API calls, sin file access)

    Beneficios Domain Service:
    - Lógica de negocio centralizada y testeable
    - Sin dependencias de infraestructura
    - Reutilizable en diferentes contextos
    - Fácil de testear (pure functions)
    """

    # Constantes de negocio (Business Rules)
    MIN_DAYS_BEFORE_ROTATION = 3  # Mínimo 3 días antes de poder rotar un agente
    MIN_ROI_THRESHOLD = -0.10  # ROI mínimo aceptable: -10%
    POOR_PERFORMANCE_DAYS = 3  # Días consecutivos de pobre performance para rotación
    ROTATION_PENALTY_FACTOR = 0.10  # 10% de penalización en cuentas al rotar

    def can_agent_be_rotated(
        self,
        agent_data: Dict[str, Any],
        entry_date: date,
        current_date: date,
        is_locked: bool = False,
    ) -> tuple[RotationEligibility, str]:
        """
        Determina si un agente puede ser rotado según reglas de negocio.

        Esta es lógica de negocio PURA (sin I/O, sin dependencias externas).

        Args:
            agent_data: Datos del agente (roi_7d, negative_days, etc.)
            entry_date: Fecha de entrada del agente al Top 16
            current_date: Fecha actual de evaluación
            is_locked: Si el agente está bloqueado manualmente

        Returns:
            Tuple con (RotationEligibility, razón: str)

        Example:
            >>> service = AgentRotationDomainService()
            >>> eligibility, reason = service.can_agent_be_rotated(
            ...     {"roi_7d": -0.08, "negative_days": 3},
            ...     date(2025, 10, 1),
            ...     date(2025, 10, 5)
            ... )
            >>> print(f"{eligibility.value}: {reason}")
        """
        # Regla 1: Agente bloqueado manualmente
        if is_locked:
            reason = "Agent is manually locked and cannot be rotated"
            logger.debug(f"[DOMAIN] {agent_data.get('userId', 'unknown')}: {reason}")
            return RotationEligibility.NOT_ELIGIBLE_LOCKED, reason

        # Regla 2: Tiempo mínimo de permanencia
        days_in_top16 = (current_date - entry_date).days
        if days_in_top16 < self.MIN_DAYS_BEFORE_ROTATION:
            reason = (
                f"Agent must stay at least {self.MIN_DAYS_BEFORE_ROTATION} days "
                f"(current: {days_in_top16} days)"
            )
            logger.debug(f"[DOMAIN] {agent_data.get('userId', 'unknown')}: {reason}")
            return RotationEligibility.NOT_ELIGIBLE_MINIMUM_TIME, reason

        # Regla 3: Performance positivo o aceptable
        roi = agent_data.get("roi_7d", 0.0)
        if roi >= self.MIN_ROI_THRESHOLD:
            reason = f"Agent performance is acceptable (ROI: {roi:.2%} >= {self.MIN_ROI_THRESHOLD:.2%})"
            logger.debug(f"[DOMAIN] {agent_data.get('userId', 'unknown')}: {reason}")
            return RotationEligibility.NOT_ELIGIBLE_PERFORMANCE, reason

        # Regla 4: Días negativos consecutivos
        negative_days = agent_data.get("negative_days", 0)
        if negative_days < self.POOR_PERFORMANCE_DAYS:
            reason = (
                f"Agent doesn't have enough consecutive poor days "
                f"(current: {negative_days}, required: {self.POOR_PERFORMANCE_DAYS})"
            )
            logger.debug(f"[DOMAIN] {agent_data.get('userId', 'unknown')}: {reason}")
            return RotationEligibility.NOT_ELIGIBLE_PERFORMANCE, reason

        # ✅ Agente es elegible para rotación
        reason = (
            f"Agent is eligible for rotation: ROI {roi:.2%} < {self.MIN_ROI_THRESHOLD:.2%}, "
            f"{negative_days} negative days, {days_in_top16} days in Top 16"
        )
        logger.info(f"[DOMAIN] ✅ {agent_data.get('userId', 'unknown')}: {reason}")
        return RotationEligibility.ELIGIBLE, reason

    def calculate_rotation_penalty(self, current_accounts: int) -> int:
        """
        Calcula la penalización de cuentas al rotar un agente.

        Lógica de negocio: Al rotar un agente, se pierde un porcentaje de cuentas
        debido al tiempo de transición y posible insatisfacción de clientes.

        Args:
            current_accounts: Número actual de cuentas del agente

        Returns:
            int: Número de cuentas perdidas por la rotación

        Example:
            >>> service = AgentRotationDomainService()
            >>> penalty = service.calculate_rotation_penalty(100)
            >>> print(f"Penalty: {penalty} accounts (10%)")
        """
        penalty = int(current_accounts * self.ROTATION_PENALTY_FACTOR)
        logger.debug(
            f"[DOMAIN] Rotation penalty calculated: {penalty} accounts "
            f"({self.ROTATION_PENALTY_FACTOR:.0%} of {current_accounts})"
        )
        return penalty

    def should_distribute_accounts_to_top_performers(
        self,
        available_accounts: int,
        top16_agents: List[Dict[str, Any]],
        min_accounts_per_agent: int = 50,
    ) -> bool:
        """
        Determina si se deben redistribuir cuentas a agentes top performers.

        Lógica de negocio: Si hay cuentas disponibles y algunos agentes tienen
        menos del mínimo, redistribuir equitativamente.

        Args:
            available_accounts: Cuentas disponibles para redistribuir
            top16_agents: Lista de agentes Top 16 con sus datos
            min_accounts_per_agent: Mínimo de cuentas por agente

        Returns:
            bool: True si se debe redistribuir

        Example:
            >>> service = AgentRotationDomainService()
            >>> should_redistribute = service.should_distribute_accounts_to_top_performers(
            ...     500, top16_agents, min_accounts_per_agent=50
            ... )
        """
        if available_accounts <= 0:
            logger.debug("[DOMAIN] No accounts available for redistribution")
            return False

        # Contar agentes con menos del mínimo
        agents_below_min = sum(
            1
            for agent in top16_agents
            if agent.get("accounts_count", 0) < min_accounts_per_agent
        )

        if agents_below_min == 0:
            logger.debug("[DOMAIN] All agents have sufficient accounts")
            return False

        logger.info(
            f"[DOMAIN] Redistribution recommended: {agents_below_min} agents "
            f"below minimum, {available_accounts} accounts available"
        )
        return True

    def calculate_optimal_agent_replacement(
        self,
        agents_to_exit: List[Dict[str, Any]],
        replacement_candidates: List[Dict[str, Any]],
        n: int = 1,
    ) -> List[tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Calcula los reemplazos óptimos de agentes.

        Lógica de negocio: Reemplazar agentes de peor performance con candidatos
        de mejor performance potencial.

        Args:
            agents_to_exit: Agentes que deben salir
            replacement_candidates: Candidatos para entrar
            n: Número de reemplazos a calcular

        Returns:
            Lista de tuplas (agent_out, agent_in) con los reemplazos óptimos

        Example:
            >>> service = AgentRotationDomainService()
            >>> replacements = service.calculate_optimal_agent_replacement(
            ...     agents_to_exit, candidates, n=3
            ... )
        """
        if not agents_to_exit or not replacement_candidates:
            logger.debug("[DOMAIN] No agents to exit or no replacement candidates")
            return []

        # Ordenar agentes a salir por peor performance (ROI ascendente)
        sorted_exits = sorted(agents_to_exit, key=lambda x: x.get("roi_7d", 0.0))

        # Ordenar candidatos por mejor performance (ROI descendente)
        sorted_candidates = sorted(
            replacement_candidates, key=lambda x: x.get("roi_7d", 0.0), reverse=True
        )

        # Calcular reemplazos óptimos
        replacements = []
        for i in range(min(n, len(sorted_exits), len(sorted_candidates))):
            agent_out = sorted_exits[i]
            agent_in = sorted_candidates[i]

            # Validar que el reemplazo tenga sentido (ROI mejor)
            if agent_in.get("roi_7d", 0.0) > agent_out.get("roi_7d", 0.0):
                replacements.append((agent_out, agent_in))
                logger.info(
                    f"[DOMAIN] Optimal replacement: {agent_out.get('userId')} "
                    f"(ROI: {agent_out.get('roi_7d', 0):.2%}) → "
                    f"{agent_in.get('userId')} (ROI: {agent_in.get('roi_7d', 0):.2%})"
                )
            else:
                logger.warning(
                    f"[DOMAIN] Replacement doesn't improve performance: "
                    f"{agent_out.get('userId')} → {agent_in.get('userId')}"
                )

        return replacements

    def validate_rotation_rules(
        self,
        agent_out_data: Dict[str, Any],
        agent_in_data: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Valida que una rotación cumpla con todas las reglas de negocio.

        Args:
            agent_out_data: Datos del agente que sale
            agent_in_data: Datos del agente que entra

        Returns:
            Tuple (is_valid: bool, error_message: Optional[str])

        Example:
            >>> is_valid, error = service.validate_rotation_rules(agent_out, agent_in)
            >>> if not is_valid:
            ...     print(f"Invalid rotation: {error}")
        """
        # Validación 1: Agente nuevo debe tener mejor ROI que el saliente
        roi_out = agent_out_data.get("roi_7d", 0.0)
        roi_in = agent_in_data.get("roi_7d", 0.0)

        if roi_in <= roi_out:
            error = (
                f"Invalid rotation: New agent ROI ({roi_in:.2%}) must be better than "
                f"exiting agent ROI ({roi_out:.2%})"
            )
            logger.error(f"[DOMAIN] {error}")
            return False, error

        # Validación 2: Agente nuevo debe tener trades suficientes
        min_trades = 10
        trades_in = agent_in_data.get("total_trades_7d", 0)
        if trades_in < min_trades:
            error = (
                f"Invalid rotation: New agent has insufficient trades "
                f"({trades_in} < {min_trades} required)"
            )
            logger.error(f"[DOMAIN] {error}")
            return False, error

        # Validación 3: Agente nuevo debe tener balance mínimo
        min_balance = 1000.0
        balance_in = agent_in_data.get("balance_current", 0.0)
        if balance_in < min_balance:
            error = (
                f"Invalid rotation: New agent has insufficient balance "
                f"(${balance_in:.2f} < ${min_balance:.2f} required)"
            )
            logger.error(f"[DOMAIN] {error}")
            return False, error

        logger.info("[DOMAIN] ✅ Rotation validation passed")
        return True, None
