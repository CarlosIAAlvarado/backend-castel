"""
Nombres de colecciones de MongoDB para el sistema Casterly Rock.

Centraliza todos los nombres de colecciones para facilitar mantenimiento
y evitar inconsistencias. Todos los nombres están basados en la estructura
actual de la base de datos.
"""

# ===== COLECCIONES PRINCIPALES =====

SIMULATIONS = "simulations"
"""Colección de configuraciones de simulaciones"""

SIMULATION_STATUS = "simulation_status"
"""Colección de estados de simulaciones"""

# ===== DATOS DE MERCADO =====

BALANCES = "balances"
"""Colección de balances históricos de cuentas"""

MOVEMENTS = "mov07.10"
"""Colección de movimientos de trading"""

# ===== ANÁLISIS Y CÁLCULOS =====

DAILY_ROI_CALCULATION = "daily_roi_calculation"
"""Colección de cálculos diarios de ROI"""

# Colecciones de ROI por ventana
AGENT_ROI_7D = "agent_roi_7d"
AGENT_ROI_3D = "agent_roi_3d"
AGENT_ROI_5D = "agent_roi_5d"
AGENT_ROI_10D = "agent_roi_10d"
AGENT_ROI_15D = "agent_roi_15d"
AGENT_ROI_30D = "agent_roi_30d"


def get_agent_roi_collection(window_days: int) -> str:
    """
    Retorna el nombre de la colección de ROI para una ventana específica.

    Args:
        window_days: Ventana de días (3, 5, 7, 10, 15, 30)

    Returns:
        Nombre de la colección
    """
    return f"agent_roi_{window_days}d"


# ===== TOP 16 =====

TOP16_BY_DAY = "top16_by_day"
"""Colección general de Top 16 (legacy)"""

# Colecciones de Top 16 por ventana
TOP16_7D = "top16_7d"
TOP16_3D = "top16_3d"
TOP16_5D = "top16_5d"
TOP16_10D = "top16_10d"
TOP16_15D = "top16_15d"
TOP16_30D = "top16_30d"


def get_top16_collection(window_days: int) -> str:
    """
    Retorna el nombre de la colección de Top 16 para una ventana específica.

    Args:
        window_days: Ventana de días (3, 5, 7, 10, 15, 30)

    Returns:
        Nombre de la colección
    """
    return f"top16_{window_days}d"


# ===== GESTIÓN DE AGENTES =====

AGENT_STATES = "agent_states"
"""Colección de estados de agentes en Casterly Rock"""

ASSIGNMENTS = "assignments"
"""Colección de asignaciones de cuentas a agentes"""

ROTATION_LOG = "rotation_log"
"""Colección de logs de rotaciones de agentes"""

RANK_CHANGES = "rank_changes"
"""Colección de cambios de ranking"""

# ===== CUENTAS Y CLIENTES =====

CLIENT_ACCOUNTS = "cuentas_clientes_trading"
"""Colección de cuentas de clientes"""

ASSIGNMENT_HISTORY = "historial_asignaciones_clientes"
"""Colección de historial de asignaciones"""

ACCOUNT_SNAPSHOTS = "distribucion_cuentas_snapshot"
"""Colección de snapshots de distribución de cuentas"""

CLIENT_ACCOUNT_SNAPSHOTS = "client_accounts_snapshots"
"""Colección de snapshots de cuentas de clientes"""

REBALANCING_LOG = "rebalanceo_log"
"""Colección de logs de rebalanceo"""

# ===== UTILIDADES =====

ALL_COLLECTIONS = [
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
    REBALANCING_LOG
]
"""Lista de todas las colecciones del sistema"""
