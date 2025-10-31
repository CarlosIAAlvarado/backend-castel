from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Dict, Any, Optional, List
from app.infrastructure.di.providers import (
    AgentStateRepositoryDep,
    AssignmentRepositoryDep,
    RotationLogRepositoryDep
)
from app.config.database import database_manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/summary")
async def get_summary_report(
    start_date: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    assignment_repo: AssignmentRepositoryDep = None,
    rotation_log_repo: RotationLogRepositoryDep = None,
    state_repo: AgentStateRepositoryDep = None
) -> Dict[str, Any]:
    """
    Calcula KPIs del resumen ejecutivo usando agent_roi_XD como fuente principal.
    Lee automáticamente la ventana de la última simulación ejecutada.
    """
    try:
        # Obtener window_days de la última simulación
        db = database_manager.get_database()
        system_config_col = db["system_config"]
        config = system_config_col.find_one({"config_key": "last_simulation"})
        window_days = config.get("window_days", 7) if config else 7

        logger.info(f"Usando ventana de {window_days} días para el reporte")

        # Obtener colecciones dinámicas según ventana
        from app.utils.collection_names import get_roi_collection_name, get_top16_collection_name
        roi_collection_name = get_roi_collection_name(window_days)
        top16_collection_name = get_top16_collection_name(window_days)

        roi_collection = database_manager.get_collection(roi_collection_name)
        top16_collection = database_manager.get_collection(top16_collection_name)

        # Si no se especifican fechas, usar la más reciente
        if not end_date:
            latest_doc = roi_collection.find_one(sort=[("target_date", -1)])
            if not latest_doc:
                # FALLBACK: Si no hay datos en la colección ROI dinámica, usar top16
                logger.warning(f"No se encontraron datos en {roi_collection_name}, usando {top16_collection_name} como fallback")
                latest_top16 = top16_collection.find_one(sort=[("date", -1)])
                if not latest_top16:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No se encontraron datos en {roi_collection_name} ni {top16_collection_name}"
                    )
                # Usar datos de top16
                return await _get_summary_from_top16(latest_top16["date"], assignment_repo, rotation_log_repo, state_repo, window_days)

            end_date = date.fromisoformat(latest_doc["target_date"])
            # Calcular start_date desde window_start
            # Si window_start no existe (datos antiguos), calcular desde target_date
            if "window_start" in latest_doc:
                start_date = date.fromisoformat(latest_doc["window_start"])
            else:
                # Retroceder window_days desde target_date
                start_date = end_date - timedelta(days=window_days - 1)

        # Obtener todos los agentes con datos ROI
        roi_docs = list(roi_collection.find({"target_date": end_date.isoformat()}))

        if not roi_docs:
            return {
                "success": False,
                "message": f"No se encontraron datos para la fecha {end_date.isoformat()}"
            }

        # Obtener asignaciones activas para calcular balances
        assignments = list(assignment_repo.get_active_assignments())

        # Mapa de balances por agente
        agent_balances = {}
        for assignment in assignments:
            agent_id = assignment.agent_id
            agent_balances[agent_id] = agent_balances.get(agent_id, 0.0) + assignment.balance

        # ==========================================
        # CÁLCULOS DE KPIs DESDE agent_roi_7d
        # ==========================================

        total_balance = sum(agent_balances.values()) if agent_balances else 1.0
        weighted_roi_sum = 0.0
        simple_roi_sum = 0.0
        all_daily_rois = []  # Para volatilidad
        agent_drawdowns = []  # Para max drawdown
        positive_roi_count = 0  # Para win rate

        for doc in roi_docs:
            userId = doc.get("userId")
            roi_7d_total = doc.get("roi_7d_total", 0.0)  # ROI total de 7 días
            daily_rois = doc.get("daily_rois", [])

            # ROI Total (ponderado por balance)
            balance = agent_balances.get(userId, 0.0)
            weight = balance / total_balance if total_balance > 0 else 0.0
            weighted_roi_sum += roi_7d_total * weight

            # ROI Promedio (simple)
            simple_roi_sum += roi_7d_total

            # Win Rate
            if roi_7d_total > 0:
                positive_roi_count += 1

            # Volatilidad (recolectar todos los ROIs diarios)
            for day in daily_rois:
                roi_day = day.get("roi", 0.0)
                if roi_day != 0:  # Solo si tiene trades
                    all_daily_rois.append(roi_day)

            # Max Drawdown (calcular para cada agente)
            if len(daily_rois) >= 2:
                cumulative = [1.0]  # Empezar con 100%
                for day in daily_rois:
                    roi = day.get("roi", 0)
                    cumulative.append(cumulative[-1] * (1 + roi))

                # Calcular max drawdown
                peak = cumulative[0]
                max_dd = 0.0

                for value in cumulative:
                    if value > peak:
                        peak = value
                    if peak > 0:
                        drawdown = (value - peak) / peak
                        if drawdown < max_dd:
                            max_dd = drawdown

                agent_drawdowns.append({
                    "userId": userId,
                    "drawdown": max_dd
                })

        # Calcular métricas finales
        num_agents = len(roi_docs)

        # ROI Total (ponderado)
        total_roi = weighted_roi_sum

        # ROI Promedio (simple)
        average_roi = simple_roi_sum / num_agents if num_agents > 0 else 0.0

        # Max Drawdown (peor de todos los agentes)
        if agent_drawdowns:
            worst_agent = min(agent_drawdowns, key=lambda x: x["drawdown"])
            max_drawdown = worst_agent["drawdown"]
            max_drawdown_agent = worst_agent["userId"]
        else:
            max_drawdown = 0.0
            max_drawdown_agent = None

        # Volatilidad (desviación estándar con N-1)
        if all_daily_rois and len(all_daily_rois) > 1:
            mean_roi = sum(all_daily_rois) / len(all_daily_rois)
            variance = sum((x - mean_roi) ** 2 for x in all_daily_rois) / (len(all_daily_rois) - 1)
            volatility = variance ** 0.5
        else:
            volatility = 0.0

        # Win Rate
        win_rate = positive_roi_count / num_agents if num_agents > 0 else 0.0

        # Rotaciones
        rotation_logs = rotation_log_repo.get_by_date_range(start_date, end_date)
        total_rotations = len(rotation_logs)

        # Agentes activos - Usar colección dinámica según window_days
        top16_docs = list(top16_collection.find({"date": end_date.isoformat()}))
        active_agents_final = [doc["agent_id"] for doc in top16_docs if doc.get("is_in_casterly", False)]

        # Fallback a agent_states si la colección dinámica está vacía
        if not active_agents_final:
            states_final = state_repo.get_by_date(end_date)
            active_agents_final = [s.agent_id for s in states_final if s.is_in_casterly]

        return {
            "success": True,
            "window_days": window_days,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "kpis": {
                "total_roi": round(total_roi, 4),  # ROI ponderado por balance
                "average_roi": round(average_roi, 4),  # ROI promedio simple
                "max_drawdown": round(max_drawdown, 4),  # Max drawdown desde daily_rois
                "max_drawdown_agent": max_drawdown_agent,  # Agente con peor drawdown
                "volatility": round(volatility, 4),  # Volatilidad desde daily_rois
                "total_rotations": total_rotations,
                "active_agents_count": len(active_agents_final),
                "unique_agents_in_period": num_agents,
                "win_rate": round(win_rate, 4)
            },
            "active_agents": active_agents_final
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar reporte de resumen: {str(e)}"
        )


async def _get_summary_from_top16(
    date_str: str,
    assignment_repo: AssignmentRepositoryDep,
    rotation_log_repo: RotationLogRepositoryDep,
    state_repo: AgentStateRepositoryDep,
    window_days: int = 7
) -> Dict[str, Any]:
    """
    Función FALLBACK para obtener summary desde colección top16 cuando agent_roi no tiene datos.
    """
    from datetime import datetime
    from app.utils.collection_names import get_top16_collection_name

    db = database_manager.get_database()
    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = db[top16_collection_name]

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_date = target_date - timedelta(days=window_days - 1)

    # Obtener Top 16 del día
    top16_docs = list(top16_collection.find({"date": date_str}).sort("rank", 1))

    if not top16_docs:
        return {
            "success": False,
            "message": f"No se encontraron datos para la fecha {date_str}"
        }

    # Calcular KPIs básicos desde top16_by_day
    roi_field = f"roi_{window_days}d"
    total_roi = sum(doc.get(roi_field, 0.0) for doc in top16_docs)
    avg_roi = total_roi / len(top16_docs) if top16_docs else 0.0
    positive_count = sum(1 for doc in top16_docs if doc.get(roi_field, 0.0) > 0)
    win_rate = positive_count / len(top16_docs) if top16_docs else 0.0

    # Rotaciones
    rotation_logs = rotation_log_repo.get_by_date_range(start_date, target_date)

    # Agentes activos
    active_agents = [doc["agent_id"] for doc in top16_docs if doc.get("is_in_casterly", False)]

    return {
        "success": True,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": target_date.isoformat()
        },
        "kpis": {
            "total_roi": round(avg_roi, 4),  # Usar avg como aproximación
            "average_roi": round(avg_roi, 4),
            "max_drawdown": 0.0,  # No disponible desde top16_by_day
            "max_drawdown_agent": None,
            "volatility": 0.0,  # No disponible desde top16_by_day
            "total_rotations": len(rotation_logs),
            "active_agents_count": len(active_agents),
            "unique_agents_in_period": len(top16_docs),
            "win_rate": round(win_rate, 4)
        },
        "active_agents": active_agents
    }


@router.get("/roi-distribution")
async def get_roi_distribution(
    target_date: Optional[date] = Query(None, description="Fecha objetivo (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Distribución de AGENTES por ROI usando la colección dinámica según ventana de simulación.

    VERSION 4.0:
    - Lee window_days de system_config para usar la colección correcta
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
        # Obtener window_days de la última simulación
        db = database_manager.get_database()
        system_config_col = db["system_config"]
        config = system_config_col.find_one({"config_key": "last_simulation"})
        window_days = config.get("window_days", 7) if config else 7

        # Obtener colección dinámica
        from app.utils.collection_names import get_top16_collection_name
        top16_collection_name = get_top16_collection_name(window_days)
        top16_collection = database_manager.get_collection(top16_collection_name)

        logger.info(f"ROI Distribution usando colección: {top16_collection_name}")

        # Obtener la fecha más reciente si no se especifica
        if not target_date:
            latest_doc = top16_collection.find_one(sort=[("date", -1)])
            if not latest_doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"No se encontraron datos en {top16_collection_name}"
                )
            target_date = date.fromisoformat(latest_doc["date"])

        # Obtener Top 16 agentes que están activos en Casterly Rock
        top16_docs = list(top16_collection.find({
            "date": target_date.isoformat(),
            "is_in_casterly": True  # Solo agentes activos en Casterly
        }))

        if not top16_docs:
            return {
                "success": False,
                "message": f"No se encontraron agentes en Casterly Rock para la fecha {target_date.isoformat()}"
            }

        # Preparar datos de agentes con ROI y AUM
        roi_field = f"roi_{window_days}d"
        agents_with_roi = []
        for doc in top16_docs:
            agents_with_roi.append({
                "agent_id": doc.get("agent_id"),
                "rank": doc.get("rank"),
                "roi_7d": doc.get(roi_field, 0.0),  # ROI (campo dinamico segun ventana)
                "total_aum": doc.get("total_aum", 0.0),  # AUM del agente
                "n_accounts": doc.get("n_accounts", 0)
            })

        if not agents_with_roi:
            return {
                "success": False,
                "message": f"No se pudieron obtener datos para la fecha {target_date.isoformat()}"
            }

        # Definir rangos de ROI en porcentaje
        roi_ranges = {
            "< -10%": {"min": float('-inf'), "max": -10.0},
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
            "> 10%": {"min": 10.0, "max": float('inf')}
        }

        # Inicializar distribución (ahora cuenta AGENTES, no cuentas)
        distribution = {range_key: {"agents": 0, "total_aum": 0.0} for range_key in roi_ranges.keys()}

        # Calcular totales
        total_agents = len(agents_with_roi)
        total_aum = sum(agent["total_aum"] for agent in agents_with_roi)

        # Clasificar cada agente en su rango de ROI
        for agent in agents_with_roi:
            roi_decimal = agent["roi_7d"]  # ROI en decimal (ej: 0.09295290 = 9.30%)
            roi_pct = roi_decimal * 100  # Convertir a porcentaje
            aum = agent["total_aum"]

            # Encontrar rango correspondiente
            for range_key, range_vals in roi_ranges.items():
                if range_vals["min"] <= roi_pct < range_vals["max"]:
                    distribution[range_key]["agents"] += 1
                    distribution[range_key]["total_aum"] += aum
                    break

        # Convertir a lista ordenada
        distribution_list = []
        for range_key in roi_ranges.keys():
            distribution_list.append({
                "roi_range": range_key,
                "agents": distribution[range_key]["agents"],
                "total_aum": round(distribution[range_key]["total_aum"], 2)
            })

        return {
            "success": True,
            "date": target_date.isoformat(),
            "summary": {
                "total_agents": total_agents,  # Agentes activos en Casterly Rock
                "total_aum": round(total_aum, 2),  # AUM total de todos los agentes
                "source": "top16_by_day"  # Fuente de datos
            },
            "distribution": distribution_list
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar distribucion de ROI: {str(e)}"
        )




@router.get("/top-agents")
async def get_top_agents(
    date: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD. Si no se especifica, retorna el Top 16 del dia mas reciente")
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

    # Obtener window_days de la última simulación
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})
    window_days = config.get("window_days", 7) if config else 7

    # Obtener colección dinámica
    from app.utils.collection_names import get_top16_collection_name
    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = db[top16_collection_name]

    logger.info(f"Top Agents usando colección: {top16_collection_name}")

    if date:
        try:
            target_date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            date_str = date
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")
    else:
        latest_doc = top16_collection.find_one(sort=[("date", -1)])
        if not latest_doc:
            return {
                "success": False,
                "message": f"No hay datos de {top16_collection_name} disponibles",
                "date": None,
                "top16": []
            }
        date_str = latest_doc["date"]

    # Obtener Top 16 directamente de la colección dinámica
    top16_docs = list(top16_collection.find({
        "date": date_str
    }).sort("rank", 1))

    if not top16_docs:
        return {
            "success": False,
            "message": f"No se encontraron agentes para la fecha {date_str}",
            "date": date_str,
            "top16": []
        }

    # Mapear a formato de respuesta
    roi_field = f"roi_{window_days}d"
    top16_data = []
    for doc in top16_docs:
        top16_data.append({
            "rank": doc.get("rank"),
            "agent_id": doc.get("agent_id"),
            "roi_7d": doc.get(roi_field, 0.0),
            "n_accounts": doc.get("n_accounts", 0),
            "total_aum": doc.get("total_aum", 0.0),
            "is_in_casterly": doc.get("is_in_casterly", True)
        })

    in_casterly_count = sum(1 for agent in top16_data if agent["is_in_casterly"])

    # Obtener rango de fechas ROI_7D desde agent_roi_7d
    roi_7d_collection = db.agent_roi_7d
    roi_7d_doc = roi_7d_collection.find_one({"target_date": date_str})

    window_start = None
    window_end = None
    if roi_7d_doc:
        window_start = roi_7d_doc.get("window_start")
        window_end = roi_7d_doc.get("window_end")

    return {
        "success": True,
        "date": date_str,
        "window_start": window_start,
        "window_end": window_end,
        "total_agents": len(top16_data),
        "in_casterly_count": in_casterly_count,
        "top16": top16_data
    }


@router.get("/rotation-history")
async def get_rotation_history(
    start_date: Optional[str] = Query(None, description="Fecha inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha fin en formato YYYY-MM-DD"),
    agent_id: Optional[str] = Query(None, description="Filtrar por agent_id (puede ser agent_out o agent_in)"),
    rotation_log_repo: RotationLogRepositoryDep = None
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
            "rotations": []
        }

    rotations_data = []
    for rotation in rotations:
        rotations_data.append({
            "date": rotation.date.isoformat() if hasattr(rotation.date, 'isoformat') else str(rotation.date),
            "agent_out": rotation.agent_out,
            "agent_in": rotation.agent_in,
            "reason": rotation.reason.value if hasattr(rotation.reason, 'value') else rotation.reason,
            "roi_7d_out": rotation.roi_7d_out,
            "roi_total_out": rotation.roi_total_out,
            "roi_7d_in": rotation.roi_7d_in,
            "n_accounts": rotation.n_accounts,
            "total_aum": rotation.total_aum
        })

    return {
        "success": True,
        "start_date": start_date,
        "end_date": end_date,
        "agent_id": agent_id,
        "total_rotations": len(rotations_data),
        "rotations": rotations_data
    }


@router.get("/rank-changes")
async def get_rank_changes(
    start_date: Optional[str] = Query(None, description="Fecha inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha fin en formato YYYY-MM-DD"),
    agent_id: Optional[str] = Query(None, description="Filtrar por agent_id"),
    min_change: Optional[int] = Query(None, description="Filtrar por cambio mínimo de posiciones (ej: 3)", ge=1)
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
            "rank_changes": []
        }

    # Convertir entidades a diccionarios
    rank_changes_data = []
    for rc in rank_changes:
        rank_changes_data.append({
            "date": rc.date.isoformat() if hasattr(rc.date, 'isoformat') else str(rc.date),
            "agent_id": rc.agent_id,
            "previous_rank": rc.previous_rank,
            "current_rank": rc.current_rank,
            "rank_change": rc.rank_change,
            "movement_type": rc.movement_type,
            "is_significant": rc.is_significant,
            "previous_roi": rc.previous_roi,
            "current_roi": rc.current_roi,
            "roi_change": rc.roi_change,
            "is_in_casterly": rc.is_in_casterly
        })

    # Calcular estadísticas
    total_ups = sum(1 for rc in rank_changes_data if rc["rank_change"] > 0)
    total_downs = sum(1 for rc in rank_changes_data if rc["rank_change"] < 0)
    avg_change = sum(abs(rc["rank_change"]) for rc in rank_changes_data) / len(rank_changes_data) if rank_changes_data else 0

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
            "average_absolute_change": round(avg_change, 2)
        },
        "rank_changes": rank_changes_data
    }


@router.get("/top16-timeline")
async def get_top16_timeline(
    target_date: Optional[date] = Query(None, description="Fecha objetivo (YYYY-MM-DD). Si no se especifica, usa la más reciente")
) -> Dict[str, Any]:
    """
    Obtiene el timeline del Top 16 día por día según la ventana de la última simulación.

    Muestra cómo cambió la composición del Top 16 durante la ventana configurada,
    indicando qué agentes entraron, salieron y su rank en cada día.

    Retorna:
    - dates: Lista de fechas en el período
    - agents: Lista de agentes únicos con su timeline
    """
    from datetime import timedelta
    from app.utils.collection_names import get_top16_collection_name

    db = database_manager.get_database()

    # Obtener window_days de la última simulación
    system_config_col = db["system_config"]
    config = system_config_col.find_one({"config_key": "last_simulation"})
    window_days = config.get("window_days", 7) if config else 7

    logger.info(f"Timeline usando ventana de {window_days} días")

    # Obtener colección dinámica
    top16_collection_name = get_top16_collection_name(window_days)
    top16_collection = db[top16_collection_name]
    rotation_collection = db.rotation_log

    # Obtener fecha más reciente si no se especifica
    if not target_date:
        latest_doc = top16_collection.find_one(sort=[("date", -1)])
        if not latest_doc:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontraron datos en {top16_collection_name}"
            )
        target_date = date.fromisoformat(latest_doc["date"])

    # Calcular ventana según window_days
    start_date = target_date - timedelta(days=window_days - 1)

    # Generar lista de fechas
    dates = []
    current = start_date
    while current <= target_date:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    # Obtener todos los registros de top16_by_day en el rango
    top16_docs = list(top16_collection.find({
        "date": {"$gte": start_date.isoformat(), "$lte": target_date.isoformat()}
    }).sort("date", 1))

    if not top16_docs:
        return {
            "success": False,
            "message": f"No se encontraron datos para el período {start_date.isoformat()} - {target_date.isoformat()}",
            "dates": dates,
            "agents": []
        }

    # Obtener información de ROI diario para detectar días de pérdida
    # OPTIMIZADO: Una sola consulta bulk en lugar de N×M consultas individuales
    from app.utils.collection_names import get_roi_collection_name
    roi_collection_name = get_roi_collection_name(window_days)
    roi_collection = db[roi_collection_name]

    # Crear un mapa de agent_id -> date -> daily_roi_for_that_date
    daily_roi_map = {}  # {agent_id: {date: roi_value}}

    # Obtener todos los agentes únicos del top16
    unique_agents = list(set(doc["agent_id"] for doc in top16_docs))

    logger.info(f"[TIMELINE] Obteniendo daily_roi para {len(unique_agents)} agentes en {len(dates)} fechas")

    # OPTIMIZACION: Una sola consulta para todos los agentes y fechas
    roi_docs = list(roi_collection.find({
        "userId": {"$in": unique_agents},
        "target_date": {"$in": dates}
    }))

    logger.info(f"[TIMELINE] Encontrados {len(roi_docs)} documentos de ROI")

    # Construir el mapa desde los documentos obtenidos
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

    # Obtener rotaciones en el período
    # Las fechas en rotation_log están guardadas como strings ISO, no como datetime
    logger.info(f"[TIMELINE DEBUG] start_date type: {type(start_date)}, value: {start_date}")
    logger.info(f"[TIMELINE DEBUG] target_date type: {type(target_date)}, value: {target_date}")

    start_date_str = start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date
    target_date_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else target_date

    start_date_str = start_date_str + "T00:00:00" if isinstance(start_date_str, str) and "T" not in start_date_str else start_date_str
    target_date_str = target_date_str + "T23:59:59" if isinstance(target_date_str, str) and "T" not in target_date_str else target_date_str

    rotation_docs = list(rotation_collection.find({
        "date": {"$gte": start_date_str, "$lte": target_date_str}
    }).sort("date", 1))

    # Crear mapas de rotaciones por agente y fecha
    rotation_out_map = {}  # {agent_id: {date: {reason, details}}}
    rotation_in_map = {}   # {agent_id: {date: {reason, details}}}

    print(f"\n========== [TIMELINE DEBUG] ==========")
    print(f"Rango de fechas: {start_date} a {target_date}")
    print(f"start_date_str: {start_date_str}")
    print(f"target_date_str: {target_date_str}")
    print(f"Total rotaciones encontradas: {len(rotation_docs)}")

    if len(rotation_docs) > 0:
        print(f"Primera rotacion: {rotation_docs[0]}")
    else:
        # Ver si hay rotaciones en general
        all_rotations = list(rotation_collection.find().limit(5))
        print(f"Total rotaciones en toda la coleccion: {rotation_collection.count_documents({})}")
        if all_rotations:
            print(f"Ejemplo de rotacion (cualquier fecha): {all_rotations[0]}")
    print(f"======================================\n")

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
            rotation_out_map[agent_out][rot_date_str] = {
                "reason": reason,
                "details": reason_details
            }

        # Registrar entrada
        if agent_in:
            if agent_in not in rotation_in_map:
                rotation_in_map[agent_in] = {}
            rotation_in_map[agent_in][rot_date_str] = {
                "reason": reason,
                "details": reason_details
            }

    # Agrupar por agente
    agents_data = {}
    roi_field = f"roi_{window_days}d"

    for doc in top16_docs:
        agent_id = doc.get("agent_id")
        date_str = doc.get("date")
        rank = doc.get("rank")
        roi_value = doc.get(roi_field, 0.0)
        is_in_casterly = doc.get("is_in_casterly", False)

        if agent_id not in agents_data:
            agents_data[agent_id] = {
                "agent_id": agent_id,
                "timeline": {},
                "entry_info": rotation_in_map.get(agent_id, {}),
                "exit_info": rotation_out_map.get(agent_id, {})
            }

        # Obtener el ROI diario específico de este día
        daily_roi = daily_roi_map.get(agent_id, {}).get(date_str, None)
        is_loss_day = daily_roi is not None and daily_roi < 0

        agents_data[agent_id]["timeline"][date_str] = {
            "rank": rank,
            "roi_7d": roi_value,
            "in_top16": is_in_casterly,
            "daily_roi": daily_roi,
            "is_loss_day": is_loss_day
        }

    # Construir timeline completo para cada agente (rellenar días faltantes)
    agents_list = []
    for agent_id, agent_info in agents_data.items():
        timeline = []
        for date_str in dates:
            if date_str in agent_info["timeline"]:
                timeline.append({
                    "date": date_str,
                    **agent_info["timeline"][date_str]
                })
            else:
                # No estaba en el Top 16 ese día
                # Pero podría tener daily_roi si tiene datos
                daily_roi = daily_roi_map.get(agent_id, {}).get(date_str, None)
                is_loss_day = daily_roi is not None and daily_roi < 0

                timeline.append({
                    "date": date_str,
                    "rank": None,
                    "roi_7d": None,
                    "in_top16": False,
                    "daily_roi": daily_roi,
                    "is_loss_day": is_loss_day
                })

        agents_list.append({
            "agent_id": agent_id,
            "timeline": timeline,
            "entry_info": agent_info.get("entry_info", {}),
            "exit_info": agent_info.get("exit_info", {})
        })

    # Ordenar agentes por su mejor rank
    agents_list.sort(key=lambda a: min(
        [day["rank"] for day in a["timeline"] if day["rank"] is not None],
        default=999
    ))

    # Log de ejemplo
    if agents_list:
        sample_agent = agents_list[0]
        logger.info(f"[TIMELINE] Ejemplo de agente: {sample_agent['agent_id']}")
        logger.info(f"[TIMELINE]   entry_info: {sample_agent.get('entry_info', {})}")
        logger.info(f"[TIMELINE]   exit_info: {sample_agent.get('exit_info', {})}")

    return {
        "success": True,
        "window_days": window_days,
        "target_date": target_date.isoformat() if hasattr(target_date, 'isoformat') else target_date,
        "start_date": start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date,
        "dates": dates,
        "total_agents": len(agents_list),
        "agents": agents_list
    }
