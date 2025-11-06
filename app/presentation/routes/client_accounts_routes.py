"""
Rutas de API para el microservicio de cuentas de clientes.

Endpoints disponibles:
- POST /api/client-accounts/initialize - Inicializar distribucion
- POST /api/client-accounts/reset - Resetear cuentas para nueva simulacion
- GET /api/client-accounts - Obtener lista de cuentas
- PUT /api/client-accounts/update-roi - Actualizar ROI de cuentas
- POST /api/client-accounts/rebalance - Re-balancear cuentas
- GET /api/client-accounts/history/{cuenta_id} - Historial de una cuenta
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.application.services.client_accounts_service import ClientAccountsService
from app.config.database import database_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client-accounts", tags=["client-accounts"])


# Schemas de request/response
class InitializeRequest(BaseModel):
    """Request para inicializar distribucion de cuentas."""
    simulation_id: str = Field(..., description="ID de la simulacion")
    num_accounts: int = Field(1000, description="Numero de cuentas a distribuir", ge=1)
    num_top_agents: int = Field(16, description="Numero de mejores agentes", ge=1)


class InitializeResponse(BaseModel):
    """Response de inicializacion."""
    simulation_id: str
    total_accounts: int
    total_agents: int
    accounts_per_agent: dict
    snapshot_id: str
    fecha_asignacion: str


class ResetSimulationResponse(BaseModel):
    """Response de reset de simulacion."""
    cuentas_reseteadas: int
    total_cuentas: int
    fecha_reset: str
    balance_inicial_preserved: bool
    historial_limpiado: bool
    snapshots_limpiados: bool


class UpdateRoiRequest(BaseModel):
    """Request para actualizar ROI."""
    simulation_id: str = Field(..., description="ID de la simulacion")


class UpdateRoiResponse(BaseModel):
    """Response de actualizacion de ROI."""
    simulation_id: str
    cuentas_actualizadas: int
    fecha_actualizacion: str


class ClientAccount(BaseModel):
    """Modelo de cuenta de cliente."""
    cuenta_id: str
    nombre_cliente: str
    balance_inicial: float
    balance_actual: float
    roi_total: float
    win_rate: float
    agente_actual: str
    fecha_asignacion_agente: str
    roi_agente_al_asignar: float
    roi_acumulado_con_agente: float
    numero_cambios_agente: int
    estado: str


class ClientAccountsListResponse(BaseModel):
    """Response de lista de cuentas."""
    total: int
    skip: int
    limit: int
    accounts: list[ClientAccount]


# Dependency para obtener el servicio
def get_client_accounts_service() -> ClientAccountsService:
    """
    Dependency para obtener instancia del servicio.

    Returns:
        Instancia de ClientAccountsService
    """
    db = database_manager.get_database()
    return ClientAccountsService(db)


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_client_accounts(
    request: InitializeRequest,
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Inicializa la distribucion de cuentas de clientes para una simulacion.

    Distribuye equitativamente las cuentas entre los Top N agentes.

    Args:
        request: Datos de inicializacion
        service: Servicio de cuentas de clientes

    Returns:
        Resumen de la distribucion inicial

    Raises:
        HTTPException: Si hay error en la inicializacion
    """
    try:
        logger.info(f"Iniciando distribucion para simulacion {request.simulation_id}")

        result = service.initialize_client_accounts(
            simulation_id=request.simulation_id,
            num_accounts=request.num_accounts,
            num_top_agents=request.num_top_agents
        )

        return InitializeResponse(**result)

    except ValueError as e:
        logger.error(f"Error de validacion: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error al inicializar cuentas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/reset", response_model=ResetSimulationResponse)
async def reset_simulation_accounts(
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Resetea todas las cuentas para una nueva simulacion independiente.

    Este endpoint resetea todos los valores de las cuentas EXCEPTO balance_inicial
    que permanece en $1,000. Util para iniciar una nueva simulacion desde cero
    manteniendo las mismas cuentas.

    Resetea:
    - balance_actual -> vuelve a balance_inicial
    - roi_total -> 0.0
    - roi_acumulado_con_agente -> 0.0
    - numero_cambios_agente -> 0
    - win_rate -> 0.0
    - historial_agentes -> limpiado
    - snapshots -> limpiados
    - logs de rebalanceo -> limpiados

    NO modifica:
    - balance_inicial (permanece en $1,000)
    - cuenta_id
    - nombre_cliente
    - created_at

    Args:
        service: Servicio de cuentas de clientes

    Returns:
        Resumen del reset (numero de cuentas reseteadas)

    Raises:
        HTTPException 400: Si no hay cuentas para resetear
        HTTPException 500: Error interno
    """
    try:
        logger.info("Ejecutando reset de simulacion")

        result = service.reset_simulation_accounts()

        logger.info(f"Reset completado: {result['cuentas_reseteadas']} cuentas reseteadas")

        return ResetSimulationResponse(**result)

    except ValueError as e:
        logger.error(f"Error de validacion: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error al resetear cuentas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("")
async def get_client_accounts(
    simulation_id: Optional[str] = Query(None, description="ID de la simulacion (opcional)"),
    skip: int = Query(0, ge=0, description="Numero de registros a omitir"),
    limit: int = Query(1000, ge=1, le=10000, description="Numero maximo de registros"),
    agente_id: Optional[str] = Query(None, description="Filtrar por agente"),
    search: Optional[str] = Query(None, description="Buscar por nombre, email, cuenta_id o agente"),
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Obtiene lista de cuentas de clientes con paginacion y busqueda.

    Compatible con frontend - Devuelve formato esperado con campos renombrados.

    Args:
        simulation_id: ID de la simulacion (opcional)
        skip: Numero de registros a omitir (paginacion)
        limit: Numero maximo de registros a devolver
        agente_id: Filtro opcional por agente
        search: Termino de busqueda (nombre, email, cuenta_id o agente)
        service: Servicio de cuentas de clientes

    Returns:
        Lista de cuentas formateadas (sin historial embebido)

    Raises:
        HTTPException: Si hay error al obtener cuentas
    """
    try:
        logger.info(f"Obteniendo cuentas: skip={skip}, limit={limit}, agente_id={agente_id}, search={search}")

        # Usar el nuevo método del servicio
        accounts = service.get_all_client_accounts_formatted(
            simulation_id=simulation_id,
            skip=skip,
            limit=limit,
            agente_id=agente_id,
            search=search
        )

        return accounts

    except Exception as e:
        logger.error(f"Error al obtener cuentas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.put("/update-roi", response_model=UpdateRoiResponse)
async def update_client_accounts_roi(
    request: UpdateRoiRequest,
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Actualiza el ROI de todas las cuentas de clientes basado en el ROI actual de sus agentes.

    Formula aplicada: ROI_Cliente = (ROI_Agente_Actual - ROI_Agente_Al_Asignar)

    Args:
        request: Datos de actualizacion
        service: Servicio de cuentas de clientes

    Returns:
        Resumen de actualizaciones

    Raises:
        HTTPException: Si hay error al actualizar ROI
    """
    try:
        logger.info(f"Actualizando ROI para simulacion {request.simulation_id}")

        result = service.update_client_accounts_roi(
            simulation_id=request.simulation_id
        )

        return UpdateRoiResponse(**result)

    except Exception as e:
        logger.error(f"Error al actualizar ROI: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/stats")
async def get_client_accounts_stats(
    simulation_id: str = Query(..., description="ID de la simulacion"),
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Obtiene estadísticas agregadas de las cuentas de clientes.

    Compatible con frontend - Devuelve formato esperado por ClientAccountStats.

    Args:
        simulation_id: ID de la simulacion
        service: Servicio de cuentas de clientes

    Returns:
        Estadisticas agregadas

    Raises:
        HTTPException: Si hay error al calcular estadisticas
    """
    try:
        logger.info(f"Obteniendo estadisticas para simulacion {simulation_id}")

        # Usar el nuevo método del servicio
        stats = service.get_client_accounts_stats(simulation_id)

        return stats

    except Exception as e:
        logger.error(f"Error al calcular estadisticas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/latest-simulation")
async def get_latest_simulation():
    """
    Obtiene información sobre la última simulación con snapshots.

    Returns:
        Información de la última simulación (simulation_id, fechas disponibles)

    Raises:
        HTTPException 404: Si no hay snapshots
        HTTPException 500: Error interno
    """
    try:
        logger.info("Obteniendo información de la última simulación")

        db = database_manager.get_database()
        snapshots_col = db.client_accounts_snapshots

        # Obtener el snapshot más reciente
        latest_snapshot = snapshots_col.find_one(sort=[("target_date", -1)])

        if not latest_snapshot:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron snapshots en la base de datos"
            )

        simulation_id = latest_snapshot["simulation_id"]

        # Obtener todos los snapshots de esta simulación
        snapshots = list(
            snapshots_col.find({"simulation_id": simulation_id})
            .sort("target_date", 1)
        )

        dates = [s["target_date"] for s in snapshots]

        return {
            "simulation_id": simulation_id,
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "available_dates": dates,
            "total_snapshots": len(snapshots)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener última simulación: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/timeline")
def _validate_timeline_dates(start_date: str, end_date: str) -> tuple[Any, Any]:
    """
    Valida las fechas del timeline.

    Returns:
        tuple: (start_dt, end_dt) como objetos datetime

    Raises:
        HTTPException: Si las fechas son inválidas
    """
    from datetime import datetime

    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de fecha invalido: {e}")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date debe ser menor o igual que end_date")

    return start_dt, end_dt


def _get_snapshots(start_date: str, end_date: str, simulation_id: Optional[str]) -> List[Dict[str, Any]]:
    """
    Obtiene snapshots del rango de fechas especificado.

    Returns:
        Lista de snapshots ordenados por fecha

    Raises:
        HTTPException: Si no se encuentran snapshots
    """
    db = database_manager.get_database()
    snapshots_col = db.client_accounts_snapshots

    query = {
        "target_date": {
            "$gte": start_date,
            "$lte": end_date
        }
    }

    if simulation_id:
        query["simulation_id"] = simulation_id

    snapshots = list(snapshots_col.find(query).sort("target_date", 1))

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron snapshots para el rango {start_date} - {end_date}"
        )

    return snapshots


def _build_aggregate_stats(snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Construye estadísticas agregadas de los snapshots.

    Returns:
        Lista de estadísticas por fecha
    """
    return [
        {
            "date": s["target_date"],
            "balance_total": s["balance_total"],
            "roi_promedio": s["roi_promedio"],
            "cuentas_activas": s["total_cuentas"]
        }
        for s in snapshots
    ]


def _build_account_timeline(cuenta_id: str, snapshots: List[Dict[str, Any]], service: ClientAccountsService) -> List[Dict[str, Any]]:
    """
    Construye el timeline de una cuenta específica.

    Returns:
        Lista con un elemento conteniendo el timeline de la cuenta

    Raises:
        HTTPException: Si no se encuentra la cuenta
    """
    cuenta_timeline = []
    for snapshot in snapshots:
        cuentas_estado = snapshot.get("cuentas_estado", [])
        cuenta_data = next((c for c in cuentas_estado if c["cuenta_id"] == cuenta_id), None)

        if cuenta_data:
            cuenta_timeline.append({
                "date": snapshot["target_date"],
                "balance": cuenta_data["balance"],
                "roi": cuenta_data["roi"],
                "agente": cuenta_data["agente"],
                "evento": None
            })

    if not cuenta_timeline:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontro la cuenta {cuenta_id} en los snapshots"
        )

    # Obtener info básica de la cuenta
    cuenta = service.cuentas_trading_col.find_one({"cuenta_id": cuenta_id})
    if not cuenta:
        raise HTTPException(status_code=404, detail=f"Cuenta {cuenta_id} no encontrada")

    return [{
        "cuenta_id": cuenta_id,
        "nombre_cliente": cuenta["nombre_cliente"],
        "timeline": cuenta_timeline
    }]


async def get_client_accounts_timeline(
    start_date: str = Query(..., description="Fecha inicio (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Fecha fin (YYYY-MM-DD)"),
    simulation_id: Optional[str] = Query(None, description="ID de simulacion"),
    cuenta_id: Optional[str] = Query(None, description="Filtrar por cuenta"),
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Obtiene la evolucion dia a dia de las cuentas de clientes.

    Esta función ha sido refactorizada para reducir complejidad (14 -> ~6).

    Este endpoint devuelve un timeline completo con:
    - Estadisticas agregadas por dia
    - Evolucion de cada cuenta dia a dia
    - Eventos de rotacion marcados

    Args:
        start_date: Fecha inicio en formato YYYY-MM-DD
        end_date: Fecha fin en formato YYYY-MM-DD
        simulation_id: ID de la simulacion (opcional)
        cuenta_id: Filtrar por cuenta especifica (opcional)
        service: Servicio de cuentas de clientes

    Returns:
        Timeline con evolucion diaria de cuentas

    Raises:
        HTTPException 400: Si las fechas son invalidas
        HTTPException 404: Si no se encuentran datos
        HTTPException 500: Error interno
    """
    try:
        logger.info(f"Obteniendo timeline: {start_date} -> {end_date}, simulation_id={simulation_id}")

        # 1. Validar fechas
        _validate_timeline_dates(start_date, end_date)

        # 2. Obtener snapshots
        snapshots = _get_snapshots(start_date, end_date, simulation_id)

        # 3. Construir respuesta
        dates = [s["target_date"] for s in snapshots]
        aggregate_stats = _build_aggregate_stats(snapshots)

        # 4. Construir timeline de cuenta específica si se solicita
        accounts_timeline = []
        if cuenta_id:
            accounts_timeline = _build_account_timeline(cuenta_id, snapshots, service)

        return {
            "simulation_id": simulation_id or snapshots[0].get("simulation_id", "unknown"),
            "start_date": start_date,
            "end_date": end_date,
            "dates": dates,
            "aggregate_stats": aggregate_stats,
            "accounts": accounts_timeline
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener timeline: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/snapshots/{date}")
async def get_snapshot_by_date(
    date: str,
    simulation_id: Optional[str] = Query(None, description="ID de simulacion")
):
    """
    Obtiene el snapshot del estado de las cuentas en una fecha especifica.

    Args:
        date: Fecha en formato YYYY-MM-DD
        simulation_id: ID de simulacion (opcional)

    Returns:
        Snapshot con estado completo de las cuentas

    Raises:
        HTTPException 404: Si no se encuentra snapshot
        HTTPException 500: Error interno
    """
    try:
        logger.info(f"Obteniendo snapshot para fecha {date}, simulation_id={simulation_id}")

        from datetime import datetime

        # Validar formato de fecha
        try:
            datetime.fromisoformat(date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Formato de fecha invalido: {e}")

        db = database_manager.get_database()
        snapshots_col = db.client_accounts_snapshots

        query = {"target_date": date}
        if simulation_id:
            query["simulation_id"] = simulation_id

        snapshot = snapshots_col.find_one(query, sort=[("createdAt", -1)])

        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontro snapshot para la fecha {date}"
            )

        # Calcular mejor y peor cuenta
        cuentas_estado = snapshot.get("cuentas_estado", [])

        mejor_cuenta = None
        peor_cuenta = None

        if cuentas_estado:
            mejor_cuenta = max(cuentas_estado, key=lambda c: c["roi"])
            peor_cuenta = min(cuentas_estado, key=lambda c: c["roi"])

        return {
            "snapshot_id": str(snapshot["_id"]),
            "simulation_id": snapshot["simulation_id"],
            "target_date": snapshot["target_date"],
            "total_cuentas": snapshot["total_cuentas"],
            "balance_total": snapshot["balance_total"],
            "roi_promedio": snapshot["roi_promedio"] * 100,
            "win_rate_promedio": snapshot["win_rate_promedio"] * 100,
            "distribucion_agentes": snapshot["distribucion_agentes"],
            "mejor_cuenta": {
                "cuenta_id": mejor_cuenta["cuenta_id"],
                "balance": mejor_cuenta["balance"],
                "roi": mejor_cuenta["roi"] * 100,
                "agente": mejor_cuenta["agente"]
            } if mejor_cuenta else None,
            "peor_cuenta": {
                "cuenta_id": peor_cuenta["cuenta_id"],
                "balance": peor_cuenta["balance"],
                "roi": peor_cuenta["roi"] * 100,
                "agente": peor_cuenta["agente"]
            } if peor_cuenta else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener snapshot: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/{cuenta_id}/history-detailed")
async def get_client_account_history_detailed(
    cuenta_id: str,
    simulation_id: Optional[str] = Query(None, description="ID de simulacion"),
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Obtiene el historial DETALLADO de asignaciones de una cuenta.

    A diferencia del endpoint /history/{cuenta_id}, este devuelve informacion
    mas completa con todos los campos necesarios para visualizacion avanzada.

    Args:
        cuenta_id: ID de la cuenta
        simulation_id: ID de simulacion (opcional)
        service: Servicio de cuentas de clientes

    Returns:
        Historial detallado con toda la informacion

    Raises:
        HTTPException 404: Si la cuenta no existe
        HTTPException 500: Error interno
    """
    try:
        logger.info(f"Obteniendo historial detallado de cuenta {cuenta_id}")

        # Reutilizar metodo existente del servicio
        cuenta = service.get_client_account_by_id(cuenta_id)

        # El servicio ya devuelve el formato correcto con historial embebido
        # Solo necesitamos formatear un poco mas para el response

        return {
            "cuenta_id": cuenta["account_id"],
            "nombre_cliente": cuenta["nombre_cliente"],
            "balance_inicial": cuenta["balance_inicial"],
            "balance_actual": cuenta["balance_actual"],
            "roi_total": cuenta["roi_total"],
            "total_asignaciones": len(cuenta["historial"]),
            "historial": [
                {
                    "asignacion_numero": idx + 1,
                    "agente_id": h["agente_id"],
                    "fecha_inicio": h["fecha_inicio"],
                    "fecha_fin": h["fecha_fin"],
                    "dias_con_agente": h.get("dias_con_agente"),
                    "roi_agente_inicio": h["roi_inicial"],
                    "roi_agente_fin": h["roi_final"],
                    "roi_cuenta_ganado": h.get("roi_cuenta_ganado"),
                    "balance_inicio": h["balance_inicial"],
                    "balance_fin": h["balance_final"],
                    "motivo_cambio": h["motivo_cambio"],
                    "detalles_cambio": _get_cambio_detalles(h["motivo_cambio"])
                }
                for idx, h in enumerate(cuenta["historial"])
            ]
        }

    except ValueError as e:
        logger.warning(f"Cuenta no encontrada: {cuenta_id}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Error al obtener historial detallado: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


def _get_cambio_detalles(motivo: str) -> str:
    """Helper para obtener descripcion del motivo de cambio."""
    detalles = {
        "inicial": "Asignacion inicial al crear la cuenta",
        "rotacion": "Agente salio por 3 dias consecutivos de perdida",
        "re-balanceo": "Re-balanceo para optimizar distribucion"
    }
    return detalles.get(motivo, "Cambio manual")


@router.get("/{cuenta_id}")
async def get_client_account_detail(
    cuenta_id: str,
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Obtiene el detalle completo de una cuenta de cliente con su historial embebido.

    Compatible con frontend - Devuelve formato esperado por ClientAccount con historial[].

    Args:
        cuenta_id: ID de la cuenta
        service: Servicio de cuentas de clientes

    Returns:
        ClientAccount con historial embebido

    Raises:
        HTTPException 404: Si la cuenta no existe
        HTTPException 500: Si hay error interno
    """
    try:
        logger.info(f"Obteniendo detalle de cuenta {cuenta_id}")

        # Usar el nuevo método del servicio
        cuenta = service.get_client_account_by_id(cuenta_id)

        return cuenta

    except ValueError as e:
        logger.warning(f"Cuenta no encontrada: {cuenta_id}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Error al obtener cuenta {cuenta_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/history/{cuenta_id}")
async def get_account_history(
    cuenta_id: str,
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Obtiene el historial completo de asignaciones de agentes para una cuenta.

    Args:
        cuenta_id: ID de la cuenta
        service: Servicio de cuentas de clientes

    Returns:
        Historial de asignaciones

    Raises:
        HTTPException: Si hay error al obtener historial
    """
    try:
        logger.info(f"Obteniendo historial para cuenta {cuenta_id}")

        historial = list(
            service.historial_col.find({"cuenta_id": cuenta_id})
            .sort("fecha_inicio", -1)
        )

        return {
            "cuenta_id": cuenta_id,
            "total_asignaciones": len(historial),
            "historial": [
                {
                    "agente_id": h["agente_id"],
                    "fecha_inicio": h["fecha_inicio"].isoformat(),
                    "fecha_fin": h["fecha_fin"].isoformat() if h["fecha_fin"] else None,
                    "roi_agente_inicio": h["roi_agente_inicio"],
                    "roi_agente_fin": h.get("roi_agente_fin"),
                    "roi_cuenta_ganado": h.get("roi_cuenta_ganado"),
                    "balance_inicio": h["balance_inicio"],
                    "balance_fin": h.get("balance_fin"),
                    "motivo_cambio": h["motivo_cambio"],
                    "dias_con_agente": h.get("dias_con_agente")
                }
                for h in historial
            ]
        }

    except Exception as e:
        logger.error(f"Error al obtener historial: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


class RebalanceRequest(BaseModel):
    """Request para re-balanceo de cuentas."""
    simulation_id: str = Field(..., description="ID de la simulacion")
    max_move_percentage: float = Field(0.30, description="Porcentaje maximo de cuentas a mover", ge=0.0, le=1.0)


class RebalanceResponse(BaseModel):
    """Response de re-balanceo."""
    simulation_id: str
    fecha_rebalanceo: str
    roi_promedio_pre: float
    roi_promedio_post: float
    total_cuentas: int
    cuentas_bajo_promedio: int
    cuentas_movidas: int
    porcentaje_movidas: float
    max_permitido: int
    movimientos: list


@router.post("/rebalance", response_model=RebalanceResponse)
async def rebalance_accounts(
    request: RebalanceRequest,
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Re-balancea cuentas cada 7 dias para equilibrar ROI entre todas las cuentas.

    Algoritmo:
    1. Calcula ROI promedio de todas las cuentas
    2. Identifica cuentas bajo el promedio
    3. Mueve cuentas bajo promedio a agentes con mejor ROI
    4. Limite: No mueve mas del 30% de cuentas (configurable)

    Args:
        request: Datos de re-balanceo
        service: Servicio de cuentas de clientes

    Returns:
        Resumen del re-balanceo con movimientos realizados

    Raises:
        HTTPException: Si hay error al re-balancear
    """
    try:
        logger.info(f"Iniciando re-balanceo para simulacion {request.simulation_id}")

        result = service.rebalance_accounts(
            simulation_id=request.simulation_id,
            max_move_percentage=request.max_move_percentage
        )

        return RebalanceResponse(**result)

    except Exception as e:
        logger.error(f"Error al re-balancear cuentas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


class RotateAgentRequest(BaseModel):
    """Request para rotacion de agente."""
    simulation_id: str = Field(..., description="ID de la simulacion")
    agente_rotado: str = Field(..., description="ID del agente que falla y debe ser rotado")
    agente_sustituto: str = Field(..., description="ID del agente que lo reemplaza")


class RotateAgentResponse(BaseModel):
    """Response de rotacion de agente."""
    simulation_id: str
    agente_rotado: str
    agente_sustituto: str
    cuentas_redistribuidas: int
    fecha_rotacion: str
    roi_agente_rotado: float | None
    roi_agente_sustituto: float
    distribucion_actual: dict


@router.post("/rotate-agent", response_model=RotateAgentResponse)
async def rotate_failed_agent(
    request: RotateAgentRequest,
    service: ClientAccountsService = Depends(get_client_accounts_service)
):
    """
    Rota un agente que ha fallado y redistribuye sus cuentas a un agente sustituto.

    Criterios de falla de un agente:
    - 3 dias consecutivos de perdidas
    - ROI del agente cae a -10% o menos

    El proceso:
    1. Obtiene todas las cuentas del agente rotado
    2. Cierra los registros en el historial
    3. Reasigna todas las cuentas al agente sustituto
    4. Mantiene el ROI historico de cada cuenta
    5. Crea snapshot de la nueva distribucion

    Args:
        request: Datos de rotacion (agente_rotado, agente_sustituto)
        service: Servicio de cuentas de clientes

    Returns:
        Resumen de la rotacion con cuentas redistribuidas

    Raises:
        HTTPException: Si hay error al rotar agente
    """
    try:
        logger.info(
            f"Rotando agente {request.agente_rotado} por {request.agente_sustituto}"
        )

        result = service.rotate_failed_agent(
            simulation_id=request.simulation_id,
            agente_rotado=request.agente_rotado,
            agente_sustituto=request.agente_sustituto
        )

        return RotateAgentResponse(**result)

    except ValueError as e:
        logger.error(f"Error de validacion: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error al rotar agente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# ========== NUEVOS ENDPOINTS - INTEGRACION CON SIMULACION ==========

class SyncWithSimulationRequest(BaseModel):
    """Request para sincronizacion manual."""
    simulation_id: str = Field(..., description="ID de la simulacion")
    target_date: str = Field(..., description="Fecha objetivo (YYYY-MM-DD)")
    window_days: int = Field(7, description="Ventana de dias para ROI", ge=3, le=30)
    dry_run: bool = Field(False, description="Si True, simula sin guardar")


class SyncWithSimulationResponse(BaseModel):
    """Response de sincronizacion."""
    success: bool
    simulation_id: str
    target_date: str
    cuentas_actualizadas: int
    cuentas_redistribuidas: int
    rotaciones_procesadas: int
    snapshot_id: Optional[str]
    fecha_sincronizacion: str
    estadisticas: dict


@router.post("/sync-with-simulation", response_model=SyncWithSimulationResponse)
async def sync_with_simulation(
    request: SyncWithSimulationRequest
):
    """
    Sincroniza manualmente las cuentas con el estado actual de la simulacion.

    Este endpoint permite ejecutar el proceso de sincronizacion de forma manual
    para una fecha especifica. Util para:
    - Re-procesar un dia especifico
    - Corregir datos
    - Testing

    Args:
        request: Datos de sincronizacion

    Returns:
        Resultado de la sincronizacion

    Raises:
        HTTPException 400: Parametros invalidos
        HTTPException 500: Error interno
    """
    try:
        logger.info(f"Sincronizacion manual solicitada: {request.simulation_id}, {request.target_date}")

        from datetime import datetime
        from app.application.services.client_accounts_simulation_service import ClientAccountsSimulationService

        # Validar fecha
        try:
            target_date = datetime.fromisoformat(request.target_date).date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Formato de fecha invalido: {e}")

        # Crear servicio de sincronizacion
        db = database_manager.get_database()
        sync_service = ClientAccountsSimulationService(db)

        # Ejecutar sincronizacion
        result = await sync_service.sync_with_simulation_day(
            target_date=target_date,
            simulation_id=request.simulation_id,
            window_days=request.window_days,
            dry_run=request.dry_run
        )

        return SyncWithSimulationResponse(
            success=True,
            simulation_id=request.simulation_id,
            target_date=request.target_date,
            cuentas_actualizadas=result.cuentas_actualizadas,
            cuentas_redistribuidas=result.cuentas_redistribuidas,
            rotaciones_procesadas=result.rotaciones_procesadas,
            snapshot_id=result.snapshot_id,
            fecha_sincronizacion=result.timestamp.isoformat(),
            estadisticas={
                "balance_total_antes": result.balance_total_antes,
                "balance_total_despues": result.balance_total_despues,
                "roi_promedio_antes": result.roi_promedio_antes,
                "roi_promedio_despues": result.roi_promedio_despues
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en sincronizacion manual: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
