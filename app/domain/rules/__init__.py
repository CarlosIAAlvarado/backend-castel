"""
Domain Rules Module for Casterly Rock Simulation.

Este modulo contiene las reglas de negocio implementadas usando Strategy Pattern.
Permite crear reglas configurables y extensibles sin modificar el codigo existente.
"""

from app.domain.rules.exit_rule import ExitRule
from app.domain.rules.consecutive_fall_rule import ConsecutiveFallRule
from app.domain.rules.roi_threshold_rule import ROIThresholdRule
from app.domain.rules.combined_rule import CombinedRule

__all__ = [
    "ExitRule",
    "ConsecutiveFallRule",
    "ROIThresholdRule",
    "CombinedRule"
]
