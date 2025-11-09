"""
Constantes del dominio de negocio.

Este paquete contiene todas las constantes y reglas de negocio
del sistema Casterly Rock.
"""

from .business_rules import (
    STOP_LOSS_THRESHOLD,
    CONSECUTIVE_FALL_THRESHOLD,
    MIN_AUM_DEFAULT,
    TOP_N_AGENTS,
    AVAILABLE_WINDOWS,
    DEFAULT_WINDOW_DAYS,
    SIMULATION_PERIOD_DAYS
)

__all__ = [
    "STOP_LOSS_THRESHOLD",
    "CONSECUTIVE_FALL_THRESHOLD",
    "MIN_AUM_DEFAULT",
    "TOP_N_AGENTS",
    "AVAILABLE_WINDOWS",
    "DEFAULT_WINDOW_DAYS",
    "SIMULATION_PERIOD_DAYS"
]
