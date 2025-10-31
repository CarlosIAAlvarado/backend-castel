import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, call
from app.domain.events import (
    EventBus,
    AgentExitedEvent,
    AgentEnteredEvent,
    AgentRotationCompletedEvent,
    AccountsReassignedEvent,
    DailyProcessCompletedEvent
)


class TestEventBus:
    """Tests para el Event Bus (Publisher/Subscriber)"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.unit
    def test_subscribe_registers_handler(self, event_bus):
        """Test que subscribe registra un handler correctamente"""
        handler = Mock()

        event_bus.subscribe(AgentExitedEvent, handler)

        assert event_bus.get_handlers_count(AgentExitedEvent) == 1

    @pytest.mark.unit
    def test_publish_executes_subscribed_handlers(self, event_bus):
        """Test que publish ejecuta todos los handlers registrados"""
        handler1 = Mock()
        handler2 = Mock()

        event_bus.subscribe(AgentExitedEvent, handler1)
        event_bus.subscribe(AgentExitedEvent, handler2)

        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days"
        )

        event_bus.publish(event)

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)

    @pytest.mark.unit
    def test_publish_does_not_execute_handlers_of_other_events(self, event_bus):
        """Test que publish solo ejecuta handlers del tipo de evento correcto"""
        handler_exit = Mock()
        handler_enter = Mock()

        event_bus.subscribe(AgentExitedEvent, handler_exit)
        event_bus.subscribe(AgentEnteredEvent, handler_enter)

        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days"
        )

        event_bus.publish(event)

        handler_exit.assert_called_once()
        handler_enter.assert_not_called()

    @pytest.mark.unit
    def test_unsubscribe_removes_handler(self, event_bus):
        """Test que unsubscribe elimina un handler registrado"""
        handler = Mock()

        event_bus.subscribe(AgentExitedEvent, handler)
        assert event_bus.get_handlers_count(AgentExitedEvent) == 1

        event_bus.unsubscribe(AgentExitedEvent, handler)
        assert event_bus.get_handlers_count(AgentExitedEvent) == 0

    @pytest.mark.unit
    def test_publish_continues_if_handler_fails(self, event_bus):
        """Test que publish continua ejecutando handlers si uno falla"""
        handler1 = Mock(side_effect=Exception("Handler 1 failed"))
        handler2 = Mock()

        event_bus.subscribe(AgentExitedEvent, handler1)
        event_bus.subscribe(AgentExitedEvent, handler2)

        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days"
        )

        event_bus.publish(event)

        # Handler2 debe ejecutarse a pesar del error en handler1
        handler2.assert_called_once_with(event)

    @pytest.mark.unit
    def test_clear_handlers_removes_all_handlers_for_event_type(self, event_bus):
        """Test que clear_handlers elimina todos los handlers de un tipo"""
        handler1 = Mock()
        handler2 = Mock()

        event_bus.subscribe(AgentExitedEvent, handler1)
        event_bus.subscribe(AgentExitedEvent, handler2)

        assert event_bus.get_handlers_count(AgentExitedEvent) == 2

        event_bus.clear_handlers(AgentExitedEvent)

        assert event_bus.get_handlers_count(AgentExitedEvent) == 0

    @pytest.mark.unit
    def test_clear_handlers_without_type_removes_all(self, event_bus):
        """Test que clear_handlers sin parametro elimina todos los handlers"""
        handler1 = Mock()
        handler2 = Mock()

        event_bus.subscribe(AgentExitedEvent, handler1)
        event_bus.subscribe(AgentEnteredEvent, handler2)

        event_bus.clear_handlers()

        assert event_bus.get_handlers_count(AgentExitedEvent) == 0
        assert event_bus.get_handlers_count(AgentEnteredEvent) == 0


class TestDomainEvents:
    """Tests para eventos de dominio"""

    @pytest.mark.unit
    def test_agent_exited_event_creation(self):
        """Test que AgentExitedEvent se crea correctamente"""
        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days",
            roi_total=-0.08,
            fall_days=3,
            n_accounts=5,
            total_aum=250000.0
        )

        assert event.agent_id == "futures-001"
        assert event.exit_date == date(2025, 10, 15)
        assert event.reason == "Consecutive fall days"
        assert event.roi_total == -0.08
        assert event.fall_days == 3
        assert event.event_id is not None
        assert event.occurred_at is not None

    @pytest.mark.unit
    def test_agent_entered_event_creation(self):
        """Test que AgentEnteredEvent se crea correctamente"""
        event = AgentEnteredEvent(
            agent_id="futures-017",
            entry_date=date(2025, 10, 15),
            roi_7d=0.05,
            n_accounts=5,
            total_aum=250000.0,
            replaced_agent_id="futures-001"
        )

        assert event.agent_id == "futures-017"
        assert event.entry_date == date(2025, 10, 15)
        assert event.roi_7d == 0.05
        assert event.replaced_agent_id == "futures-001"

    @pytest.mark.unit
    def test_rotation_completed_event_creation(self):
        """Test que AgentRotationCompletedEvent se crea correctamente"""
        event = AgentRotationCompletedEvent(
            rotation_date=date(2025, 10, 15),
            agent_out="futures-001",
            agent_in="futures-017",
            reason="Consecutive fall days",
            n_accounts=5,
            total_aum=250000.0
        )

        assert event.rotation_date == date(2025, 10, 15)
        assert event.agent_out == "futures-001"
        assert event.agent_in == "futures-017"
        assert event.reason == "Consecutive fall days"

    @pytest.mark.unit
    def test_event_to_dict_serialization(self):
        """Test que evento se serializa correctamente a diccionario"""
        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days",
            roi_total=-0.08
        )

        event_dict = event.to_dict()

        assert event_dict["event_id"] == event.event_id
        assert event_dict["event_type"] == "AgentExitedEvent"
        assert event_dict["agent_id"] == "futures-001"
        assert event_dict["exit_date"] == "2025-10-15"
        assert event_dict["reason"] == "Consecutive fall days"
        assert event_dict["roi_total"] == -0.08

    @pytest.mark.unit
    def test_accounts_reassigned_event_creation(self):
        """Test que AccountsReassignedEvent se crea correctamente"""
        event = AccountsReassignedEvent(
            reassignment_date=date(2025, 10, 15),
            from_agent_id="futures-001",
            to_agent_id="futures-017",
            account_ids=["acc-001", "acc-002", "acc-003"],
            total_aum_transferred=150000.0
        )

        assert event.from_agent_id == "futures-001"
        assert event.to_agent_id == "futures-017"
        assert len(event.account_ids) == 3
        assert event.total_aum_transferred == 150000.0

    @pytest.mark.unit
    def test_daily_process_completed_event_creation(self):
        """Test que DailyProcessCompletedEvent se crea correctamente"""
        event = DailyProcessCompletedEvent(
            process_date=date(2025, 10, 15),
            agents_in_casterly=16,
            total_aum=800000.0,
            rotations_count=2,
            growth_agents=12,
            fall_agents=4,
            processing_time_ms=1500.0
        )

        assert event.process_date == date(2025, 10, 15)
        assert event.agents_in_casterly == 16
        assert event.total_aum == 800000.0
        assert event.rotations_count == 2
        assert event.growth_agents == 12
        assert event.fall_agents == 4

    @pytest.mark.unit
    def test_event_immutability(self):
        """Test que los eventos son inmutables (no deberian modificarse)"""
        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days"
        )

        original_event_id = event.event_id
        original_occurred_at = event.occurred_at

        # Los eventos no deben cambiar su event_id ni occurred_at
        assert event.event_id == original_event_id
        assert event.occurred_at == original_occurred_at


class TestEventHandlersIntegration:
    """Tests de integracion para handlers de eventos"""

    @pytest.fixture
    def event_bus(self):
        bus = EventBus()
        bus.clear_handlers()
        return bus

    @pytest.mark.integration
    def test_multiple_handlers_receive_same_event(self, event_bus):
        """Test que multiples handlers reciben el mismo evento"""
        received_events = []

        def handler1(event):
            received_events.append(("handler1", event))

        def handler2(event):
            received_events.append(("handler2", event))

        event_bus.subscribe(AgentExitedEvent, handler1)
        event_bus.subscribe(AgentExitedEvent, handler2)

        event = AgentExitedEvent(
            agent_id="futures-001",
            exit_date=date(2025, 10, 15),
            reason="Consecutive fall days"
        )

        event_bus.publish(event)

        assert len(received_events) == 2
        assert received_events[0][0] == "handler1"
        assert received_events[1][0] == "handler2"
        # Ambos handlers recibieron el mismo evento
        assert received_events[0][1] is event
        assert received_events[1][1] is event
