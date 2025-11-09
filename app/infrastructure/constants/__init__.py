"""
Constantes de infraestructura.

Este paquete contiene todas las constantes relacionadas con la capa de
infraestructura del sistema Casterly Rock (bases de datos, colecciones, etc.).
"""

from .collection_names import (
    SIMULATIONS,
    SIMULATION_STATUS,
    BALANCES,
    MOVEMENTS,
    DAILY_ROI_CALCULATION,
    AGENT_ROI_7D,
    AGENT_ROI_3D,
    AGENT_ROI_5D,
    AGENT_ROI_10D,
    AGENT_ROI_15D,
    AGENT_ROI_30D,
    TOP16_BY_DAY,
    TOP16_7D,
    TOP16_3D,
    TOP16_5D,
    TOP16_10D,
    TOP16_15D,
    TOP16_30D,
    AGENT_STATES,
    ASSIGNMENTS,
    ROTATION_LOG,
    RANK_CHANGES,
    CLIENT_ACCOUNTS,
    ASSIGNMENT_HISTORY,
    ACCOUNT_SNAPSHOTS,
    CLIENT_ACCOUNT_SNAPSHOTS,
    REBALANCING_LOG,
    get_agent_roi_collection,
    get_top16_collection,
    ALL_COLLECTIONS
)

__all__ = [
    "SIMULATIONS",
    "SIMULATION_STATUS",
    "BALANCES",
    "MOVEMENTS",
    "DAILY_ROI_CALCULATION",
    "AGENT_ROI_7D",
    "AGENT_ROI_3D",
    "AGENT_ROI_5D",
    "AGENT_ROI_10D",
    "AGENT_ROI_15D",
    "AGENT_ROI_30D",
    "TOP16_BY_DAY",
    "TOP16_7D",
    "TOP16_3D",
    "TOP16_5D",
    "TOP16_10D",
    "TOP16_15D",
    "TOP16_30D",
    "AGENT_STATES",
    "ASSIGNMENTS",
    "ROTATION_LOG",
    "RANK_CHANGES",
    "CLIENT_ACCOUNTS",
    "ASSIGNMENT_HISTORY",
    "ACCOUNT_SNAPSHOTS",
    "CLIENT_ACCOUNT_SNAPSHOTS",
    "REBALANCING_LOG",
    "get_agent_roi_collection",
    "get_top16_collection",
    "ALL_COLLECTIONS"
]
