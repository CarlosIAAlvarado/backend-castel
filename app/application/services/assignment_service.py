from typing import List, Dict, Any
from datetime import date, datetime
import random
import pytz
from app.domain.entities.assignment import Assignment
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.domain.repositories.balance_repository import BalanceRepository
from app.application.services.selection_service import SelectionService


class AssignmentService:
    """
    Servicio para la asignacion de cuentas a agentes.

    Responsabilidades:
    - Cargar todas las cuentas disponibles
    - Distribuir cuentas entre los Top 16 agentes
    - Guardar asignaciones en base de datos
    - Consultar asignaciones activas
    """

    def __init__(
        self,
        assignment_repo: AssignmentRepository,
        balance_repo: BalanceRepository,
        selection_service: SelectionService
    ):
        """
        Constructor con inyeccion de dependencias.

        Args:
            assignment_repo: Repositorio de asignaciones
            balance_repo: Repositorio de balances
            selection_service: Servicio de seleccion de agentes
        """
        self.assignment_repo = assignment_repo
        self.balance_repo = balance_repo
        self.selection_service = selection_service
        self.timezone = pytz.timezone("America/Bogota")

    def get_available_accounts(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Obtiene todas las cuentas disponibles con sus balances en una fecha.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de diccionarios con account_id y balance
        """
        balances = self.balance_repo.get_all_by_date(target_date)

        accounts = []
        for balance in balances:
            accounts.append({
                "account_id": balance.user_id,
                "balance": balance.balance
            })

        return accounts

    def distribute_accounts_randomly(
        self,
        accounts: List[Dict[str, Any]],
        top_agents: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Distribuye cuentas aleatoriamente entre los agentes del Top 16.

        Logica:
        - Mezcla aleatoriamente la lista de cuentas
        - Asigna cuentas de forma equitativa y circular entre los 16 agentes
        - Si hay N cuentas y 16 agentes, cada agente recibe N/16 cuentas (aprox)

        Args:
            accounts: Lista de cuentas disponibles
            top_agents: Lista de agentes Top 16

        Returns:
            Diccionario {agent_id: [lista de cuentas asignadas]}
        """
        shuffled_accounts = accounts.copy()
        random.shuffle(shuffled_accounts)

        assignments = {agent["agent_id"]: [] for agent in top_agents}

        agent_ids = [agent["agent_id"] for agent in top_agents]
        num_agents = len(agent_ids)

        for idx, account in enumerate(shuffled_accounts):
            agent_id = agent_ids[idx % num_agents]
            assignments[agent_id].append(account)

        return assignments

    def create_initial_assignments(
        self,
        target_date: date,
        casterly_agent_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Proceso completo de asignacion inicial de cuentas.

        Pasos:
        1. Obtener Top 16 agentes del dia (o usar casterly_agent_ids si se provee)
        2. Cargar todas las cuentas disponibles
        3. Distribuir aleatoriamente
        4. Guardar en base de datos

        Args:
            target_date: Fecha de asignacion (debe ser 01-Sep-2025 segun especificacion)
            casterly_agent_ids: IDs de agentes Top 16 (opcional, si None los calcula)

        Returns:
            Diccionario con resumen de asignaciones creadas
        """
        if casterly_agent_ids is None:
            top_16, _ = self.selection_service.select_top_16(target_date)
        else:
            top_16 = [{"agent_id": aid} for aid in casterly_agent_ids]

        if len(top_16) != 16:
            raise ValueError(f"Se requieren exactamente 16 agentes para Casterly Rock. Recibidos: {len(top_16)}")

        accounts = self.get_available_accounts(target_date)

        if not accounts:
            raise ValueError(f"No se encontraron cuentas disponibles para la fecha {target_date}")

        distribution = self.distribute_accounts_randomly(accounts, top_16)

        assignment_entities = []
        assignment_time = datetime.now(self.timezone)

        for agent_id, agent_accounts in distribution.items():
            for account in agent_accounts:
                assignment_entity = Assignment(
                    date=datetime.combine(target_date, datetime.min.time()),
                    account_id=account["account_id"],
                    agent_id=agent_id,
                    balance=account["balance"],
                    assigned_at=assignment_time,
                    is_active=True
                )
                assignment_entities.append(assignment_entity)

        saved_assignments = self.assignment_repo.create_batch(assignment_entities)

        assignments_per_agent = {}
        total_aum_per_agent = {}

        for agent_id in distribution.keys():
            agent_assignments = distribution[agent_id]
            assignments_per_agent[agent_id] = len(agent_assignments)
            total_aum_per_agent[agent_id] = sum(acc["balance"] for acc in agent_assignments)

        return {
            "success": True,
            "date": target_date.isoformat(),
            "total_accounts": len(accounts),
            "total_agents": len(top_16),
            "total_assignments": len(saved_assignments),
            "assignments_per_agent": assignments_per_agent,
            "total_aum_per_agent": total_aum_per_agent,
            "top_16_agents": [agent["agent_id"] for agent in top_16]
        }

    def get_active_assignments(self, target_date: date = None) -> List[Assignment]:
        """
        Obtiene las asignaciones activas.

        Args:
            target_date: Fecha objetivo (opcional)

        Returns:
            Lista de Assignment activos
        """
        if target_date:
            return self.assignment_repo.get_by_date(target_date)
        else:
            return self.assignment_repo.get_active_assignments()

    def get_agent_accounts(self, agent_id: str) -> List[str]:
        """
        Obtiene las cuentas asignadas a un agente.

        Args:
            agent_id: ID del agente

        Returns:
            Lista de account_ids asignados al agente
        """
        assignments = self.assignment_repo.get_active_by_agent(agent_id)
        return [assignment.account_id for assignment in assignments]

    def save_daily_snapshot(self, target_date: date) -> Dict[str, Any]:
        """
        Guarda un snapshot diario de todas las asignaciones activas.

        Optimizado para velocidad usando insert_many directo.

        Args:
            target_date: Fecha del snapshot

        Returns:
            Diccionario con resultado del guardado
        """
        from app.config.database import database_manager

        collection = database_manager.get_collection("assignments")

        active_docs = list(collection.find(
            {"is_active": True},
            {"account_id": 1, "agent_id": 1, "balance": 1}
        ))

        if not active_docs:
            return {
                "success": False,
                "message": "No hay asignaciones activas para guardar"
            }

        snapshot_time = datetime.now(self.timezone)
        target_date_iso = target_date.isoformat()

        snapshot_docs = [
            {
                "date": target_date_iso,
                "account_id": doc["account_id"],
                "agent_id": doc["agent_id"],
                "balance": doc["balance"],
                "assigned_at": snapshot_time.isoformat(),
                "is_active": True,
                "createdAt": snapshot_time,
                "updatedAt": snapshot_time
            }
            for doc in active_docs
        ]

        result = collection.insert_many(snapshot_docs, ordered=False)

        return {
            "success": True,
            "date": target_date_iso,
            "total_snapshots_saved": len(result.inserted_ids)
        }
