from typing import List, Dict, Any, Optional
from datetime import date
from app.domain.entities.agent_state import AgentState
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl


class ExitRulesService:
    """
    Servicio para evaluacion de reglas de salida de agentes.

    Reglas implementadas:
    - Regla 1: 3 dias consecutivos en caida
    - Regla 2: Stop Loss de -10% desde entrada

    Responsabilidades:
    - Evaluar si un agente debe salir de Casterly Rock
    - Marcar agentes como OUT (is_in_casterly = False)
    - Identificar motivo de salida
    """

    def __init__(self):
        self.state_repo = AgentStateRepositoryImpl()
        self.assignment_repo = AssignmentRepositoryImpl()

    def evaluate_rule_1(self, agent_state: AgentState, threshold: int = 3) -> tuple[bool, Optional[str]]:
        """
        Evalua Regla 1: 3 dias consecutivos en caida.

        Args:
            agent_state: Estado actual del agente
            threshold: Numero minimo de dias consecutivos en caida (default: 3)

        Returns:
            Tupla (debe_salir, motivo)
        """
        if agent_state.fall_days >= threshold:
            return (True, f"{agent_state.fall_days} dias consecutivos en caida (>= {threshold})")
        return (False, None)

    def evaluate_rule_2(self, agent_state: AgentState, threshold: float = -0.10) -> tuple[bool, Optional[str]]:
        """
        Evalua Regla 2: Stop Loss de -10% desde entrada.

        Args:
            agent_state: Estado actual del agente
            threshold: Umbral de stop loss (default: -0.10 = -10%)

        Returns:
            Tupla (debe_salir, motivo)
        """
        if agent_state.roi_since_entry is not None and agent_state.roi_since_entry <= threshold:
            return (True, f"Stop Loss alcanzado: {agent_state.roi_since_entry:.2%} (<= {threshold:.2%})")
        return (False, None)

    def evaluate_agent(
        self,
        agent_id: str,
        target_date: date,
        fall_threshold: int = 3,
        stop_loss_threshold: float = -0.10
    ) -> Dict[str, Any]:
        """
        Evalua todas las reglas de salida para un agente.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo
            fall_threshold: Umbral de dias consecutivos en caida
            stop_loss_threshold: Umbral de stop loss

        Returns:
            Diccionario con resultado de evaluacion
        """
        agent_state = self.state_repo.get_by_agent_and_date(agent_id, target_date)

        if not agent_state:
            return {
                "agent_id": agent_id,
                "should_exit": False,
                "reason": "No se encontro estado para esta fecha"
            }

        if not agent_state.is_in_casterly:
            return {
                "agent_id": agent_id,
                "should_exit": False,
                "reason": "Agente ya esta fuera de Casterly Rock"
            }

        should_exit_rule1, reason_rule1 = self.evaluate_rule_1(agent_state, fall_threshold)
        should_exit_rule2, reason_rule2 = self.evaluate_rule_2(agent_state, stop_loss_threshold)

        should_exit = should_exit_rule1 or should_exit_rule2
        reasons = []
        if reason_rule1:
            reasons.append(reason_rule1)
        if reason_rule2:
            reasons.append(reason_rule2)

        return {
            "agent_id": agent_id,
            "should_exit": should_exit,
            "reasons": reasons,
            "state": agent_state.state.value,
            "fall_days": agent_state.fall_days,
            "roi_since_entry": agent_state.roi_since_entry,
            "roi_day": agent_state.roi_day
        }

    def evaluate_all_agents(
        self,
        target_date: date,
        fall_threshold: int = 3,
        stop_loss_threshold: float = -0.10
    ) -> Dict[str, Any]:
        """
        Evalua reglas de salida para todos los agentes activos.
        Version optimizada que evita consultas redundantes.

        Args:
            target_date: Fecha objetivo
            fall_threshold: Umbral de dias consecutivos en caida
            stop_loss_threshold: Umbral de stop loss

        Returns:
            Diccionario con resumen de evaluacion
        """
        states = self.state_repo.get_by_date(target_date)

        active_agents = [state for state in states if state.is_in_casterly]

        evaluations = []
        agents_to_exit = []

        for state in active_agents:
            should_exit_rule1, reason_rule1 = self.evaluate_rule_1(state, fall_threshold)
            should_exit_rule2, reason_rule2 = self.evaluate_rule_2(state, stop_loss_threshold)

            should_exit = should_exit_rule1 or should_exit_rule2
            reasons = []
            if reason_rule1:
                reasons.append(reason_rule1)
            if reason_rule2:
                reasons.append(reason_rule2)

            evaluation = {
                "agent_id": state.agent_id,
                "should_exit": should_exit,
                "reasons": reasons,
                "state": state.state.value,
                "fall_days": state.fall_days,
                "roi_since_entry": state.roi_since_entry,
                "roi_day": state.roi_day
            }

            evaluations.append(evaluation)

            if should_exit:
                agents_to_exit.append(evaluation)

        return {
            "success": True,
            "date": target_date.isoformat(),
            "total_active_agents": len(active_agents),
            "total_agents_to_exit": len(agents_to_exit),
            "agents_to_exit": agents_to_exit,
            "all_evaluations": evaluations
        }

    def mark_agent_out(
        self,
        agent_id: str,
        target_date: date,
        reason: str
    ) -> Dict[str, Any]:
        """
        Marca un agente como OUT (fuera de Casterly Rock).

        Actualiza el estado del agente para marcarlo como inactivo.

        Args:
            agent_id: ID del agente
            target_date: Fecha de salida
            reason: Motivo de salida

        Returns:
            Diccionario con resultado de la operacion
        """
        agent_state = self.state_repo.get_by_agent_and_date(agent_id, target_date)

        if not agent_state:
            return {
                "success": False,
                "message": f"No se encontro estado para agente {agent_id} en fecha {target_date}"
            }

        if not agent_state.is_in_casterly:
            return {
                "success": False,
                "message": f"Agente {agent_id} ya esta marcado como OUT"
            }

        assignments = self.assignment_repo.get_active_by_agent(agent_id)
        n_accounts = len(assignments)

        updated_state = self.state_repo.update_state(
            agent_id,
            target_date,
            {"is_in_casterly": False}
        )

        return {
            "success": True,
            "agent_id": agent_id,
            "date": target_date.isoformat(),
            "reason": reason,
            "n_accounts": n_accounts,
            "previous_state": agent_state.state.value,
            "fall_days": agent_state.fall_days,
            "roi_since_entry": agent_state.roi_since_entry
        }

    def mark_multiple_agents_out(
        self,
        target_date: date,
        fall_threshold: int = 3,
        stop_loss_threshold: float = -0.10
    ) -> Dict[str, Any]:
        """
        Evalua y marca multiples agentes como OUT basado en reglas.

        Args:
            target_date: Fecha objetivo
            fall_threshold: Umbral de dias consecutivos en caida
            stop_loss_threshold: Umbral de stop loss

        Returns:
            Diccionario con resumen de agentes marcados como OUT
        """
        evaluation_result = self.evaluate_all_agents(
            target_date,
            fall_threshold,
            stop_loss_threshold
        )

        agents_to_exit = evaluation_result["agents_to_exit"]

        marked_out = []

        for agent_eval in agents_to_exit:
            agent_id = agent_eval["agent_id"]
            reasons = agent_eval["reasons"]
            reason_str = "; ".join(reasons)

            result = self.mark_agent_out(agent_id, target_date, reason_str)

            if result["success"]:
                marked_out.append(result)

        return {
            "success": True,
            "date": target_date.isoformat(),
            "total_evaluated": evaluation_result["total_active_agents"],
            "total_marked_out": len(marked_out),
            "marked_out": marked_out
        }
