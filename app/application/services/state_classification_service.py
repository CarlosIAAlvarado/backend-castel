from typing import List, Dict, Any, Optional
from datetime import date, datetime
from app.domain.entities.agent_state import AgentState, StateType
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl
from app.infrastructure.repositories.movement_repository_impl import MovementRepositoryImpl
from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl
from app.application.services.kpi_calculation_service import KPICalculationService


class StateClassificationService:
    """
    Servicio para clasificacion de estado de agentes.

    Responsabilidades:
    - Calcular ROI diario por agente
    - Clasificar estado: GROWTH vs FALL
    - Mantener contador de dias consecutivos en caida
    - Detectar agentes que deben ser expulsados
    """

    def __init__(self):
        self.state_repo = AgentStateRepositoryImpl()
        self.movement_repo = MovementRepositoryImpl()
        self.balance_repo = BalanceRepositoryImpl()
        self.assignment_repo = AssignmentRepositoryImpl()

    def calculate_daily_roi(
        self,
        agent_id: str,
        target_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula el ROI diario de un agente.

        Formula: ROI_day = PnL_day / Balance_base

        Donde:
        - PnL_day: Ganancia o perdida neta total del agente en ese dia
        - Balance_base: Saldo total de las cuentas al cierre del dia anterior

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

        Returns:
            Diccionario con roi_day, pnl_day, balance_base o None si no hay datos
        """
        assignments = self.assignment_repo.get_active_by_agent(agent_id)

        if not assignments:
            return None

        account_ids = [assignment.account_id for assignment in assignments]

        movements = self.movement_repo.get_by_agent_and_date(agent_id, target_date)
        pnl_day = sum(movement.closed_pnl for movement in movements)

        balance_base = 0.0
        for account_id in account_ids:
            balance = self.balance_repo.get_by_account_and_date(account_id, target_date)
            if balance:
                balance_base += balance.balance

        if balance_base == 0:
            return None

        roi_day = pnl_day / balance_base

        return {
            "roi_day": roi_day,
            "pnl_day": pnl_day,
            "balance_base": balance_base
        }

    def classify_state(
        self,
        agent_id: str,
        target_date: date,
        previous_state: Optional[AgentState] = None
    ) -> AgentState:
        """
        Clasifica el estado de un agente en una fecha.

        Logica:
        - roi_day > 0 → GROWTH (resetea fall_days a 0)
        - roi_day < 0 → FALL (incrementa fall_days)

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo
            previous_state: Estado del dia anterior (para calcular fall_days)

        Returns:
            AgentState clasificado
        """
        roi_data = self.calculate_daily_roi(agent_id, target_date)

        if roi_data is None:
            raise ValueError(f"No se pudo calcular ROI para agente {agent_id} en fecha {target_date}")

        roi_day = roi_data["roi_day"]
        pnl_day = roi_data["pnl_day"]
        balance_base = roi_data["balance_base"]

        if roi_day > 0:
            state = StateType.GROWTH
            fall_days = 0
        else:
            state = StateType.FALL
            if previous_state and previous_state.state == StateType.FALL:
                fall_days = previous_state.fall_days + 1
            else:
                fall_days = 1

        entry_date = previous_state.entry_date if previous_state else target_date
        roi_since_entry = previous_state.roi_since_entry if previous_state else 0.0
        roi_since_entry += roi_day

        agent_state = AgentState(
            date=target_date,
            agent_id=agent_id,
            state=state,
            roi_day=roi_day,
            pnl_day=pnl_day,
            balance_base=balance_base,
            fall_days=fall_days,
            is_in_casterly=True,
            roi_since_entry=roi_since_entry,
            entry_date=entry_date
        )

        return agent_state

    def classify_all_agents(
        self,
        target_date: date,
        agent_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Clasifica el estado de todos los agentes activos en una fecha.

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de IDs de agentes a clasificar (opcional)

        Returns:
            Diccionario con resumen de clasificacion y lista de estados
        """
        if agent_ids is None:
            assignments = self.assignment_repo.get_by_date(target_date)
            agent_ids = list(set(assignment.agent_id for assignment in assignments))

        classified_states = []
        growth_count = 0
        fall_count = 0

        for agent_id in agent_ids:
            previous_state = self.state_repo.get_latest_by_agent(agent_id)

            try:
                agent_state = self.classify_state(agent_id, target_date, previous_state)
                classified_states.append(agent_state)

                if agent_state.state == StateType.GROWTH:
                    growth_count += 1
                else:
                    fall_count += 1

            except ValueError as e:
                print(f"Error clasificando agente {agent_id}: {str(e)}")
                continue

        saved_states = self.state_repo.create_batch(classified_states)

        return {
            "success": True,
            "date": target_date.isoformat(),
            "total_agents": len(saved_states),
            "growth_count": growth_count,
            "fall_count": fall_count,
            "states": [
                {
                    "agent_id": state.agent_id,
                    "state": state.state,
                    "roi_day": state.roi_day,
                    "fall_days": state.fall_days
                }
                for state in saved_states
            ]
        }

    def classify_agents_from_roi_data(
        self,
        target_date: date,
        agent_ids: List[str],
        agents_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Clasifica el estado de agentes usando datos de ROI precalculados.
        Version optimizada que evita recalcular ROI y consulta estados previos en batch.

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de IDs de agentes a clasificar
            agents_data: Datos de ROI ya calculados

        Returns:
            Diccionario con resumen de clasificacion
        """
        roi_map = {agent["agent_id"]: agent for agent in agents_data}

        previous_states_map = self.state_repo.get_latest_by_agents_batch(agent_ids)

        classified_states = []
        growth_count = 0
        fall_count = 0

        for agent_id in agent_ids:
            if agent_id not in roi_map:
                continue

            agent_data = roi_map[agent_id]
            roi_day = agent_data.get("roi_7d", 0.0)

            previous_state = previous_states_map.get(agent_id)

            if roi_day > 0:
                state = StateType.GROWTH
                fall_days = 0
            else:
                state = StateType.FALL
                if previous_state and previous_state.state == StateType.FALL:
                    fall_days = previous_state.fall_days + 1
                else:
                    fall_days = 1

            entry_date = previous_state.entry_date if previous_state else target_date
            roi_since_entry = previous_state.roi_since_entry if previous_state else 0.0
            roi_since_entry += roi_day

            try:
                kpis_7d = KPICalculationService.calculate_all_kpis(
                    agent_id=agent_id,
                    target_date=target_date,
                    lookback_days=7
                )
                roi_7d = kpis_7d.get("roi_period", 0.0)
                sharpe_ratio = kpis_7d.get("sharpe_ratio", 0.0)
                max_drawdown = kpis_7d.get("max_drawdown", 0.0)
                volatility = kpis_7d.get("volatility", 0.0)
            except Exception:
                roi_7d = agent_data.get("roi_7d", 0.0)
                sharpe_ratio = 0.0
                max_drawdown = 0.0
                volatility = 0.0

            try:
                kpis_30d = KPICalculationService.calculate_roi_30d(
                    agent_id=agent_id,
                    target_date=target_date
                )
                roi_30d = kpis_30d.get("roi_30d", 0.0)
            except Exception:
                roi_30d = 0.0

            agent_state = AgentState(
                date=target_date,
                agent_id=agent_id,
                state=state,
                roi_day=roi_day,
                pnl_day=agent_data.get("total_pnl", 0.0),
                balance_base=agent_data.get("balance_current", 0.0),
                fall_days=fall_days,
                is_in_casterly=True,
                roi_since_entry=roi_since_entry,
                entry_date=entry_date,
                roi_7d=roi_7d,
                roi_30d=roi_30d,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                volatility=volatility
            )

            classified_states.append(agent_state)

            if agent_state.state == StateType.GROWTH:
                growth_count += 1
            else:
                fall_count += 1

        saved_states = self.state_repo.create_batch(classified_states)

        return {
            "success": True,
            "date": target_date.isoformat(),
            "total_agents": len(saved_states),
            "growth_count": growth_count,
            "fall_count": fall_count
        }

    def get_agents_at_risk(
        self,
        target_date: date,
        fall_threshold: int = 3,
        stop_loss_threshold: float = -0.10
    ) -> List[Dict[str, Any]]:
        """
        Identifica agentes en riesgo de expulsion.

        Criterios:
        - fall_days >= fall_threshold (default: 3)
        - roi_since_entry <= stop_loss_threshold (default: -10%)

        Args:
            target_date: Fecha objetivo
            fall_threshold: Dias consecutivos en caida
            stop_loss_threshold: Umbral de stop loss

        Returns:
            Lista de agentes en riesgo con motivo
        """
        states = self.state_repo.get_by_date(target_date)

        agents_at_risk = []

        for state in states:
            if not state.is_in_casterly:
                continue

            reasons = []

            if state.fall_days >= fall_threshold:
                reasons.append(f"{state.fall_days} dias consecutivos en caida")

            if state.roi_since_entry and state.roi_since_entry <= stop_loss_threshold:
                reasons.append(f"Stop Loss alcanzado: {state.roi_since_entry:.2%}")

            if reasons:
                agents_at_risk.append({
                    "agent_id": state.agent_id,
                    "fall_days": state.fall_days,
                    "roi_since_entry": state.roi_since_entry,
                    "reasons": reasons
                })

        return agents_at_risk
