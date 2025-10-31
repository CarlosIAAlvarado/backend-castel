import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock
from app.application.services.movement_query_service import MovementQueryService
from app.domain.entities.movement import Movement


class TestMovementQueryService:
    """Tests para el servicio de consulta de movimientos"""

    @pytest.fixture
    def mock_movement_repo(self):
        return Mock()

    @pytest.fixture
    def movement_service(self, mock_movement_repo):
        return MovementQueryService(mock_movement_repo)

    @pytest.fixture
    def sample_movements(self):
        """Fixture con movimientos de ejemplo"""
        target_date = date(2025, 10, 15)
        return [
            Movement(
                agent_id="futures-001",
                date=target_date,
                account_id="acc-001",
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.5,
                price=50000.0,
                resultado=1500.0,
                comision=10.0
            ),
            Movement(
                agent_id="futures-001",
                date=target_date,
                account_id="acc-002",
                symbol="ETHUSDT",
                side="SELL",
                quantity=10.0,
                price=3000.0,
                resultado=-500.0,
                comision=5.0
            ),
            Movement(
                agent_id="futures-002",
                date=target_date,
                account_id="acc-003",
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.5,
                price=50000.0,
                resultado=800.0,
                comision=8.0
            )
        ]

    @pytest.mark.unit
    def test_get_movements_by_date_range_returns_all_movements(
        self, movement_service, mock_movement_repo, sample_movements
    ):
        """Test que retorna todos los movimientos en un rango de fechas"""
        start_date = date(2025, 10, 10)
        end_date = date(2025, 10, 15)

        mock_movement_repo.get_by_date_range.return_value = sample_movements

        result = movement_service.get_movements_by_date_range(start_date, end_date)

        assert len(result) == 3
        mock_movement_repo.get_by_date_range.assert_called_once_with(start_date, end_date, None)

    @pytest.mark.unit
    def test_get_movements_by_date_range_filters_by_agent(
        self, movement_service, mock_movement_repo, sample_movements
    ):
        """Test que filtra movimientos por agente especifico"""
        start_date = date(2025, 10, 10)
        end_date = date(2025, 10, 15)
        agent_id = "futures-001"

        # Filtrar solo movimientos del agente
        filtered_movements = [m for m in sample_movements if m.agent_id == agent_id]
        mock_movement_repo.get_by_date_range.return_value = filtered_movements

        result = movement_service.get_movements_by_date_range(start_date, end_date, agent_id)

        assert len(result) == 2
        assert all(m.agent_id == agent_id for m in result)
        mock_movement_repo.get_by_date_range.assert_called_once_with(start_date, end_date, agent_id)

    @pytest.mark.unit
    def test_get_movements_by_date_range_handles_empty_result(
        self, movement_service, mock_movement_repo
    ):
        """Test que maneja correctamente cuando no hay movimientos"""
        start_date = date(2025, 10, 10)
        end_date = date(2025, 10, 15)

        mock_movement_repo.get_by_date_range.return_value = []

        result = movement_service.get_movements_by_date_range(start_date, end_date)

        assert result == []

    @pytest.mark.unit
    def test_get_movements_by_agent_and_date_returns_agent_movements(
        self, movement_service, mock_movement_repo, sample_movements
    ):
        """Test que retorna movimientos de un agente en una fecha"""
        target_date = date(2025, 10, 15)
        agent_id = "futures-001"

        agent_movements = [m for m in sample_movements if m.agent_id == agent_id]
        mock_movement_repo.get_by_agent_and_date.return_value = agent_movements

        result = movement_service.get_movements_by_agent_and_date(agent_id, target_date)

        assert len(result) == 2
        assert all(m.agent_id == agent_id for m in result)
        mock_movement_repo.get_by_agent_and_date.assert_called_once_with(agent_id, target_date)

    @pytest.mark.unit
    def test_get_movements_by_agent_and_date_handles_no_movements(
        self, movement_service, mock_movement_repo
    ):
        """Test que maneja correctamente cuando el agente no tiene movimientos"""
        target_date = date(2025, 10, 15)
        agent_id = "futures-999"

        mock_movement_repo.get_by_agent_and_date.return_value = []

        result = movement_service.get_movements_by_agent_and_date(agent_id, target_date)

        assert result == []

    @pytest.mark.unit
    def test_count_operations_by_agent_and_period_returns_count(
        self, movement_service, mock_movement_repo
    ):
        """Test que retorna el conteo correcto de operaciones"""
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 15)
        agent_id = "futures-001"

        mock_movement_repo.count_by_agent_and_period.return_value = 25

        result = movement_service.count_operations_by_agent_and_period(agent_id, start_date, end_date)

        assert result == 25
        mock_movement_repo.count_by_agent_and_period.assert_called_once_with(agent_id, start_date, end_date)

    @pytest.mark.unit
    def test_count_operations_returns_zero_when_no_operations(
        self, movement_service, mock_movement_repo
    ):
        """Test que retorna 0 cuando no hay operaciones"""
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 15)
        agent_id = "futures-999"

        mock_movement_repo.count_by_agent_and_period.return_value = 0

        result = movement_service.count_operations_by_agent_and_period(agent_id, start_date, end_date)

        assert result == 0

    @pytest.mark.unit
    def test_validates_date_range(self, movement_service, mock_movement_repo):
        """Test que valida rangos de fechas correctos"""
        start_date = date(2025, 10, 15)
        end_date = date(2025, 10, 10)  # end_date < start_date

        # El repositorio debería manejar la validación, pero el servicio puede pre-validar
        # Asumimos que el repositorio lanza ValueError
        mock_movement_repo.get_by_date_range.side_effect = ValueError("start_date debe ser <= end_date")

        with pytest.raises(ValueError, match="start_date debe ser <= end_date"):
            movement_service.get_movements_by_date_range(start_date, end_date)

    @pytest.mark.unit
    def test_handles_repository_errors_gracefully(
        self, movement_service, mock_movement_repo
    ):
        """Test que maneja errores del repositorio correctamente"""
        start_date = date(2025, 10, 10)
        end_date = date(2025, 10, 15)

        mock_movement_repo.get_by_date_range.side_effect = Exception("Database connection error")

        with pytest.raises(Exception, match="Database connection error"):
            movement_service.get_movements_by_date_range(start_date, end_date)
