from typing import Dict, Optional
from datetime import date, datetime
from app.domain.repositories.balance_repository import BalanceRepository
from app.infrastructure.utils.data_normalizer import normalizer
import pytz


class BalanceQueryService:
    """
    Servicio especializado en consultas de balances.

    Responsabilidad unica: Obtener balances de la base de datos.
    Cumple con Single Responsibility Principle (SRP).
    """

    def __init__(self, balance_repo: BalanceRepository):
        """
        Constructor con inyeccion de dependencias.

        Args:
            balance_repo: Repositorio de balances
        """
        self.balance_repo = balance_repo

    def get_balance_by_agent_and_date(
        self,
        userId: str,
        target_date: date
    ) -> Optional[float]:
        """
        Obtiene el balance de un agente en una fecha especifica.

        CAMBIO VERSION 2.1: Renombrado y ahora usa userId explícitamente.

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha objetivo

        Returns:
            Balance normalizado o None si no se encuentra
        """
        from app.config.database import database_manager

        collection = database_manager.get_collection("balances")

        tz = pytz.timezone("America/Bogota")
        start_dt = tz.localize(datetime.combine(target_date, datetime.min.time()))
        end_dt = tz.localize(datetime.combine(target_date, datetime.max.time()))

        balance_doc = collection.find_one({
            "userId": userId,
            "createdAt": {
                "$gte": start_dt.isoformat(),
                "$lte": end_dt.isoformat()
            }
        })

        if not balance_doc:
            balances = list(collection.find({"userId": userId}).sort("createdAt", -1).limit(1))
            if balances:
                balance_doc = balances[0]

        if balance_doc:
            return normalizer.normalize_balance(balance_doc.get("balance"))

        return None

    def get_balance_by_account_and_date(
        self,
        account_id: str,
        target_date: date
    ) -> Optional[float]:
        """
        MÉTODO LEGACY - Alias de get_balance_by_agent_and_date().
        Mantenido por compatibilidad con código existente.

        Args:
            account_id: ID de la cuenta (userId)
            target_date: Fecha objetivo

        Returns:
            Balance normalizado o None si no se encuentra
        """
        return self.get_balance_by_agent_and_date(account_id, target_date)

    def get_all_balances_by_date(self, target_date: date) -> Dict[str, float]:
        """
        Obtiene todos los balances de una fecha.

        Args:
            target_date: Fecha objetivo

        Returns:
            Diccionario con {account_id: balance}
        """
        from app.config.database import database_manager

        collection = database_manager.get_collection("balances")

        date_str = target_date.isoformat()

        balances = collection.find({
            "date": date_str
        })

        result = {}
        for balance_doc in balances:
            account_id = balance_doc.get("account_id")
            balance_value = normalizer.normalize_balance(balance_doc.get("balance"))
            if account_id:
                result[account_id] = balance_value

        return result
