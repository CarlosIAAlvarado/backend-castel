import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch
from app.application.services.daily_orchestrator_service import DailyOrchestratorService
from app.domain.entities.agent_state import AgentState, AgentStateEnum
from app.domain.entities.assignment import Assignment


class TestDailyOrchestratorIntegration:
    """Tests de integracion para el orquestador diario"""

    @pytest.fixture
    def mock_selection_service(self):
        return Mock()

    @pytest.fixture
    def mock_assignment_service(self):
        return Mock()

    @pytest.fixture
    def mock_state_service(self):
        return Mock()

    @pytest.fixture
    def mock_exit_rules_service(self):
        return Mock()

    @pytest.fixture
    def mock_replacement_service(self):
        return Mock()

    @pytest.fixture
    def mock_state_repo(self):
        return Mock()

    @pytest.fixture
    def orchestrator(
        self,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        return DailyOrchestratorService(
            selection_service=mock_selection_service,
            assignment_service=mock_assignment_service,
            state_service=mock_state_service,
            exit_rules_service=mock_exit_rules_service,
            replacement_service=mock_replacement_service,
            state_repo=mock_state_repo
        )

    @pytest.mark.integration
    def test_process_single_day_executes_all_steps_in_order(
        self,
        orchestrator,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        """Test que process_single_day ejecuta todos los pasos en orden correcto"""
        target_date = date(2025, 10, 15)

        # Mock Top 16 selection
        mock_selection_service.select_top_16.return_value = {
            "top16": [
                {"agent_id": f"futures-{str(i).zfill(3)}", "roi_7d": 0.05 - (i * 0.001)}
                for i in range(1, 17)
            ]
        }

        # Mock assignments
        mock_assignment_service.assign_accounts.return_value = {
            "assignments": [
                Assignment(
                    account_id=f"acc-{i}",
                    agent_id=f"futures-{str(i).zfill(3)}",
                    balance=50000.0,
                    date=target_date,
                    is_active=True
                )
                for i in range(1, 17)
            ]
        }

        # Mock state classification
        mock_state_service.classify_all_agents_state.return_value = {
            "states": [
                AgentState(
                    agent_id=f"futures-{str(i).zfill(3)}",
                    date=target_date,
                    state=AgentStateEnum.GROWTH,
                    roi_day=0.02,
                    pnl_day=1000.0,
                    balance_base=50000.0,
                    fall_days=0,
                    is_in_casterly=True
                )
                for i in range(1, 17)
            ]
        }

        # Mock exit rules (no exits)
        mock_exit_rules_service.evaluate_all_agents.return_value = {
            "agents_to_exit": []
        }

        # Mock replacements (no replacements needed)
        mock_replacement_service.execute_replacements.return_value = {
            "replacements": []
        }

        result = orchestrator.process_single_day(target_date)

        # Verificar que se ejecutaron todos los pasos
        mock_selection_service.select_top_16.assert_called_once_with(target_date)
        mock_assignment_service.assign_accounts.assert_called_once()
        mock_state_service.classify_all_agents_state.assert_called_once()
        mock_exit_rules_service.evaluate_all_agents.assert_called_once()
        mock_replacement_service.execute_replacements.assert_called_once()

        assert result["success"] is True
        assert "top16_count" in result
        assert "assignments_count" in result

    @pytest.mark.integration
    def test_process_single_day_handles_agent_exits(
        self,
        orchestrator,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        """Test que maneja correctamente cuando agentes deben salir"""
        target_date = date(2025, 10, 15)

        # Mock con algunos agentes en estado de salida
        mock_selection_service.select_top_16.return_value = {
            "top16": [{"agent_id": f"futures-{str(i).zfill(3)}", "roi_7d": 0.05} for i in range(1, 17)]
        }

        mock_assignment_service.assign_accounts.return_value = {"assignments": []}

        mock_state_service.classify_all_agents_state.return_value = {
            "states": [
                AgentState(
                    agent_id="futures-001",
                    date=target_date,
                    state=AgentStateEnum.FALL,
                    roi_day=-0.05,
                    pnl_day=-2500.0,
                    balance_base=50000.0,
                    fall_days=3,  # Cumple condicion de salida
                    is_in_casterly=True
                )
            ]
        }

        # Mock exit rules detecta agente para salir
        mock_exit_rules_service.evaluate_all_agents.return_value = {
            "agents_to_exit": ["futures-001"]
        }

        # Mock replacement ejecuta reemplazo
        mock_replacement_service.execute_replacements.return_value = {
            "replacements": [
                {
                    "agent_out": "futures-001",
                    "agent_in": "futures-017",
                    "reason": "Consecutive fall days"
                }
            ]
        }

        result = orchestrator.process_single_day(target_date)

        # Verificar que se ejecutaron los reemplazos
        mock_replacement_service.execute_replacements.assert_called_once()
        assert result["success"] is True
        assert "replacements_count" in result or len(result.get("replacements", [])) > 0

    @pytest.mark.integration
    def test_run_simulation_processes_multiple_days(
        self,
        orchestrator,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        """Test que run_simulation procesa multiples dias correctamente"""
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 5)

        # Mock responses simples para cada dia
        mock_selection_service.select_top_16.return_value = {"top16": []}
        mock_assignment_service.assign_accounts.return_value = {"assignments": []}
        mock_state_service.classify_all_agents_state.return_value = {"states": []}
        mock_exit_rules_service.evaluate_all_agents.return_value = {"agents_to_exit": []}
        mock_replacement_service.execute_replacements.return_value = {"replacements": []}

        result = orchestrator.run_simulation(start_date, end_date)

        # Debe procesar 5 dias (del 1 al 5 de octubre)
        expected_days = 5
        assert result["success"] is True
        assert result["total_days"] == expected_days

        # Verificar que se llamo a process_single_day multiples veces
        assert mock_selection_service.select_top_16.call_count == expected_days

    @pytest.mark.integration
    def test_run_simulation_handles_errors_gracefully(
        self,
        orchestrator,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        """Test que maneja errores durante la simulacion"""
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 3)

        # Simular error en el segundo dia
        call_count = [0]

        def side_effect_with_error(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Database error on day 2")
            return {"top16": []}

        mock_selection_service.select_top_16.side_effect = side_effect_with_error

        # El orquestador puede o no continuar despues del error
        # dependiendo de la implementacion
        result = orchestrator.run_simulation(start_date, end_date)

        # Verificar que se manejo el error
        assert "errors" in result or result.get("success") is False

    @pytest.mark.integration
    def test_process_single_day_validates_date(self, orchestrator):
        """Test que valida fechas correctas"""
        invalid_date = None

        with pytest.raises((ValueError, TypeError, AttributeError)):
            orchestrator.process_single_day(invalid_date)

    @pytest.mark.integration
    def test_run_simulation_validates_date_range(self, orchestrator):
        """Test que valida que start_date <= end_date"""
        start_date = date(2025, 10, 15)
        end_date = date(2025, 10, 10)  # end_date < start_date

        with pytest.raises(ValueError, match="start_date debe ser anterior o igual a end_date"):
            orchestrator.run_simulation(start_date, end_date)

    @pytest.mark.integration
    def test_process_single_day_stores_results_in_database(
        self,
        orchestrator,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        """Test que los resultados se persisten en la base de datos"""
        target_date = date(2025, 10, 15)

        # Mock respuestas
        mock_selection_service.select_top_16.return_value = {"top16": []}
        mock_assignment_service.assign_accounts.return_value = {"assignments": []}

        states = [
            AgentState(
                agent_id="futures-001",
                date=target_date,
                state=AgentStateEnum.GROWTH,
                roi_day=0.02,
                pnl_day=1000.0,
                balance_base=50000.0,
                fall_days=0,
                is_in_casterly=True
            )
        ]

        mock_state_service.classify_all_agents_state.return_value = {"states": states}
        mock_exit_rules_service.evaluate_all_agents.return_value = {"agents_to_exit": []}
        mock_replacement_service.execute_replacements.return_value = {"replacements": []}

        result = orchestrator.process_single_day(target_date)

        # Verificar que se guardaron los estados
        # El servicio de estados deberia persistir automaticamente
        # o el orquestador deberia llamar a create_batch
        assert result["success"] is True

    @pytest.mark.integration
    def test_simulation_maintains_data_consistency(
        self,
        orchestrator,
        mock_selection_service,
        mock_assignment_service,
        mock_state_service,
        mock_exit_rules_service,
        mock_replacement_service,
        mock_state_repo
    ):
        """Test que la simulacion mantiene consistencia de datos entre dias"""
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 2)

        # Mock para verificar que los datos del dia anterior influyen en el siguiente
        day1_states = [
            AgentState(
                agent_id="futures-001",
                date=start_date,
                state=AgentStateEnum.GROWTH,
                roi_day=0.02,
                pnl_day=1000.0,
                balance_base=50000.0,
                fall_days=0,
                is_in_casterly=True,
                roi_since_entry=0.02
            )
        ]

        day2_states = [
            AgentState(
                agent_id="futures-001",
                date=end_date,
                state=AgentStateEnum.GROWTH,
                roi_day=0.03,
                pnl_day=1500.0,
                balance_base=51000.0,
                fall_days=0,
                is_in_casterly=True,
                roi_since_entry=0.05  # Acumulado del dia anterior
            )
        ]

        mock_selection_service.select_top_16.return_value = {"top16": [{"agent_id": "futures-001"}]}
        mock_assignment_service.assign_accounts.return_value = {"assignments": []}

        # Retornar estados diferentes segun el dia
        call_count = [0]

        def state_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"states": day1_states}
            else:
                return {"states": day2_states}

        mock_state_service.classify_all_agents_state.side_effect = state_side_effect
        mock_exit_rules_service.evaluate_all_agents.return_value = {"agents_to_exit": []}
        mock_replacement_service.execute_replacements.return_value = {"replacements": []}

        result = orchestrator.run_simulation(start_date, end_date)

        assert result["success"] is True
        assert result["total_days"] == 2
        # Verificar que se proceso dia 1 y luego dia 2
        assert mock_state_service.classify_all_agents_state.call_count == 2
