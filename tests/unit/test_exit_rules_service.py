import pytest
from datetime import date
from unittest.mock import Mock, MagicMock
from app.application.services.exit_rules_service import ExitRulesService
from app.domain.rules.consecutive_fall_rule import ConsecutiveFallRule
from app.domain.rules.roi_threshold_rule import ROIThresholdRule
from app.domain.rules.combined_rule import CombinedRule
from app.domain.entities.agent_state import AgentState, AgentStateEnum


class TestConsecutiveFallRule:
    """Tests para la regla de caidas consecutivas (Strategy Pattern)"""

    @pytest.mark.unit
    def test_should_exit_when_fall_days_exceeds_threshold(self):
        """Test que la regla se activa cuando fall_days >= min_fall_days"""
        rule = ConsecutiveFallRule(min_fall_days=3)

        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.02,
            pnl_day=-1000.0,
            balance_base=50000.0,
            fall_days=3,
            is_in_casterly=True
        )

        assert rule.should_exit(agent_state) is True
        assert "3 dias" in rule.get_reason()

    @pytest.mark.unit
    def test_should_not_exit_when_fall_days_below_threshold(self):
        """Test que la regla NO se activa cuando fall_days < min_fall_days"""
        rule = ConsecutiveFallRule(min_fall_days=3)

        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.02,
            pnl_day=-1000.0,
            balance_base=50000.0,
            fall_days=2,
            is_in_casterly=True
        )

        assert rule.should_exit(agent_state) is False

    @pytest.mark.unit
    def test_raises_error_for_invalid_min_fall_days(self):
        """Test que valida min_fall_days >= 1"""
        with pytest.raises(ValueError, match="min_fall_days debe ser mayor o igual a 1"):
            ConsecutiveFallRule(min_fall_days=0)


class TestROIThresholdRule:
    """Tests para la regla de umbral de ROI (Strategy Pattern)"""

    @pytest.mark.unit
    def test_should_exit_when_roi_below_threshold(self):
        """Test que la regla se activa cuando ROI < min_roi"""
        rule = ROIThresholdRule(min_roi=-0.10)

        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.05,
            pnl_day=-2500.0,
            balance_base=50000.0,
            fall_days=1,
            is_in_casterly=True,
            roi_since_entry=-0.12
        )

        assert rule.should_exit(agent_state) is True
        assert "-0.10" in rule.get_reason() or "-10" in rule.get_reason()

    @pytest.mark.unit
    def test_should_not_exit_when_roi_above_threshold(self):
        """Test que la regla NO se activa cuando ROI >= min_roi"""
        rule = ROIThresholdRule(min_roi=-0.10)

        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.02,
            pnl_day=-1000.0,
            balance_base=50000.0,
            fall_days=1,
            is_in_casterly=True,
            roi_since_entry=-0.05
        )

        assert rule.should_exit(agent_state) is False

    @pytest.mark.unit
    def test_should_not_exit_when_roi_is_none(self):
        """Test que la regla NO se activa cuando roi_since_entry es None"""
        rule = ROIThresholdRule(min_roi=-0.10)

        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.GROWTH,
            roi_day=0.02,
            pnl_day=1000.0,
            balance_base=50000.0,
            fall_days=0,
            is_in_casterly=True,
            roi_since_entry=None
        )

        assert rule.should_exit(agent_state) is False


class TestCombinedRule:
    """Tests para la regla combinada con operadores AND/OR (Strategy Pattern)"""

    @pytest.mark.unit
    def test_or_operator_exits_when_any_rule_triggers(self):
        """Test operador OR: se activa si cualquier regla se cumple"""
        rule1 = ConsecutiveFallRule(min_fall_days=3)
        rule2 = ROIThresholdRule(min_roi=-0.10)
        combined = CombinedRule([rule1, rule2], operator="OR")

        # Solo cumple rule1
        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.02,
            pnl_day=-1000.0,
            balance_base=50000.0,
            fall_days=3,
            is_in_casterly=True,
            roi_since_entry=-0.05  # No cumple rule2
        )

        assert combined.should_exit(agent_state) is True

    @pytest.mark.unit
    def test_and_operator_exits_only_when_all_rules_trigger(self):
        """Test operador AND: se activa solo si todas las reglas se cumplen"""
        rule1 = ConsecutiveFallRule(min_fall_days=3)
        rule2 = ROIThresholdRule(min_roi=-0.10)
        combined = CombinedRule([rule1, rule2], operator="AND")

        # Cumple ambas reglas
        agent_state_both = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.05,
            pnl_day=-2500.0,
            balance_base=50000.0,
            fall_days=3,
            is_in_casterly=True,
            roi_since_entry=-0.12
        )

        assert combined.should_exit(agent_state_both) is True

        # Solo cumple rule1
        agent_state_one = AgentState(
            agent_id="futures-002",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.02,
            pnl_day=-1000.0,
            balance_base=50000.0,
            fall_days=3,
            is_in_casterly=True,
            roi_since_entry=-0.05
        )

        assert combined.should_exit(agent_state_one) is False

    @pytest.mark.unit
    def test_get_triggered_reasons_returns_all_active_rules(self):
        """Test que retorna las razones de todas las reglas activas"""
        rule1 = ConsecutiveFallRule(min_fall_days=3)
        rule2 = ROIThresholdRule(min_roi=-0.10)
        combined = CombinedRule([rule1, rule2], operator="OR")

        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.05,
            pnl_day=-2500.0,
            balance_base=50000.0,
            fall_days=3,
            is_in_casterly=True,
            roi_since_entry=-0.12
        )

        reasons = combined.get_triggered_reasons(agent_state)

        assert len(reasons) == 2
        assert any("3 dias" in reason for reason in reasons)
        assert any("-0.10" in reason or "-10" in reason for reason in reasons)

    @pytest.mark.unit
    def test_raises_error_for_empty_rules_list(self):
        """Test que valida que la lista de reglas no este vacia"""
        with pytest.raises(ValueError, match="La lista de reglas no puede estar vacia"):
            CombinedRule([], operator="OR")

    @pytest.mark.unit
    def test_raises_error_for_invalid_operator(self):
        """Test que valida operadores validos (AND/OR)"""
        rule1 = ConsecutiveFallRule(min_fall_days=3)

        with pytest.raises(ValueError, match="Operador invalido"):
            CombinedRule([rule1], operator="XOR")


class TestExitRulesService:
    """Tests para el servicio de reglas de salida"""

    @pytest.fixture
    def mock_state_repo(self):
        return Mock()

    @pytest.fixture
    def mock_assignment_repo(self):
        return Mock()

    @pytest.mark.unit
    def test_service_uses_default_rules_when_none_provided(self, mock_state_repo, mock_assignment_repo):
        """Test que el servicio usa reglas por defecto si no se proporcionan"""
        service = ExitRulesService(mock_state_repo, mock_assignment_repo)

        # Debe tener reglas por defecto (ConsecutiveFallRule OR ROIThresholdRule)
        assert service.exit_rule is not None
        assert isinstance(service.exit_rule, CombinedRule)

    @pytest.mark.unit
    def test_service_accepts_custom_rules(self, mock_state_repo, mock_assignment_repo):
        """Test que el servicio acepta reglas personalizadas"""
        custom_rule = ConsecutiveFallRule(min_fall_days=5)
        service = ExitRulesService(mock_state_repo, mock_assignment_repo, exit_rules=[custom_rule])

        assert service.exit_rule is not None
        assert isinstance(service.exit_rule, CombinedRule)

    @pytest.mark.unit
    def test_evaluate_agent_detects_exit_condition(self, mock_state_repo, mock_assignment_repo):
        """Test que evalua correctamente cuando se cumple condicion de salida"""
        # Mock del estado del agente
        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.FALL,
            roi_day=-0.05,
            pnl_day=-2500.0,
            balance_base=50000.0,
            fall_days=3,
            is_in_casterly=True,
            roi_since_entry=-0.05
        )

        mock_state_repo.get_by_agent_and_date.return_value = agent_state

        service = ExitRulesService(mock_state_repo, mock_assignment_repo)
        result = service.evaluate_agent("futures-001", date(2025, 10, 15))

        assert result["should_exit"] is True
        assert len(result["reasons"]) > 0

    @pytest.mark.unit
    def test_evaluate_agent_returns_false_when_no_exit_condition(self, mock_state_repo, mock_assignment_repo):
        """Test que retorna False cuando no se cumple condicion de salida"""
        agent_state = AgentState(
            agent_id="futures-001",
            date=date(2025, 10, 15),
            state=AgentStateEnum.GROWTH,
            roi_day=0.03,
            pnl_day=1500.0,
            balance_base=50000.0,
            fall_days=0,
            is_in_casterly=True,
            roi_since_entry=0.05
        )

        mock_state_repo.get_by_agent_and_date.return_value = agent_state

        service = ExitRulesService(mock_state_repo, mock_assignment_repo)
        result = service.evaluate_agent("futures-001", date(2025, 10, 15))

        assert result["should_exit"] is False
        assert len(result["reasons"]) == 0

    @pytest.mark.unit
    def test_evaluate_agent_handles_missing_state(self, mock_state_repo, mock_assignment_repo):
        """Test que maneja correctamente cuando no existe el estado"""
        mock_state_repo.get_by_agent_and_date.return_value = None

        service = ExitRulesService(mock_state_repo, mock_assignment_repo)
        result = service.evaluate_agent("futures-999", date(2025, 10, 15))

        assert result["should_exit"] is False
        assert "error" in result or result["reasons"] == []
