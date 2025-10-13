from typing import List, Dict, Any
from datetime import date, datetime, timedelta
from app.application.services.selection_service import SelectionService
from app.application.services.assignment_service import AssignmentService
from app.application.services.state_classification_service import StateClassificationService
from app.application.services.exit_rules_service import ExitRulesService
from app.application.services.replacement_service import ReplacementService
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl


class DailyOrchestratorService:
    """
    Servicio orquestador para la simulacion diaria completa.

    Coordina todos los servicios para ejecutar el flujo diario:
    1. Calcular KPIs (ROI, ranking)
    2. Clasificar estados (GROWTH/FALL)
    3. Evaluar reglas de salida
    4. Ejecutar rotaciones si es necesario
    5. Actualizar asignaciones

    Periodo: 01-Sep-2025 a 07-Oct-2025
    """

    def __init__(self):
        self.selection_service = SelectionService()
        self.assignment_service = AssignmentService()
        self.state_service = StateClassificationService()
        self.exit_rules_service = ExitRulesService()
        self.replacement_service = ReplacementService()
        self.state_repo = AgentStateRepositoryImpl()

    def process_day_one(self, target_date: date) -> Dict[str, Any]:
        """
        Procesa el dia 1 (01-Sep-2025): Asignacion inicial.

        Pasos:
        1. Seleccionar Top 16 por ROI_7D
        2. Asignar cuentas aleatoriamente
        3. Guardar Top 16 en base de datos
        4. Clasificar estados iniciales

        Args:
            target_date: Fecha del dia 1 (debe ser 01-Sep-2025)

        Returns:
            Diccionario con resultado del dia 1
        """
        top16, top16_all = self.selection_service.select_top_16(target_date)

        casterly_agent_ids = [agent["agent_id"] for agent in top16]

        top16_saved = self.selection_service.save_top16_to_database(target_date, top16, casterly_agent_ids)

        assignment_result = self.assignment_service.create_initial_assignments(
            target_date,
            casterly_agent_ids
        )

        classification_result = self.state_service.classify_all_agents(
            target_date,
            casterly_agent_ids
        )

        return {
            "success": True,
            "date": target_date.isoformat(),
            "phase": "day_one_initialization",
            "top_16_agents": casterly_agent_ids,
            "total_accounts_assigned": assignment_result["total_assignments"],
            "states_classified": classification_result["total_agents"],
            "growth_count": classification_result["growth_count"],
            "fall_count": classification_result["fall_count"]
        }

    def process_daily(self, target_date: date) -> Dict[str, Any]:
        """
        Procesa un dia normal de simulacion (02-Sep en adelante).

        Pasos:
        1. Calcular ROI diario y clasificar estados
        2. Guardar Top 16 del dia
        3. Evaluar reglas de salida
        4. Ejecutar rotaciones si es necesario
        5. Actualizar lista de Casterly activos

        Args:
            target_date: Fecha del dia a procesar

        Returns:
            Diccionario con resultado del dia
        """
        states = self.state_repo.get_by_date(target_date - timedelta(days=1))
        current_casterly_agents = list(set([
            state.agent_id for state in states if state.is_in_casterly
        ]))

        if not current_casterly_agents:
            return {
                "success": False,
                "message": f"No hay agentes activos en Casterly para la fecha {target_date}"
            }

        previous_top16 = self.selection_service.get_top16_by_date(target_date - timedelta(days=1))
        if previous_top16:
            top30_candidates = [t.agent_id for t in previous_top16[:30]] if len(previous_top16) >= 30 else [t.agent_id for t in previous_top16]
        else:
            top30_candidates = []

        relevant_agents = list(set(current_casterly_agents + top30_candidates))

        agents_data = self.selection_service.calculate_all_agents_roi_7d(
            target_date,
            agent_ids=relevant_agents
        )

        ranked_agents = self.selection_service.rank_agents_by_roi_7d(agents_data)
        top16 = ranked_agents[:16]

        top16_saved = self.selection_service.save_top16_to_database(target_date, top16, current_casterly_agents)

        classification_result = self.state_service.classify_all_agents(
            target_date,
            current_casterly_agents
        )

        evaluation_result = self.exit_rules_service.evaluate_all_agents(
            target_date,
            fall_threshold=3,
            stop_loss_threshold=-0.10
        )

        agents_to_exit = evaluation_result["agents_to_exit"]
        rotations_executed = []
        new_agents_to_classify = []

        for agent_eval in agents_to_exit:
            agent_out = agent_eval["agent_id"]
            reasons = agent_eval["reasons"]
            reason_str = "; ".join(reasons)

            mark_result = self.exit_rules_service.mark_agent_out(
                agent_out,
                target_date,
                reason_str
            )

            if mark_result["success"]:
                replacement_agent = self.replacement_service.find_replacement_agent(
                    target_date,
                    current_casterly_agents
                )

                if replacement_agent:
                    agent_in = replacement_agent["agent_id"]

                    transfer_result = self.replacement_service.transfer_accounts(
                        agent_out,
                        agent_in,
                        target_date
                    )

                    if not transfer_result.get("success"):
                        continue

                    state_out = self.state_repo.get_by_agent_and_date(agent_out, target_date)
                    roi_7d_out = state_out.roi_day if state_out else 0.0
                    roi_total_out = state_out.roi_since_entry if state_out else 0.0

                    rotation_log = self.replacement_service.register_rotation(
                        date=target_date,
                        agent_out=agent_out,
                        agent_in=agent_in,
                        reason=reason_str,
                        roi_7d_out=roi_7d_out,
                        roi_total_out=roi_total_out,
                        roi_7d_in=replacement_agent.get("roi_7d", 0.0),
                        n_accounts=transfer_result["n_accounts_transferred"],
                        total_aum=transfer_result["total_aum_transferred"]
                    )

                    replacement_result = {
                        "success": True,
                        "date": target_date.isoformat(),
                        "agent_out": agent_out,
                        "agent_in": agent_in,
                        "reason": reason_str,
                        "n_accounts_transferred": transfer_result["n_accounts_transferred"],
                        "total_aum_transferred": transfer_result["total_aum_transferred"],
                        "agent_out_roi_7d": roi_7d_out,
                        "agent_out_roi_total": roi_total_out,
                        "agent_in_roi_7d": replacement_agent.get("roi_7d", 0.0),
                        "rotation_log_id": rotation_log.id
                    }

                    rotations_executed.append(replacement_result)
                    if agent_out in current_casterly_agents:
                        current_casterly_agents.remove(agent_out)
                    current_casterly_agents.append(agent_in)
                    new_agents_to_classify.append(agent_in)

        if new_agents_to_classify:
            new_agents_classification = self.state_service.classify_all_agents(
                target_date,
                new_agents_to_classify
            )

        return {
            "success": True,
            "date": target_date.isoformat(),
            "phase": "daily_processing",
            "active_agents": len(current_casterly_agents),
            "states_classified": classification_result["total_agents"],
            "growth_count": classification_result["growth_count"],
            "fall_count": classification_result["fall_count"],
            "agents_evaluated": evaluation_result["total_active_agents"],
            "agents_exited": len(agents_to_exit),
            "rotations_executed": len(rotations_executed),
            "rotations_detail": rotations_executed,
            "current_casterly_agents": current_casterly_agents
        }

    def run_simulation(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Ejecuta la simulacion completa para el periodo especificado.

        Proceso:
        1. Dia 1: Asignacion inicial
        2. Dias 2-N: Procesamiento diario con rotaciones

        Args:
            start_date: Fecha de inicio (debe ser 01-Sep-2025)
            end_date: Fecha de fin (debe ser 07-Oct-2025)

        Returns:
            Diccionario con resumen completo de la simulacion
        """
        if start_date > end_date:
            return {
                "success": False,
                "message": "start_date debe ser menor o igual que end_date"
            }

        daily_results = []
        current_date = start_date

        day_one_result = self.process_day_one(current_date)
        daily_results.append(day_one_result)

        current_date += timedelta(days=1)

        while current_date <= end_date:
            daily_result = self.process_daily(current_date)
            daily_results.append(daily_result)
            current_date += timedelta(days=1)

        total_rotations = sum(
            result.get("rotations_executed", 0)
            for result in daily_results
        )

        return {
            "success": True,
            "simulation_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": len(daily_results)
            },
            "summary": {
                "total_rotations": total_rotations,
                "final_casterly_agents": daily_results[-1].get("current_casterly_agents", [])
            },
            "daily_results": daily_results
        }

    def get_simulation_summary(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Obtiene un resumen de la simulacion sin detalles diarios.

        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin

        Returns:
            Resumen consolidado
        """
        rotation_logs = self.replacement_service.rotation_log_repo.get_by_date_range(
            start_date,
            end_date
        )

        states_final = self.state_repo.get_by_date(end_date)
        active_agents = [state.agent_id for state in states_final if state.is_in_casterly]

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_rotations": len(rotation_logs),
            "final_active_agents": len(active_agents),
            "active_agents_list": active_agents
        }
