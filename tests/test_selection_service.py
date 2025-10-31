import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from app.application.services.selection_service import SelectionService

@pytest.fixture
def selection_service():
    return SelectionService()

@pytest.fixture
def mock_balance_repo():
    with patch('app.application.services.selection_service.BalanceRepositoryImpl') as mock:
        yield mock

@pytest.fixture
def mock_top16_repo():
    with patch('app.application.services.selection_service.Top16RepositoryImpl') as mock:
        yield mock

class TestSelectionService:

    @pytest.mark.unit
    def test_get_all_agents_from_balances_returns_unique_agents(self, selection_service):
        """Test que get_all_agents_from_balances retorna agentes unicos"""
        target_date = date(2024, 1, 1)

        mock_balances = [
            Mock(account_id="agent_1"),
            Mock(account_id="agent_2"),
            Mock(account_id="agent_1"),
            Mock(account_id="agent_3")
        ]

        selection_service.balance_repo.get_all_by_date = Mock(return_value=mock_balances)

        result = selection_service.get_all_agents_from_balances(target_date)

        assert len(result) == 3
        assert "agent_1" in result
        assert "agent_2" in result
        assert "agent_3" in result

    @pytest.mark.unit
    def test_get_all_agents_from_balances_handles_empty_balances(self, selection_service):
        """Test que maneja correctamente cuando no hay balances"""
        target_date = date(2024, 1, 1)

        selection_service.balance_repo.get_all_by_date = Mock(return_value=[])

        result = selection_service.get_all_agents_from_balances(target_date)

        assert result == []

    @pytest.mark.unit
    def test_get_all_agents_from_balances_ignores_null_account_ids(self, selection_service):
        """Test que ignora balances con account_id nulo"""
        target_date = date(2024, 1, 1)

        mock_balances = [
            Mock(account_id="agent_1"),
            Mock(account_id=None),
            Mock(account_id="agent_2"),
            Mock(account_id="")
        ]

        selection_service.balance_repo.get_all_by_date = Mock(return_value=mock_balances)

        result = selection_service.get_all_agents_from_balances(target_date)

        assert len(result) == 2
        assert "agent_1" in result
        assert "agent_2" in result

    @pytest.mark.unit
    @patch('app.application.services.selection_service.KPICalculationService')
    def test_calculate_single_agent_roi_success(self, mock_kpi_service, selection_service):
        """Test calculo de ROI exitoso para un agente"""
        mock_kpi_service.calculate_roi_7d.return_value = {
            "balance_current": 10000.0,
            "roi_7d": 5.5,
            "total_pnl_7d": 500.0
        }

        result = selection_service._calculate_single_agent_roi(
            agent_id="agent_1",
            target_date=date(2024, 1, 1),
            balances_cache={}
        )

        assert result["agent_id"] == "agent_1"
        assert result["roi_7d"] == 5.5
        assert result["total_aum"] == 10000.0
        assert result["total_pnl"] == 500.0

    @pytest.mark.unit
    @patch('app.application.services.selection_service.KPICalculationService')
    def test_calculate_single_agent_roi_handles_error(self, mock_kpi_service, selection_service):
        """Test que maneja errores en calculo de ROI"""
        mock_kpi_service.calculate_roi_7d.side_effect = Exception("Database error")

        result = selection_service._calculate_single_agent_roi(
            agent_id="agent_1",
            target_date=date(2024, 1, 1),
            balances_cache={}
        )

        assert result is None

    @pytest.mark.unit
    def test_calculate_single_agent_roi_returns_zero_for_missing_data(self, selection_service):
        """Test que retorna valores por defecto cuando faltan datos"""
        with patch('app.application.services.selection_service.KPICalculationService') as mock_kpi:
            mock_kpi.calculate_roi_7d.return_value = {}

            result = selection_service._calculate_single_agent_roi(
                agent_id="agent_1",
                target_date=date(2024, 1, 1),
                balances_cache={}
            )

            assert result["roi_7d"] == 0.0
            assert result["total_aum"] == 0.0
            assert result["total_pnl"] == 0.0
