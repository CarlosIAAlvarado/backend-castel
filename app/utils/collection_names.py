"""
Helper para nombres de colecciones dinámicas basadas en window_days.

Permite usar diferentes ventanas de ROI (3, 5, 7, 10, 15, 30 días)
con colecciones separadas para cada una.

Author: Sistema Casterly Rock
Date: 2025-10-28
Version: 1.0
"""


def get_roi_collection_name(window_days: int) -> str:
    """
    Obtiene el nombre de la colección de ROI según la ventana de días.

    Args:
        window_days: Número de días de la ventana (3, 5, 7, 10, 15, 30)

    Returns:
        Nombre de la colección (ej: "agent_roi_7d", "agent_roi_30d")

    Examples:
        >>> get_roi_collection_name(7)
        'agent_roi_7d'
        >>> get_roi_collection_name(30)
        'agent_roi_30d'
    """
    return f"agent_roi_{window_days}d"


def get_top16_collection_name(window_days: int) -> str:
    """
    Obtiene el nombre de la colección de Top16 según la ventana de días.

    Args:
        window_days: Número de días de la ventana (3, 5, 7, 10, 15, 30)

    Returns:
        Nombre de la colección (ej: "top16_7d", "top16_30d")

    Examples:
        >>> get_top16_collection_name(7)
        'top16_7d'
        >>> get_top16_collection_name(30)
        'top16_30d'
    """
    return f"top16_{window_days}d"


def get_daily_roi_collection_name(window_days: int) -> str:
    """
    Obtiene el nombre de la colección de Daily ROI (cache) según la ventana.

    Args:
        window_days: Número de días de la ventana (3, 5, 7, 10, 15, 30)

    Returns:
        Nombre de la colección (ej: "daily_roi_calc_7d", "daily_roi_calc_30d")

    Examples:
        >>> get_daily_roi_collection_name(7)
        'daily_roi_calc_7d'
        >>> get_daily_roi_collection_name(30)
        'daily_roi_calc_30d'
    """
    return f"daily_roi_calc_{window_days}d"


def validate_window_days(window_days: int) -> bool:
    """
    Valida que la ventana de días sea una opción válida.

    Args:
        window_days: Número de días a validar

    Returns:
        True si es válido, False si no

    Examples:
        >>> validate_window_days(7)
        True
        >>> validate_window_days(8)
        False
    """
    valid_windows = [3, 5, 7, 10, 15, 30]
    return window_days in valid_windows


def get_all_valid_windows() -> list[int]:
    """
    Retorna lista de todas las ventanas válidas.

    Returns:
        Lista de ventanas válidas [3, 5, 7, 10, 15, 30]
    """
    return [3, 5, 7, 10, 15, 30]
