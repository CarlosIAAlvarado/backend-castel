import pytest
from datetime import date
from unittest.mock import Mock, patch
from app.application.services.state_classification_service import StateClassificationService
from app.domain.entities.agent_state import StateType

@pytest.fixture
def classification_service():
    return StateClassificationService()

@pytest.fixture
def mock_assignments():
    return [
        Mock(account_id="ACC001", agent_id="agent_1"),
        Mock(account_id="ACC002", agent_id="agent_1")
    ]

@pytest.fixture
def mock_movements():
    return [
        Mock(closed_pnl=100.0),
        Mock(closed_pnl=50.0)
    ]

@pytest.fixture
def mock_balances():
    return [
        Mock(balance=10000.0),
        Mock(balance=5000.0)
    ]

class TestStateClassificationService:

    @pytest.mark.unit
    def test_calculate_daily_roi_success(self, classification_service, mock_assignments, mock_movements, mock_balances):
        """Test calculo exitoso de ROI diario"""
        target_date = date(2024, 1, 1)

        classification_service.assignment_repo.get_active_by_agent = Mock(return_value=mock_assignments)
        classification_service.movement_repo.get_by_agent_and_date = Mock(return_value=mock_movements)

        def mock_get_balance(account_id, date):
            return mock_balances[0] if account_id == "ACC001" else mock_balances[1]

        classification_service.balance_repo.get_by_account_and_date = Mock(side_effect=mock_get_balance)

        result = classification_service.calculate_daily_roi("agent_1", target_date)

        assert result is not None
        assert result["pnl_day"] == 150.0
        assert result["balance_base"] == 15000.0
        assert result["roi_day"] == 0.01

    @pytest.mark.unit
    def test_calculate_daily_roi_no_assignments(self, classification_service):
        """Test que retorna None cuando no hay asignaciones"""
        classification_service.assignment_repo.get_active_by_agent = Mock(return_value=[])

        result = classification_service.calculate_daily_roi("agent_1", date(2024, 1, 1))

        assert result is None

    @pytest.mark.unit
    def test_calculate_daily_roi_zero_balance(self, classification_service, mock_assignments):
        """Test que retorna None cuando balance base es cero"""
        classification_service.assignment_repo.get_active_by_agent = Mock(return_value=mock_assignments)
        classification_service.movement_repo.get_by_agent_and_date = Mock(return_value=[])
        classification_service.balance_repo.get_by_account_and_date = Mock(return_value=None)

        result = classification_service.calculate_daily_roi("agent_1", date(2024, 1, 1))

        assert result is None

    @pytest.mark.unit
    @patch.object(StateClassificationService, 'calculate_daily_roi')
    def test_classify_state_growth(self, mock_calc_roi, classification_service):
        """Test clasificacion de estado GROWTH cuando ROI > 0"""
        mock_calc_roi.return_value = {
            "roi_day": 0.05,
            "pnl_day": 500.0,
            "balance_base": 10000.0
        }

        result = classification_service.classify_state("agent_1", date(2024, 1, 1))

        assert result.state == StateType.GROWTH
        assert result.fall_days == 0
        assert result.roi_day == 0.05

    @pytest.mark.unit
    @patch.object(StateClassificationService, 'calculate_daily_roi')
    def test_classify_state_fall_first_day(self, mock_calc_roi, classification_service):
        """Test clasificacion de estado FALL en primer dia de caida"""
        mock_calc_roi.return_value = {
            "roi_day": -0.03,
            "pnl_day": -300.0,
            "balance_base": 10000.0
        }

        result = classification_service.classify_state("agent_1", date(2024, 1, 1))

        assert result.state == StateType.FALL
        assert result.fall_days == 1
        assert result.roi_day == -0.03

    @pytest.mark.unit
    @patch.object(StateClassificationService, 'calculate_daily_roi')
    def test_classify_state_fall_consecutive_days(self, mock_calc_roi, classification_service):
        """Test que incrementa fall_days cuando sigue en caida"""
        mock_calc_roi.return_value = {
            "roi_day": -0.02,
            "pnl_day": -200.0,
            "balance_base": 10000.0
        }

        previous_state = Mock(
            state=StateType.FALL,
            fall_days=2,
            entry_date=date(2024, 1, 1),
            roi_since_entry=-0.05
        )

        result = classification_service.classify_state("agent_1", date(2024, 1, 3), previous_state)

        assert result.state == StateType.FALL
        assert result.fall_days == 3

    @pytest.mark.unit
    @patch.object(StateClassificationService, 'calculate_daily_roi')
    def test_classify_state_resets_fall_days_on_growth(self, mock_calc_roi, classification_service):
        """Test que resetea fall_days cuando pasa de FALL a GROWTH"""
        mock_calc_roi.return_value = {
            "roi_day": 0.04,
            "pnl_day": 400.0,
            "balance_base": 10000.0
        }

        previous_state = Mock(
            state=StateType.FALL,
            fall_days=2,
            entry_date=date(2024, 1, 1),
            roi_since_entry=-0.03
        )

        result = classification_service.classify_state("agent_1", date(2024, 1, 3), previous_state)

        assert result.state == StateType.GROWTH
        assert result.fall_days == 0

    @pytest.mark.unit
    @patch.object(StateClassificationService, 'calculate_daily_roi')
    def test_classify_state_raises_error_when_no_roi_data(self, mock_calc_roi, classification_service):
        """Test que lanza ValueError cuando no se puede calcular ROI"""
        mock_calc_roi.return_value = None

        with pytest.raises(ValueError, match="No se pudo calcular ROI"):
            classification_service.classify_state("agent_1", date(2024, 1, 1))

    @pytest.mark.unit
    def test_get_agents_at_risk_by_fall_days(self, classification_service):
        """Test identificacion de agentes en riesgo por dias consecutivos en caida"""
        mock_states = [
            Mock(
                agent_id="agent_1",
                is_in_casterly=True,
                fall_days=3,
                roi_since_entry=-0.05
            ),
            Mock(
                agent_id="agent_2",
                is_in_casterly=True,
                fall_days=2,
                roi_since_entry=-0.02
            )
        ]

        classification_service.state_repo.get_by_date = Mock(return_value=mock_states)

        result = classification_service.get_agents_at_risk(date(2024, 1, 1), fall_threshold=3)

        assert len(result) == 1
        assert result[0]["agent_id"] == "agent_1"
        assert result[0]["fall_days"] == 3

    @pytest.mark.unit
    def test_get_agents_at_risk_by_stop_loss(self, classification_service):
        """Test identificacion de agentes en riesgo por stop loss"""
        mock_states = [
            Mock(
                agent_id="agent_1",
                is_in_casterly=True,
                fall_days=1,
                roi_since_entry=-0.15
            ),
            Mock(
                agent_id="agent_2",
                is_in_casterly=True,
                fall_days=1,
                roi_since_entry=-0.05
            )
        ]

        classification_service.state_repo.get_by_date = Mock(return_value=mock_states)

        result = classification_service.get_agents_at_risk(
            date(2024, 1, 1),
            fall_threshold=3,
            stop_loss_threshold=-0.10
        )

        assert len(result) == 1
        assert result[0]["agent_id"] == "agent_1"
        assert "Stop Loss" in result[0]["reasons"][0]

    @pytest.mark.unit
    def test_get_agents_at_risk_ignores_not_in_casterly(self, classification_service):
        """Test que ignora agentes que no estan en Casterly"""
        mock_states = [
            Mock(
                agent_id="agent_1",
                is_in_casterly=False,
                fall_days=5,
                roi_since_entry=-0.20
            )
        ]

        classification_service.state_repo.get_by_date = Mock(return_value=mock_states)

        result = classification_service.get_agents_at_risk(date(2024, 1, 1))

        assert len(result) == 0
