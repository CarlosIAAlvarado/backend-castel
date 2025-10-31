import pytest
from datetime import datetime
import pytz
from app.infrastructure.utils.data_normalizer import DataNormalizer

class TestDataNormalizer:

    @pytest.mark.unit
    @pytest.mark.parametrize("input_value,expected", [
        ("8,43", 8.43),
        ("8.43", 8.43),
        (8.43, 8.43),
        (8, 8.0),
        ("100,50", 100.50),
        ("-50,75", -50.75),
        (None, 0.0),
        ("", 0.0),
        ("invalid", 0.0),
        ("  10,5  ", 10.5),
    ])
    def test_normalize_pnl(self, input_value, expected):
        """Test que normalize_pnl maneja diferentes formatos correctamente"""
        result = DataNormalizer.normalize_pnl(input_value)
        assert result == expected

    @pytest.mark.unit
    @pytest.mark.parametrize("input_value,expected", [
        ("1000,50", 1000.50),
        ("1000.50", 1000.50),
        (1000.50, 1000.50),
        (1000, 1000.0),
        (None, 0.0),
        ("", 0.0),
        ("invalid", 0.0),
    ])
    def test_normalize_balance(self, input_value, expected):
        """Test que normalize_balance maneja diferentes formatos correctamente"""
        result = DataNormalizer.normalize_balance(input_value)
        assert result == expected

    @pytest.mark.unit
    def test_normalize_datetime_iso_with_z():
        """Test parseo de fecha ISO con Z"""
        date_str = "2025-10-07T05:00:10.065Z"
        result = DataNormalizer.normalize_datetime(date_str)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    @pytest.mark.unit
    def test_normalize_datetime_iso_without_z():
        """Test parseo de fecha ISO sin Z"""
        date_str = "2025-10-07T05:00:10.065"
        result = DataNormalizer.normalize_datetime(date_str)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    @pytest.mark.unit
    def test_normalize_datetime_simple_string():
        """Test parseo de fecha en formato simple"""
        date_str = "2025-10-07 10:32:43"
        result = DataNormalizer.normalize_datetime(date_str)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    @pytest.mark.unit
    def test_normalize_datetime_already_parsed():
        """Test que maneja datetime ya parseado"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = DataNormalizer.normalize_datetime(dt)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    @pytest.mark.unit
    def test_normalize_datetime_none():
        """Test que maneja None correctamente"""
        result = DataNormalizer.normalize_datetime(None)
        assert result is None

    @pytest.mark.unit
    def test_normalize_datetime_invalid():
        """Test que maneja fechas invalidas"""
        result = DataNormalizer.normalize_datetime("invalid-date")
        assert result is None

    @pytest.mark.unit
    def test_normalize_datetime_custom_format():
        """Test parseo con formato personalizado"""
        date_str = "01/12/2024 14:30:00"
        result = DataNormalizer.normalize_datetime(date_str, source_format="%d/%m/%Y %H:%M:%S")

        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 1

    @pytest.mark.unit
    def test_ensure_timezone_naive_datetime():
        """Test que localiza datetime sin timezone"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = DataNormalizer._ensure_timezone(dt)

        assert result.tzinfo is not None
        assert str(result.tzinfo) in ["America/Bogota", "-05:00", "-0500"]

    @pytest.mark.unit
    def test_ensure_timezone_aware_datetime():
        """Test que convierte datetime con timezone diferente"""
        utc = pytz.UTC
        dt = utc.localize(datetime(2024, 1, 1, 12, 0, 0))
        result = DataNormalizer._ensure_timezone(dt)

        assert result.tzinfo is not None

    @pytest.mark.unit
    @pytest.mark.parametrize("input_value,expected", [
        ("user123", "user123"),
        ("  user123  ", "user123"),
        (None, ""),
        ("", ""),
        (123, "123"),
    ])
    def test_normalize_user_id(self, input_value, expected):
        """Test que normalize_user_id limpia correctamente"""
        result = DataNormalizer.normalize_user_id(input_value)
        assert result == expected

    @pytest.mark.unit
    @pytest.mark.parametrize("input_value,expected", [
        ("btcusdt", "BTCUSDT"),
        ("BTCUSDT", "BTCUSDT"),
        ("  ethusdt  ", "ETHUSDT"),
        (None, ""),
        ("", ""),
        ("BtC", "BTC"),
    ])
    def test_normalize_symbol(self, input_value, expected):
        """Test que normalize_symbol convierte a mayusculas"""
        result = DataNormalizer.normalize_symbol(input_value)
        assert result == expected
