from datetime import datetime
from typing import Optional, Union
import pytz
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Servicio de normalizacion de datos provenientes de MongoDB.

    Maneja la conversion de:
    - P&L de strings con comas a floats
    - Fechas de diferentes formatos a datetime con timezone Bogota
    - Balances a floats
    - User IDs y simbolos a strings normalizados
    """

    @staticmethod
    def normalize_pnl(pnl_value: Union[str, float, int, None]) -> float:
        """
        Normaliza valores de P&L (profit and loss) de diferentes formatos a float.

        Maneja:
        - Strings con comas como separador decimal ("8,43" -> 8.43)
        - Numeros ya en formato float/int
        - Valores None o invalidos (retorna 0.0)

        Args:
            pnl_value: Valor de P&L en cualquier formato

        Returns:
            Float normalizado
        """
        if pnl_value is None:
            return 0.0

        if isinstance(pnl_value, (float, int)):
            return float(pnl_value)

        if isinstance(pnl_value, str):
            cleaned = pnl_value.strip().replace(',', '.')

            try:
                return float(cleaned)
            except ValueError:
                return 0.0

        return 0.0

    @staticmethod
    def normalize_datetime(
        date_value: Union[str, datetime, None],
        source_format: str = "auto"
    ) -> Optional[datetime]:
        """
        Normaliza fechas de diferentes formatos a datetime con timezone Bogota.

        Formatos soportados:
        - ISO con Z: "2025-10-07T05:00:10.065Z"
        - ISO sin Z: "2025-10-07T05:00:10.065"
        - String simple: "2025-10-07 10:32:43"
        - Datetime ya parseado

        Args:
            date_value: Fecha en cualquier formato soportado
            source_format: Formato personalizado o "auto" para deteccion automatica

        Returns:
            Datetime con timezone America/Bogota o None si falla el parseo
        """
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return DataNormalizer._ensure_timezone(date_value)

        if isinstance(date_value, str):
            try:
                if source_format == "auto":
                    if 'T' in date_value and 'Z' in date_value:
                        parsed = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                    elif 'T' in date_value:
                        parsed = datetime.fromisoformat(date_value)
                    else:
                        parsed = datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S")
                else:
                    parsed = datetime.strptime(date_value, source_format)

                return DataNormalizer._ensure_timezone(parsed)

            except Exception as e:
                logger.warning(f"Error parsing date '{date_value}': {e}")
                return None

        return None

    @staticmethod
    def _ensure_timezone(dt: datetime) -> datetime:
        """
        Asegura que un datetime tenga timezone America/Bogota.

        Si el datetime no tiene timezone, lo localiza.
        Si ya tiene timezone, lo convierte a Bogota.

        Args:
            dt: Datetime a procesar

        Returns:
            Datetime con timezone America/Bogota
        """
        tz = pytz.timezone(settings.timezone)

        if dt.tzinfo is None:
            return tz.localize(dt)
        else:
            return dt.astimezone(tz)

    @staticmethod
    def normalize_balance(balance_value: Union[str, float, int, None]) -> float:
        """
        Normaliza valores de balance a float. Mismo comportamiento que normalize_pnl.

        Args:
            balance_value: Valor de balance en cualquier formato

        Returns:
            Float normalizado
        """
        if balance_value is None:
            return 0.0

        if isinstance(balance_value, (float, int)):
            return float(balance_value)

        if isinstance(balance_value, str):
            cleaned = balance_value.strip().replace(',', '.')
            try:
                return float(cleaned)
            except ValueError:
                return 0.0

        return 0.0

    @staticmethod
    def normalize_user_id(user_id: Union[str, None]) -> str:
        """
        Normaliza user ID a string limpio.

        Args:
            user_id: ID del usuario

        Returns:
            String sin espacios o vacio si es None
        """
        if user_id is None:
            return ""
        return str(user_id).strip()

    @staticmethod
    def normalize_symbol(symbol: Union[str, None]) -> str:
        """
        Normaliza simbolos de trading a mayusculas y sin espacios.

        Args:
            symbol: Simbolo (ej: "btcusdt")

        Returns:
            Simbolo normalizado (ej: "BTCUSDT") o vacio si es None
        """
        if symbol is None:
            return ""
        return str(symbol).strip().upper()


normalizer = DataNormalizer()
