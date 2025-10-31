from typing import List, Optional
from datetime import datetime, date
from app.domain.repositories.simulation_repository import SimulationRepository
from app.domain.entities.simulation import (
    Simulation,
    SimulationConfig,
    SimulationKPIs,
    TopAgentSummary,
    RotationsSummary,
    DailyMetric
)
from app.config.database import database_manager


class SimulationRepositoryImpl(SimulationRepository):
    """
    Implementacion concreta del repositorio de simulaciones usando MongoDB.
    """

    def __init__(self):
        self.collection_name = "simulations"

    def create(self, simulation: Simulation) -> Simulation:
        """Crea una nueva simulacion en la base de datos."""
        collection = database_manager.get_collection(self.collection_name)

        doc = simulation.model_dump(by_alias=True, exclude_none=True)
        if "_id" in doc:
            del doc["_id"]
        if "id" in doc:
            del doc["id"]

        # Convertir objetos date a isoformat para MongoDB
        doc = self._convert_dates_to_str(doc)

        # Asegurar que created_at este presente
        if "createdAt" not in doc:
            doc["createdAt"] = datetime.now()

        result = collection.insert_one(doc)
        simulation.id = str(result.inserted_id)

        return simulation

    def _convert_dates_to_str(self, obj):
        """Convierte recursivamente objetos date/datetime a strings ISO."""
        if isinstance(obj, dict):
            return {k: self._convert_dates_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_dates_to_str(item) for item in obj]
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    def get_all(self, limit: int = 50) -> List[Simulation]:
        """Obtiene todas las simulaciones ordenadas por fecha descendente."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find().sort("createdAt", -1).limit(limit)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_id(self, simulation_id: str) -> Optional[Simulation]:
        """Obtiene una simulacion por su simulation_id."""
        collection = database_manager.get_collection(self.collection_name)

        doc = collection.find_one({"simulation_id": simulation_id})

        if not doc:
            return None

        return self._doc_to_entity(doc)

    def update(self, simulation_id: str, name: str, description: Optional[str] = None) -> bool:
        """Actualiza el nombre y descripcion de una simulacion."""
        collection = database_manager.get_collection(self.collection_name)

        update_fields = {"name": name}
        if description is not None:
            update_fields["description"] = description

        result = collection.update_one(
            {"simulation_id": simulation_id},
            {"$set": update_fields}
        )

        return result.modified_count > 0

    def delete(self, simulation_id: str) -> bool:
        """Elimina una simulacion por su simulation_id."""
        collection = database_manager.get_collection(self.collection_name)

        result = collection.delete_one({"simulation_id": simulation_id})

        return result.deleted_count > 0

    def count(self) -> int:
        """Cuenta el total de simulaciones guardadas."""
        collection = database_manager.get_collection(self.collection_name)

        return collection.count_documents({})

    def get_by_ids(self, simulation_ids: List[str]) -> List[Simulation]:
        """Obtiene multiples simulaciones por sus IDs para comparacion."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({"simulation_id": {"$in": simulation_ids}})

        return [self._doc_to_entity(doc) for doc in docs]

    def _doc_to_entity(self, doc: dict) -> Simulation:
        """Convierte un documento de MongoDB a entidad Simulation."""
        # Convertir subdocumentos a entidades
        config = SimulationConfig(**doc["config"])
        kpis = SimulationKPIs(**doc["kpis"])
        top_16_final = [TopAgentSummary(**agent) for agent in doc["top_16_final"]]
        rotations_summary = RotationsSummary(**doc["rotations_summary"])
        daily_metrics = [DailyMetric(**metric) for metric in doc["daily_metrics"]]

        return Simulation(
            _id=str(doc["_id"]),
            simulation_id=doc["simulation_id"],
            name=doc.get("name", "Simulacion sin nombre"),
            description=doc.get("description"),
            createdAt=doc.get("createdAt"),
            config=config,
            kpis=kpis,
            top_16_final=top_16_final,
            rotations_summary=rotations_summary,
            daily_metrics=daily_metrics
        )
