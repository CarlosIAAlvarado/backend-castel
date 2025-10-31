import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock
from app.application.services.data_aggregation_service import DataAggregationService
from app.domain.entities.movement import Movement
from app.domain.entities.balance import Balance


class TestDataAggregationService:
    """Tests para el servicio de agregacion de datos"""

    @pytest.fixture
    def mock_movement_query_service(self):
        return Mock()

    @pytest.fixture
    def mock_balance_query_service(self):
        return Mock()

    @pytest.fixture
    def aggregation_service(self, mock_movement_query_service, mock_balance_query_service):
        return DataAggregationService(mock_movement_query_service, mock_balance_query_service)

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
                account_id="acc-001",
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
                account_id="acc-002",
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.5,
                price=50000.0,
                resultado=800.0,
                comision=8.0
            )
        ]

    @pytest.fixture
    def sample_balances(self):
        """Fixture con balances de ejemplo"""
        target_date = date(2025, 10, 15)
        return [
            Balance(
                account_id="acc-001",
                balance=51000.0,
                createdAt=target_date
            ),
            Balance(
                account_id="acc-002",
                balance=30800.0,
                createdAt=target_date
            )
        ]

    @pytest.mark.unit
    def test_aggregate_movements_by_day_and_agent(
        self, aggregation_service, sample_movements
    ):
        """Test que agrega movimientos correctamente por dia y agente"""
        result = DataAggregationService.aggregate_movements_by_day_and_agent(sample_movements)

        assert len(result) == 2  # 2 agentes
        assert date(2025, 10, 15) in result
        assert "futures-001" in result[date(2025, 10, 15)]
        assert "futures-002" in result[date(2025, 10, 15)]

        # Verificar agregacion de futures-001
        agent_001_data = result[date(2025, 10, 15)]["futures-001"]
        assert agent_001_data["total_pnl"] == 1000.0  # 1500 - 500
        assert agent_001_data["total_commission"] == 15.0  # 10 + 5
        assert agent_001_data["operations_count"] == 2

    @pytest.mark.unit
    def test_aggregate_movements_handles_empty_list(self, aggregation_service):
        """Test que maneja correctamente lista vacia de movimientos"""
        result = DataAggregationService.aggregate_movements_by_day_and_agent([])

        assert result == {}

    @pytest.mark.unit
    def test_aggregate_movements_handles_multiple_days(self, aggregation_service):
        """Test que agrega movimientos de multiples dias correctamente"""
        day1 = date(2025, 10, 14)
        day2 = date(2025, 10, 15)

        movements = [
            Movement(
                agent_id="futures-001",
                date=day1,
                account_id="acc-001",
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                price=50000.0,
                resultado=500.0,
                comision=5.0
            ),
            Movement(
                agent_id="futures-001",
                date=day2,
                account_id="acc-001",
                symbol="BTCUSDT",
                side="SELL",
                quantity=1.0,
                price=51000.0,
                resultado=1000.0,
                comision=10.0
            )
        ]

        result = DataAggregationService.aggregate_movements_by_day_and_agent(movements)

        assert len(result) == 2  # 2 dias
        assert day1 in result
        assert day2 in result
        assert result[day1]["futures-001"]["total_pnl"] == 500.0
        assert result[day2]["futures-001"]["total_pnl"] == 1000.0

    @pytest.mark.unit
    def test_match_movements_with_balances(
        self, aggregation_service, sample_movements, sample_balances
    ):
        """Test que hace match de movimientos con balances correctamente"""
        aggregated = DataAggregationService.aggregate_movements_by_day_and_agent(sample_movements)

        result = DataAggregationService.match_movements_with_balances(
            aggregated,
            sample_balances,
            date(2025, 10, 15)
        )

        assert date(2025, 10, 15) in result
        assert "futures-001" in result[date(2025, 10, 15)]
        assert "futures-002" in result[date(2025, 10, 15)]

        # Verificar que se añadio balance a futures-001
        agent_001 = result[date(2025, 10, 15)]["futures-001"]
        assert "balance" in agent_001
        assert agent_001["balance"] == 51000.0

    @pytest.mark.unit
    def test_match_movements_with_balances_handles_missing_balance(
        self, aggregation_service, sample_movements
    ):
        """Test que maneja correctamente cuando falta balance para un agente"""
        aggregated = DataAggregationService.aggregate_movements_by_day_and_agent(sample_movements)

        # Solo un balance
        balances = [
            Balance(
                account_id="acc-001",
                balance=51000.0,
                createdAt=date(2025, 10, 15)
            )
        ]

        result = DataAggregationService.match_movements_with_balances(
            aggregated,
            balances,
            date(2025, 10, 15)
        )

        # futures-002 no tiene balance matching
        agent_002 = result[date(2025, 10, 15)]["futures-002"]
        assert agent_002.get("balance") is None or agent_002.get("balance") == 0.0

    @pytest.mark.unit
    def test_get_agent_data_with_lookback(
        self, aggregation_service, mock_movement_query_service, mock_balance_query_service
    ):
        """Test que obtiene datos del agente con lookback period"""
        target_date = date(2025, 10, 15)
        agent_id = "futures-001"
        lookback_days = 7

        # Mock movements
        movements = [
            Movement(
                agent_id=agent_id,
                date=target_date - timedelta(days=i),
                account_id="acc-001",
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                price=50000.0,
                resultado=100.0 * i,
                comision=5.0
            )
            for i in range(lookback_days)
        ]

        mock_movement_query_service.get_movements_by_date_range.return_value = movements

        # Mock balances
        balances = [
            Balance(
                account_id="acc-001",
                balance=50000.0,
                createdAt=target_date
            )
        ]

        mock_balance_query_service.get_balances_by_date.return_value = balances

        result = aggregation_service.get_agent_data_with_lookback(
            agent_id=agent_id,
            target_date=target_date,
            lookback_days=lookback_days
        )

        assert result is not None
        assert len(result) > 0
        mock_movement_query_service.get_movements_by_date_range.assert_called_once()

    @pytest.mark.unit
    def test_get_agent_data_with_lookback_handles_no_data(
        self, aggregation_service, mock_movement_query_service, mock_balance_query_service
    ):
        """Test que maneja correctamente cuando no hay datos"""
        target_date = date(2025, 10, 15)
        agent_id = "futures-999"
        lookback_days = 7

        mock_movement_query_service.get_movements_by_date_range.return_value = []
        mock_balance_query_service.get_balances_by_date.return_value = []

        result = aggregation_service.get_agent_data_with_lookback(
            agent_id=agent_id,
            target_date=target_date,
            lookback_days=lookback_days
        )

        # Debe retornar estructura vacia o None
        assert result is not None
        # La estructura puede ser vacia o con valores por defecto

    @pytest.mark.unit
    def test_aggregate_movements_calculates_correct_totals(self, aggregation_service):
        """Test que calcula correctamente totales de P&L y comisiones"""
        movements = [
            Movement(
                agent_id="futures-001",
                date=date(2025, 10, 15),
                account_id="acc-001",
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                price=50000.0,
                resultado=1000.0,
                comision=10.0
            ),
            Movement(
                agent_id="futures-001",
                date=date(2025, 10, 15),
                account_id="acc-001",
                symbol="ETHUSDT",
                side="SELL",
                quantity=5.0,
                price=3000.0,
                resultado=-300.0,
                comision=3.0
            ),
            Movement(
                agent_id="futures-001",
                date=date(2025, 10, 15),
                account_id="acc-001",
                symbol="BTCUSDT",
                side="SELL",
                quantity=0.5,
                price=51000.0,
                resultado=500.0,
                comision=5.0
            )
        ]

        result = DataAggregationService.aggregate_movements_by_day_and_agent(movements)

        agent_data = result[date(2025, 10, 15)]["futures-001"]

        # Verificar totales: 1000 - 300 + 500 = 1200
        assert agent_data["total_pnl"] == 1200.0
        # Verificar comisiones: 10 + 3 + 5 = 18
        assert agent_data["total_commission"] == 18.0
        # Verificar conteo
        assert agent_data["operations_count"] == 3
