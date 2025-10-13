from fastapi import APIRouter, HTTPException, Query
from datetime import date
from typing import Dict, Any, Optional, List
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl
from app.infrastructure.repositories.rotation_log_repository_impl import RotationLogRepositoryImpl
from app.config.database import database_manager

router = APIRouter(prefix="/api/reports", tags=["Reports"])

state_repo = AgentStateRepositoryImpl()
assignment_repo = AssignmentRepositoryImpl()
rotation_log_repo = RotationLogRepositoryImpl()


@router.get("/summary")
async def get_summary_report(
    start_date: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha de fin (YYYY-MM-DD)")
) -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("agent_states")

        if not start_date or not end_date:
            latest_doc = collection.find_one(sort=[("date", -1)])
            if not latest_doc:
                raise HTTPException(
                    status_code=404,
                    detail="No se encontraron datos en la base de datos"
                )
            end_date = date.fromisoformat(latest_doc["date"])
            earliest_doc = collection.find_one(sort=[("date", 1)])
            start_date = date.fromisoformat(earliest_doc["date"])

        pipeline = [
            {
                "$match": {
                    "date": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    },
                    "is_in_casterly": True
                }
            },
            {
                "$group": {
                    "_id": "$agent_id",
                    "total_roi": {"$sum": "$roi_day"},
                    "roi_values": {"$push": "$roi_day"},
                    "roi_since_entry_values": {"$push": "$roi_since_entry"},
                    "days_in_casterly": {"$sum": 1}
                }
            }
        ]

        agent_stats = list(collection.aggregate(pipeline))

        if not agent_stats:
            return {
                "success": False,
                "message": "No se encontraron agentes activos en el periodo especificado"
            }

        # Obtener asignaciones activas para calcular ROI ponderado
        assignments = list(assignment_repo.get_active_assignments())

        # Crear set de agent_ids para búsqueda rápida
        agent_ids_in_stats = {ag["_id"] for ag in agent_stats}

        # Sumar balances por agente (un agente puede tener múltiples asignaciones/cuentas)
        agent_balances = {}
        for a in assignments:
            if a.agent_id in agent_ids_in_stats:
                agent_balances[a.agent_id] = agent_balances.get(a.agent_id, 0.0) + a.balance

        # ROI Total (promedio ponderado por balance)
        total_balance = sum(agent_balances.values()) if agent_balances else 1.0
        weighted_roi = 0.0

        for agent in agent_stats:
            agent_id = agent["_id"]
            balance = agent_balances.get(agent_id, 0.0)
            weight = balance / total_balance if total_balance > 0 else 0.0
            weighted_roi += agent["total_roi"] * weight

        # ROI Promedio (simple - para comparación)
        total_roi_sum = sum(agent["total_roi"] for agent in agent_stats)
        avg_roi_simple = total_roi_sum / len(agent_stats) if agent_stats else 0

        # Max Drawdown (cálculo correcto desde picos)
        # Para cada agente, calcular el max drawdown de su serie roi_since_entry
        agent_drawdowns = []
        for agent in agent_stats:
            roi_series = agent.get("roi_since_entry_values", [])
            if roi_series and len(roi_series) >= 2:
                # Convertir ROI acumulado a serie de retornos
                cumulative = [1.0]  # Empezar con 1.0 (100%)
                for roi in roi_series:
                    cumulative.append(1.0 + roi)  # roi_since_entry ya es decimal

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

                agent_drawdowns.append(max_dd)

        # El max drawdown global es el peor de todos los agentes
        max_drawdown_global = min(agent_drawdowns) if agent_drawdowns else 0.0

        # Volatilidad (desviación estándar muestral - usando N-1)
        all_roi_values = []
        for agent in agent_stats:
            all_roi_values.extend(agent["roi_values"])

        if all_roi_values and len(all_roi_values) > 1:
            mean_roi = sum(all_roi_values) / len(all_roi_values)
            # Varianza muestral (N-1)
            variance = sum((x - mean_roi) ** 2 for x in all_roi_values) / (len(all_roi_values) - 1)
            volatility = variance ** 0.5
        else:
            volatility = 0.0

        rotation_logs = rotation_log_repo.get_by_date_range(start_date, end_date)
        total_rotations = len(rotation_logs)

        states_final = state_repo.get_by_date(end_date)
        active_agents_final = [s.agent_id for s in states_final if s.is_in_casterly]

        # Calcular Win Rate (% de agentes con ROI positivo)
        positive_roi_agents = sum(1 for agent in agent_stats if agent["total_roi"] > 0)
        win_rate = (positive_roi_agents / len(agent_stats)) if agent_stats else 0

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "kpis": {
                "total_roi": round(weighted_roi, 4),  # ROI ponderado por balance
                "average_roi": round(avg_roi_simple, 4),  # ROI promedio simple
                "max_drawdown": round(max_drawdown_global, 4),  # Max drawdown correcto
                "volatility": round(volatility, 4),  # Volatilidad con N-1
                "total_rotations": total_rotations,
                "active_agents_count": len(active_agents_final),
                "unique_agents_in_period": len(agent_stats),
                "win_rate": round(win_rate, 4)  # Nuevo: Win rate
            },
            "active_agents": active_agents_final
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar reporte de resumen: {str(e)}"
        )


@router.get("/roi-distribution")
async def get_roi_distribution(
    target_date: Optional[date] = Query(None, description="Fecha objetivo (YYYY-MM-DD)")
) -> Dict[str, Any]:
    try:
        assignment_collection = database_manager.get_collection("assignments")
        state_collection = database_manager.get_collection("agent_states")

        if not target_date:
            latest_doc = state_collection.find_one(sort=[("date", -1)])
            if not latest_doc:
                raise HTTPException(
                    status_code=404,
                    detail="No se encontraron datos en la base de datos"
                )
            target_date = date.fromisoformat(latest_doc["date"])

        states = list(state_collection.find({
            "date": target_date.isoformat(),
            "is_in_casterly": True
        }))

        if not states:
            return {
                "success": False,
                "message": f"No se encontraron agentes activos para la fecha {target_date.isoformat()}"
            }

        active_agents = [state["agent_id"] for state in states]

        active_assignments = list(assignment_collection.find({
            "is_active": True,
            "agent_id": {"$in": active_agents}
        }))

        if not active_assignments:
            return {
                "success": False,
                "message": f"No se encontraron asignaciones activas para la fecha {target_date.isoformat()}"
            }

        states_map = {state["agent_id"]: state for state in states}

        accounts_with_roi = []
        for assignment in active_assignments:
            agent_id = assignment["agent_id"]
            if agent_id in states_map:
                accounts_with_roi.append({
                    "account_id": assignment["account_id"],
                    "agent_id": agent_id,
                    "balance": assignment["balance"],
                    "roi_since_entry": states_map[agent_id]["roi_since_entry"]
                })

        if not accounts_with_roi:
            return {
                "success": False,
                "message": f"No se pudieron calcular ROIs para la fecha {target_date.isoformat()}"
            }

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

        distribution = {range_key: {"accounts": 0, "total_aum": 0.0} for range_key in roi_ranges.keys()}

        total_accounts = len(accounts_with_roi)
        total_aum = sum(acc["balance"] for acc in accounts_with_roi)

        for account in accounts_with_roi:
            roi_decimal = account["roi_since_entry"]
            roi_pct = roi_decimal * 100 if roi_decimal is not None else 0.0
            balance = account["balance"]

            for range_key, range_vals in roi_ranges.items():
                if range_vals["min"] <= roi_pct < range_vals["max"]:
                    distribution[range_key]["accounts"] += 1
                    distribution[range_key]["total_aum"] += balance
                    break

        distribution_list = []
        for range_key in roi_ranges.keys():
            distribution_list.append({
                "roi_range": range_key,
                "accounts": distribution[range_key]["accounts"],
                "total_aum": round(distribution[range_key]["total_aum"], 2)
            })

        return {
            "success": True,
            "date": target_date.isoformat(),
            "summary": {
                "total_accounts": total_accounts,
                "total_aum": round(total_aum, 2)
            },
            "distribution": distribution_list
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar distribucion de ROI: {str(e)}"
        )


@router.get("/roi-evolution")
async def get_roi_evolution(
    start_date: Optional[date] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha fin (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Obtiene la evolución del ROI día a día para graficar la serie temporal real.
    Calcula el ROI acumulado promedio de todos los agentes en Casterly Rock por día.
    """
    try:
        state_collection = database_manager.get_collection("agent_states")

        # Si no se especifica rango, usar últimos 30 días desde la última fecha disponible
        if not end_date:
            latest_doc = state_collection.find_one(sort=[("date", -1)])
            if not latest_doc:
                raise HTTPException(status_code=404, detail="No se encontraron datos")
            end_date = date.fromisoformat(latest_doc["date"])

        if not start_date:
            # Calcular 30 días antes
            from datetime import timedelta
            start_date = end_date - timedelta(days=30)

        # Obtener todos los agent_states del período, agrupados por fecha
        pipeline = [
            {
                "$match": {
                    "date": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    },
                    "is_in_casterly": True
                }
            },
            {
                "$group": {
                    "_id": "$date",
                    "avg_roi_since_entry": {"$avg": "$roi_since_entry"},
                    "agents_count": {"$sum": 1},
                    "roi_values": {"$push": "$roi_since_entry"}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]

        daily_data = list(state_collection.aggregate(pipeline))

        if not daily_data:
            return {
                "success": False,
                "message": f"No se encontraron datos para el período {start_date} - {end_date}"
            }

        # Formatear datos para el gráfico
        evolution_data = []
        for day_data in daily_data:
            evolution_data.append({
                "date": day_data["_id"],
                "avg_roi": round(day_data["avg_roi_since_entry"], 6),
                "agents_count": day_data["agents_count"]
            })

        # Calcular línea de tendencia (regresión lineal simple)
        n = len(evolution_data)
        if n >= 2:
            x_vals = list(range(n))
            y_vals = [d["avg_roi"] for d in evolution_data]

            # Calcular pendiente y ordenada
            x_mean = sum(x_vals) / n
            y_mean = sum(y_vals) / n

            numerator = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
            denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))

            if denominator != 0:
                slope = numerator / denominator
                intercept = y_mean - slope * x_mean

                # Agregar valores de tendencia
                for i, data in enumerate(evolution_data):
                    data["trend"] = round(intercept + slope * i, 6)
            else:
                for data in evolution_data:
                    data["trend"] = data["avg_roi"]
        else:
            for data in evolution_data:
                data["trend"] = data["avg_roi"]

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "data": evolution_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar evolución de ROI: {str(e)}"
        )


@router.get("/agents-performance")
async def get_agents_performance(
    start_date: Optional[date] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha fin (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Obtiene el rendimiento de agentes clasificados por estado (Growth, Fall, Neutral).
    - Growth: Agentes con ROI positivo en el período
    - Fall: Agentes con ROI negativo en el período
    - Neutral: Agentes con ROI cercano a 0 (entre -0.1% y +0.1%)
    """
    try:
        state_collection = database_manager.get_collection("agent_states")

        # Si no se especifica rango, usar últimos 30 días
        if not end_date:
            latest_doc = state_collection.find_one(sort=[("date", -1)])
            if not latest_doc:
                raise HTTPException(status_code=404, detail="No se encontraron datos")
            end_date = date.fromisoformat(latest_doc["date"])

        if not start_date:
            from datetime import timedelta
            start_date = end_date - timedelta(days=30)

        # Obtener ROI acumulado total por agente en el período (suma de roi_day)
        pipeline = [
            {
                "$match": {
                    "date": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    },
                    "is_in_casterly": True
                }
            },
            {
                "$group": {
                    "_id": "$agent_id",
                    "total_roi": {"$sum": "$roi_day"},
                    "days_count": {"$sum": 1}
                }
            }
        ]

        agent_stats = list(state_collection.aggregate(pipeline))

        # Si no hay datos con roi_day (todos son 0), usar el ROI since entry al final del período
        if agent_stats and all(abs(agent["total_roi"]) < 0.000001 for agent in agent_stats):
            # Usar roi_since_entry de la fecha final del período
            final_states = list(state_collection.find({
                "date": end_date.isoformat(),
                "is_in_casterly": True
            }))

            if final_states:
                agent_stats = [
                    {
                        "_id": state["agent_id"],
                        "total_roi": state["roi_since_entry"]
                    }
                    for state in final_states
                ]

        if not agent_stats:
            return {
                "success": False,
                "message": f"No se encontraron agentes para el período {start_date} - {end_date}"
            }

        # Clasificar agentes por rendimiento
        growth_count = 0
        fall_count = 0
        neutral_count = 0

        growth_agents = []
        fall_agents = []
        neutral_agents = []

        threshold = 0.001  # 0.1% - umbral para considerar neutral

        for agent in agent_stats:
            agent_id = agent["_id"]
            total_roi = agent["total_roi"]

            if total_roi > threshold:
                growth_count += 1
                growth_agents.append({
                    "agent_id": agent_id,
                    "roi": round(total_roi, 6)
                })
            elif total_roi < -threshold:
                fall_count += 1
                fall_agents.append({
                    "agent_id": agent_id,
                    "roi": round(total_roi, 6)
                })
            else:
                neutral_count += 1
                neutral_agents.append({
                    "agent_id": agent_id,
                    "roi": round(total_roi, 6)
                })

        total_agents = len(agent_stats)

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_agents": total_agents,
                "growth_count": growth_count,
                "fall_count": fall_count,
                "neutral_count": neutral_count,
                "growth_percentage": round((growth_count / total_agents * 100), 2) if total_agents > 0 else 0,
                "fall_percentage": round((fall_count / total_agents * 100), 2) if total_agents > 0 else 0,
                "neutral_percentage": round((neutral_count / total_agents * 100), 2) if total_agents > 0 else 0
            },
            "details": {
                "growth_agents": growth_agents,
                "fall_agents": fall_agents,
                "neutral_agents": neutral_agents
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar rendimiento de agentes: {str(e)}"
        )
