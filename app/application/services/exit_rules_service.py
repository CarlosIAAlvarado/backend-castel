from typing import List, Dict, Any, Optional
from datetime import date
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.domain.rules.exit_rule import ExitRule
from app.domain.rules.consecutive_fall_rule import ConsecutiveFallRule
from app.domain.rules.roi_threshold_rule import ROIThresholdRule
from app.domain.rules.combined_rule import CombinedRule


class ExitRulesService:
    """
    Servicio para evaluacion de reglas de salida de agentes.

    Usa Strategy Pattern para reglas configurables y extensibles.

    Reglas por defecto:
    - ConsecutiveFallRule: 3 dias consecutivos en caida
    - ROIThresholdRule: Stop Loss de -10% desde entrada
    - Operador: OR (si cualquier regla se cumple, el agente sale)

    Responsabilidades:
    - Evaluar si un agente debe salir de Casterly Rock usando reglas configurables
    - Marcar agentes como OUT (is_in_casterly = False)
    - Identificar motivo de salida

    Cumple con Open/Closed Principle (OCP):
    - Abierto para extension: Se pueden agregar nuevas reglas sin modificar este codigo
    - Cerrado para modificacion: No se modifica al agregar reglas
    """

    def __init__(
        self,
        state_repo: AgentStateRepository,
        assignment_repo: AssignmentRepository,
        exit_rules: Optional[List[ExitRule]] = None
    ):
        """
        Constructor con inyeccion de dependencias y reglas configurables.

        Args:
            state_repo: Repositorio de estados de agentes
            assignment_repo: Repositorio de asignaciones
            exit_rules: Lista de reglas personalizadas (opcional)
                       Si es None, usa reglas por defecto
        """
        self.state_repo = state_repo
        self.assignment_repo = assignment_repo

        if exit_rules is None:
            self.exit_rules = [
                ConsecutiveFallRule(min_fall_days=3),
                ROIThresholdRule(min_roi=-0.10)
            ]
            self.exit_rule = CombinedRule(self.exit_rules, operator="OR")
        else:
            self.exit_rule = CombinedRule(exit_rules, operator="OR")

    def evaluate_agent(
        self,
        agent_id: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        Evalua reglas de salida para un agente usando Strategy Pattern.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo

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

        should_exit = self.exit_rule.should_exit(agent_state)

        reasons = []
        if should_exit and isinstance(self.exit_rule, CombinedRule):
            reasons = self.exit_rule.get_triggered_reasons(agent_state)
        elif should_exit:
            reasons = [self.exit_rule.get_reason()]

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
        target_date: date
    ) -> Dict[str, Any]:
        """
        Evalua reglas de salida para todos los agentes activos usando Strategy Pattern.

        Args:
            target_date: Fecha objetivo

        Returns:
            Diccionario con resumen de evaluacion
        """
        states = self.state_repo.get_by_date(target_date)

        active_agents = [state for state in states if state.is_in_casterly]

        evaluations = []
        agents_to_exit = []

        for state in active_agents:
            should_exit = self.exit_rule.should_exit(state)

            reasons = []
            if should_exit and isinstance(self.exit_rule, CombinedRule):
                reasons = self.exit_rule.get_triggered_reasons(state)
            elif should_exit:
                reasons = [self.exit_rule.get_reason()]

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

        self.state_repo.update_state(
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
        target_date: date
    ) -> Dict[str, Any]:
        """
        Evalua y marca multiples agentes como OUT basado en reglas configurables.

        Args:
            target_date: Fecha objetivo

        Returns:
            Diccionario con resumen de agentes marcados como OUT
        """
        evaluation_result = self.evaluate_all_agents(target_date)

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
