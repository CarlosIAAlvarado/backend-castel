from typing import List, Optional, Dict
from datetime import date, datetime
from pymongo.client_session import ClientSession
from app.domain.repositories.balance_repository import BalanceRepository
from app.domain.repositories.balance_queries import BalanceAggregationQueries
from app.domain.entities.balance import Balance
from app.config.database import database_manager
from app.infrastructure.utils.data_normalizer import normalizer
import pytz


class BalanceRepositoryImpl(BalanceRepository, BalanceAggregationQueries):
    """
    Implementacion concreta del repositorio de balances usando MongoDB.

    Implementa multiples interfaces especializadas segun ISP:
    - BalanceRepository: Operaciones basicas de consulta de balances
    - BalanceAggregationQueries: Operaciones especializadas de agregacion de AUM

    Soporte para transacciones:
    - Acepta session opcional en constructor para Unit of Work
    - Todas las operaciones respetan la session si existe
    """

    def __init__(self, session: Optional[ClientSession] = None):
        self.collection_name = "balances"
        self.session = session

    def get_by_account_and_date(self, account_id: str, target_date: date) -> Optional[Balance]:
        """Obtiene el balance de una cuenta en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(target_date, datetime.max.time()))

        doc = collection.find_one({
            "userId": account_id,
            "createdAt": {
                "$gte": start_dt,
                "$lte": end_dt
            }
        }, session=self.session)

        if not doc:
            docs = list(collection.find({"userId": account_id}, session=self.session).sort("createdAt", -1).limit(1))
            if docs:
                doc = docs[0]

        if doc:
            return self._doc_to_entity(doc)

        return None

    def get_all_by_date(self, target_date: date) -> List[Balance]:
        """Obtiene todos los balances de una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        # Buscar por createdAt en el rango del día
        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(target_date, datetime.max.time()))

        docs = collection.find({
            "createdAt": {
                "$gte": start_dt,
                "$lte": end_dt
            }
        }, session=self.session)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_account_range(self, account_id: str, start_date: date, end_date: date) -> List[Balance]:
        """Obtiene los balances de una cuenta en un rango de fechas."""
        collection = database_manager.get_collection(self.collection_name)

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(start_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(end_date, datetime.max.time()))

        docs = collection.find({
            "userId": account_id,
            "createdAt": {
                "$gte": start_dt,
                "$lte": end_dt
            }
        }, session=self.session).sort("createdAt", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_all_by_date_range(self, start_date: date, end_date: date) -> List[Balance]:
        """Obtiene todos los balances de TODAS las cuentas en un rango de fechas."""
        collection = database_manager.get_collection(self.collection_name)

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(start_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(end_date, datetime.max.time()))

        docs = collection.find({
            "createdAt": {
                "$gte": start_dt.isoformat(),
                "$lte": end_dt.isoformat()
            }
        }, session=self.session).sort("createdAt", 1)

        return [self._doc_to_entity(doc) for doc in docs]

    def get_total_aum_by_date(self, target_date: date) -> float:
        """Obtiene el AUM total de todas las cuentas en una fecha."""
        collection = database_manager.get_collection(self.collection_name)

        # Buscar por createdAt en el rango del día
        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(target_date, datetime.max.time()))

        pipeline = [
            {
                "$match": {
                    "createdAt": {
                        "$gte": start_dt,
                        "$lte": end_dt
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_aum": {"$sum": "$balance"}
                }
            }
        ]

        result = list(collection.aggregate(pipeline, session=self.session))

        if not result:
            return 0.0

        return float(result[0].get("total_aum", 0.0))

    def get_aum_evolution(
        self,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, any]]:
        """Obtiene la evolucion del AUM total en un rango de fechas."""
        collection = database_manager.get_collection(self.collection_name)

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(start_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(end_date, datetime.max.time()))

        pipeline = [
            {
                "$match": {
                    "createdAt": {
                        "$gte": start_dt,
                        "$lte": end_dt
                    }
                }
            },
            {
                "$addFields": {
                    "date_only": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$createdAt"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$date_only",
                    "aum": {"$sum": "$balance"}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]

        results = list(collection.aggregate(pipeline, session=self.session))

        evolution = []
        for result in results:
            date_obj = datetime.fromisoformat(result["_id"]).date() if isinstance(result["_id"], str) else result["_id"]
            evolution.append({
                "date": date_obj,
                "aum": float(result.get("aum", 0.0))
            })

        return evolution

    def _doc_to_entity(self, doc: dict) -> Balance:
        """Convierte un documento de MongoDB a entidad Balance."""
        return Balance(
            _id=str(doc["_id"]),
            userIdDB=doc.get("userIdDB", ""),
            userId=doc.get("userId", ""),
            account_id=doc.get("account_id"),  # Agregado por migracion
            balance=normalizer.normalize_balance(doc.get("balance")),
            createdAt=normalizer.normalize_datetime(doc.get("createdAt")),
            updatedAt=normalizer.normalize_datetime(doc.get("updatedAt"))
        )
