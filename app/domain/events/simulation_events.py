from datetime import date
from typing import Dict, Any
from app.domain.events.base import DomainEvent


class DailyProcessCompletedEvent(DomainEvent):
    """
    Evento: Se ha completado el procesamiento de un dia.

    Este evento se dispara cuando se terminan todas las operaciones
    diarias (seleccion, asignacion, clasificacion, evaluacion, rotaciones).
    """

    def __init__(
        self,
        process_date: date,
        agents_in_casterly: int,
        total_aum: float,
        rotations_count: int,
        growth_agents: int,
        fall_agents: int,
        processing_time_ms: float = 0.0
    ):
        super().__init__()
        self.process_date = process_date
        self.agents_in_casterly = agents_in_casterly
        self.total_aum = total_aum
        self.rotations_count = rotations_count
        self.growth_agents = growth_agents
        self.fall_agents = fall_agents
        self.processing_time_ms = processing_time_ms

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "process_date": self.process_date.isoformat(),
            "agents_in_casterly": self.agents_in_casterly,
            "total_aum": self.total_aum,
            "rotations_count": self.rotations_count,
            "growth_agents": self.growth_agents,
            "fall_agents": self.fall_agents,
            "processing_time_ms": self.processing_time_ms
        }


class SimulationCompletedEvent(DomainEvent):
    """
    Evento: Se ha completado toda la simulacion.

    Este evento se dispara cuando finaliza el procesamiento
    de todos los dias del rango de simulacion.
    """

    def __init__(
        self,
        start_date: date,
        end_date: date,
        total_days: int,
        total_rotations: int,
        final_agents_count: int,
        final_aum: float,
        simulation_duration_seconds: float = 0.0,
        success: bool = True,
        errors: list = None
    ):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.total_days = total_days
        self.total_rotations = total_rotations
        self.final_agents_count = final_agents_count
        self.final_aum = final_aum
        self.simulation_duration_seconds = simulation_duration_seconds
        self.success = success
        self.errors = errors or []

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_days": self.total_days,
            "total_rotations": self.total_rotations,
            "final_agents_count": self.final_agents_count,
            "final_aum": self.final_aum,
            "simulation_duration_seconds": self.simulation_duration_seconds,
            "success": self.success,
            "errors_count": len(self.errors),
            "errors": self.errors
        }
