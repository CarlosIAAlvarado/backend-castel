from typing import List, Optional
from datetime import date, datetime
from pymongo.client_session import ClientSession
from app.domain.repositories.top16_repository import Top16Repository
from app.domain.entities.top16_day import Top16Day
from app.config.database import database_manager


class Top16RepositoryImpl(Top16Repository):
    """
    Implementacion concreta del repositorio de Top16 usando MongoDB.
    Soporta colecciones dinámicas para diferentes ventanas de días.

    Soporte para transacciones:
    - Acepta session opcional en constructor para Unit of Work
    - Todas las operaciones respetan la session si existe
    """

    def __init__(self, collection_name: str = "top16_by_day", session: Optional[ClientSession] = None):
        """
        Inicializa el repositorio.

        Args:
            collection_name: Nombre de la colección (ej: "top16_7d", "top16_30d").
                            Default: "top16_by_day" (para retrocompatibilidad)
            session: Session de MongoDB para transacciones (opcional)
        """
        self.collection_name = collection_name
        self.session = session

    def delete_all(self) -> int:
        """
        Elimina todos los registros de top16_by_day.
        Usado para mantener solo el snapshot mas reciente.

        Returns:
            Numero de registros eliminados
        """
        collection = database_manager.get_collection(self.collection_name)
        result = collection.delete_many({}, session=self.session)
        return result.deleted_count

    def create_batch(self, top16_list: List[Top16Day]) -> List[Top16Day]:
        """
        Crea multiples registros de Top 16 en una fecha.
        Guarda historial completo para consultas historicas.
        """
        collection = database_manager.get_collection(self.collection_name)

        docs = []
        for top16 in top16_list:
            doc = top16.model_dump(by_alias=True, exclude_none=True)
            if "_id" in doc:
                del doc["_id"]
            if "id" in doc:
                del doc["id"]
            if isinstance(doc.get("date"), date):
                doc["date"] = doc["date"].isoformat()
            doc["createdAt"] = datetime.now()
            docs.append(doc)

        if docs:
            result = collection.insert_many(docs, session=self.session)
            for i, inserted_id in enumerate(result.inserted_ids):
                top16_list[i].id = str(inserted_id)

        return top16_list

    def get_by_date(self, target_date: date) -> List[Top16Day]:
        """Obtiene el ranking Top 16 de una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({"date": target_date.isoformat()}, session=self.session).sort("rank", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_in_casterly_by_date(self, target_date: date) -> List[Top16Day]:
        """Obtiene solo los agentes que estan dentro de Casterly Rock en una fecha."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "date": target_date.isoformat(),
            "is_in_casterly": True
        }, session=self.session).sort("rank", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_agent_range(self, agent_id: str, start_date: date, end_date: date) -> List[Top16Day]:
        """Obtiene el historial de ranking de un agente en un periodo."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "agent_id": agent_id,
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }, session=self.session).sort("date", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def _doc_to_entity(self, doc: dict) -> Top16Day:
        """Convierte un documento de MongoDB a entidad Top16Day."""
        return Top16Day(
            _id=str(doc["_id"]),
            date=date.fromisoformat(doc["date"]),
            rank=doc["rank"],
            agent_id=doc["agent_id"],
            # Soportar diferentes ventanas de ROI (3d, 5d, 7d, 10d, 14d, 15d, 30d)
            roi_3d=doc.get("roi_3d"),
            roi_5d=doc.get("roi_5d"),
            roi_7d=doc.get("roi_7d"),
            roi_10d=doc.get("roi_10d"),
            roi_14d=doc.get("roi_14d"),
            roi_15d=doc.get("roi_15d"),
            roi_30d=doc.get("roi_30d"),
            n_accounts=doc["n_accounts"],
            total_aum=doc["total_aum"],
            is_in_casterly=doc.get("is_in_casterly", False),
            createdAt=doc.get("createdAt")
        )
