from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from datetime import date, timedelta, datetime
from typing import Dict, Any, List, Optional
import uuid
import logging
import asyncio
import threading
from app.infrastructure.di.providers import (
    DailyOrchestratorServiceDep,
    SimulationRepositoryDep,
    ClientAccountsServiceDep,
    SelectionServiceDep,
    RotationLogRepositoryDep,
    SimulationStatusRepositoryDep
)
from app.config.database import database_manager
from app.domain.entities.simulation import (
    Simulation,
    SimulationConfig,
    SimulationKPIs,
    TopAgentSummary,
    RotationsSummary,
    DailyMetric
)
from app.domain.entities.simulation_status import SimulationStatus
from app.domain.entities.rotation_log import RotationLog, RotationReason
from app.domain.entities.top16_day import Top16Day
from app.utils.collection_names import get_roi_collection_name, get_top16_collection_name
from app.infrastructure.config.console_logger import ConsoleLogger as log

logger = logging.getLogger("trading_simulation.simulation_routes")

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


class SimulationRequest(BaseModel):
    start_date: date = Field(..., description="Fecha inicial de la simulacion (YYYY-MM-DD)")
    end_date: date = Field(..., description="Fecha final de la simulacion (YYYY-MM-DD)")
    window_days: int = Field(7, description="Hipótesis de frecuencia de rebalanceo (3, 5, 7, 10, 15, 30)")
    update_client_accounts: bool = Field(False, description="Si True, sincroniza cuentas de clientes durante la simulacion")
    simulation_id: Optional[str] = Field(None, description="ID de la simulacion (se genera automaticamente si no se proporciona)")
    simulation_name: Optional[str] = Field(None, description="Nombre descriptivo de la simulacion")
    dry_run: bool = Field(False, description="Si True, simula sin guardar cambios en client accounts")

    @validator('end_date')
    def validate_date_range(cls, end_date, values):
        """Valida que el rango sea de minimo 3 dias (cambiado temporalmente para testing)."""
        if 'start_date' not in values:
            raise ValueError("start_date es requerido")

        start = values['start_date']
        diff_days = (end_date - start).days + 1

        if diff_days < 3:
            raise ValueError(
                f"El rango debe ser de minimo 3 dias. "
                f"Rango actual: {diff_days} dias"
            )

        if end_date < start:
            raise ValueError("end_date debe ser posterior a start_date")

        return end_date

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-09-01",
                "end_date": "2025-10-01",
                "update_client_accounts": True,
                "simulation_id": "sim_30d_2025-09-01_to_2025-10-01",
                "simulation_name": "Simulacion Septiembre 2025",
                "dry_run": False
            }
        }


@router.get("/last-config")
async def get_last_simulation_config() -> Dict[str, Any]:
    """
    Obtiene la configuración de la última simulación ejecutada.

    Returns:
        Dict con window_days, target_date, window_start de la última simulación
    """
    try:
        db = database_manager.get_database()
        system_config_col = db["system_config"]

        config = system_config_col.find_one({"config_key": "last_simulation"})

        if not config:
            # Si no hay configuración guardada, usar valores por defecto
            return {
                "success": True,
                "window_days": 7,
                "target_date": None,
                "window_start": None,
                "message": "No hay simulaciones previas, usando valores por defecto"
            }

        return {
            "success": True,
            "window_days": config.get("window_days", 7),
            "target_date": config.get("target_date"),
            "window_start": config.get("window_start"),
            "updated_at": config.get("updated_at")
        }
    except Exception as e:
        logger.error(f"Error al obtener configuración de última simulación: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "window_days": 7
        }


@router.get("/executed-dates")
async def get_executed_simulation_dates(
    simulation_repo: SimulationRepositoryDep
) -> Dict[str, Any]:
    """
    Obtiene el rango de fechas donde se ejecutaron simulaciones.
    Este endpoint es para el Dashboard, que solo debe mostrar fechas de simulaciones ejecutadas.

    Retorna:
    - min_date: Fecha inicial de la simulación más antigua ejecutada
    - max_date: Fecha final de la simulación más reciente ejecutada
    - total_simulations: Total de simulaciones ejecutadas
    """
    try:
        simulations = simulation_repo.get_all()

        if not simulations:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron simulaciones ejecutadas. Por favor ejecute una simulación primero."
            )

        # Obtener fechas de todas las simulaciones
        all_start_dates = []
        all_end_dates = []

        for sim in simulations:
            if sim.config and sim.config.start_date and sim.config.target_date:
                all_start_dates.append(sim.config.start_date)
                all_end_dates.append(sim.config.target_date)

        if not all_start_dates or not all_end_dates:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron fechas válidas en las simulaciones ejecutadas"
            )

        min_date = min(all_start_dates)
        max_date = max(all_end_dates)

        return {
            "success": True,
            "min_date": min_date.isoformat(),
            "max_date": max_date.isoformat(),
            "total_simulations": len(simulations),
            "total_days": (max_date - min_date).days + 1
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener fechas de simulaciones ejecutadas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener fechas de simulaciones ejecutadas: {str(e)}"
        )


@router.get("/available-dates")
async def get_available_dates() -> Dict[str, Any]:
    """
    Obtiene el rango de fechas disponibles para ejecutar simulaciones.
    Este endpoint es para la Configuración de Simulación, muestra todas las fechas con datos disponibles.

    Retorna:
    - min_date: Fecha minima disponible (primera fecha en balances)
    - max_date: Fecha maxima disponible (ultima fecha en movements)
    - full_window_from: Fecha desde donde hay 7 dias completos de datos
    - total_days: Total de dias con datos disponibles
    """
    try:
        db = database_manager.get_database()

        # OPTIMIZACION: Solo traer el campo createdAt (no documentos completos)
        balances_collection = db.balances
        min_balance = balances_collection.find_one(
            projection={"createdAt": 1, "_id": 0},
            sort=[("createdAt", 1)]
        )
        max_balance = balances_collection.find_one(
            projection={"createdAt": 1, "_id": 0},
            sort=[("createdAt", -1)]
        )

        # Obtener rango de fechas desde movements (usa createdAt)
        movements_collection = db["mov07.10"]
        min_movement = movements_collection.find_one(
            projection={"createdAt": 1, "_id": 0},
            sort=[("createdAt", 1)]
        )
        max_movement = movements_collection.find_one(
            projection={"createdAt": 1, "_id": 0},
            sort=[("createdAt", -1)]
        )

        if not min_balance or not max_balance:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron datos en la coleccion balances"
            )

        if not min_movement or not max_movement:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron datos en la coleccion movements"
            )

        # Convertir createdAt (string ISO o datetime) a date
        # Extraer solo la fecha (primeros 10 caracteres YYYY-MM-DD)
        min_date_balance = date.fromisoformat(str(min_balance["createdAt"])[:10])
        max_date_balance = date.fromisoformat(str(max_balance["createdAt"])[:10])

        # Fechas desde movements
        min_date_movement = date.fromisoformat(str(min_movement["createdAt"])[:10])
        max_date_movement = date.fromisoformat(str(max_movement["createdAt"])[:10])

        # La fecha minima absoluta es la primera fecha en balances
        min_date = min_date_balance

        # La fecha maxima es la menor entre balances y movements
        max_date = min(max_date_balance, max_date_movement)

        # Calcular fecha desde donde hay 7 dias completos
        # Necesitamos que min_date_movement + 7 dias <= target_date
        full_window_from = min_date_movement + timedelta(days=7)

        # Calcular total de dias
        total_days = (max_date - min_date).days + 1

        return {
            "success": True,
            "min_date": min_date.isoformat(),
            "max_date": max_date.isoformat(),
            "full_window_from": full_window_from.isoformat(),
            "total_days": total_days,
            "balances_range": {
                "min": min_date_balance.isoformat(),
                "max": max_date_balance.isoformat()
            },
            "movements_range": {
                "min": min_date_movement.isoformat(),
                "max": max_date_movement.isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener fechas disponibles: {str(e)}"
        )


# ============================================================================
# FUNCIONES AUXILIARES PARA REDUCIR COMPLEJIDAD DE run_simulation
# ============================================================================

def _validate_date_ranges(request: SimulationRequest, db) -> tuple[date, date, date, int]:
    """
    Valida rangos de fechas y retorna start_date, end_date, max_date, total_days.

    Raises:
        HTTPException: Si las fechas no son válidas o no hay datos suficientes
    """
    balances_collection = db.balances
    min_balance = balances_collection.find_one(
        projection={"createdAt": 1, "_id": 0},
        sort=[("createdAt", 1)]
    )
    max_balance = balances_collection.find_one(
        projection={"createdAt": 1, "_id": 0},
        sort=[("createdAt", -1)]
    )

    movements_collection = db["mov07.10"]
    min_movement = movements_collection.find_one(
        projection={"createdAt": 1, "_id": 0},
        sort=[("createdAt", 1)]
    )
    max_movement = movements_collection.find_one(
        projection={"createdAt": 1, "_id": 0},
        sort=[("createdAt", -1)]
    )

    if not min_balance or not max_balance or not min_movement or not max_movement:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron datos suficientes en las colecciones"
        )

    max_date_balance = date.fromisoformat(str(max_balance["createdAt"])[:10])
    min_date_movement = date.fromisoformat(str(min_movement["createdAt"])[:10])
    max_date_movement = date.fromisoformat(str(max_movement["createdAt"])[:10])
    max_date = min(max_date_balance, max_date_movement)

    start_date = request.start_date
    end_date = request.end_date

    if end_date > max_date:
        raise HTTPException(
            status_code=400,
            detail=f"La fecha final no puede ser mayor a {max_date.isoformat()}"
        )

    if start_date < min_date_movement:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficientes datos historicos. "
                   f"La fecha inicial debe ser >= {min_date_movement.isoformat()}"
        )

    total_days = (end_date - start_date).days + 1

    logger.info(f"=== INICIANDO SIMULACION DE {total_days} DIAS ===")
    logger.info(f"Fecha inicial: {start_date}")
    logger.info(f"Fecha final: {end_date}")
    logger.info(f"Total días a procesar: {total_days}")
    logger.info("======================================")

    return start_date, end_date, max_date, total_days


def _clean_collections(db, request: SimulationRequest) -> List[Dict[str, Any]]:
    """
    Limpia TODAS las colecciones antes de ejecutar una nueva simulación.

    Esto previene data duplicada o data basura de simulaciones anteriores.
    Se limpian todas las colecciones relacionadas con:
    - Estados de agentes y asignaciones
    - ROI y métricas por ventana
    - Top16 por ventana
    - Logs de rotaciones y cambios de ranking
    - Cuentas de clientes y sus historiales
    - Metadatos de simulaciones
    """
    collections_to_clean = [
        # Estados y asignaciones
        "agent_states",
        "assignments",
        "rotation_log",
        "daily_roi_calculation",

        # Cuentas de clientes y sus historiales
        "cuentas_clientes_trading",
        "historial_asignaciones_clientes",
        "snapshots_clientes",
        "client_accounts_snapshots",  # Snapshots de simulaciones de client accounts
        "client_accounts_simulations",  # Metadatos de simulaciones de client accounts
        "rebalanceo_log",

        # Colecciones de ROI por ventana (3d, 5d, 7d, 10d, 15d, 30d)
        "agent_roi_3d",
        "agent_roi_5d",
        "agent_roi_7d",
        "agent_roi_10d",
        "agent_roi_15d",
        "agent_roi_30d",

        # Colecciones de Top16 por ventana (3d, 5d, 7d, 10d, 15d, 30d)
        "top16_3d",
        "top16_5d",
        "top16_7d",
        "top16_10d",
        "top16_15d",
        "top16_30d",

        # Cambios de ranking
        "rank_changes",

        # Metadatos de simulaciones
        "simulations"
    ]

    cleaned_collections = []
    total_deleted = 0

    for collection_name in collections_to_clean:
        try:
            result = db[collection_name].delete_many({})
            deleted_count = result.deleted_count
            total_deleted += deleted_count
            cleaned_collections.append({
                "collection": collection_name,
                "deleted_count": deleted_count
            })
            logger.info(f"✓ Limpiada colección '{collection_name}': {deleted_count} documentos eliminados")
        except Exception as e:
            logger.warning(f"⚠ Error al limpiar colección '{collection_name}': {str(e)}")
            cleaned_collections.append({
                "collection": collection_name,
                "deleted_count": 0,
                "error": str(e)
            })

    total_days = (request.end_date - request.start_date).days + 1
    logger.info(f"=" * 80)
    logger.info(f"LIMPIEZA COMPLETA: {len(collections_to_clean)} colecciones procesadas")
    logger.info(f"Total de documentos eliminados: {total_deleted}")
    logger.info(f"Simulación configurada para {total_days} días")
    logger.info(f"=" * 80)

    return cleaned_collections


def _create_empty_accounts(db, request: SimulationRequest) -> None:
    """Crea 1000 cuentas de clientes vacías (sin agentes asignados)."""
    if not request.update_client_accounts or request.dry_run:
        return

    try:
        logger.info("Creando 1000 cuentas de clientes (sin agentes asignados)...")
        from datetime import datetime

        cuentas_vacias = []
        fecha_temporal = datetime.utcnow()
        for i in range(1, 1001):
            cuenta = {
                "cuenta_id": f"CL{i:04d}",
                "nombre_cliente": f"Cliente {i:04d}",
                "balance_inicial": 1000.0,
                "balance_actual": 1000.0,
                "roi_total": 0.0,
                "win_rate": 0.0,
                "agente_actual": "PENDING",
                "fecha_asignacion_agente": fecha_temporal,
                "roi_agente_al_asignar": 0.0,
                "roi_acumulado_con_agente": 0.0,
                "roi_historico_anterior": 0.0,
                "numero_cambios_agente": 0,
                "estado": "activo",
                "created_at": fecha_temporal,
                "updated_at": fecha_temporal
            }
            cuentas_vacias.append(cuenta)

        db["cuentas_clientes_trading"].insert_many(cuentas_vacias)
        logger.info("Cuentas creadas: 1000 cuentas sin agentes asignados")
        logger.info("Las cuentas seran redistribuidas automaticamente al Top16 en el primer dia de simulacion")
    except Exception as e:
        logger.error(f"Error al crear cuentas: {str(e)}", exc_info=True)


async def _process_simulation_days(
    orchestrator_service,
    selection_service,
    rotation_log_repo,
    status_repo,
    db,
    request: SimulationRequest,
    date_range: List[date],
    window_days: int
) -> tuple[List[Dict[str, Any]], int]:
    """
    Procesa todos los días de la simulación y detecta rotaciones.

    Args:
        window_days: Ventana de días usada para cálculo de ROI (3, 5, 7, 10, 15, 30)
        status_repo: Repositorio para actualizar el estado de la simulación

    Returns:
        Tupla con (all_results, total_rotations_detected)
    """
    log.separator("=", 80)
    log.info(f"Procesando {len(date_range)} días: {date_range[0]} -> {date_range[-1]}", context="[LOOP DIAS]")
    log.separator("=", 80)
    logger.info(f"Procesando {len(date_range)} días secuencialmente: {date_range[0]} -> {date_range[-1]}")

    all_results = []
    previous_top16 = None
    total_rotations_detected = 0

    for idx, current_date in enumerate(date_range, 1):
        logger.info(f"Día {idx}/{len(date_range)} - Procesando: {current_date}")
        logger.info(f"[{idx}/{len(date_range)}] Procesando fecha: {current_date}")

        status_repo.update_progress(
            current_day=idx,
            message=f"Procesando día {idx}/{len(date_range)}: {current_date}"
        )

        total_days = len(date_range)
        simulation_id_to_use = request.simulation_id or f"sim_{total_days}d_{request.start_date.isoformat()}_to_{request.end_date.isoformat()}"

        day_result = await orchestrator_service.process_single_date(
            target_date=current_date,
            skip_cache_clear=True,
            window_days=window_days,
            update_client_accounts=request.update_client_accounts,
            simulation_id=simulation_id_to_use,
            dry_run=request.dry_run
        )

        top16_collection_name = get_top16_collection_name(window_days)
        top16_collection = db[top16_collection_name]
        top16_docs = list(top16_collection.find({"date": current_date.isoformat()}).sort("rank", 1))
        roi_field = f"roi_{window_days}d"
        current_top16 = [
            Top16Day(
                date=doc["date"],
                rank=doc["rank"],
                agent_id=doc["agent_id"],
                roi_7d=doc.get(roi_field, 0.0),
                total_aum=doc["total_aum"],
                n_accounts=doc["n_accounts"],
                is_in_casterly=doc.get("is_in_casterly", False)
            )
            for doc in top16_docs
        ]

        logger.debug(f"previous_top16: {'Existe' if previous_top16 else 'None'} (len={len(previous_top16) if previous_top16 else 0})")
        logger.debug(f"current_top16: {'Existe' if current_top16 else 'None'} (len={len(current_top16) if current_top16 else 0})")

        rotations = []
        rank_changes = []
        if previous_top16 is not None and len(previous_top16) > 0:
            logger.info(f"Detectando rotaciones para fecha {current_date}")
            logger.debug(f"Previous Top16: {len(previous_top16)} agentes")
            logger.debug(f"Current Top16: {len(current_top16)} agentes")

            rotations = selection_service.detect_rotations(
                previous_top16=previous_top16,
                current_top16=current_top16,
                current_date=current_date
            )

            logger.info(f"Rotaciones detectadas: {len(rotations)}")
            if len(rotations) > 0:
                for rot in rotations:
                    logger.debug(f"  - {rot.get('agent_out')} OUT -> {rot.get('agent_in')} IN (Razón: {rot.get('reason')})")
            else:
                prev_agents = {a.agent_id for a in previous_top16}
                curr_agents = {a.agent_id for a in current_top16}
                logger.info(f"[ROTATIONS] No se detectaron cambios. Agentes anteriores == Agentes actuales: {prev_agents == curr_agents}")
                if prev_agents != curr_agents:
                    logger.warning("[ROTATIONS] ATENCIÓN: Los agentes son diferentes pero no se detectaron rotaciones!")
                    logger.warning(f"[ROTATIONS]   Solo en anterior: {prev_agents - curr_agents}")
                    logger.warning(f"[ROTATIONS]   Solo en actual: {curr_agents - prev_agents}")

            if rotations:
                for rotation_data in rotations:
                    try:
                        agent_out = rotation_data.get("agent_out")
                        agent_in = rotation_data.get("agent_in")

                        if not agent_out or not agent_in:
                            logger.warning(
                                f"[ROTATION_SKIP] Rotación inválida omitida: "
                                f"agent_out={agent_out}, agent_in={agent_in}. "
                                f"Se requiere AMBOS agentes para registrar una rotación."
                            )
                            continue

                        rotation_entity = RotationLog(
                            date=rotation_data["date"],
                            agent_out=agent_out,
                            agent_in=agent_in,
                            reason=rotation_data.get("reason", RotationReason.DAILY_ROTATION),
                            reason_details=rotation_data.get("reason_details"),
                            roi_7d_out=rotation_data.get("roi_7d_out", 0.0),
                            roi_total_out=0.0,
                            roi_7d_in=rotation_data.get("roi_7d_in", 0.0),
                            n_accounts=rotation_data.get("n_accounts", 0),
                            total_aum=rotation_data.get("total_aum", 0.0)
                        )
                        rotation_log_repo.create(rotation_entity)
                        total_rotations_detected += 1
                    except Exception as e:
                        logger.error(f"Error al guardar rotación: {str(e)}")

            rank_changes = selection_service.detect_rank_changes(
                previous_top16=previous_top16,
                current_top16=current_top16,
                current_date=current_date
            )

            if rank_changes:
                from app.domain.entities.rank_change import RankChange
                from app.infrastructure.repositories.rank_change_repository_impl import RankChangeRepositoryImpl
                rank_change_repo = RankChangeRepositoryImpl()

                for rank_change_data in rank_changes:
                    try:
                        rank_change_entity = RankChange(
                            date=rank_change_data["date"],
                            agent_id=rank_change_data["agent_id"],
                            previous_rank=rank_change_data["previous_rank"],
                            current_rank=rank_change_data["current_rank"],
                            rank_change=rank_change_data["rank_change"],
                            previous_roi=rank_change_data["previous_roi"],
                            current_roi=rank_change_data["current_roi"],
                            roi_change=rank_change_data["roi_change"],
                            is_in_casterly=rank_change_data["is_in_casterly"]
                        )
                        rank_change_repo.create(rank_change_entity)
                    except Exception as e:
                        logger.error(f"Error al guardar cambio de ranking: {str(e)}")

        all_results.append({
            "date": current_date.isoformat(),
            "rotations_detected": len(rotations),
            "rank_changes_detected": len(rank_changes),
            "result": day_result
        })

        previous_top16 = current_top16

        logger.info(
            f"[{idx}/{len(date_range)}] Completado: {current_date} "
            f"({len(rotations)} rotaciones, {len(rank_changes)} cambios de ranking)"
        )

    total_rank_changes = sum(r.get("rank_changes_detected", 0) for r in all_results)
    logger.info(
        f"Total detectado en todo el período: "
        f"{total_rotations_detected} rotaciones, {total_rank_changes} cambios de ranking"
    )

    return all_results, total_rotations_detected


async def _save_simulation_summary(
    simulation_repo,
    db,
    request: SimulationRequest,
    start_date: date,
    end_date: date,
    top16_agent_ids: List[str],
    window_days: int
) -> Optional[str]:
    """
    Guarda el resumen de la simulación.

    Returns:
        simulation_id si se guardó exitosamente, None si no
    """
    simulation_id = None
    try:
        from datetime import datetime
        simulation_id = str(uuid.uuid4())

        total_simulations = simulation_repo.count()
        if total_simulations >= 50:
            logger.warning("Limite de 50 simulaciones alcanzado. No se guardara esta simulacion.")
            return None

        total_days = (end_date - start_date).days + 1
        simulation_name = request.simulation_name or f"Simulacion {total_days}D {start_date.isoformat()} a {end_date.isoformat()}"

        top16_data = _get_top16_final(db, end_date, window_days)
        summary_data = await _get_summary_kpis(db, end_date, top16_agent_ids, window_days)
        rotations_data = _get_rotations_summary(db, start_date, end_date)
        daily_metrics_data = _calculate_daily_metrics(db, start_date, end_date, top16_agent_ids, window_days)

        simulation = Simulation(
            simulation_id=simulation_id,
            name=simulation_name,
            description=None,
            created_at=datetime.now(),
            config=SimulationConfig(
                target_date=end_date,
                start_date=start_date,
                days_simulated=total_days,
                window_days=request.window_days,
                fall_threshold=3,
                stop_loss_threshold=-0.10
            ),
            kpis=summary_data,
            top_16_final=top16_data,
            rotations_summary=rotations_data,
            daily_metrics=daily_metrics_data
        )

        simulation_repo.create(simulation)
        logger.info(f"Resumen de simulacion guardado con ID: {simulation_id}")
        return simulation_id
    except Exception as e:
        logger.error(f"Error al guardar resumen de simulacion: {str(e)}", exc_info=True)
        return None


def _save_system_config(db, request: SimulationRequest, start_date: date, end_date: date, window_days: int) -> None:
    """Guarda la configuración de la última simulación."""
    try:
        from datetime import datetime
        total_days = (end_date - start_date).days + 1
        system_config_col = db["system_config"]
        system_config_col.update_one(
            {"config_key": "last_simulation"},
            {
                "$set": {
                    "config_key": "last_simulation",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_days": total_days,
                    "window_days": window_days,
                    "updated_at": datetime.now().isoformat()
                }
            },
            upsert=True
        )
        logger.info(f"Configuración de última simulación guardada: {total_days} dias, window_days: {window_days}")
    except Exception as e:
        logger.error(f"Error al guardar configuración de última simulación: {str(e)}")


def _save_client_accounts_snapshot(
    client_accounts_service,
    request: SimulationRequest,
    start_date: date,
    end_date: date,
    all_results: List[Dict[str, Any]],
    window_days: int,
    redistribution_result: Optional[Dict],
    roi_update_result: Optional[Dict]
) -> Optional[Dict[str, Any]]:
    """Guarda snapshot de Client Accounts simulation."""
    if not request.update_client_accounts or request.dry_run:
        return None

    try:
        logger.info("Guardando snapshot de Client Accounts simulation...")
        total_days = (end_date - start_date).days + 1
        simulation_id_to_use = request.simulation_id or f"sim_{total_days}d_{start_date.isoformat()}_to_{end_date.isoformat()}"

        metadata = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_days": total_days,
            "total_days_processed": len(all_results),
            "redistribution": redistribution_result,
            "roi_update": roi_update_result
        }

        snapshot_result = client_accounts_service.save_simulation_snapshot(
            simulation_id=simulation_id_to_use,
            simulation_date=end_date,
            window_days=window_days,
            metadata=metadata
        )

        logger.info(f"Snapshot de Client Accounts guardado: {snapshot_result['snapshot_id']}")
        return snapshot_result
    except Exception as e:
        logger.error(f"Error al guardar snapshot de Client Accounts: {str(e)}", exc_info=True)
        return None


def _run_simulation_background(
    request: SimulationRequest,
    orchestrator_service,
    simulation_repo,
    client_accounts_service,
    selection_service,
    rotation_log_repo,
    status_repo
) -> None:
    """
    Ejecuta la simulación en segundo plano en un thread separado.
    Esta función NO retorna nada, solo ejecuta y actualiza el estado.
    IMPORTANTE: Esta función es SÍNCRONA y se ejecuta en un thread separado.
    """
    try:
        # Crear un nuevo event loop para este thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Ejecutar la simulación asíncrona en el nuevo loop
        loop.run_until_complete(_run_simulation_async(
            request,
            orchestrator_service,
            simulation_repo,
            client_accounts_service,
            selection_service,
            rotation_log_repo,
            status_repo
        ))
        loop.close()

    except Exception as e:
        logger.error(f"Error en thread de simulación: {str(e)}", exc_info=True)
        try:
            status_repo.mark_completed()
        except:
            pass


async def _run_simulation_async(
    request: SimulationRequest,
    orchestrator_service,
    simulation_repo,
    client_accounts_service,
    selection_service,
    rotation_log_repo,
    status_repo
) -> None:
    """
    Lógica asíncrona de la simulación.
    """
    try:
        db = database_manager.get_database()

        # Recuperar las fechas validadas desde el estado
        current_status = status_repo.get_current()
        if not current_status:
            logger.error("No se encontró estado de simulación para ejecutar background task")
            return

        start_date = date.fromisoformat(current_status.start_date)
        end_date = date.fromisoformat(current_status.end_date)
        total_days = current_status.total_days

        # 2. Limpiar colecciones temporales
        cleaned_collections = _clean_collections(db, request)

        # 3. Crear cuentas vacías si es necesario
        _create_empty_accounts(db, request)

        # 4. Generar rango de fechas a procesar
        date_range = []
        current = start_date
        while current <= end_date:
            date_range.append(current)
            current += timedelta(days=1)

        # 5. Procesar todos los días de la simulación usando run_simulation (con rebalanceo)
        logger.info(f"Ejecutando simulación con rebalanceo (window_days={request.window_days})")

        orchestrator_result = await orchestrator_service.run_simulation(
            start_date=start_date,
            end_date=end_date,
            update_client_accounts=request.update_client_accounts,
            simulation_id=request.simulation_id,
            window_days=request.window_days,
            dry_run=request.dry_run
        )

        # Extraer resultados del orchestrator
        daily_results_raw = orchestrator_result.get("daily_results", [])
        total_rotations_detected = orchestrator_result.get("summary", {}).get("total_rotations", 0)

        # Adaptar formato para compatibilidad con código existente
        all_results = []
        for day_result in daily_results_raw:
            rotations_count = 0
            if "rebalancing" in day_result and day_result["rebalancing"].get("is_rebalancing_day"):
                rotations_count += day_result["rebalancing"].get("total_rotations", 0)
            if "rotations_executed" in day_result:
                rotations_exec = day_result.get("rotations_executed", [])
                if isinstance(rotations_exec, int):
                    rotations_count += rotations_exec
                else:
                    rotations_count += len(rotations_exec)

            all_results.append({
                "date": day_result.get("date"),
                "rotations_detected": rotations_count,
                "rank_changes_detected": 0,
                "result": day_result
            })

        # 6. Obtener resultado del último día
        result = all_results[-1]["result"] if all_results else {}

        # 7. Guardar resumen de simulación
        top16_agent_ids = [agent.agent_id for agent in _get_top16_final(db, end_date, request.window_days)]
        simulation_id = await _save_simulation_summary(
            simulation_repo,
            db,
            request,
            start_date,
            end_date,
            top16_agent_ids,
            request.window_days
        )

        # 8. Guardar configuración del sistema
        _save_system_config(db, request, start_date, end_date, request.window_days)

        # 9. Guardar snapshot de client accounts
        redistribution_result = None
        roi_update_result = None
        client_accounts_snapshot_info = _save_client_accounts_snapshot(
            client_accounts_service,
            request,
            start_date,
            end_date,
            all_results,
            request.window_days,
            redistribution_result,
            roi_update_result
        )

        # 9.5. Marcar simulación como completada
        status_repo.mark_completed()
        logger.info("Simulación completada exitosamente en background")

        # Invalidate cache
        from app.core.cache import cache_service
        invalidated_count = await cache_service.delete_pattern("summary:*")
        if invalidated_count > 0:
            logger.info(f"✓ Invalidated {invalidated_count} summary cache entries after simulation")

    except Exception as e:
        logger.error(f"Error en simulación background: {str(e)}", exc_info=True)
        status_repo.mark_completed()


@router.post("/run")
async def run_simulation(
    request: SimulationRequest,
    orchestrator_service: DailyOrchestratorServiceDep,
    simulation_repo: SimulationRepositoryDep,
    client_accounts_service: ClientAccountsServiceDep,
    selection_service: SelectionServiceDep,
    rotation_log_repo: RotationLogRepositoryDep,
    status_repo: SimulationStatusRepositoryDep
) -> Dict[str, Any]:
    """
    Ejecuta una simulación de trading para un rango de fechas (mínimo 30 días).

    El sistema procesa todos los días del rango y guarda los datos completos.
    Los KPIs se pueden calcular posteriormente para diferentes ventanas mediante filtros.
    """
    log.separator("=", 80)
    log.success(f"Simulación iniciada - start_date={request.start_date}, end_date={request.end_date}", context="[SIMULATION]")
    log.separator("=", 80)
    logger.info(f"Recibida solicitud de simulación: start_date={request.start_date}, end_date={request.end_date}")

    try:
        db = database_manager.get_database()

        # 1. Validar rangos de fechas
        start_date, end_date, max_date, total_days = _validate_date_ranges(request, db)

        # 2. IMPORTANTE: Crear estado inicial de simulación ANTES de iniciar background task
        # Esto permite que el frontend detecte inmediatamente que la simulación está corriendo
        initial_status = SimulationStatus(
            is_running=True,
            current_day=0,
            total_days=total_days,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            estimated_seconds_per_day=22,
            message="Iniciando simulación..."
        )
        status_repo.upsert(initial_status)
        logger.info("Estado inicial de simulación guardado (is_running=True)")

        # 3. Lanzar simulación en segundo plano usando un thread separado
        simulation_thread = threading.Thread(
            target=_run_simulation_background,
            args=(
                request,
                orchestrator_service,
                simulation_repo,
                client_accounts_service,
                selection_service,
                rotation_log_repo,
                status_repo
            ),
            daemon=True  # El thread se detendrá cuando el proceso principal termine
        )
        simulation_thread.start()
        logger.info("Simulación lanzada en thread separado")

        # 4. Retornar inmediatamente
        return {
            "success": True,
            "message": "Simulación iniciada en segundo plano",
            "simulation_started": True,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_days": total_days,
            "estimated_duration_seconds": total_days * 22
        }

    except ValueError as e:
        status_repo.mark_completed()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al ejecutar la simulacion: {str(e)}", exc_info=True)
        status_repo.mark_completed()
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar la simulacion: {str(e)}"
        )


@router.get("/status")
async def get_simulation_status(
    status_repo: SimulationStatusRepositoryDep
) -> Dict[str, Any]:
    """
    Obtiene el estado actual de la simulacion en curso.

    Returns:
        Estado de la simulacion o indicador de que no hay simulacion activa
    """
    try:
        current_status = status_repo.get_current()

        if not current_status:
            return {
                "is_running": False,
                "message": "No hay simulación en curso"
            }

        return {
            "is_running": current_status.is_running,
            "current_day": current_status.current_day,
            "total_days": current_status.total_days,
            "start_date": current_status.start_date,
            "end_date": current_status.end_date,
            "started_at": current_status.started_at.isoformat(),
            "updated_at": current_status.updated_at.isoformat(),
            "estimated_seconds_per_day": current_status.estimated_seconds_per_day,
            "message": current_status.message,
            "progress_percentage": (current_status.current_day / current_status.total_days) * 100 if current_status.total_days > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error al obtener estado de simulacion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener estado de simulacion: {str(e)}"
        )


@router.post("/cancel")
async def cancel_simulation(
    status_repo: SimulationStatusRepositoryDep
) -> Dict[str, Any]:
    """
    Cancela la simulacion en curso.

    Marca la simulacion como cancelada (is_running=False) para que el proceso
    actual se detenga de forma segura.

    Returns:
        Confirmacion de cancelacion
    """
    try:
        current_status = status_repo.get_current()

        if not current_status or not current_status.is_running:
            return {
                "success": False,
                "message": "No hay simulacion en curso para cancelar"
            }

        # Marcar como cancelada
        status_repo.mark_cancelled()

        logger.info("Simulacion cancelada exitosamente por peticion del usuario")

        return {
            "success": True,
            "message": "Simulacion cancelada exitosamente"
        }

    except Exception as e:
        logger.error(f"Error al cancelar simulacion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al cancelar simulacion: {str(e)}"
        )


async def _get_summary_kpis(db, end_date: date, top16_agent_ids: List[str], window_days: int = 7) -> SimulationKPIs:
    """
    Obtiene los KPIs de la simulacion desde agent_roi_XD.
    Calcula los KPIs SOLO para los Top 16 agentes.
    """
    from app.utils.collection_names import get_roi_collection_name
    roi_collection_name = get_roi_collection_name(window_days)
    roi_collection = db[roi_collection_name]

    logger.info(f"Obteniendo KPIs desde coleccion: {roi_collection_name}")

    # Filtrar SOLO los Top 16 agentes
    roi_docs = list(roi_collection.find({
        "target_date": end_date.isoformat(),
        "userId": {"$in": top16_agent_ids}
    }))

    if not roi_docs:
        return SimulationKPIs(
            total_roi=0.0,
            avg_roi=0.0,
            volatility=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            active_agents_count=0,
            unique_agents_in_period=0,
            sharpe_ratio=None
        )

    # Calcular KPIs basicos
    total_agents = len(roi_docs)
    roi_field = f"roi_{window_days}d"
    total_roi = sum(doc.get(roi_field, 0.0) for doc in roi_docs)
    avg_roi = total_roi / total_agents if total_agents > 0 else 0.0

    # Volatilidad
    all_daily_rois = []
    for doc in roi_docs:
        daily_rois_list = doc.get("daily_rois", [])
        for day in daily_rois_list:
            roi = day.get("roi", 0.0)
            if roi != 0:
                all_daily_rois.append(roi)

    if len(all_daily_rois) > 1:
        mean_roi = sum(all_daily_rois) / len(all_daily_rois)
        variance = sum((x - mean_roi) ** 2 for x in all_daily_rois) / len(all_daily_rois)
        volatility = variance ** 0.5
    else:
        volatility = 0.0

    # Max Drawdown
    max_drawdown = 0.0
    for doc in roi_docs:
        daily_rois_list = doc.get("daily_rois", [])
        if len(daily_rois_list) >= 2:
            cumulative = [1.0]
            for day in daily_rois_list:
                roi = day.get("roi", 0)
                cumulative.append(cumulative[-1] * (1 + roi))

            peak = cumulative[0]
            for value in cumulative:
                if value > peak:
                    peak = value
                drawdown = (value - peak) / peak if peak > 0 else 0
                if drawdown < max_drawdown:
                    max_drawdown = drawdown

    # Win Rate
    positive_agents = sum(1 for doc in roi_docs if doc.get(roi_field, 0.0) > 0)
    win_rate = positive_agents / total_agents if total_agents > 0 else 0.0

    # Sharpe Ratio
    sharpe_ratio = None
    if volatility > 0:
        sharpe_ratio = avg_roi / volatility

    # El conteo de agentes activos es simplemente los Top 16
    # (todos están en Casterly por definición)
    active_agents_count = len(roi_docs)

    return SimulationKPIs(
        total_roi=total_roi,
        avg_roi=avg_roi,
        volatility=volatility,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        active_agents_count=active_agents_count,
        unique_agents_in_period=total_agents,
        sharpe_ratio=sharpe_ratio
    )


def _get_top16_final(db, end_date: date, window_days: int = 7) -> List[TopAgentSummary]:
    """
    Obtiene el Top 16 final desde top16_XD (coleccion dinamica).
    Intenta primero con la coleccion especifica, luego con top16_7d como fallback.
    """
    from app.utils.collection_names import get_top16_collection_name
    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = db[top16_collection_name]

    logger.info(f"Obteniendo Top 16 final desde coleccion: {top16_collection_name}")

    top16_docs = list(top16_collection.find({
        "date": end_date.isoformat()
    }).sort("rank", 1))

    # Fallback: Si no hay datos en la coleccion especifica, intentar con top16_7d
    if not top16_docs and window_days != 7:
        logger.warning(f"No se encontraron datos en {top16_collection_name}, intentando con top16_7d")
        top16_collection = db["top16_7d"]
        top16_docs = list(top16_collection.find({
            "date": end_date.isoformat()
        }).sort("rank", 1))

    roi_field = f"roi_{window_days}d"
    return [
        TopAgentSummary(
            rank=doc.get("rank"),
            agent_id=doc.get("agent_id"),
            roi_7d=doc.get(roi_field, doc.get("roi_7d", 0.0)),  # Fallback a roi_7d si no existe el campo especifico
            total_aum=doc.get("total_aum", 0.0),
            n_accounts=doc.get("n_accounts", 0),
            is_in_casterly=doc.get("is_in_casterly", False)
        )
        for doc in top16_docs
    ]


def _get_rotations_summary(db, start_date: date, end_date: date) -> RotationsSummary:
    """
    Obtiene el resumen de rotaciones desde rotation_log.
    """
    rotation_collection = db.rotation_log

    # Query que funciona tanto con "YYYY-MM-DD" como con "YYYY-MM-DDT00:00:00"
    rotation_docs = list(rotation_collection.find({
        "date": {
            "$gte": start_date.isoformat(),
            "$lte": (end_date.isoformat() + "T23:59:59")  # Captura todo el día
        }
    }))

    total_rotations = len(rotation_docs)

    rotations_by_reason = {}
    agents_rotated_out = []
    agents_rotated_in = []

    for doc in rotation_docs:
        reason = doc.get("reason", "UNKNOWN")
        rotations_by_reason[reason] = rotations_by_reason.get(reason, 0) + 1

        agent_out = doc.get("agent_out")
        if agent_out and agent_out not in agents_rotated_out:
            agents_rotated_out.append(agent_out)

        agent_in = doc.get("agent_in")
        if agent_in and agent_in not in agents_rotated_in:
            agents_rotated_in.append(agent_in)

    return RotationsSummary(
        total_rotations=total_rotations,
        rotations_by_reason=rotations_by_reason,
        agents_rotated_out=agents_rotated_out,
        agents_rotated_in=agents_rotated_in
    )


def _calculate_daily_metrics(db, start_date: date, end_date: date, top16_agent_ids: List[str], window_days: int = 7) -> List[DailyMetric]:
    """
    Calcula metricas diarias para graficos de evolucion.
    Usa daily_roi_calculation para obtener ROI diario (no acumulado) de cada día.
    """
    # Usar daily_roi_calculation que contiene ROI diario real
    daily_roi_collection = db["daily_roi_calculation"]

    logger.info("[DEBUG] _calculate_daily_metrics llamado con:")
    logger.info(f"[DEBUG]   start_date: {start_date}")
    logger.info(f"[DEBUG]   end_date: {end_date}")
    logger.info(f"[DEBUG]   window_days: {window_days}")
    logger.info(f"[DEBUG]   Usando coleccion: daily_roi_calculation")
    logger.info(f"[DEBUG]   top16_agent_ids (total {len(top16_agent_ids)}): {top16_agent_ids[:3]}...")

    # Obtener ROIs diarios (no acumulados) de TODOS los días en el rango
    # IMPORTANTE: El campo se llama 'userId', no 'agent_id'
    roi_docs = list(daily_roi_collection.find({
        "userId": {"$in": top16_agent_ids},
        "date": {
            "$gte": start_date.isoformat(),
            "$lte": end_date.isoformat()
        }
    }).sort("date", 1))

    logger.info(f"[DEBUG] Documentos encontrados en daily_roi_calculation: {len(roi_docs)}")

    if not roi_docs:
        logger.warning(f"No se encontraron datos en daily_roi_calculation para los Top 16 agentes en rango {start_date} - {end_date}")
        return []

    # Organizar documentos por fecha para fácil acceso
    docs_by_date = {}
    for doc in roi_docs:
        doc_date = doc.get("date")
        if doc_date not in docs_by_date:
            docs_by_date[doc_date] = []
        docs_by_date[doc_date].append(doc)

    # Calcular métricas para cada día del rango
    num_days = (end_date - start_date).days + 1
    daily_metrics = []
    cumulative_roi = 0.0

    for day_index in range(num_days):
        current_date = start_date + timedelta(days=day_index)
        current_date_str = current_date.isoformat()

        daily_roi_sum = 0.0
        active_agents_count = 0
        total_pnl_sum = 0.0

        # Buscar documentos de este día
        docs_for_day = docs_by_date.get(current_date_str, [])

        if docs_for_day:
            for doc in docs_for_day:
                # El ROI diario real está en roi_day
                roi_value = doc.get("roi_day", 0.0)
                # El P&L del día es el total_pnl_day
                pnl_value = doc.get("total_pnl_day", 0.0)

                daily_roi_sum += roi_value
                total_pnl_sum += pnl_value

                if roi_value != 0.0 or pnl_value != 0.0:
                    active_agents_count += 1

        cumulative_roi += daily_roi_sum

        daily_metrics.append(DailyMetric(
            date=current_date,
            roi_cumulative=cumulative_roi,
            active_agents=active_agents_count,
            total_pnl=total_pnl_sum
        ))

    logger.info(f"[DEBUG] daily_metrics generados: {len(daily_metrics)} dias")
    if daily_metrics:
        logger.info(f"[DEBUG] Primer dia: {daily_metrics[0].model_dump()}")
        logger.info(f"[DEBUG] Ultimo dia: {daily_metrics[-1].model_dump()}")

    return daily_metrics
