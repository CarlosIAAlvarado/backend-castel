from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.infrastructure.di.providers import SimulationRepositoryDep, DatabaseDep
from app.domain.entities.simulation import Simulation
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["Simulations Comparison"])


class UpdateSimulationRequest(BaseModel):
    """Request para actualizar una simulacion."""
    name: str = Field(..., min_length=1, max_length=100, description="Nombre de la simulacion")
    description: Optional[str] = Field(None, max_length=500, description="Descripcion opcional")


class CompareSimulationsRequest(BaseModel):
    """Request para comparar simulaciones."""
    simulation_ids: List[str] = Field(..., min_items=2, max_items=5, description="Lista de IDs de simulaciones a comparar (2-5)")


@router.get("")
async def get_all_simulations(
    limit: int = Query(50, ge=1, le=100, description="Numero maximo de simulaciones a retornar"),
    simulation_repo: SimulationRepositoryDep = None
) -> Dict[str, Any]:
    """
    Obtiene todas las simulaciones guardadas ordenadas por fecha descendente.

    Args:
        limit: Numero maximo de simulaciones (default: 50, max: 100)
        simulation_repo: Repositorio de simulaciones inyectado

    Returns:
        Lista de simulaciones con metadata
    """
    try:
        simulations = simulation_repo.get_all(limit=limit)
        total_count = simulation_repo.count()

        return {
            "success": True,
            "total_count": total_count,
            "returned_count": len(simulations),
            "limit": limit,
            "simulations": [sim.model_dump(by_alias=True, exclude_none=True) for sim in simulations]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener simulaciones: {str(e)}"
        )


@router.get("/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    simulation_repo: SimulationRepositoryDep = None
) -> Dict[str, Any]:
    """
    Obtiene una simulacion especifica por su ID.

    Args:
        simulation_id: UUID de la simulacion
        simulation_repo: Repositorio de simulaciones inyectado

    Returns:
        Datos completos de la simulacion

    Raises:
        404: Si la simulacion no existe
    """
    try:
        simulation = simulation_repo.get_by_id(simulation_id)

        if not simulation:
            raise HTTPException(
                status_code=404,
                detail=f"Simulacion con ID {simulation_id} no encontrada"
            )

        return {
            "success": True,
            "simulation": simulation.model_dump(by_alias=True, exclude_none=True)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener simulacion: {str(e)}"
        )


@router.patch("/{simulation_id}")
async def update_simulation(
    simulation_id: str,
    request: UpdateSimulationRequest,
    simulation_repo: SimulationRepositoryDep = None
) -> Dict[str, Any]:
    """
    Actualiza el nombre y descripcion de una simulacion.

    Args:
        simulation_id: UUID de la simulacion
        request: Datos a actualizar (nombre y descripcion)
        simulation_repo: Repositorio de simulaciones inyectado

    Returns:
        Confirmacion de actualizacion

    Raises:
        404: Si la simulacion no existe
    """
    try:
        # Verificar que existe
        existing = simulation_repo.get_by_id(simulation_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Simulacion con ID {simulation_id} no encontrada"
            )

        # Actualizar
        updated = simulation_repo.update(
            simulation_id=simulation_id,
            name=request.name,
            description=request.description
        )

        if not updated:
            raise HTTPException(
                status_code=500,
                detail="No se pudo actualizar la simulacion"
            )

        return {
            "success": True,
            "message": "Simulacion actualizada exitosamente",
            "simulation_id": simulation_id,
            "name": request.name,
            "description": request.description
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar simulacion: {str(e)}"
        )


@router.delete("/{simulation_id}")
async def delete_simulation(
    simulation_id: str,
    simulation_repo: SimulationRepositoryDep = None,
    db: DatabaseDep = None
) -> Dict[str, Any]:
    """
    Elimina una simulacion y todos sus datos relacionados.

    Elimina datos de las siguientes colecciones:
    - simulations
    - historial_asignaciones_clientes
    - distribucion_cuentas_snapshot
    - rebalanceo_log

    Args:
        simulation_id: UUID de la simulacion
        simulation_repo: Repositorio de simulaciones inyectado
        db: Base de datos inyectada

    Returns:
        Confirmacion de eliminacion con conteo de registros eliminados

    Raises:
        404: Si la simulacion no existe
        500: Si hay error al eliminar
    """
    try:
        logger.info(f"Iniciando eliminacion de simulacion {simulation_id} y datos relacionados")

        # Verificar que existe
        existing = simulation_repo.get_by_id(simulation_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Simulacion con ID {simulation_id} no encontrada"
            )

        # Contador de documentos eliminados
        deleted_counts = {}

        # 1. Eliminar de historial_asignaciones_clientes
        result_historial = db.historial_asignaciones_clientes.delete_many(
            {"simulation_id": simulation_id}
        )
        deleted_counts["historial_asignaciones"] = result_historial.deleted_count
        logger.info(f"Eliminados {result_historial.deleted_count} registros de historial_asignaciones_clientes")

        # 2. Eliminar de distribucion_cuentas_snapshot
        result_snapshot = db.distribucion_cuentas_snapshot.delete_many(
            {"simulation_id": simulation_id}
        )
        deleted_counts["snapshots"] = result_snapshot.deleted_count
        logger.info(f"Eliminados {result_snapshot.deleted_count} registros de distribucion_cuentas_snapshot")

        # 3. Eliminar de rebalanceo_log
        result_rebalanceo = db.rebalanceo_log.delete_many(
            {"simulation_id": simulation_id}
        )
        deleted_counts["rebalanceo_logs"] = result_rebalanceo.deleted_count
        logger.info(f"Eliminados {result_rebalanceo.deleted_count} registros de rebalanceo_log")

        # 4. Eliminar la simulacion principal
        deleted = simulation_repo.delete(simulation_id)

        if not deleted:
            raise HTTPException(
                status_code=500,
                detail="No se pudo eliminar la simulacion"
            )

        logger.info(f"Simulacion {simulation_id} eliminada exitosamente con todos sus datos relacionados")

        return {
            "success": True,
            "message": "Simulacion y datos relacionados eliminados exitosamente",
            "simulation_id": simulation_id,
            "deleted_records": deleted_counts
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar simulacion {simulation_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar simulacion: {str(e)}"
        )


@router.post("/compare")
async def compare_simulations(
    request: CompareSimulationsRequest,
    simulation_repo: SimulationRepositoryDep = None
) -> Dict[str, Any]:
    """
    Compara 2 a 5 simulaciones lado a lado.

    Args:
        request: Lista de IDs de simulaciones a comparar (2-5)
        simulation_repo: Repositorio de simulaciones inyectado

    Returns:
        Datos comparativos estructurados

    Raises:
        400: Si el numero de IDs es invalido
        404: Si alguna simulacion no existe
    """
    try:
        # Validar cantidad
        num_simulations = len(request.simulation_ids)
        if num_simulations < 2:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar al menos 2 simulaciones para comparar"
            )
        if num_simulations > 5:
            raise HTTPException(
                status_code=400,
                detail="No se pueden comparar mas de 5 simulaciones a la vez"
            )

        # Obtener simulaciones
        simulations = simulation_repo.get_by_ids(request.simulation_ids)

        # Verificar que todas existen
        if len(simulations) != num_simulations:
            found_ids = {sim.simulation_id for sim in simulations}
            missing_ids = set(request.simulation_ids) - found_ids
            raise HTTPException(
                status_code=404,
                detail=f"Simulaciones no encontradas: {', '.join(missing_ids)}"
            )

        # Estructurar comparacion
        comparison = {
            "success": True,
            "total_simulations": len(simulations),
            "simulations_metadata": [
                {
                    "simulation_id": sim.simulation_id,
                    "name": sim.name,
                    "description": sim.description,
                    "created_at": sim.created_at.isoformat() if sim.created_at else None,
                    "config": sim.config.model_dump()
                }
                for sim in simulations
            ],
            "kpis_comparison": {
                "headers": ["Metrica"] + [sim.name for sim in simulations],
                "rows": _build_kpis_comparison_rows(simulations)
            },
            "top16_comparison": {
                "common_agents": _get_common_agents(simulations),
                "partially_common_agents": _get_partially_common_agents(simulations),
                "unique_agents_per_sim": _get_unique_agents_per_sim(simulations),
                "agent_combinations": _get_agent_combinations(simulations)
            },
            "rotations_comparison": {
                "total_rotations": [sim.rotations_summary.total_rotations for sim in simulations],
                "rotations_by_reason": [sim.rotations_summary.rotations_by_reason for sim in simulations]
            },
            "daily_metrics": [
                {
                    "simulation_id": sim.simulation_id,
                    "name": sim.name,
                    "metrics": [metric.model_dump() for metric in sim.daily_metrics]
                }
                for sim in simulations
            ]
        }

        return comparison

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al comparar simulaciones: {str(e)}"
        )


def _build_kpis_comparison_rows(simulations: List[Simulation]) -> List[List[Any]]:
    """
    Construye las filas de comparacion de KPIs.
    """
    kpi_fields = [
        ("ROI Total (%)", "total_roi", True),
        ("ROI Promedio (%)", "avg_roi", True),
        ("Volatilidad (%)", "volatility", True),
        ("Max Drawdown (%)", "max_drawdown", True),
        ("Win Rate (%)", "win_rate", True),
        ("Agentes Activos", "active_agents_count", False),
        ("Total Agentes Periodo", "unique_agents_in_period", False),
        ("Sharpe Ratio", "sharpe_ratio", False)
    ]

    rows = []
    for label, field, is_percentage in kpi_fields:
        row = [label]
        for sim in simulations:
            value = getattr(sim.kpis, field)
            if value is None:
                row.append("N/A")
            elif is_percentage:
                row.append(f"{value * 100:.2f}%")
            else:
                row.append(f"{value:.2f}" if isinstance(value, float) else str(value))
        rows.append(row)

    return rows


def _get_common_agents(simulations: List[Simulation]) -> List[str]:
    """
    Obtiene los agentes que aparecen en el Top 16 de todas las simulaciones.
    """
    if not simulations:
        return []

    # Obtener conjuntos de agent_ids de cada simulacion
    agent_sets = [
        {agent.agent_id for agent in sim.top_16_final}
        for sim in simulations
    ]

    # Interseccion de todos los conjuntos
    common = set.intersection(*agent_sets) if agent_sets else set()

    return sorted(list(common))


def _get_partially_common_agents(simulations: List[Simulation]) -> List[str]:
    """
    Obtiene los agentes que aparecen en 2 o mas simulaciones, pero no en todas.
    """
    if len(simulations) < 2:
        return []

    # Contar en cuantas simulaciones aparece cada agente
    agent_count = {}
    for sim in simulations:
        for agent in sim.top_16_final:
            agent_count[agent.agent_id] = agent_count.get(agent.agent_id, 0) + 1

    # Obtener agentes comunes a todas (para excluirlos)
    common_to_all = _get_common_agents(simulations)

    # Filtrar agentes que aparecen en 2+ simulaciones pero no en todas
    partially_common = [
        agent_id for agent_id, count in agent_count.items()
        if count >= 2 and agent_id not in common_to_all
    ]

    return sorted(partially_common)


def _get_unique_agents_per_sim(simulations: List[Simulation]) -> Dict[str, List[str]]:
    """
    Obtiene TODOS los agentes del Top 16 de cada simulacion.
    """
    result = {}

    for sim in simulations:
        # Devolver TODOS los agentes del Top 16, no solo los unicos
        all_agents = [agent.agent_id for agent in sim.top_16_final]
        result[sim.simulation_id] = sorted(all_agents)

    return result


def _get_agent_combinations(simulations: List[Simulation]) -> Dict[str, str]:
    """
    Mapea cada agente a un identificador de combinacion (ej: "0,2,4" para sims 0, 2 y 4).
    Este identificador se usa para asignar colores unicos por combinacion.
    """
    agent_sim_map = {}

    # Para cada agente, registrar en que simulaciones aparece
    for idx, sim in enumerate(simulations):
        for agent in sim.top_16_final:
            if agent.agent_id not in agent_sim_map:
                agent_sim_map[agent.agent_id] = []
            agent_sim_map[agent.agent_id].append(idx)

    # Convertir a string "0,1,2" para usar como clave de color
    result = {}
    for agent_id, sim_indices in agent_sim_map.items():
        result[agent_id] = ",".join(map(str, sorted(sim_indices)))

    return result
