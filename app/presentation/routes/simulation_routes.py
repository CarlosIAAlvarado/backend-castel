from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import date, timedelta, datetime
from typing import Dict, Any, List, Optional
import uuid
import logging
from app.infrastructure.di.providers import (
    DailyOrchestratorServiceDep,
    SimulationRepositoryDep,
    ClientAccountsServiceDep,
    SelectionServiceDep,
    RotationLogRepositoryDep
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
from app.domain.entities.rotation_log import RotationLog, RotationReason
from app.domain.entities.top16_day import Top16Day
from app.utils.collection_names import get_roi_collection_name, get_top16_collection_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


class SimulationRequest(BaseModel):
    target_date: date = Field(..., description="Fecha final de la simulacion (YYYY-MM-DD). El sistema simulara N dias hacia ATRAS desde esta fecha.")
    window_days: int = Field(7, description="Ventana de dias para calcular ROI (3, 5, 7, 10, 15, 30)", ge=3, le=30)
    update_client_accounts: bool = Field(False, description="Si True, sincroniza cuentas de clientes durante la simulacion")
    simulation_id: Optional[str] = Field(None, description="ID de la simulacion (se genera automaticamente si no se proporciona)")
    dry_run: bool = Field(False, description="Si True, simula sin guardar cambios en client accounts")

    class Config:
        json_schema_extra = {
            "example": {
                "target_date": "2025-10-07",
                "window_days": 7,
                "update_client_accounts": True,
                "simulation_id": "sim_7d_2025-10-07",
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


@router.get("/available-dates")
async def get_available_dates() -> Dict[str, Any]:
    """
    Obtiene el rango de fechas disponibles para ejecutar simulaciones.

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


@router.post("/run")
async def run_simulation(
    request: SimulationRequest,
    orchestrator_service: DailyOrchestratorServiceDep,
    simulation_repo: SimulationRepositoryDep,
    client_accounts_service: ClientAccountsServiceDep,
    selection_service: SelectionServiceDep,
    rotation_log_repo: RotationLogRepositoryDep
) -> Dict[str, Any]:
    print("\n" + "="*80)
    print(f"[SIMULACION INICIADA] window_days={request.window_days}, target_date={request.target_date}")
    print("="*80 + "\n")
    logger.info(f"[SIMULACION] Recibida solicitud: window_days={request.window_days}, target_date={request.target_date}")

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

        # Convertir createdAt a date
        min_date_balance = date.fromisoformat(str(min_balance["createdAt"])[:10])
        max_date_balance = date.fromisoformat(str(max_balance["createdAt"])[:10])
        min_date_movement = date.fromisoformat(str(min_movement["createdAt"])[:10])
        max_date_movement = date.fromisoformat(str(max_movement["createdAt"])[:10])

        # Validar que target_date este en el rango disponible
        min_date = min_date_balance
        max_date = min(max_date_balance, max_date_movement)

        if request.target_date > max_date:
            raise HTTPException(
                status_code=400,
                detail=f"La fecha objetivo no puede ser mayor a {max_date.isoformat()}"
            )

        # NUEVA LOGICA: Calcular ROI con ventana dinámica para UNA SOLA FECHA
        # Si target_date = 07/10 y window_days = 15, entonces:
        # - Ventana ROI: 23/09 a 07/10 (15 días)
        # - NO se simula múltiples días
        target_date = request.target_date
        window_start = target_date - timedelta(days=request.window_days - 1)  # window_days incluye target_date

        # Validar que haya datos suficientes para la ventana ROI
        if window_start < min_date_movement:
            raise HTTPException(
                status_code=400,
                detail=f"No hay suficientes datos historicos. Para calcular ROI_{request.window_days}D hasta {target_date.isoformat()}, "
                       f"se necesitan datos desde {window_start.isoformat()}, pero solo hay datos desde {min_date_movement.isoformat()}. "
                       f"Selecciona una fecha >= {(min_date_movement + timedelta(days=request.window_days)).isoformat()}"
            )

        # Log para debugging
        logger.info(f"=== INICIANDO SIMULACION ROI_{request.window_days}D ===")
        logger.info(f"target_date seleccionado: {target_date}")
        logger.info(f"Ventana ROI: {window_start} -> {target_date}")
        logger.info(f"Total días en ventana: {request.window_days}")
        logger.info(f"Colección ROI: {get_roi_collection_name(request.window_days)}")
        logger.info(f"Colección Top16: {get_top16_collection_name(request.window_days)}")
        logger.info(f"======================================")

        # LIMPIAR COLECCIONES TEMPORALES ANTES DE CALCULAR
        # Preservar: balances, mov07.10 (datos historicos reales)
        # Usar nombres dinámicos basados en window_days
        roi_collection_name = get_roi_collection_name(request.window_days)
        top16_collection_name = get_top16_collection_name(request.window_days)

        collections_to_clean = [
            "agent_states",
            "assignments",
            "rotation_log",
            top16_collection_name,  # Dinámico: top16_7d, top16_30d, etc.
            "daily_roi_calculation",
            roi_collection_name,  # Dinámico: agent_roi_7d, agent_roi_30d, etc.
            # Limpiar tablas de Client Accounts para nueva simulación
            "cuentas_clientes_trading",
            "historial_asignaciones_clientes",
            "snapshots_clientes",
            "rebalanceo_log"
        ]

        cleaned_collections = []
        for collection_name in collections_to_clean:
            result = db[collection_name].delete_many({})
            cleaned_collections.append({
                "collection": collection_name,
                "deleted_count": result.deleted_count
            })

        logger.info(f"Colecciones limpiadas (window={request.window_days}d): {cleaned_collections}")

        # ===================================================================
        # CREAR CUENTAS VACIAS (si update_client_accounts=True)
        # ===================================================================
        # NOTA: Solo creamos las cuentas SIN agentes asignados ni historial.
        # La redistribucion automatica al Top16 se hara en el primer dia
        # cuando se ejecute sync_with_simulation_day()
        if request.update_client_accounts and not request.dry_run:
            try:
                logger.info("Creando 1000 cuentas de clientes (sin agentes asignados)...")
                from datetime import datetime

                # Crear 1000 cuentas vacías con valores temporales
                # NOTA: Usamos valores temporales (PENDING) porque el schema de MongoDB
                # requiere que estos campos existan. Se sobrescribiran en el primer dia.
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
                        # Valores temporales que se sobrescribiran en el primer dia
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

                # Insertar todas las cuentas
                db["cuentas_clientes_trading"].insert_many(cuentas_vacias)
                logger.info(f"Cuentas creadas: 1000 cuentas sin agentes asignados")
                logger.info("Las cuentas seran redistribuidas automaticamente al Top16 en el primer dia de simulacion")
            except Exception as e:
                logger.error(f"Error al crear cuentas: {str(e)}", exc_info=True)

        # ===================================================================
        # OPTIMIZACION: Ejecutar día por día SIN limpiar cache repetidamente
        # ===================================================================
        # Generar todas las fechas desde window_start hasta target_date
        date_range = []
        current = window_start
        while current <= target_date:
            date_range.append(current)
            current += timedelta(days=1)

        print(f"\n{'='*80}")
        print(f"[LOOP DIAS] Procesando {len(date_range)} días: {date_range[0]} -> {date_range[-1]}")
        print(f"{'='*80}\n")
        logger.info(f"Procesando {len(date_range)} días secuencialmente: {date_range[0]} -> {date_range[-1]}")

        all_results = []
        previous_top16 = None  # Para detectar rotaciones
        total_rotations_detected = 0

        for idx, current_date in enumerate(date_range, 1):
            print(f"[DIA {idx}/{len(date_range)}] Procesando: {current_date}")
            logger.info(f"[{idx}/{len(date_range)}] Procesando fecha: {current_date}")

            # OPTIMIZACION: skip_cache_clear=True para no limpiar cache en cada iteracion
            # El cache ya se limpio arriba en collections_to_clean
            # NUEVO: Agregar parametros de Client Accounts
            simulation_id_to_use = request.simulation_id or f"sim_{request.window_days}d_{request.target_date.isoformat()}"

            day_result = await orchestrator_service.process_single_date(
                target_date=current_date,
                skip_cache_clear=True,
                window_days=request.window_days,
                update_client_accounts=request.update_client_accounts,
                simulation_id=simulation_id_to_use,
                dry_run=request.dry_run
            )

            # Obtener Top 16 del día actual desde la colección dinámica correcta
            top16_collection_name = get_top16_collection_name(request.window_days)
            top16_collection = db[top16_collection_name]

            top16_docs = list(top16_collection.find({"date": current_date.isoformat()}).sort("rank", 1))
            roi_field = f"roi_{request.window_days}d"
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

            print(f"  [DEBUG] previous_top16: {'Existe' if previous_top16 else 'None'} (len={len(previous_top16) if previous_top16 else 0})")
            print(f"  [DEBUG] current_top16: {'Existe' if current_top16 else 'None'} (len={len(current_top16) if current_top16 else 0})")

            # Detectar rotaciones si hay un día anterior
            rotations = []
            rank_changes = []
            if previous_top16 is not None and len(previous_top16) > 0:
                print(f"  [ROTATIONS] Detectando rotaciones para fecha {current_date}")
                print(f"  [ROTATIONS] Previous Top16: {len(previous_top16)} agentes")
                print(f"  [ROTATIONS] Current Top16: {len(current_top16)} agentes")

                # Detectar rotaciones (entradas/salidas del Top 16)
                rotations = selection_service.detect_rotations(
                    previous_top16=previous_top16,
                    current_top16=current_top16,
                    current_date=current_date
                )

                print(f"  [ROTATIONS] Rotaciones detectadas: {len(rotations)}")
                if len(rotations) > 0:
                    for rot in rotations:
                        print(f"    - {rot.get('agent_out')} OUT -> {rot.get('agent_in')} IN (Razón: {rot.get('reason')})")
                else:
                    # Log para debugging: mostrar agentes de ambos días
                    prev_agents = set([a.agent_id for a in previous_top16])
                    curr_agents = set([a.agent_id for a in current_top16])
                    logger.info(f"[ROTATIONS] No se detectaron cambios. Agentes anteriores == Agentes actuales: {prev_agents == curr_agents}")
                    if prev_agents != curr_agents:
                        logger.warning(f"[ROTATIONS] ATENCIÓN: Los agentes son diferentes pero no se detectaron rotaciones!")
                        logger.warning(f"[ROTATIONS]   Solo en anterior: {prev_agents - curr_agents}")
                        logger.warning(f"[ROTATIONS]   Solo en actual: {curr_agents - prev_agents}")

                # Guardar rotaciones en rotation_log
                if rotations:
                    for rotation_data in rotations:
                        try:
                            rotation_entity = RotationLog(
                                date=rotation_data["date"],
                                agent_out=rotation_data["agent_out"],
                                agent_in=rotation_data["agent_in"],
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

                # Detectar cambios de ranking (movimientos internos dentro del Top 16)
                rank_changes = selection_service.detect_rank_changes(
                    previous_top16=previous_top16,
                    current_top16=current_top16,
                    current_date=current_date
                )

                # Guardar rank changes en rank_changes collection
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

            # Actualizar previous_top16 para el siguiente día
            previous_top16 = current_top16

            logger.info(
                f"[{idx}/{len(date_range)}] Completado: {current_date} "
                f"({len(rotations)} rotaciones, {len(rank_changes)} cambios de ranking)"
            )

        # Usar el resultado del último día como resultado principal
        result = all_results[-1]["result"] if all_results else {}

        # Calcular total de rank changes
        total_rank_changes = sum(r.get("rank_changes_detected", 0) for r in all_results)

        logger.info(
            f"Total detectado en todo el período: "
            f"{total_rotations_detected} rotaciones, {total_rank_changes} cambios de ranking"
        )

        # NOTA: La inicializacion y redistribucion ahora se hace ANTES del loop de simulacion
        # para que las cuentas esten disponibles desde el primer dia.
        # Este codigo se mantiene comentado como respaldo pero ya no se usa.

        # # VERIFICAR E INICIALIZAR CUENTAS SI ES NECESARIO
        # try:
        #     cuentas_count = client_accounts_service.cuentas_trading_col.count_documents({"estado": "activo"})
        #     if cuentas_count < 1000:
        #         cuentas_faltantes = 1000 - cuentas_count
        #         logger.info(f"Solo hay {cuentas_count} cuentas activas. Creando {cuentas_faltantes} cuentas para completar 1000...")
        #         init_result = client_accounts_service.initialize_client_accounts(
        #             simulation_id="auto_init",
        #             num_accounts=cuentas_faltantes,
        #             num_top_agents=16
        #         )
        #         logger.info(f"Inicialización completada: {init_result.get('cuentas_creadas', 0)} cuentas creadas. Total: {cuentas_count + init_result.get('cuentas_creadas', 0)} cuentas")
        # except Exception as e:
        #     logger.warning(f"No se pudieron inicializar cuentas automáticamente: {str(e)}")

        # # REDISTRIBUIR CUENTAS AL TOP16 AUTOMATICAMENTE
        # redistribution_result = None
        # try:
        #     logger.info("Redistribuyendo cuentas al Top16 automáticamente...")
        #     redistribution_result = client_accounts_service.redistribute_accounts_to_top16(
        #         target_date=target_date.isoformat(),
        #         window_days=request.window_days
        #     )
        #     logger.info(
        #         f"Redistribución completada: {redistribution_result.get('cuentas_reasignadas', 0)} "
        #         f"cuentas reasignadas a {redistribution_result.get('num_agentes_top16', 0)} agentes"
        #     )
        # except Exception as e:
        #     logger.error(f"Error al redistribuir cuentas: {str(e)}", exc_info=True)
        #     # No propagamos el error - la simulacion se ejecuto correctamente
        #     redistribution_result = {"error": str(e), "cuentas_reasignadas": 0}

        # # ACTUALIZAR ROI DE CUENTAS DE CLIENTES AUTOMATICAMENTE
        # roi_update_result = None
        # try:
        #     logger.info("Actualizando ROI de cuentas de clientes automáticamente...")
        #     roi_update_result = client_accounts_service.update_client_accounts_roi(
        #         simulation_id="auto_update",
        #         window_days=request.window_days
        #     )
        #     logger.info(f"ROI actualizado: {roi_update_result.get('cuentas_actualizadas', 0)} cuentas")
        # except Exception as e:
        #     logger.error(f"Error al actualizar ROI de cuentas: {str(e)}", exc_info=True)
        #     # No propagamos el error - la simulacion se ejecuto correctamente
        #     roi_update_result = {"error": str(e), "cuentas_actualizadas": 0}

        redistribution_result = None
        roi_update_result = None

        # GUARDAR RESUMEN DE SIMULACION (opcional - no afecta la ejecucion)
        simulation_id = None
        try:
            simulation_id = str(uuid.uuid4())

            # Verificar limite de 50 simulaciones
            total_simulations = simulation_repo.count()
            if total_simulations >= 50:
                logger.warning("Limite de 50 simulaciones alcanzado. No se guardara esta simulacion.")
            else:
                # Obtener Top 16 final primero
                top16_data = _get_top16_final(db, target_date, request.window_days)

                # Extraer IDs de los Top 16 agentes
                top16_agent_ids = [agent.agent_id for agent in top16_data]

                # Obtener KPIs calculados SOLO para los Top 16
                summary_data = await _get_summary_kpis(db, target_date, top16_agent_ids, request.window_days)

                # Obtener resumen de rotaciones
                rotations_data = _get_rotations_summary(db, window_start, target_date)

                # Calcular metricas diarias para la ventana completa
                daily_metrics_data = _calculate_daily_metrics(db, window_start, target_date, top16_agent_ids, request.window_days)

                # Crear entidad Simulation
                simulation = Simulation(
                    simulation_id=simulation_id,
                    name=f"ROI_{request.window_days}D {target_date.isoformat()}",
                    description=None,
                    created_at=datetime.now(),
                    config=SimulationConfig(
                        target_date=target_date,
                        start_date=window_start,
                        days_simulated=request.window_days,
                        fall_threshold=3,
                        stop_loss_threshold=-0.10
                    ),
                    kpis=summary_data,
                    top_16_final=top16_data,
                    rotations_summary=rotations_data,
                    daily_metrics=daily_metrics_data
                )

                # Guardar simulacion
                saved_simulation = simulation_repo.create(simulation)
                logger.info(f"Resumen de simulacion guardado con ID: {simulation_id}")
        except Exception as e:
            logger.error(f"Error al guardar resumen de simulacion: {str(e)}", exc_info=True)
            # No propagamos el error - la simulacion se ejecuto correctamente
            simulation_id = None  # Resetear para indicar que no se guardo

        # GUARDAR CONFIGURACION DE LA ULTIMA SIMULACION
        try:
            system_config_col = db["system_config"]
            system_config_col.update_one(
                {"config_key": "last_simulation"},
                {
                    "$set": {
                        "config_key": "last_simulation",
                        "window_days": request.window_days,
                        "target_date": target_date.isoformat(),
                        "window_start": window_start.isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                },
                upsert=True
            )
            logger.info(f"Configuración de última simulación guardada: window_days={request.window_days}")
        except Exception as e:
            logger.error(f"Error al guardar configuración de última simulación: {str(e)}")

        # GUARDAR SNAPSHOT DE CLIENT ACCOUNTS SIMULATION
        client_accounts_snapshot_info = None
        if request.update_client_accounts and not request.dry_run:
            try:
                logger.info("Guardando snapshot de Client Accounts simulation...")
                simulation_id_to_use = request.simulation_id or f"sim_{request.window_days}d_{request.target_date.isoformat()}"

                # Calcular metadata adicional
                metadata = {
                    "window_days": request.window_days,
                    "target_date": target_date.isoformat(),
                    "window_start": window_start.isoformat(),
                    "total_days_processed": len(all_results),
                    "redistribution": redistribution_result,
                    "roi_update": roi_update_result
                }

                snapshot_result = client_accounts_service.save_simulation_snapshot(
                    simulation_id=simulation_id_to_use,
                    simulation_date=target_date,
                    window_days=request.window_days,
                    metadata=metadata
                )

                client_accounts_snapshot_info = snapshot_result
                logger.info(f"Snapshot de Client Accounts guardado: {snapshot_result['snapshot_id']}")
            except Exception as e:
                logger.error(f"Error al guardar snapshot de Client Accounts: {str(e)}", exc_info=True)
                # No propagamos el error - la simulación se ejecutó correctamente

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
                "target_date": request.target_date.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": target_date.isoformat(),
                "days_in_window": len(date_range),
                "description": f"Simulación histórica día por día desde {window_start.isoformat()} hasta {target_date.isoformat()}"
            },
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al ejecutar la simulacion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar la simulacion: {str(e)}"
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
    total_roi = sum(doc.get("roi_7d_total", 0.0) for doc in roi_docs)
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
    positive_agents = sum(1 for doc in roi_docs if doc.get("roi_7d_total", 0.0) > 0)
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
    """
    from app.utils.collection_names import get_top16_collection_name
    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = db[top16_collection_name]

    logger.info(f"Obteniendo Top 16 final desde coleccion: {top16_collection_name}")

    top16_docs = list(top16_collection.find({
        "date": end_date.isoformat()
    }).sort("rank", 1))

    roi_field = f"roi_{window_days}d"
    return [
        TopAgentSummary(
            rank=doc.get("rank"),
            agent_id=doc.get("agent_id"),
            roi_7d=doc.get(roi_field, 0.0),
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

    rotation_docs = list(rotation_collection.find({
        "date": {
            "$gte": start_date.isoformat(),
            "$lte": end_date.isoformat()
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
    Agrega los daily_rois de los Top 16 agentes desde la coleccion ROI correspondiente.
    """
    from app.utils.collection_names import get_roi_collection_name
    roi_collection_name = get_roi_collection_name(window_days)
    agent_roi_collection = db[roi_collection_name]

    logger.info(f"[DEBUG] _calculate_daily_metrics llamado con:")
    logger.info(f"[DEBUG]   start_date: {start_date}")
    logger.info(f"[DEBUG]   end_date: {end_date}")
    logger.info(f"[DEBUG]   window_days: {window_days}")
    logger.info(f"[DEBUG]   Usando coleccion: {roi_collection_name}")
    logger.info(f"[DEBUG]   top16_agent_ids (total {len(top16_agent_ids)}): {top16_agent_ids[:3]}...")

    # Obtener documentos de la coleccion ROI dinamica para los Top 16 agentes
    # IMPORTANTE: El campo se llama 'userId', no 'agent_id'
    roi_docs = list(agent_roi_collection.find({
        "userId": {"$in": top16_agent_ids},
        "target_date": end_date.isoformat()
    }))

    logger.info(f"[DEBUG] Documentos encontrados en {roi_collection_name}: {len(roi_docs)}")

    if not roi_docs:
        logger.warning(f"No se encontraron datos en {roi_collection_name} para los Top 16 agentes en target_date={end_date}")
        return []

    # Calcular el numero de dias
    num_days = (end_date - start_date).days + 1

    daily_metrics = []
    cumulative_roi = 0.0

    for day_index in range(num_days):
        current_date = start_date + timedelta(days=day_index)

        # Sumar el ROI del dia para todos los Top 16 agentes
        daily_roi_sum = 0.0
        active_agents = 0
        total_pnl = 0.0

        for doc in roi_docs:
            daily_rois_list = doc.get("daily_rois", [])

            # Verificar que el indice este dentro del rango
            if day_index < len(daily_rois_list):
                day_data = daily_rois_list[day_index]
                roi = day_data.get("roi", 0.0)
                pnl = day_data.get("pnl", 0.0)

                daily_roi_sum += roi
                total_pnl += pnl

                # Contar agentes activos (con ROI != 0)
                if roi != 0.0:
                    active_agents += 1

        cumulative_roi += daily_roi_sum

        daily_metrics.append(DailyMetric(
            date=current_date,
            roi_cumulative=cumulative_roi,
            active_agents=active_agents,
            total_pnl=total_pnl
        ))

    logger.info(f"[DEBUG] daily_metrics generados: {len(daily_metrics)} dias")
    if daily_metrics:
        logger.info(f"[DEBUG] Primer dia: {daily_metrics[0].model_dump()}")
        logger.info(f"[DEBUG] Ultimo dia: {daily_metrics[-1].model_dump()}")

    return daily_metrics
