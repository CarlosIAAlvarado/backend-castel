from fastapi import APIRouter, HTTPException, Query
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl
from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl
from app.infrastructure.repositories.rotation_log_repository_impl import RotationLogRepositoryImpl

router = APIRouter(prefix="/api", tags=["Query Endpoints"])

state_repo = AgentStateRepositoryImpl()
top16_repo = Top16RepositoryImpl()
assignment_repo = AssignmentRepositoryImpl()
rotation_log_repo = RotationLogRepositoryImpl()


@router.get("/agents/daily-kpis")
async def get_agents_daily_kpis(
    date: str = Query(..., description="Fecha en formato YYYY-MM-DD")
) -> Dict[str, Any]:
    """
    Obtiene los KPIs diarios de todos los agentes para una fecha especifica.

    Retorna:
    - agent_id
    - state (GROWTH/FALL)
    - roi_day
    - pnl_day
    - balance_base
    - fall_days
    - is_in_casterly
    - roi_since_entry
    - entry_date
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")

    states = state_repo.get_by_date(target_date)

    if not states:
        return {
            "success": False,
            "message": f"No se encontraron datos para la fecha {date}",
            "date": date,
            "agents": []
        }

    agents_data = []
    for state in states:
        agents_data.append({
            "agent_id": state.agent_id,
            "state": state.state.value,
            "roi_day": state.roi_day,
            "pnl_day": state.pnl_day,
            "balance_base": state.balance_base,
            "fall_days": state.fall_days,
            "is_in_casterly": state.is_in_casterly,
            "roi_since_entry": state.roi_since_entry,
            "entry_date": state.entry_date.isoformat() if state.entry_date else None
        })

    growth_count = sum(1 for agent in agents_data if agent["state"] == "GROWTH")
    fall_count = sum(1 for agent in agents_data if agent["state"] == "FALL")
    in_casterly_count = sum(1 for agent in agents_data if agent["is_in_casterly"])

    return {
        "success": True,
        "date": date,
        "total_agents": len(agents_data),
        "growth_count": growth_count,
        "fall_count": fall_count,
        "in_casterly_count": in_casterly_count,
        "agents": agents_data
    }


@router.get("/top16")
async def get_top16(
    date: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD. Si no se especifica, retorna el Top 16 del dia mas reciente")
) -> Dict[str, Any]:
    """
    Obtiene el ranking Top 16 de una fecha especifica o del dia mas reciente.
    Calcula ROI 7D y ROI 30D en tiempo real desde agent_states.

    Retorna:
    - rank
    - agent_id
    - roi_7d (calculado desde agent_states)
    - roi_30d (calculado desde agent_states)
    - n_accounts
    - total_aum
    - is_in_casterly
    """
    from app.config.database import database_manager
    from datetime import timedelta

    db = database_manager.get_database()

    # Determinar fecha objetivo
    if date:
        try:
            target_date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            date_str = date
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")
    else:
        # Obtener última fecha disponible
        latest_state = db.agent_states.find_one(sort=[("date", -1)])
        if not latest_state:
            return {
                "success": False,
                "message": "No hay datos de agent_states disponibles",
                "date": None,
                "top16": []
            }
        target_date_obj = datetime.fromisoformat(latest_state["date"]).date()
        date_str = target_date_obj.isoformat()

    # Obtener TODOS los agent_states de la fecha objetivo
    # Usar agregación para obtener solo UN registro por agente
    # Priorizar registros donde is_in_casterly: True
    target_states_pipeline = [
        {"$match": {"date": date_str}},
        {"$sort": {"agent_id": 1, "is_in_casterly": -1}},  # Ordenar por agent_id y priorizar is_in_casterly: True
        {"$group": {
            "_id": "$agent_id",
            "agent_id": {"$first": "$agent_id"},
            "roi_since_entry": {"$first": "$roi_since_entry"},
            "is_in_casterly": {"$first": "$is_in_casterly"}
        }}
    ]

    target_states = list(db.agent_states.aggregate(target_states_pipeline))

    if not target_states:
        return {
            "success": False,
            "message": f"No se encontraron agentes para la fecha {date_str}",
            "date": date_str,
            "top16": []
        }

    # Calcular fechas para ROI 7D y 30D
    date_7d_ago = (target_date_obj - timedelta(days=7)).isoformat()
    date_30d_ago = (target_date_obj - timedelta(days=30)).isoformat()

    # Obtener asignaciones activas para conocer el AUM por agente
    active_assignments = list(db.assignments.find({"is_active": True}))

    # Crear mapa de balances por agente
    agent_balances = {}
    agent_n_accounts = {}
    for assignment in active_assignments:
        agent_id = assignment["agent_id"]
        if agent_id not in agent_balances:
            agent_balances[agent_id] = 0.0
            agent_n_accounts[agent_id] = 0
        agent_balances[agent_id] += assignment["balance"]
        agent_n_accounts[agent_id] += 1

    # Construir datos de Top 16 con ROI calculados
    top16_data = []

    for state in target_states:
        agent_id = state["agent_id"]

        # ROI actual (desde entry)
        roi_since_entry = state.get("roi_since_entry", 0.0)

        # Calcular ROI 7D: cambio en roi_since_entry de hace 7 días a hoy
        state_7d = db.agent_states.find_one({
            "agent_id": agent_id,
            "date": {"$gte": date_7d_ago, "$lte": date_str}
        }, sort=[("date", 1)])

        if state_7d:
            roi_7d = roi_since_entry - state_7d.get("roi_since_entry", 0.0)
        else:
            roi_7d = 0.0

        # Calcular ROI 30D: cambio en roi_since_entry de hace 30 días a hoy
        state_30d = db.agent_states.find_one({
            "agent_id": agent_id,
            "date": {"$gte": date_30d_ago, "$lte": date_str}
        }, sort=[("date", 1)])

        if state_30d:
            roi_30d = roi_since_entry - state_30d.get("roi_since_entry", 0.0)
        else:
            roi_30d = None  # No hay datos suficientes

        top16_data.append({
            "agent_id": agent_id,
            "roi_since_entry": roi_since_entry,
            "roi_7d": roi_7d,
            "roi_30d": roi_30d,
            "n_accounts": agent_n_accounts.get(agent_id, 0),
            "total_aum": agent_balances.get(agent_id, 0.0),
            "is_in_casterly": state.get("is_in_casterly", True)
        })

    # Ordenar por ROI since entry descendente (mejor rendimiento histórico primero)
    # Si todos los ROI 7D son 0, usar roi_since_entry como criterio principal
    all_roi_7d_zero = all(agent["roi_7d"] == 0 for agent in top16_data)

    if all_roi_7d_zero:
        # Ordenar por ROI total desde entry
        top16_data.sort(key=lambda x: x["roi_since_entry"], reverse=True)
    else:
        # Ordenar por ROI 7D
        top16_data.sort(key=lambda x: x["roi_7d"], reverse=True)

    # Asignar ranks y limitar a top 16
    for idx, agent in enumerate(top16_data[:16], start=1):
        agent["rank"] = idx

    top16_final = top16_data[:16]
    in_casterly_count = sum(1 for agent in top16_final if agent["is_in_casterly"])

    return {
        "success": True,
        "date": date_str,
        "total_agents": len(top16_final),
        "in_casterly_count": in_casterly_count,
        "top16": top16_final
    }


@router.get("/assignments")
async def get_assignments(
    date: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD. Si no se especifica, retorna asignaciones activas actuales"),
    agent_id: Optional[str] = Query(None, description="Filtrar por agent_id especifico")
) -> Dict[str, Any]:
    """
    Obtiene las asignaciones de cuentas para una fecha o agente especifico.

    Si no se proporciona fecha, retorna todas las asignaciones activas actuales.

    Retorna:
    - account_id
    - agent_id
    - balance
    - assigned_at
    - is_active
    - date
    """
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")

        assignments = assignment_repo.get_by_date(target_date)
        date_str = date
    else:
        if agent_id:
            assignments = assignment_repo.get_active_by_agent(agent_id)
        else:
            from app.config.database import database_manager
            db = database_manager.get_database()
            collection = db[assignment_repo.collection_name]
            docs = list(collection.find({"is_active": True}))
            assignments = [assignment_repo._doc_to_entity(doc) for doc in docs]

        date_str = "current"

    if not assignments:
        return {
            "success": False,
            "message": f"No se encontraron asignaciones para {date_str}" + (f" y agente {agent_id}" if agent_id else ""),
            "date": date_str,
            "agent_id": agent_id,
            "assignments": []
        }

    assignments_data = []
    agents_summary = {}
    total_aum = 0.0

    for assignment in assignments:
        if agent_id and assignment.agent_id != agent_id:
            continue

        assignments_data.append({
            "account_id": assignment.account_id,
            "agent_id": assignment.agent_id,
            "balance": assignment.balance,
            "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            "is_active": assignment.is_active,
            "date": assignment.date.isoformat()
        })

        if assignment.agent_id not in agents_summary:
            agents_summary[assignment.agent_id] = {
                "n_accounts": 0,
                "total_aum": 0.0
            }

        agents_summary[assignment.agent_id]["n_accounts"] += 1
        agents_summary[assignment.agent_id]["total_aum"] += assignment.balance
        total_aum += assignment.balance

    return {
        "success": True,
        "date": date_str,
        "agent_id": agent_id,
        "total_assignments": len(assignments_data),
        "total_agents": len(agents_summary),
        "total_aum": total_aum,
        "agents_summary": agents_summary,
        "assignments": assignments_data
    }


@router.get("/rotation-log")
async def get_rotation_log(
    start_date: Optional[str] = Query(None, description="Fecha inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha fin en formato YYYY-MM-DD"),
    agent_id: Optional[str] = Query(None, description="Filtrar por agent_id (puede ser agent_out o agent_in)")
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
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")

        rotations = rotation_log_repo.get_by_date_range(start, end)
    else:
        from app.config.database import database_manager
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
