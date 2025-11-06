"""
Console Logger con colores para mensajes importantes
Usar solo para mensajes críticos que siempre deben verse
"""
from enum import Enum
from datetime import datetime


class LogLevel(Enum):
    """Códigos ANSI para colores en consola"""
    DEBUG = '\033[36m'
    INFO = '\033[32m'
    WARNING = '\033[33m'
    ERROR = '\033[31m'
    SUCCESS = '\033[92m'
    CRITICAL = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class ConsoleLogger:
    """
    Logger personalizado que SIEMPRE muestra en consola con colores.
    Usar solo para mensajes importantes que necesitan destacar.

    Examples:
        >>> from app.infrastructure.config.console_logger import ConsoleLogger as log
        >>> log.info("Simulación iniciada", context="[SIMULATION]")
        >>> log.success("Procesados 100 agentes", context="[ROTATION]")
        >>> log.warning("Balance bajo promedio", context="[REBALANCE]")
        >>> log.error("Error en base de datos", context="[DATABASE]")
    """

    @staticmethod
    def _format_message(level: LogLevel, message: str, context: str = "") -> str:
        """Formatea el mensaje con timestamp, nivel y contexto"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        ctx = f" {context}" if context else ""
        return f"{level.value}[{timestamp}] [{level.name}]{ctx} {message}{LogLevel.RESET.value}"

    @staticmethod
    def debug(message: str, context: str = "") -> None:
        """
        Mensaje de debug (color cyan)

        Args:
            message: Mensaje a mostrar
            context: Contexto opcional (ej: "[SIMULATION]")
        """
        print(ConsoleLogger._format_message(LogLevel.DEBUG, message, context))

    @staticmethod
    def info(message: str, context: str = "") -> None:
        """
        Mensaje informativo (color verde)

        Args:
            message: Mensaje a mostrar
            context: Contexto opcional (ej: "[SIMULATION]")
        """
        print(ConsoleLogger._format_message(LogLevel.INFO, message, context))

    @staticmethod
    def warning(message: str, context: str = "") -> None:
        """
        Mensaje de advertencia (color amarillo)

        Args:
            message: Mensaje a mostrar
            context: Contexto opcional (ej: "[REBALANCE]")
        """
        print(ConsoleLogger._format_message(LogLevel.WARNING, message, context))

    @staticmethod
    def error(message: str, context: str = "") -> None:
        """
        Mensaje de error (color rojo)

        Args:
            message: Mensaje a mostrar
            context: Contexto opcional (ej: "[DATABASE]")
        """
        print(ConsoleLogger._format_message(LogLevel.ERROR, message, context))

    @staticmethod
    def success(message: str, context: str = "") -> None:
        """
        Mensaje de éxito (color verde brillante)

        Args:
            message: Mensaje a mostrar
            context: Contexto opcional (ej: "[ROTATION]")
        """
        print(ConsoleLogger._format_message(LogLevel.SUCCESS, message, context))

    @staticmethod
    def critical(message: str, context: str = "") -> None:
        """
        Mensaje crítico (color rojo brillante + bold)

        Args:
            message: Mensaje a mostrar
            context: Contexto opcional (ej: "[CRITICAL]")
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        ctx = f" {context}" if context else ""
        formatted = f"{LogLevel.BOLD.value}{LogLevel.CRITICAL.value}[{timestamp}] [CRITICAL]{ctx} {message}{LogLevel.RESET.value}"
        print(formatted)

    @staticmethod
    def separator(char: str = "=", length: int = 80) -> None:
        """
        Imprime un separador visual

        Args:
            char: Carácter para el separador
            length: Longitud del separador
        """
        print(LogLevel.INFO.value + char * length + LogLevel.RESET.value)
