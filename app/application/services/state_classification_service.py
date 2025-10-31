from typing import List, Dict, Any, Optional
from datetime import date, datetime
import logging
from app.domain.entities.agent_state import AgentState, StateType
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.domain.repositories.movement_repository import MovementRepository
from app.domain.repositories.balance_repository import BalanceRepository
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.application.services.daily_roi_calculation_service import DailyROICalculationService
from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository

logger = logging.getLogger(__name__)


class StateClassificationService:
    """
    Servicio para clasificacion de estado de agentes.

    VERSION 2.0 - NUEVA LOGICA ROI
    Ahora usa DailyROICalculationService para obtener ROI_day desde cache temporal.

    Responsabilidades:
    - Obtener ROI diario desde daily_roi_calculation (nueva logica)
    - Clasificar estado: GROWTH vs FALL
    - Mantener contador de dias consecutivos en caida
    - Detectar agentes que deben ser expulsados
    """

    def __init__(
        self,
        state_repo: AgentStateRepository,
        movement_repo: MovementRepository,
        balance_repo: BalanceRepository,
        assignment_repo: AssignmentRepository,
        daily_roi_service: DailyROICalculationService,
        roi_7d_repo: ROI7DRepository
    ):
        """
        Constructor con inyeccion de dependencias.

        VERSION 2.2: Agregado ROI7DRepository

        VERSION 2.0: Agregado DailyROICalculationService

        Args:
            state_repo: Repositorio de estados de agentes
            movement_repo: Repositorio de movimientos
            balance_repo: Repositorio de balances
            assignment_repo: Repositorio de asignaciones
            daily_roi_service: Servicio de calculo de ROI diario (VERSION 2.0)
            roi_7d_repo: Repositorio de ROI 7D (VERSION 2.2)
        """
        self.state_repo = state_repo
        self.movement_repo = movement_repo
        self.balance_repo = balance_repo
        self.assignment_repo = assignment_repo
        self.daily_roi_service = daily_roi_service
        self.roi_7d_repo = roi_7d_repo

    async def calculate_daily_roi(
        self,
        userId: str,
        target_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene el ROI diario de un agente desde la coleccion temporal.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador.

        VERSION 2.0: NUEVA LOGICA
        Ahora busca en daily_roi_calculation en lugar de calcular manualmente.
        Si no existe en cache, lo calcula y guarda.

        Formula nueva: ROI_day = sum(closedPnl_i) / balance_base

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha objetivo

        Returns:
            Diccionario con roi_day, pnl_day, balance_base o None si no hay datos
        """
        target_date_str = target_date.isoformat()

        daily_roi_entity = await self.daily_roi_service.calculate_roi_for_day(
            userId, target_date
        )

        if not daily_roi_entity:
            logger.warning(
                f"No se pudo calcular ROI diario para userId {userId} en fecha {target_date_str}"
            )
            return None

        return {
            "roi_day": daily_roi_entity.roi_day,
            "pnl_day": daily_roi_entity.total_pnl_day,
            "balance_base": daily_roi_entity.balance_base
        }

    async def classify_state(
        self,
        userId: str,
        target_date: date,
        previous_state: Optional[AgentState] = None,
        roi_7d: Optional[float] = None,
        total_balance: Optional[float] = None
    ) -> AgentState:
        """
        Clasifica el estado de un agente en una fecha.

        CAMBIO VERSION 2.2: Agregados parametros opcionales roi_7d y total_balance

        CAMBIO VERSION 2.1: Ahora usa userId como identificador.

        VERSION 2.0: Convertido a async para usar nueva logica ROI

        Logica:
        - roi_day > 0 → GROWTH (resetea fall_days a 0)
        - roi_day < 0 → FALL (incrementa fall_days)

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha objetivo
            previous_state: Estado del dia anterior (para calcular fall_days)
            roi_7d: ROI de 7 dias (opcional, se obtiene de agent_roi_7d)
            total_balance: Balance total del agente (opcional, se calcula de assignments)

        Returns:
            AgentState clasificado
        """
        roi_data = await self.calculate_daily_roi(userId, target_date)

        if roi_data is None:
            raise ValueError(f"No se pudo calcular ROI para userId {userId} en fecha {target_date}")

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

        # Calcular balance total si no se proporciona
        if total_balance is None:
            active_assignments = self.assignment_repo.get_by_agent_and_date(userId, target_date)
            total_balance = sum(assignment.balance for assignment in active_assignments)

        agent_state = AgentState(
            date=target_date,
            agent_id=userId,
            state=state,
            roi_day=roi_day,
            pnl_day=pnl_day,
            balance_base=balance_base,
            balance=total_balance,
            fall_days=fall_days,
            is_in_casterly=True,
            roi_since_entry=roi_since_entry,
            entry_date=entry_date,
            roi_7d=roi_7d
        )

        return agent_state

    async def classify_all_agents(
        self,
        target_date: date,
        agent_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Clasifica el estado de todos los agentes activos en una fecha.

        VERSION 2.2: Ahora obtiene ROI_7D y balance total para cada agente

        VERSION 2.0: Convertido a async para usar nueva logica ROI

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

        # Obtener todos los ROI_7D para la fecha objetivo
        target_date_str = target_date.isoformat()

        for agent_id in agent_ids:
            previous_state = self.state_repo.get_latest_by_agent(agent_id)

            try:
                # Obtener ROI_7D del agente
                roi_7d_entity = await self.roi_7d_repo.find_by_agent_and_date(agent_id, target_date_str)
                roi_7d = roi_7d_entity.roi_7d_total if roi_7d_entity else None

                # Obtener balance total del agente
                active_assignments = self.assignment_repo.get_by_agent_and_date(agent_id, target_date)
                total_balance = sum(assignment.balance for assignment in active_assignments)

                agent_state = await self.classify_state(
                    agent_id,
                    target_date,
                    previous_state,
                    roi_7d=roi_7d,
                    total_balance=total_balance
                )
                classified_states.append(agent_state)

                if agent_state.state == StateType.GROWTH:
                    growth_count += 1
                else:
                    fall_count += 1

            except ValueError as e:
                logger.error(f"Error clasificando agente {agent_id}: {str(e)}")
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
                    "fall_days": state.fall_days,
                    "balance": state.balance,
                    "roi_7d": state.roi_7d
                }
                for state in saved_states
            ]
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
