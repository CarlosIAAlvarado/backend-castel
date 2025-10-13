from typing import List, Optional
from datetime import date, datetime
from app.domain.repositories.balance_repository import BalanceRepository
from app.domain.entities.balance import Balance
from app.config.database import database_manager
from app.infrastructure.utils.data_normalizer import normalizer
import pytz


class BalanceRepositoryImpl(BalanceRepository):
    """
    Implementacion concreta del repositorio de balances usando MongoDB.
    """

    def __init__(self):
        self.collection_name = "balances"

    def get_by_account_and_date(self, account_id: str, target_date: date) -> Optional[Balance]:
        """Obtiene el balance de una cuenta en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(target_date, datetime.max.time()))

        doc = collection.find_one({
            "userId": account_id,
            "createdAt": {
                "$gte": start_dt.isoformat(),
                "$lte": end_dt.isoformat()
            }
        })

        if not doc:
            docs = list(collection.find({"userId": account_id}).sort("createdAt", -1).limit(1))
            if docs:
                doc = docs[0]

        if doc:
            return self._doc_to_entity(doc)

        return None

    def get_all_by_date(self, target_date: date) -> List[Balance]:
        """Obtiene todos los balances de una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        # Usar campo 'date' agregado por migracion (formato ISO: "2025-09-01")
        date_str = target_date.isoformat()

        docs = collection.find({
            "date": date_str
        })

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
                "$gte": start_dt.isoformat(),
                "$lte": end_dt.isoformat()
            }
        }).sort("createdAt", 1)

        return [self._doc_to_entity(doc) for doc in docs]

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
