"""
Configuración de logging para Trading Simulation Platform
Soporta logging a consola (desarrollo) y archivo (producción)
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logging(log_level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """
    Configura el sistema de logging para la aplicación.

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Si True, también escribe logs a archivo

    Returns:
        Logger configurado

    Examples:
        >>> logger = setup_logging("DEBUG")
        >>> logger.info("Aplicación iniciada")
    """
    logger = logging.getLogger("trading_simulation")
    logger.setLevel(getattr(logging, log_level.upper()))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_filename = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Obtiene el logger configurado.

    Args:
        name: Nombre del logger (opcional)

    Returns:
        Logger configurado

    Examples:
        >>> logger = get_logger()
        >>> logger.info("Mensaje de log")
    """
    if name:
        return logging.getLogger(f"trading_simulation.{name}")
    return logging.getLogger("trading_simulation")
