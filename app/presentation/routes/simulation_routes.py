from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import date
from typing import Dict, Any
from app.application.services.daily_orchestrator_service import DailyOrchestratorService
from app.config.database import database_manager

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])

orchestrator_service = DailyOrchestratorService()


class SimulationRequest(BaseModel):
    start_date: date = Field(..., description="Fecha de inicio de la simulacion (YYYY-MM-DD)")
    end_date: date = Field(..., description="Fecha de fin de la simulacion (YYYY-MM-DD)")

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-09-01",
                "end_date": "2025-10-07"
            }
        }


@router.post("/run")
async def run_simulation(request: SimulationRequest) -> Dict[str, Any]:
    try:
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=400,
                detail="La fecha de inicio debe ser anterior o igual a la fecha de fin"
            )

        # LIMPIAR COLECCIONES ANTES DE EJECUTAR LA SIMULACIÓN
        # Preservar: balances, mov07.10 y movements (datos historicos reales)
        db = database_manager.get_database()

        collections_to_clean = [
            "agent_states",
            "assignments",
            "rotation_log",
            "top16_by_day",
            "top16_day"
        ]

        cleaned_collections = []
        for collection_name in collections_to_clean:
            result = db[collection_name].delete_many({})
            cleaned_collections.append({
                "collection": collection_name,
                "deleted_count": result.deleted_count
            })

        # Ejecutar la simulación con datos limpios
        result = orchestrator_service.run_simulation(
            start_date=request.start_date,
            end_date=request.end_date
        )

        return {
            "success": True,
            "message": "Simulacion ejecutada exitosamente",
            "cleaned_collections": cleaned_collections,
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar la simulacion: {str(e)}"
        )
