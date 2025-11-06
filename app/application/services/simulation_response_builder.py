"""
Servicio para construir respuestas de simulación.

Este servicio aplica el principio Single Responsibility (SRP) al
separar la lógica de construcción de respuestas del orquestador principal.
"""

from typing import Dict, Any, List
from datetime import date
import logging

logger = logging.getLogger(__name__)


class SimulationResponseBuilder:
    """
    Servicio especializado en construcción de respuestas de simulación.

    Responsabilidad única: Transformar datos de simulación en respuestas HTTP.
    Cumple con Single Responsibility Principle (SRP).
    """

    @staticmethod
    def build_daily_response(
        target_date: date,
        top16: List[Dict[str, Any]],
        current_casterly_agents: List[str],
        classification_result: Dict[str, Any],
        evaluation_result: Dict[str, Any],
        rotations_executed: List[Dict[str, Any]],
        client_accounts_result: Any,
        window_days: int
    ) -> Dict[str, Any]:
        """
        Construye la respuesta para process_daily.

        Args:
            target_date: Fecha del día procesado
            top16: Lista de agentes del Top 16
            current_casterly_agents: Lista de IDs de agentes activos
            classification_result: Resultado de clasificación de estados
            evaluation_result: Resultado de evaluación de reglas de salida
            rotations_executed: Lista de rotaciones ejecutadas
            client_accounts_result: Resultado de sincronización de cuentas
            window_days: Ventana de días usada

        Returns:
            Diccionario con respuesta completa del día
        """
        # Preparar datos del Top 16 con ROI
        roi_field = f"roi_{window_days}d"
        top_16_with_data = [
            {
                "userId": agent["userId"],
                "roi_7d": agent.get(roi_field, 0.0),
                "total_pnl": agent.get("total_pnl", 0.0),
                "balance": agent.get("balance_current", 0.0),
                "total_trades_7d": agent.get("total_trades_7d", 0),
                "rank": agent.get("rank", idx + 1)
            }
            for idx, agent in enumerate(top16)
        ]

        result = {
            "success": True,
            "date": target_date.isoformat(),
            "phase": "daily_processing",
            "top_16_data": top_16_with_data,
            "active_agents": len(current_casterly_agents),
            "states_classified": classification_result["total_agents"],
            "growth_count": classification_result["growth_count"],
            "fall_count": classification_result["fall_count"],
            "agents_evaluated": evaluation_result["total_active_agents"],
            "agents_exited": len(evaluation_result["agents_to_exit"]),
            "rotations_executed": len(rotations_executed),
            "rotations_detail": rotations_executed,
            "current_casterly_agents": current_casterly_agents
        }

        # Agregar resultado de sincronización si existe
        if client_accounts_result:
            if isinstance(client_accounts_result, dict):
                result["client_accounts_sync"] = client_accounts_result
            else:
                result["client_accounts_sync"] = {
                    "success": True,
                    "cuentas_actualizadas": client_accounts_result.cuentas_actualizadas,
                    "cuentas_redistribuidas": client_accounts_result.cuentas_redistribuidas,
                    "rotaciones_procesadas": client_accounts_result.rotaciones_procesadas,
                    "snapshot_id": client_accounts_result.snapshot_id,
                    "balance_total_antes": client_accounts_result.balance_total_antes,
                    "balance_total_despues": client_accounts_result.balance_total_despues,
                    "roi_promedio_antes": client_accounts_result.roi_promedio_antes,
                    "roi_promedio_despues": client_accounts_result.roi_promedio_despues
                }

        return result

    @staticmethod
    def build_simulation_response(
        simulation_id: str,
        target_date: date,
        window_start: date,
        top16_agent_ids: List[str],
        window_days: int,
        cleaned_collections: List[Dict[str, Any]],
        all_results: List[Dict[str, Any]],
        total_rotations_detected: int,
        redistribution_result: Dict[str, Any],
        roi_update_result: Dict[str, Any],
        client_accounts_snapshot_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Construye la respuesta completa de una simulación.

        Args:
            simulation_id: ID de la simulación
            target_date: Fecha objetivo
            window_start: Fecha de inicio de ventana
            top16_agent_ids: IDs de agentes del Top 16
            window_days: Ventana de días
            cleaned_collections: Colecciones limpiadas
            all_results: Resultados de todos los días
            total_rotations_detected: Total de rotaciones
            redistribution_result: Resultado de redistribución
            roi_update_result: Resultado de actualización de ROI
            client_accounts_snapshot_info: Info del snapshot de cuentas

        Returns:
            Diccionario con respuesta completa de simulación
        """
        result = all_results[-1]["result"] if all_results else {}

        return {
            "success": True,
            "message": "Simulación histórica día por día completada exitosamente",
            "simulation_id": simulation_id,
            "cleaned_collections": cleaned_collections,
            "historical_processing": {
                "days_processed": len(all_results),
                "total_rotations_detected": total_rotations_detected,
                "daily_results": all_results
            },
            "redistribution": {
                "cuentas_reasignadas": redistribution_result.get("cuentas_reasignadas", 0) if redistribution_result else 0,
                "num_agentes_top16": redistribution_result.get("num_agentes_top16", 0) if redistribution_result else 0,
                "cuentas_por_agente": redistribution_result.get("cuentas_por_agente", 0) if redistribution_result else 0,
                "error": redistribution_result.get("error") if redistribution_result and "error" in redistribution_result else None
            },
            "roi_update": {
                "cuentas_actualizadas": roi_update_result.get("cuentas_actualizadas", 0) if roi_update_result else 0,
                "error": roi_update_result.get("error") if roi_update_result and "error" in roi_update_result else None
            },
            "client_accounts_snapshot": client_accounts_snapshot_info,
            "simulation_info": {
                "target_date": target_date.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": target_date.isoformat(),
                "days_in_window": len(all_results),
                "description": f"Simulación histórica día por día desde {window_start.isoformat()} hasta {target_date.isoformat()}"
            },
            "data": result
        }
