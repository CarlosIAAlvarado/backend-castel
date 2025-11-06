from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Dict, Any, Optional, List
from app.infrastructure.di.providers import AgentStateRepositoryDep, AssignmentRepositoryDep, RotationLogRepositoryDep
from app.config.database import database_manager
import logging

logger = logging.getLogger("trading_simulation.reports_routes")
router = APIRouter(prefix="/api/reports", tags=["Reports"])


# ============================================================================
# FUNCIONES AUXILIARES PARA REDUCIR COMPLEJIDAD DE get_summary_report
# ============================================================================

def _get_window_days_from_config() -> int:
    """
    Obtiene window_days de la última simulación ejecutada.

    Estrategia:
    1. Lee window_days de system_config
    2. Verifica que daily_roi_calculation tenga datos
    3. Si no tiene datos, intenta inferir de agent_roi_*d collections
    """
    db = database_manager.get_database()
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})

    # Primero, verificar si daily_roi_calculation tiene datos
    daily_roi_collection = db["daily_roi_calculation"]
    if daily_roi_collection.count_documents({}, limit=1) > 0:
        # Si system_config tiene window_days, usarlo
        if config and "window_days" in config:
            window_days_from_config = config["window_days"]
            logger.info(f"window_days encontrado en system_config: {window_days_from_config} días")
            logger.info(f"Verificado: daily_roi_calculation tiene datos")
            return window_days_from_config
        else:
            # Inferir window_days del total_days en system_config
            if config and "total_days" in config:
                total_days = config["total_days"]
                logger.info(f"window_days no encontrado, usando total_days de system_config: {total_days}")
                return total_days
            else:
                logger.warning("system_config incompleto, detectando desde agent_roi collections...")
    else:
        logger.warning("daily_roi_calculation está vacía, detectando desde agent_roi collections...")

    # Fallback: detectar desde agent_roi_*d collections
    from app.utils.collection_names import get_roi_collection_name
    possible_windows = [30, 15, 10, 7, 5, 3]

    for window in possible_windows:
        collection_name = get_roi_collection_name(window)
        collection = db[collection_name]
        if collection.count_documents({}, limit=1) > 0:
            logger.info(f"✓ Auto-detectado window_days={window} (colección {collection_name} tiene datos)")
            return window

    # Si no se encuentra ninguna, usar 7 por defecto
    logger.warning("No se pudo detectar window_days, usando 7 por defecto")
    return 7


def _get_date_range_from_roi_collection(roi_collection, end_date: Optional[date], window_days: int) -> tuple[Optional[date], Optional[date]]:
    """
    Obtiene el rango de fechas desde la colección ROI.

    Returns:
        tuple[start_date, end_date]
    """
    if not end_date:
        latest_doc = roi_collection.find_one(sort=[("target_date", -1)])
        if not latest_doc:
            return None, None

        end_date = date.fromisoformat(latest_doc["target_date"])
        if "window_start" in latest_doc:
            start_date = date.fromisoformat(latest_doc["window_start"])
        else:
            start_date = end_date - timedelta(days=window_days - 1)
    else:
        start_date = end_date - timedelta(days=window_days - 1)

    return start_date, end_date


def _calculate_agent_balances(assignments) -> Dict[str, float]:
    """Calcula el balance total por agente desde asignaciones."""
    agent_balances = {}
    for assignment in assignments:
        agent_id = assignment.agent_id
        agent_balances[agent_id] = agent_balances.get(agent_id, 0.0) + assignment.balance
    return agent_balances


def _calculate_kpis_from_roi_docs(roi_docs, agent_balances: Dict[str, float]) -> Dict[str, Any]:
    """
    Calcula todos los KPIs desde los documentos ROI.

    NOTA: Todos los documentos agent_roi_* usan el campo 'roi_7d_total' independientemente
    de la ventana (3d, 5d, 7d, 30d, etc). El nombre es legacy pero el campo existe en todas.

    Returns:
        Dict con: total_roi, average_roi, max_drawdown, max_drawdown_agent, volatility, win_rate
    """
    total_balance = sum(agent_balances.values()) if agent_balances else 1.0
    weighted_roi_sum = 0.0
    simple_roi_sum = 0.0
    all_daily_rois = []
    agent_drawdowns = []
    positive_roi_count = 0

    for doc in roi_docs:
        userId = doc.get("userId")
        # El campo siempre se llama 'roi_7d_total' incluso en agent_roi_30d, agent_roi_3d, etc.
        roi_total = doc.get("roi_7d_total", 0.0)
        daily_rois = doc.get("daily_rois", [])

        # ROI Total (ponderado por balance)
        balance = agent_balances.get(userId, 0.0)
        weight = balance / total_balance if total_balance > 0 else 0.0
        weighted_roi_sum += roi_total * weight

        # ROI Promedio (simple)
        simple_roi_sum += roi_total

        # Win Rate
        if roi_total > 0:
            positive_roi_count += 1

        # Volatilidad (recolectar todos los ROIs diarios)
        for day in daily_rois:
            roi_day = day.get("roi", 0.0)
            if roi_day != 0:
                all_daily_rois.append(roi_day)

        # Max Drawdown (calcular para cada agente)
        if len(daily_rois) >= 2:
            cumulative = [1.0]
            for day in daily_rois:
                roi = day.get("roi", 0)
                cumulative.append(cumulative[-1] * (1 + roi))

            peak = cumulative[0]
            max_dd = 0.0

            for value in cumulative:
                if value > peak:
                    peak = value
                if peak > 0:
                    drawdown = (value - peak) / peak
                    if drawdown < max_dd:
                        max_dd = drawdown

            agent_drawdowns.append({"userId": userId, "drawdown": max_dd})

    # Calcular métricas finales
    num_agents = len(roi_docs)
    total_roi = weighted_roi_sum
    average_roi = simple_roi_sum / num_agents if num_agents > 0 else 0.0

    # Max Drawdown
    if agent_drawdowns:
        worst_agent = min(agent_drawdowns, key=lambda x: x["drawdown"])
        max_drawdown = worst_agent["drawdown"]
        max_drawdown_agent = worst_agent["userId"]
    else:
        max_drawdown = 0.0
        max_drawdown_agent = None

    # Volatilidad
    if all_daily_rois and len(all_daily_rois) > 1:
        mean_roi = sum(all_daily_rois) / len(all_daily_rois)
        variance = sum((x - mean_roi) ** 2 for x in all_daily_rois) / (len(all_daily_rois) - 1)
        volatility = variance**0.5
    else:
        volatility = 0.0

    # Win Rate
    win_rate = positive_roi_count / num_agents if num_agents > 0 else 0.0

    return {
        "total_roi": round(total_roi, 4),
        "average_roi": round(average_roi, 4),
        "max_drawdown": round(max_drawdown, 4),
        "max_drawdown_agent": max_drawdown_agent,
        "volatility": round(volatility, 4),
        "win_rate": round(win_rate, 4),
        "unique_agents_in_period": num_agents,
    }


def _get_active_agents(top16_collection, state_repo, end_date: date) -> list[str]:
    """Obtiene la lista de agentes activos únicos (is_in_casterly=True)."""
    top16_docs = list(top16_collection.find({"date": end_date.isoformat()}))

    # CORRECCION: Usar SET para obtener agentes UNICOS (sin duplicados)
    # Esto resuelve el bug donde se contaban 144 agentes en lugar de 16
    active_agents_set = {doc["agent_id"] for doc in top16_docs if doc.get("is_in_casterly", False)}
    active_agents_final = list(active_agents_set)

    logger.info(f"Agentes activos únicos encontrados en top16 para {end_date.isoformat()}: {len(active_agents_final)}")

    # Fallback a agent_states si la colección dinámica está vacía
    if not active_agents_final:
        states_final = state_repo.get_by_date(end_date)
        active_agents_final = [s.agent_id for s in states_final if s.is_in_casterly]
        logger.info(f"Usando fallback a agent_states: {len(active_agents_final)} agentes activos")

    return active_agents_final


async def _calculate_dynamic_roi(
    target_date: date,
    requested_window_days: int,
    executed_window_days: int
) -> list[Dict[str, Any]]:
    """
    Calcula ROI dinámicamente para una ventana solicitada usando datos de daily_roi_calculation.

    Args:
        target_date: Fecha objetivo (fecha final de la ventana)
        requested_window_days: Ventana solicitada (3, 5, 7, 10, 15 días)
        executed_window_days: Ventana de la simulación ejecutada (ej: 30 días) - NO USADO, se usa daily_roi_calculation directamente

    Returns:
        Lista de documentos ROI calculados dinámicamente
    """
    from datetime import timedelta

    db = database_manager.get_database()

    # IMPORTANTE: La colección se llama "daily_roi_calculation" (sin sufijo _Xd)
    # Esta es una colección temporal que contiene TODOS los días de la simulación ejecutada
    daily_roi_collection_name = "daily_roi_calculation"
    daily_roi_collection = db[daily_roi_collection_name]

    # Calcular fechas del rango de la ventana solicitada
    start_date = target_date - timedelta(days=requested_window_days - 1)

    logger.info(f"Calculando ROI dinámico desde {start_date.isoformat()} hasta {target_date.isoformat()}")

    # Obtener todos los ROIs diarios en el rango
    daily_roi_docs = list(daily_roi_collection.find({
        "date": {
            "$gte": start_date.isoformat(),
            "$lte": target_date.isoformat()
        }
    }))

    logger.info(f"Encontrados {len(daily_roi_docs)} documentos en {daily_roi_collection_name} para el rango {start_date.isoformat()} - {target_date.isoformat()}")

    if not daily_roi_docs:
        # Intentar obtener cualquier documento para verificar qué fechas existen
        sample_doc = daily_roi_collection.find_one()
        if sample_doc:
            logger.warning(f"Colección {daily_roi_collection_name} tiene datos, ejemplo de fecha: {sample_doc.get('date')}")
        else:
            logger.warning(f"Colección {daily_roi_collection_name} está completamente vacía")
        return []

    # Agrupar por userId (identificador del agente) y calcular ROI acumulado
    # También guardar el ROI del último día y la fecha de cada ROI
    agent_daily_rois = {}
    for doc in daily_roi_docs:
        # daily_roi_calc usa "userId" como identificador del agente
        agent_id = doc.get("userId") or doc.get("agent_id")
        daily_roi = doc.get("roi_day", 0.0)
        doc_date = doc.get("date")

        if not agent_id:
            continue  # Skip si no tiene identificador

        if agent_id not in agent_daily_rois:
            agent_daily_rois[agent_id] = []
        agent_daily_rois[agent_id].append({
            "roi": daily_roi,
            "date": doc_date
        })

    # Calcular ROI acumulado para cada agente
    roi_docs = []
    for agent_id, daily_roi_list in agent_daily_rois.items():
        # Ordenar por fecha para asegurar el orden correcto
        daily_roi_list_sorted = sorted(daily_roi_list, key=lambda x: x["date"])

        # ROI acumulado = (1 + roi_day1) * (1 + roi_day2) * ... - 1
        roi_accumulated = 1.0
        for item in daily_roi_list_sorted:
            roi_accumulated *= (1.0 + item["roi"])
        roi_accumulated -= 1.0

        # El ROI del último día es el del día más reciente
        last_day_roi = daily_roi_list_sorted[-1]["roi"] if daily_roi_list_sorted else 0.0

        # Crear array de daily_rois en el formato esperado por el frontend
        # Formato: [{"date": "2025-10-05", "roi": 0.005}, {"date": "2025-10-06", "roi": -0.002}, ...]
        daily_rois_array = [
            {
                "date": item["date"],
                "roi": item["roi"]
            }
            for item in daily_roi_list_sorted
        ]

        roi_docs.append({
            "agent_id": agent_id,
            "userId": agent_id,  # Agregar userId para compatibilidad
            "target_date": target_date.isoformat(),
            "window_start": start_date.isoformat(),
            "window_end": target_date.isoformat(),
            f"roi_{requested_window_days}d": roi_accumulated,
            "roi_7d_total": roi_accumulated,  # Campo legacy para compatibilidad (se usa en _calculate_kpis_from_roi_docs)
            "roi_day": last_day_roi,  # ROI del último día
            "daily_rois": daily_rois_array,  # Array con el ROI de cada día
            "window_days": requested_window_days
        })

    logger.info(f"ROI dinámico calculado para {len(roi_docs)} agentes (con daily_rois de {requested_window_days} días)")
    return roi_docs


@router.get("/summary")
async def get_summary_report(
    start_date: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    window_days: Optional[int] = Query(None, description="Ventana de dias para ROI (3, 5, 7, 10, 15, 30)"),
    assignment_repo: AssignmentRepositoryDep = None,
    rotation_log_repo: RotationLogRepositoryDep = None,
    state_repo: AgentStateRepositoryDep = None,
) -> Dict[str, Any]:
    """
    Calcula KPIs del resumen ejecutivo usando agent_roi_XD como fuente principal.
    Usa el parametro window_days si se especifica, sino lee de la ultima simulacion ejecutada.

    Esta función ha sido refactorizada para reducir complejidad (22 -> ~8).
    """
    try:
        # 1. Obtener configuración de ventana solicitada y ventana de la simulación ejecutada
        requested_window_days = window_days
        if not requested_window_days:
            requested_window_days = _get_window_days_from_config()
        else:
            logger.info(f"Usando ventana especificada por parametro: {requested_window_days} dias")

        # Obtener window_days de la simulación ejecutada (puede ser diferente)
        executed_window_days = _get_window_days_from_config()

        # 2. Intentar usar colecciones de la ventana solicitada, con fallback a la ejecutada
        from app.utils.collection_names import get_roi_collection_name, get_top16_collection_name

        # Intentar con la ventana solicitada
        roi_collection_name = get_roi_collection_name(requested_window_days)
        top16_collection_name = get_top16_collection_name(requested_window_days)

        roi_collection = database_manager.get_collection(roi_collection_name)
        top16_collection = database_manager.get_collection(top16_collection_name)

        # Verificar si existen datos, si no, usar la colección de la simulación ejecutada
        if not roi_collection.find_one():
            logger.warning(f"No se encontraron datos en {roi_collection_name}, usando colección de simulación ejecutada: agent_roi_{executed_window_days}d")
            roi_collection_name = get_roi_collection_name(executed_window_days)
            top16_collection_name = get_top16_collection_name(executed_window_days)
            roi_collection = database_manager.get_collection(roi_collection_name)
            top16_collection = database_manager.get_collection(top16_collection_name)
            # Mantenemos requested_window_days para el cálculo dinámico
            window_days = requested_window_days
        else:
            window_days = requested_window_days

        # 3. Determinar rango de fechas
        # PRIORIDAD:
        # 1. Si el usuario especificó fechas (date picker) → USAR ESAS FECHAS
        # 2. Si no especificó fechas → Usar system_config como default
        db = database_manager.get_database()
        system_config_col = db["system_config"]
        config = system_config_col.find_one({"config_key": "last_simulation"})

        if start_date and end_date:
            # El usuario especificó fechas manualmente → RESPETAR SU SELECCIÓN
            logger.info(f"Usando rango de fechas especificado por el usuario: {start_date} a {end_date} (ventana: {window_days}D)")

            # Validar que las fechas estén dentro de la simulación ejecutada
            if config and "start_date" in config and "end_date" in config:
                simulation_start = date.fromisoformat(config["start_date"])
                simulation_end = date.fromisoformat(config["end_date"])

                if start_date < simulation_start or end_date > simulation_end:
                    logger.warning(f"Las fechas seleccionadas ({start_date} a {end_date}) están fuera del rango de la simulación ({simulation_start} a {simulation_end})")
        else:
            # El usuario NO especificó fechas → Usar system_config como default
            if not config or "start_date" not in config or "end_date" not in config:
                # Último fallback: leer de la colección ROI
                logger.warning("No hay system_config, leyendo de colección ROI")
                start_date, end_date = _get_date_range_from_roi_collection(roi_collection, end_date, window_days)
            else:
                # Usar las fechas de la última simulación ejecutada
                simulation_start = date.fromisoformat(config["start_date"])
                simulation_end = date.fromisoformat(config["end_date"])

                # Calcular el rango según la ventana solicitada desde el final
                # El end_date es el último día de la simulación
                # El start_date es end_date - (window_days - 1)
                end_date = simulation_end
                start_date = end_date - timedelta(days=window_days - 1)

                # Validar que start_date no sea anterior al inicio de la simulación
                if start_date < simulation_start:
                    logger.warning(f"Ventana de {window_days} días excede el inicio de la simulación. Ajustando start_date de {start_date} a {simulation_start}")
                    start_date = simulation_start

                logger.info(f"Usando rango de fechas por defecto (final de simulación): {start_date} a {end_date} (ventana: {window_days}D)")

        if not end_date:
            # FALLBACK: Si no hay datos en la coleccion ROI dinamica, usar top16
            logger.warning(
                f"No se encontraron datos en {roi_collection_name}, usando {top16_collection_name} como fallback"
            )
            latest_top16 = top16_collection.find_one(sort=[("date", -1)])
            if not latest_top16:
                raise HTTPException(
                    status_code=404,
                    detail=f"No se encontraron datos en {roi_collection_name} ni {top16_collection_name}",
                )
            return await _get_summary_from_top16(
                latest_top16["date"], assignment_repo, rotation_log_repo, state_repo, window_days
            )

        # 4. Obtener datos ROI
        # Si la ventana solicitada es diferente a la ejecutada, SIEMPRE calcular dinámicamente
        if requested_window_days != executed_window_days:
            logger.info(f"Ventana solicitada ({requested_window_days}D) diferente a la ejecutada ({executed_window_days}D). Calculando ROI dinámicamente usando daily_roi_calculation")
            roi_docs = await _calculate_dynamic_roi(
                end_date,
                requested_window_days,
                executed_window_days
            )
        else:
            # Si la ventana es la misma, usar los datos precalculados de la colección
            logger.info(f"Buscando datos ROI precalculados para fecha final: {end_date.isoformat()} (ventana: {window_days} dias)")
            roi_docs = list(roi_collection.find({"target_date": end_date.isoformat()}))

            # Si no hay datos precalculados, calcular dinámicamente
            if not roi_docs:
                logger.warning(f"No se encontraron datos precalculados en {roi_collection_name}. Calculando dinámicamente")
                roi_docs = await _calculate_dynamic_roi(
                    end_date,
                    requested_window_days,
                    executed_window_days
                )

        if not roi_docs:
            return {
                "success": False,
                "message": f"No se encontraron datos ROI para la fecha {end_date.isoformat()}"
            }

        logger.info(f"Encontrados {len(roi_docs)} documentos ROI para la fecha {end_date.isoformat()}")

        # 5. Calcular balances por agente
        assignments = list(assignment_repo.get_active_assignments())
        agent_balances = _calculate_agent_balances(assignments)

        # 6. Calcular KPIs principales
        kpis = _calculate_kpis_from_roi_docs(roi_docs, agent_balances)

        # 7. Obtener rotaciones
        rotation_logs = rotation_log_repo.get_by_date_range(start_date, end_date)
        kpis["total_rotations"] = len(rotation_logs)

        # 8. Obtener agentes activos
        # Si calculamos dinámicamente, obtener agentes desde roi_docs (Top 16 por ROI calculado)
        if requested_window_days != executed_window_days:
            # Ordenar roi_docs por ROI y tomar los 16 mejores
            sorted_roi_docs = sorted(roi_docs, key=lambda x: x.get("roi_7d_total", 0.0), reverse=True)
            top_16_agents = sorted_roi_docs[:16]
            active_agents_final = [doc.get("agent_id") or doc.get("userId") for doc in top_16_agents]
            logger.info(f"Agentes activos (Top 16) calculados dinámicamente desde roi_docs: {len(active_agents_final)}")
        else:
            # Si usamos datos precalculados, obtener desde la colección
            active_agents_final = _get_active_agents(top16_collection, state_repo, end_date)
            logger.info(f"Agentes activos obtenidos desde colección precalculada: {len(active_agents_final)}")

        kpis["active_agents_count"] = len(active_agents_final)
        # unique_agents_in_period ya viene de _calculate_kpis_from_roi_docs (línea 190)

        return {
            "success": True,
            "window_days": window_days,
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "kpis": kpis,
            "active_agents": active_agents_final,
        }

    except Exception as e:
        logger.error(f"[ERROR] Error en get_summary_report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al generar reporte de resumen: {str(e)}")


async def _get_summary_from_top16(
    date_str: str,
    assignment_repo: AssignmentRepositoryDep,
    rotation_log_repo: RotationLogRepositoryDep,
    state_repo: AgentStateRepositoryDep,
    window_days: int = 7,
) -> Dict[str, Any]:
    """
    Función FALLBACK para obtener summary desde colección top16 cuando agent_roi no tiene datos.
    """
    from datetime import datetime
    from app.utils.collection_names import get_top16_collection_name

    logger.info(f"[FALLBACK] Usando _get_summary_from_top16 para fecha={date_str}, window_days={window_days}")

    db = database_manager.get_database()
    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = db[top16_collection_name]

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_date = target_date - timedelta(days=window_days - 1)

    logger.info(f"[FALLBACK] Buscando datos en {top16_collection_name} para fecha={date_str}")

    # Obtener Top 16 del día
    top16_docs = list(top16_collection.find({"date": date_str}).sort("rank", 1))

    if not top16_docs:
        logger.warning(f"[FALLBACK] No se encontraron datos en {top16_collection_name} para fecha {date_str}")
        return {"success": False, "message": f"No se encontraron datos para la fecha {date_str}"}

    logger.info(f"[FALLBACK] Encontrados {len(top16_docs)} documentos en {top16_collection_name}")

    # Calcular KPIs básicos desde top16_by_day
    roi_field = f"roi_{window_days}d"
    total_roi = sum(doc.get(roi_field, 0.0) for doc in top16_docs)
    avg_roi = total_roi / len(top16_docs) if top16_docs else 0.0
    positive_count = sum(1 for doc in top16_docs if doc.get(roi_field, 0.0) > 0)
    win_rate = positive_count / len(top16_docs) if top16_docs else 0.0

    # Rotaciones
    try:
        rotation_logs = rotation_log_repo.get_by_date_range(start_date, target_date)
        logger.info(f"[FALLBACK] Encontradas {len(rotation_logs)} rotaciones en rango {start_date} - {target_date}")
    except Exception as e:
        logger.error(f"[FALLBACK] Error al obtener rotation_logs: {e}")
        rotation_logs = []

    # Agentes activos
    active_agents = [doc["agent_id"] for doc in top16_docs if doc.get("is_in_casterly", False)]
    logger.info(f"[FALLBACK] {len(active_agents)} agentes activos en Casterly Rock")

    return {
        "success": True,
        "window_days": window_days,
        "period": {"start_date": start_date.isoformat(), "end_date": target_date.isoformat()},
        "kpis": {
            "total_roi": round(avg_roi, 4),  # Usar avg como aproximación
            "average_roi": round(avg_roi, 4),
            "max_drawdown": 0.0,  # No disponible desde top16_by_day
            "max_drawdown_agent": None,
            "volatility": 0.0,  # No disponible desde top16_by_day
            "total_rotations": len(rotation_logs),
            "active_agents_count": len(active_agents),
            "unique_agents_in_period": len(top16_docs),
            "win_rate": round(win_rate, 4),
        },
        "active_agents": active_agents,
    }


def _get_roi_distribution_config(window_days: Optional[int] = None):
    """
    Obtiene configuración y colección para distribución de ROI.

    Args:
        window_days: Ventana de días solicitada (None = usar ventana de simulación ejecutada)

    Returns:
        Tupla de (db, top16_collection, window_days, collection_name)
    """
    db = database_manager.get_database()
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})

    # Si no se especifica window_days, usar la de la simulación ejecutada
    if window_days is None:
        window_days = config.get("window_days", 7) if config else 7
        logger.info(f"Usando ventana de simulación ejecutada: {window_days} días")
    else:
        logger.info(f"Usando ventana especificada por parámetro: {window_days} días")

    from app.utils.collection_names import get_top16_collection_name

    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = database_manager.get_collection(top16_collection_name)

    logger.info(f"ROI Distribution usando colección: {top16_collection_name}")

    return db, top16_collection, window_days, top16_collection_name


def _get_target_date_for_roi_distribution(target_date: Optional[date], top16_collection, collection_name: str) -> date:
    """
    Obtiene la fecha objetivo para distribución de ROI.
    SIEMPRE lee de system_config para usar la última simulación ejecutada.

    Args:
        target_date: Fecha especificada (puede ser None, se ignora)
        top16_collection: Colección Top 16
        collection_name: Nombre de la colección

    Returns:
        Fecha objetivo (end_date de la última simulación)

    Raises:
        HTTPException: Si no hay datos en system_config ni en la colección
    """
    # SIEMPRE leer de system_config
    db = database_manager.get_database()
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})

    if config and "end_date" in config:
        target_date = date.fromisoformat(config["end_date"])
        logger.info(f"Usando end_date de última simulación ejecutada: {target_date}")
        return target_date

    # Fallback: leer de la colección
    logger.warning("No se encontró system_config, usando fecha más reciente de la colección")
    if not target_date:
        latest_doc = top16_collection.find_one(sort=[("date", -1)])
        if not latest_doc:
            raise HTTPException(status_code=404, detail=f"No se encontraron datos en {collection_name}")
        target_date = date.fromisoformat(latest_doc["date"])

    return target_date


def _get_agents_with_roi_data(top16_collection, target_date: date, window_days: int) -> List[Dict[str, Any]]:
    """
    Obtiene agentes activos con sus datos de ROI.

    Args:
        top16_collection: Colección Top 16
        target_date: Fecha objetivo
        window_days: Ventana de días

    Returns:
        Lista de agentes con ROI
    """
    top16_docs = list(
        top16_collection.find(
            {"date": target_date.isoformat(), "is_in_casterly": True}
        )
    )

    roi_field = f"roi_{window_days}d"
    agents_with_roi = []
    for doc in top16_docs:
        agents_with_roi.append(
            {
                "agent_id": doc.get("agent_id"),
                "rank": doc.get("rank"),
                "roi_7d": doc.get(roi_field, 0.0),
                "total_aum": doc.get("total_aum", 0.0),
                "n_accounts": doc.get("n_accounts", 0),
            }
        )

    return agents_with_roi


def _define_roi_ranges() -> Dict[str, Dict[str, float]]:
    """
    Define los rangos de ROI para clasificación.

    Returns:
        Diccionario de rangos con min/max
    """
    return {
        "< -10%": {"min": float("-inf"), "max": -10.0},
        "-10% a -9%": {"min": -10.0, "max": -9.0},
        "-9% a -8%": {"min": -9.0, "max": -8.0},
        "-8% a -7%": {"min": -8.0, "max": -7.0},
        "-7% a -6%": {"min": -7.0, "max": -6.0},
        "-6% a -5%": {"min": -6.0, "max": -5.0},
        "-5% a -4%": {"min": -5.0, "max": -4.0},
        "-4% a -3%": {"min": -4.0, "max": -3.0},
        "-3% a -2%": {"min": -3.0, "max": -2.0},
        "-2% a -1%": {"min": -2.0, "max": -1.0},
        "-1% a 0%": {"min": -1.0, "max": 0.0},
        "0% a 1%": {"min": 0.0, "max": 1.0},
        "1% a 2%": {"min": 1.0, "max": 2.0},
        "2% a 3%": {"min": 2.0, "max": 3.0},
        "3% a 4%": {"min": 3.0, "max": 4.0},
        "4% a 5%": {"min": 4.0, "max": 5.0},
        "5% a 6%": {"min": 5.0, "max": 6.0},
        "6% a 7%": {"min": 6.0, "max": 7.0},
        "7% a 8%": {"min": 7.0, "max": 8.0},
        "8% a 9%": {"min": 8.0, "max": 9.0},
        "9% a 10%": {"min": 9.0, "max": 10.0},
        "> 10%": {"min": 10.0, "max": float("inf")},
    }


def _classify_agents_by_roi(
    agents_with_roi: List[Dict[str, Any]],
    roi_ranges: Dict[str, Dict[str, float]]
) -> tuple[Dict[str, Dict[str, float]], int, float]:
    """
    Clasifica agentes por rangos de ROI.

    Args:
        agents_with_roi: Lista de agentes con ROI
        roi_ranges: Rangos de ROI definidos

    Returns:
        Tupla de (distribution, total_agents, total_aum)
    """
    distribution = {range_key: {"agents": 0, "total_aum": 0.0} for range_key in roi_ranges.keys()}

    total_agents = len(agents_with_roi)
    total_aum = sum(agent["total_aum"] for agent in agents_with_roi)

    for agent in agents_with_roi:
        roi_decimal = agent["roi_7d"]
        roi_pct = roi_decimal * 100
        aum = agent["total_aum"]

        for range_key, range_vals in roi_ranges.items():
            if range_vals["min"] <= roi_pct < range_vals["max"]:
                distribution[range_key]["agents"] += 1
                distribution[range_key]["total_aum"] += aum
                break

    return distribution, total_agents, total_aum


def _build_roi_distribution_response(
    distribution: Dict[str, Dict[str, float]],
    roi_ranges: Dict[str, Dict[str, float]],
    total_agents: int,
    total_aum: float,
    target_date: date
) -> Dict[str, Any]:
    """
    Construye la respuesta de distribución de ROI.

    Args:
        distribution: Distribución calculada
        roi_ranges: Rangos de ROI
        total_agents: Total de agentes
        total_aum: AUM total
        target_date: Fecha objetivo

    Returns:
        Diccionario con respuesta completa
    """
    distribution_list = []
    for range_key in roi_ranges.keys():
        distribution_list.append(
            {
                "roi_range": range_key,
                "agents": distribution[range_key]["agents"],
                "total_aum": round(distribution[range_key]["total_aum"], 2),
            }
        )

    return {
        "success": True,
        "date": target_date.isoformat(),
        "summary": {
            "total_agents": total_agents,
            "total_aum": round(total_aum, 2),
            "source": "top16_by_day",
        },
        "distribution": distribution_list,
    }


@router.get("/roi-distribution")
async def get_roi_distribution(
    target_date: Optional[date] = Query(None, description="Fecha objetivo (YYYY-MM-DD)"),
    window_days: Optional[int] = Query(None, description="Ventana de días para calcular ROI")
) -> Dict[str, Any]:
    """
    Distribución de AGENTES por ROI usando la colección dinámica según ventana de simulación.

    Esta función ha sido refactorizada para reducir complejidad (12 -> ~6).
    Secciones extraídas:
    1. _get_roi_distribution_config: Obtiene configuración y colección
    2. _get_target_date_for_roi_distribution: Obtiene fecha objetivo
    3. _get_agents_with_roi_data: Obtiene agentes con ROI
    4. _define_roi_ranges: Define rangos de ROI
    5. _classify_agents_by_roi: Clasifica agentes
    6. _build_roi_distribution_response: Construye respuesta

    VERSION 5.0:
    - Acepta window_days como parámetro para calcular dinámicamente
    - Si window_days no se especifica, usa la ventana de la simulación ejecutada
    - Usa top16_XD como fuente de datos (Top 16 agentes seleccionados)
    - Solo incluye agentes activos en Casterly Rock (is_in_casterly = true)
    - Clasifica agentes por roi_7d en rangos de 1%
    - Más eficiente: una sola query a la base de datos

    Retorna:
    - roi_range: Rango de ROI (ej: "5% a 6%")
    - agents: Cantidad de agentes en ese rango
    - total_aum: Suma de balances de las cuentas de esos agentes
    """
    try:
        # 1. Obtener configuración y colección con ventana dinámica
        db, top16_collection, resolved_window_days, collection_name = _get_roi_distribution_config(window_days)

        # 2. Obtener fecha objetivo
        target_date = _get_target_date_for_roi_distribution(target_date, top16_collection, collection_name)

        # 3. Obtener agentes con ROI
        agents_with_roi = _get_agents_with_roi_data(top16_collection, target_date, resolved_window_days)

        if not agents_with_roi:
            return {
                "success": False,
                "message": f"No se encontraron agentes en Casterly Rock para la fecha {target_date.isoformat()}",
            }

        # 4. Definir rangos de ROI
        roi_ranges = _define_roi_ranges()

        # 5. Clasificar agentes por ROI
        distribution, total_agents, total_aum = _classify_agents_by_roi(agents_with_roi, roi_ranges)

        # 6. Construir respuesta
        return _build_roi_distribution_response(
            distribution, roi_ranges, total_agents, total_aum, target_date
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar distribucion de ROI: {str(e)}")


@router.get("/top-agents")
async def get_top_agents(
    date: Optional[str] = Query(
        None, description="Fecha FINAL del rango (YYYY-MM-DD). Si no se especifica, usa el final de la simulación"
    ),
    start_date: Optional[str] = Query(
        None, description="Fecha INICIAL del rango (YYYY-MM-DD). Si se especifica date, este parametro calcula el rango completo"
    ),
    window_days: Optional[int] = Query(None, description="Ventana de dias para ROI (3, 5, 7, 10, 15, 30)")
) -> Dict[str, Any]:
    """
    Obtiene el ranking Top 16 de agentes desde la colección dinámica.

    VERSION 3.0:
    - Lee window_days de system_config para usar la colección correcta
    - Usa top16_XD directamente (mas eficiente)
    - Retorna solo campos disponibles en top16_XD

    Retorna:
    - rank
    - agent_id
    - roi_7d
    - n_accounts
    - total_aum
    - is_in_casterly
    """
    from datetime import datetime

    db = database_manager.get_database()

    # 1. Obtener window_days solicitada y ejecutada
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})

    requested_window_days = window_days if window_days else (config.get("window_days", 7) if config else 7)
    executed_window_days = config.get("window_days", 30) if config else 30

    logger.info(f"Top Agents - Ventana solicitada: {requested_window_days}D, Ventana ejecutada: {executed_window_days}D")

    # 2. Determinar fechas (priorizar fechas del usuario)
    if date:
        # Usuario especificó fecha final
        try:
            end_date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            date_str = date
            logger.info(f"Usando fecha final especificada por usuario: {date_str}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")
    elif config and "end_date" in config:
        # Usar fecha de system_config
        date_str = config["end_date"]
        end_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        logger.info(f"Usando end_date de system_config: {date_str}")
    else:
        raise HTTPException(status_code=404, detail="No se encontró configuración de simulación")

    # 3. Si la ventana solicitada es diferente a la ejecutada, calcular dinámicamente
    from app.utils.collection_names import get_top16_collection_name, get_roi_collection_name

    if requested_window_days != executed_window_days:
        # Calcular Top 16 dinámicamente usando daily_roi_calculation
        logger.info(f"Calculando Top 16 dinámicamente para ventana {requested_window_days}D")

        # Calcular ROI dinámicamente
        roi_docs = await _calculate_dynamic_roi(
            end_date_obj,
            requested_window_days,
            executed_window_days
        )

        if not roi_docs:
            return {
                "success": False,
                "message": f"No se encontraron datos para calcular Top 16 en fecha {date_str}",
                "date": date_str,
                "top16": [],
            }

        # Ordenar por ROI y tomar los 16 mejores
        sorted_roi_docs = sorted(roi_docs, key=lambda x: x.get("roi_7d_total", 0.0), reverse=True)
        top_16_agents = sorted_roi_docs[:16]

        # Mapear a formato de respuesta
        top16_data = []
        for index, doc in enumerate(top_16_agents, start=1):
            top16_data.append({
                "rank": index,
                "agent_id": doc.get("agent_id") or doc.get("userId"),
                "roi_7d": doc.get("roi_7d_total", 0.0),
                "n_accounts": 0,  # No disponible en cálculo dinámico
                "total_aum": 0.0,  # No disponible en cálculo dinámico
                "is_in_casterly": True,
            })

        window_start_str = doc.get("window_start") if top_16_agents else None
        window_end_str = doc.get("window_end") if top_16_agents else None

    else:
        # Usar colección precalculada
        top16_collection_name = get_top16_collection_name(requested_window_days)
        top16_collection = db[top16_collection_name]
        logger.info(f"Usando colección precalculada: {top16_collection_name}")

        roi_field = f"roi_{requested_window_days}d"

        # Usar agregación para obtener agentes UNICOS y ordenados
        pipeline = [
            {"$match": {"date": date_str, "is_in_casterly": True}},
            {"$sort": {roi_field: -1}},
            {"$group": {
                "_id": "$agent_id",
                "agent_id": {"$first": "$agent_id"},
                "roi": {"$first": f"${roi_field}"},
                "n_accounts": {"$first": "$n_accounts"},
                "total_aum": {"$first": "$total_aum"},
                "is_in_casterly": {"$first": "$is_in_casterly"}
            }},
            {"$sort": {"roi": -1}},
            {"$limit": 16}
        ]

        top16_docs = list(top16_collection.aggregate(pipeline))

        if not top16_docs:
            return {
                "success": False,
                "message": f"No se encontraron agentes para la fecha {date_str}",
                "date": date_str,
                "top16": [],
            }

        # Mapear a formato de respuesta
        top16_data = []
        for index, doc in enumerate(top16_docs, start=1):
            top16_data.append({
                "rank": index,
                "agent_id": doc.get("agent_id"),
                "roi_7d": doc.get("roi", 0.0),
                "n_accounts": doc.get("n_accounts", 0),
                "total_aum": doc.get("total_aum", 0.0),
                "is_in_casterly": doc.get("is_in_casterly", True),
            })

        # Obtener rango de fechas desde la colección ROI dinámica
        roi_collection_name = get_roi_collection_name(requested_window_days)
        roi_collection = db[roi_collection_name]
        roi_doc = roi_collection.find_one({"target_date": date_str})

        window_start_str = roi_doc.get("window_start") if roi_doc else None
        window_end_str = roi_doc.get("window_end") if roi_doc else None

    # Contar agentes en Casterly Rock
    in_casterly_count = sum(1 for agent in top16_data if agent["is_in_casterly"])

    return {
        "success": True,
        "date": date_str,
        "window_start": window_start_str,
        "window_end": window_end_str,
        "total_agents": len(top16_data),
        "in_casterly_count": in_casterly_count,
        "top16": top16_data,
    }


@router.get("/rotation-history")
async def get_rotation_history(
    start_date: Optional[str] = Query(None, description="Fecha inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha fin en formato YYYY-MM-DD"),
    agent_id: Optional[str] = Query(None, description="Filtrar por agent_id (puede ser agent_out o agent_in)"),
    rotation_log_repo: RotationLogRepositoryDep = None,
) -> Dict[str, Any]:
    """
    Obtiene el historial de rotaciones.

    Filtros opcionales:
    - start_date y end_date: rango de fechas
    - agent_id: rotaciones donde el agente entro o salio

    Retorna:
    - date
    - agent_out
    - agent_in
    - reason
    - roi_7d_out
    - roi_total_out
    - roi_7d_in
    - n_accounts
    - total_aum
    """
    from datetime import datetime

    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")

        rotations = rotation_log_repo.get_by_date_range(start, end)
    else:
        db = database_manager.get_database()
        collection = db[rotation_log_repo.collection_name]
        docs = list(collection.find().sort("date", -1))
        rotations = [rotation_log_repo._doc_to_entity(doc) for doc in docs]

    if agent_id:
        rotations = [r for r in rotations if r.agent_out == agent_id or r.agent_in == agent_id]

    if not rotations:
        return {
            "success": False,
            "message": "No se encontraron rotaciones con los filtros especificados",
            "start_date": start_date,
            "end_date": end_date,
            "agent_id": agent_id,
            "rotations": [],
        }

    rotations_data = []
    for rotation in rotations:
        rotations_data.append(
            {
                "date": rotation.date.isoformat() if hasattr(rotation.date, "isoformat") else str(rotation.date),
                "agent_out": rotation.agent_out,
                "agent_in": rotation.agent_in,
                "reason": rotation.reason.value if hasattr(rotation.reason, "value") else rotation.reason,
                "roi_7d_out": rotation.roi_7d_out,
                "roi_total_out": rotation.roi_total_out,
                "roi_7d_in": rotation.roi_7d_in,
                "n_accounts": rotation.n_accounts,
                "total_aum": rotation.total_aum,
            }
        )

    return {
        "success": True,
        "start_date": start_date,
        "end_date": end_date,
        "agent_id": agent_id,
        "total_rotations": len(rotations_data),
        "rotations": rotations_data,
    }


@router.get("/rank-changes")
async def get_rank_changes(
    start_date: Optional[str] = Query(None, description="Fecha inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha fin en formato YYYY-MM-DD"),
    agent_id: Optional[str] = Query(None, description="Filtrar por agent_id"),
    min_change: Optional[int] = Query(None, description="Filtrar por cambio mínimo de posiciones (ej: 3)", ge=1),
) -> Dict[str, Any]:
    """
    Obtiene el historial de cambios de ranking dentro del Top 16.

    A diferencia de /rotation-history (entradas/salidas), este endpoint
    retorna movimientos de posición DENTRO del Top 16.

    Filtros opcionales:
    - start_date y end_date: rango de fechas
    - agent_id: cambios de un agente específico
    - min_change: solo cambios >= N posiciones (ej: 3 para cambios significativos)

    Retorna:
    - date
    - agent_id
    - previous_rank
    - current_rank
    - rank_change (positivo = subió, negativo = bajó)
    - previous_roi
    - current_roi
    - roi_change
    - is_in_casterly
    """
    from datetime import datetime
    from app.infrastructure.repositories.rank_change_repository_impl import RankChangeRepositoryImpl

    rank_change_repo = RankChangeRepositoryImpl()

    # Determinar qué método usar según los filtros
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

        if min_change:
            rank_changes = rank_change_repo.get_significant_changes(start, end, min_change)
        else:
            rank_changes = rank_change_repo.get_by_date_range(start, end)
    elif agent_id:
        rank_changes = rank_change_repo.get_by_agent(agent_id)
    else:
        # Si no hay filtros, obtener todos (limitado a últimos 100)
        rank_changes = rank_change_repo.get_all()[:100]

    # Aplicar filtro adicional de agent_id si se especificó junto con fechas
    if agent_id and (start_date and end_date):
        rank_changes = [rc for rc in rank_changes if rc.agent_id == agent_id]

    if not rank_changes:
        return {
            "success": False,
            "message": "No se encontraron cambios de ranking con los filtros especificados",
            "start_date": start_date,
            "end_date": end_date,
            "agent_id": agent_id,
            "min_change": min_change,
            "rank_changes": [],
        }

    # Convertir entidades a diccionarios
    rank_changes_data = []
    for rc in rank_changes:
        rank_changes_data.append(
            {
                "date": rc.date.isoformat() if hasattr(rc.date, "isoformat") else str(rc.date),
                "agent_id": rc.agent_id,
                "previous_rank": rc.previous_rank,
                "current_rank": rc.current_rank,
                "rank_change": rc.rank_change,
                "movement_type": rc.movement_type,
                "is_significant": rc.is_significant,
                "previous_roi": rc.previous_roi,
                "current_roi": rc.current_roi,
                "roi_change": rc.roi_change,
                "is_in_casterly": rc.is_in_casterly,
            }
        )

    # Calcular estadísticas
    total_ups = sum(1 for rc in rank_changes_data if rc["rank_change"] > 0)
    total_downs = sum(1 for rc in rank_changes_data if rc["rank_change"] < 0)
    avg_change = (
        sum(abs(rc["rank_change"]) for rc in rank_changes_data) / len(rank_changes_data) if rank_changes_data else 0
    )

    return {
        "success": True,
        "start_date": start_date,
        "end_date": end_date,
        "agent_id": agent_id,
        "min_change": min_change,
        "total_changes": len(rank_changes_data),
        "statistics": {
            "total_ups": total_ups,
            "total_downs": total_downs,
            "average_absolute_change": round(avg_change, 2),
        },
        "rank_changes": rank_changes_data,
    }


def _get_timeline_config_and_collections(db, window_days: int):
    """
    Obtiene las colecciones necesarias para el timeline.

    Returns:
        tuple: (top16_collection, rotation_collection, roi_collection)
    """
    from app.utils.collection_names import get_top16_collection_name, get_roi_collection_name

    top16_collection_name = get_top16_collection_name(window_days)
    roi_collection_name = get_roi_collection_name(window_days)

    top16_collection = db[top16_collection_name]
    rotation_collection = db.rotation_log
    roi_collection = db[roi_collection_name]

    return top16_collection, rotation_collection, roi_collection


def _calculate_timeline_date_range(target_date: Optional[date], top16_collection, window_days: int) -> tuple[date, date, List[str]]:
    """
    Calcula el rango de fechas para el timeline.
    SIEMPRE lee de system_config para usar la última simulación ejecutada.

    Returns:
        tuple: (start_date, target_date, dates_list)
    """
    from datetime import timedelta

    # SIEMPRE leer de system_config
    db = database_manager.get_database()
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})

    if config and "end_date" in config and "start_date" in config:
        simulation_end = date.fromisoformat(config["end_date"])
        simulation_start = date.fromisoformat(config["start_date"])

        # El target_date es el end_date de la simulación
        target_date = simulation_end

        # Calcular ventana según window_days
        start_date = target_date - timedelta(days=window_days - 1)

        # Validar que start_date no sea anterior al inicio de la simulación
        if start_date < simulation_start:
            logger.warning(f"Ventana de {window_days} días excede el inicio de la simulación. Ajustando start_date de {start_date} a {simulation_start}")
            start_date = simulation_start

        logger.info(f"Timeline usando rango de última simulación ejecutada: {start_date} a {target_date}")
    else:
        # Fallback: usar lógica anterior
        logger.warning("No se encontró system_config, usando fecha más reciente de la colección")
        if not target_date:
            latest_doc = top16_collection.find_one(sort=[("date", -1)])
            if not latest_doc:
                raise HTTPException(status_code=404, detail="No se encontraron datos en la colección top16")
            target_date = date.fromisoformat(latest_doc["date"])

        # Calcular ventana según window_days
        start_date = target_date - timedelta(days=window_days - 1)

    # Generar lista de fechas
    dates = []
    current = start_date
    while current <= target_date:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    return start_date, target_date, dates


def _build_daily_roi_map(roi_collection, unique_agents: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Construye un mapa de ROI diario por agente y fecha.

    Returns:
        Dict[agent_id][date] = roi_value
    """
    logger.info(f"[TIMELINE] Obteniendo daily_roi para {len(unique_agents)} agentes en {len(dates)} fechas")

    # OPTIMIZACION: Una sola consulta para todos los agentes y fechas
    roi_docs = list(roi_collection.find({"userId": {"$in": unique_agents}, "target_date": {"$in": dates}}))

    logger.info(f"[TIMELINE] Encontrados {len(roi_docs)} documentos de ROI")

    # Construir el mapa desde los documentos obtenidos
    daily_roi_map = {}
    for roi_doc in roi_docs:
        agent_id = roi_doc.get("userId")
        target_date = roi_doc.get("target_date")

        if agent_id not in daily_roi_map:
            daily_roi_map[agent_id] = {}

        # Buscar el ROI específico de ese día en daily_rois
        daily_rois = roi_doc.get("daily_rois", [])
        for daily_roi_entry in daily_rois:
            entry_date = daily_roi_entry.get("date")
            if entry_date == target_date:
                daily_roi_map[agent_id][entry_date] = daily_roi_entry.get("roi", 0.0)
                break

    return daily_roi_map


def _process_rotation_logs(
    rotation_collection,
    start_date: date,
    target_date: date
) -> tuple[Dict[str, Dict[str, Dict[str, str]]], Dict[str, Dict[str, Dict[str, str]]]]:
    """
    Procesa los logs de rotación y crea mapas de entrada/salida.

    Returns:
        tuple: (rotation_out_map, rotation_in_map)
        - rotation_out_map: {agent_id: {date: {reason, details}}}
        - rotation_in_map: {agent_id: {date: {reason, details}}}
    """
    start_date_str = start_date.isoformat() if hasattr(start_date, "isoformat") else start_date
    target_date_str = target_date.isoformat() if hasattr(target_date, "isoformat") else target_date

    start_date_str = (
        start_date_str + "T00:00:00"
        if isinstance(start_date_str, str) and "T" not in start_date_str
        else start_date_str
    )
    target_date_str = (
        target_date_str + "T23:59:59"
        if isinstance(target_date_str, str) and "T" not in target_date_str
        else target_date_str
    )

    rotation_docs = list(
        rotation_collection.find({"date": {"$gte": start_date_str, "$lte": target_date_str}}).sort("date", 1)
    )

    logger.info(f"Total rotaciones encontradas: {len(rotation_docs)}")

    if len(rotation_docs) == 0:
        logger.warning(
            f"No se encontraron rotaciones en el rango. Total en toda la colección: {rotation_collection.count_documents({})}"
        )

    rotation_out_map = {}
    rotation_in_map = {}

    for rot in rotation_docs:
        # Las fechas vienen como string "2025-10-01T00:00:00"
        # Extraer solo la parte de la fecha "2025-10-01"
        rot_date_str = rot["date"].split("T")[0] if "T" in rot["date"] else rot["date"]

        agent_out = rot.get("agent_out")
        agent_in = rot.get("agent_in")
        reason = rot.get("reason", "")
        reason_details = rot.get("reason_details", "")

        if reason_details:
            logger.info(f"[TIMELINE] {rot_date_str}: {agent_out} -> {agent_in}, details: {reason_details}")

        # Registrar salida
        if agent_out:
            if agent_out not in rotation_out_map:
                rotation_out_map[agent_out] = {}
            rotation_out_map[agent_out][rot_date_str] = {"reason": reason, "details": reason_details}

        # Registrar entrada
        if agent_in:
            if agent_in not in rotation_in_map:
                rotation_in_map[agent_in] = {}
            rotation_in_map[agent_in][rot_date_str] = {"reason": reason, "details": reason_details}

    return rotation_out_map, rotation_in_map


def _build_agents_timeline_data(
    top16_docs: List[Dict[str, Any]],
    daily_roi_map: Dict[str, Dict[str, float]],
    rotation_in_map: Dict[str, Dict[str, Dict[str, str]]],
    rotation_out_map: Dict[str, Dict[str, Dict[str, str]]],
    window_days: int
) -> Dict[str, Dict[str, Any]]:
    """
    Construye datos de timeline por agente desde documentos top16.

    Returns:
        Dict[agent_id] = {agent_id, timeline, entry_info, exit_info}
    """
    agents_data = {}
    roi_field = f"roi_{window_days}d"

    # Agrupar documentos por fecha para calcular rank dinámicamente
    docs_by_date = {}
    for doc in top16_docs:
        date_str = doc.get("date")
        if date_str not in docs_by_date:
            docs_by_date[date_str] = []
        docs_by_date[date_str].append(doc)

    # Para cada fecha, calcular el rank basado en ROI (de mayor a menor)
    for date_str, docs in docs_by_date.items():
        # IMPORTANTE: Eliminar duplicados por agent_id (tomar el de mayor ROI)
        unique_docs = {}
        for doc in docs:
            agent_id = doc.get("agent_id")
            roi_value = doc.get(roi_field, 0.0)
            # Si no existe o tiene mayor ROI, usar este documento
            if agent_id not in unique_docs or roi_value > unique_docs[agent_id].get(roi_field, 0.0):
                unique_docs[agent_id] = doc

        # Ordenar agentes por ROI descendente (mayor ROI = mejor rank)
        sorted_docs = sorted(unique_docs.values(), key=lambda d: d.get(roi_field, 0.0), reverse=True)

        # Asignar rank dinámicamente (1, 2, 3, ...)
        for rank_index, doc in enumerate(sorted_docs, start=1):
            agent_id = doc.get("agent_id")
            roi_value = doc.get(roi_field, 0.0)
            is_in_casterly = doc.get("is_in_casterly", False)

            if agent_id not in agents_data:
                agents_data[agent_id] = {
                    "agent_id": agent_id,
                    "timeline": {},
                    "entry_info": rotation_in_map.get(agent_id, {}),
                    "exit_info": rotation_out_map.get(agent_id, {}),
                }

            # Obtener el ROI diario específico de este día
            daily_roi = daily_roi_map.get(agent_id, {}).get(date_str, None)
            is_loss_day = daily_roi is not None and daily_roi < 0

            agents_data[agent_id]["timeline"][date_str] = {
                "rank": rank_index,  # Rank calculado dinámicamente
                "roi_7d": roi_value,
                "in_top16": is_in_casterly,
                "daily_roi": daily_roi,
                "is_loss_day": is_loss_day,
            }

    return agents_data


def _fill_missing_days_in_timeline(
    agents_data: Dict[str, Dict[str, Any]],
    dates: List[str],
    daily_roi_map: Dict[str, Dict[str, float]]
) -> List[Dict[str, Any]]:
    """
    Rellena días faltantes en el timeline de cada agente y ordena.

    Returns:
        Lista de agentes con timeline completo, ordenados por mejor rank
    """
    agents_list = []
    for agent_id, agent_info in agents_data.items():
        timeline = []
        for date_str in dates:
            if date_str in agent_info["timeline"]:
                timeline.append({"date": date_str, **agent_info["timeline"][date_str]})
            else:
                # No estaba en el Top 16 ese día
                # Pero podría tener daily_roi si tiene datos
                daily_roi = daily_roi_map.get(agent_id, {}).get(date_str, None)
                is_loss_day = daily_roi is not None and daily_roi < 0

                timeline.append(
                    {
                        "date": date_str,
                        "rank": None,
                        "roi_7d": None,
                        "in_top16": False,
                        "daily_roi": daily_roi,
                        "is_loss_day": is_loss_day,
                    }
                )

        agents_list.append(
            {
                "agent_id": agent_id,
                "timeline": timeline,
                "entry_info": agent_info.get("entry_info", {}),
                "exit_info": agent_info.get("exit_info", {}),
            }
        )

    # Ordenar agentes por su mejor rank
    agents_list.sort(key=lambda a: min([day["rank"] for day in a["timeline"] if day["rank"] is not None], default=999))

    return agents_list


async def _calculate_timeline_dynamically(
    db,
    config: Dict[str, Any],
    target_date: Optional[date],
    requested_window_days: int,
    executed_window_days: int
) -> Dict[str, Any]:
    """
    Calcula el timeline dinámicamente cuando la ventana solicitada es diferente a la ejecutada.

    Esta función calcula el Top 16 para cada día usando daily_roi_calculation,
    calculando el ROI acumulado para la ventana solicitada.
    """
    from datetime import timedelta

    logger.info(f"[DYNAMIC TIMELINE] Iniciando cálculo dinámico para ventana {requested_window_days}D")

    # 1. Determinar fecha objetivo
    if not target_date:
        if config and "end_date" in config:
            target_date = date.fromisoformat(config["end_date"])
        else:
            raise HTTPException(status_code=404, detail="No se encontró configuración de simulación")

    # 2. Calcular fecha de inicio y lista de fechas
    start_date = target_date - timedelta(days=requested_window_days - 1)
    dates = [(start_date + timedelta(days=i)).isoformat() for i in range(requested_window_days)]

    logger.info(f"[DYNAMIC TIMELINE] Período: {start_date.isoformat()} a {target_date.isoformat()}")

    # 3. Obtener colecciones
    daily_roi_collection = db["daily_roi_calculation"]
    rotation_collection = db.rotation_log

    # 4. Para cada día, calcular el Top 16 dinámicamente
    timeline_by_day = {}  # {date_str: [top16_agents_with_roi]}

    for current_date_str in dates:
        current_date_obj = date.fromisoformat(current_date_str)

        # Calcular ROI dinámicamente para este día específico
        roi_docs = await _calculate_dynamic_roi(
            current_date_obj,
            requested_window_days,
            executed_window_days
        )

        if not roi_docs:
            logger.warning(f"[DYNAMIC TIMELINE] No hay datos ROI para {current_date_str}")
            timeline_by_day[current_date_str] = []
            continue

        # Ordenar por ROI y tomar los 16 mejores
        sorted_roi_docs = sorted(roi_docs, key=lambda x: x.get("roi_7d_total", 0.0), reverse=True)
        top_16_for_day = sorted_roi_docs[:16]

        # Agregar rank a cada agente
        for rank, agent_doc in enumerate(top_16_for_day, start=1):
            agent_doc["rank"] = rank
            agent_doc["in_top16"] = True
            agent_doc["date"] = current_date_str

        timeline_by_day[current_date_str] = top_16_for_day
        logger.info(f"[DYNAMIC TIMELINE] {current_date_str}: {len(top_16_for_day)} agentes en Top 16")

    # 5. Construir estructura de agentes con timeline
    all_agents = set()
    for day_agents in timeline_by_day.values():
        for agent in day_agents:
            all_agents.add(agent.get("agent_id") or agent.get("userId"))

    # 6. Procesar logs de rotación
    rotation_out_map, rotation_in_map = _process_rotation_logs(rotation_collection, start_date, target_date)

    # 7. Construir timeline por agente
    agents_data = {}
    for agent_id in all_agents:
        agents_data[agent_id] = {
            "agent_id": agent_id,
            "timeline": [],
            "entry_info": rotation_in_map.get(agent_id, {}),
            "exit_info": rotation_out_map.get(agent_id, {})
        }

    # 8. Llenar timeline para cada agente
    for date_str in dates:
        day_agents = timeline_by_day.get(date_str, [])
        agents_in_top16_today = {agent.get("agent_id") or agent.get("userId"): agent for agent in day_agents}

        for agent_id in all_agents:
            day_data = {
                "date": date_str,
                "rank": None,
                "roi_7d": None,
                "in_top16": False,
                "daily_roi": None,
                "is_loss_day": False
            }

            if agent_id in agents_in_top16_today:
                agent_doc = agents_in_top16_today[agent_id]
                day_data["rank"] = agent_doc.get("rank")
                day_data["roi_7d"] = agent_doc.get("roi_7d_total", 0.0)
                day_data["in_top16"] = True

                # Obtener ROI diario del último día de la ventana
                daily_rois = agent_doc.get("daily_rois", [])
                if daily_rois:
                    last_day_roi_item = daily_rois[-1]
                    # daily_rois puede ser una lista de dicts o una lista de floats
                    if isinstance(last_day_roi_item, dict):
                        last_day_roi = last_day_roi_item.get("roi", 0.0)
                    else:
                        last_day_roi = last_day_roi_item
                    day_data["daily_roi"] = last_day_roi
                    day_data["is_loss_day"] = last_day_roi < 0

            agents_data[agent_id]["timeline"].append(day_data)

    # 9. Convertir a lista y ordenar
    agents_list = list(agents_data.values())
    agents_list.sort(key=lambda a: min([day["rank"] for day in a["timeline"] if day["rank"] is not None], default=999))

    logger.info(f"[DYNAMIC TIMELINE] Total de agentes procesados: {len(agents_list)}")

    return {
        "success": True,
        "window_days": requested_window_days,
        "target_date": target_date.isoformat(),
        "start_date": start_date.isoformat(),
        "dates": dates,
        "total_agents": len(agents_list),
        "agents": agents_list,
    }


@router.get("/top16-timeline")
async def get_top16_timeline(
    target_date: Optional[date] = Query(
        None, description="Fecha objetivo (YYYY-MM-DD). Si no se especifica, usa la más reciente"
    ),
    window_days: Optional[int] = Query(None, description="Ventana de dias para ROI (3, 5, 7, 10, 15, 30)")
) -> Dict[str, Any]:
    """
    Obtiene el timeline del Top 16 día por día según la ventana de la última simulación.

    Muestra cómo cambió la composición del Top 16 durante la ventana configurada,
    indicando qué agentes entraron, salieron y su rank en cada día.

    Esta función ha sido refactorizada para reducir complejidad (23 -> ~8).

    Retorna:
    - dates: Lista de fechas en el período
    - agents: Lista de agentes únicos con su timeline
    """
    db = database_manager.get_database()
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})

    # 1. Obtener window_days solicitada y ejecutada
    requested_window_days = window_days if window_days else (config.get("window_days", 7) if config else 7)
    executed_window_days = config.get("window_days", 30) if config else 30

    logger.info(f"Timeline - Ventana solicitada: {requested_window_days}D, Ventana ejecutada: {executed_window_days}D")

    # 2. Detectar si necesitamos cálculo dinámico
    needs_dynamic_calculation = requested_window_days != executed_window_days

    if needs_dynamic_calculation:
        logger.info(f"Timeline requiere cálculo dinámico (ventana {requested_window_days}D diferente de ejecutada {executed_window_days}D)")
        # Llamar a función de cálculo dinámico
        return await _calculate_timeline_dynamically(
            db=db,
            config=config,
            target_date=target_date,
            requested_window_days=requested_window_days,
            executed_window_days=executed_window_days
        )

    # Si la ventana es la misma, usar datos precalculados
    window_days = requested_window_days
    logger.info(f"Timeline usando datos precalculados para ventana de {window_days} días")

    # 3. Obtener colecciones necesarias
    top16_collection, rotation_collection, roi_collection = _get_timeline_config_and_collections(db, window_days)

    # 4. Calcular rango de fechas
    start_date, target_date, dates = _calculate_timeline_date_range(target_date, top16_collection, window_days)

    # 5. Obtener documentos del Top16 en el rango
    top16_docs = list(
        top16_collection.find({"date": {"$gte": start_date.isoformat(), "$lte": target_date.isoformat()}}).sort(
            "date", 1
        )
    )

    if not top16_docs:
        return {
            "success": False,
            "message": f"No se encontraron datos para el período {start_date.isoformat()} - {target_date.isoformat()}",
            "dates": dates,
            "agents": [],
        }

    # 5. Construir mapa de ROI diario
    unique_agents = list({doc["agent_id"] for doc in top16_docs})
    daily_roi_map = _build_daily_roi_map(roi_collection, unique_agents, dates)

    # 6. Procesar logs de rotación
    rotation_out_map, rotation_in_map = _process_rotation_logs(rotation_collection, start_date, target_date)

    # 7. Construir datos de timeline por agente
    agents_data = _build_agents_timeline_data(
        top16_docs,
        daily_roi_map,
        rotation_in_map,
        rotation_out_map,
        window_days
    )

    # 8. Rellenar días faltantes y ordenar
    agents_list = _fill_missing_days_in_timeline(agents_data, dates, daily_roi_map)

    # Log: Mostrar los primeros 5 agentes para debug
    logger.info(f"Timeline - Total de agentes procesados: {len(agents_list)}")
    if agents_list:
        top_5_for_log = agents_list[:5]
        for i, agent in enumerate(top_5_for_log, start=1):
            last_day = agent["timeline"][-1] if agent["timeline"] else {}
            best_rank = min([day["rank"] for day in agent["timeline"] if day["rank"] is not None], default=999)
            logger.info(f"  #{i}: {agent['agent_id']} - Mejor Rank: {best_rank}, Último día rank: {last_day.get('rank', 'N/A')}")

    # 9. Log de ejemplo
    if agents_list:
        sample_agent = agents_list[0]
        logger.info(f"[TIMELINE] Ejemplo de agente: {sample_agent['agent_id']}")
        logger.info(f"[TIMELINE]   entry_info: {sample_agent.get('entry_info', {})}")
        logger.info(f"[TIMELINE]   exit_info: {sample_agent.get('exit_info', {})}")

    return {
        "success": True,
        "window_days": window_days,
        "target_date": target_date.isoformat() if hasattr(target_date, "isoformat") else target_date,
        "start_date": start_date.isoformat() if hasattr(start_date, "isoformat") else start_date,
        "dates": dates,
        "total_agents": len(agents_list),
        "agents": agents_list,
    }
