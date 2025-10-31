from typing import List, Optional
from datetime import date, datetime
from bson import ObjectId
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.domain.repositories.assignment_read_ops import AssignmentReadOps
from app.domain.repositories.assignment_write_ops import AssignmentWriteOps
from app.domain.entities.assignment import Assignment
from app.config.database import database_manager


class AssignmentRepositoryImpl(AssignmentRepository, AssignmentReadOps, AssignmentWriteOps):
    """
    Implementacion concreta del repositorio de asignaciones usando MongoDB.

    Implementa multiples interfaces segregadas segun ISP:
    - AssignmentRepository: Interfaz completa (legacy, para compatibilidad)
    - AssignmentReadOps: Solo operaciones de lectura
    - AssignmentWriteOps: Solo operaciones de escritura

    Los servicios pueden depender de la interfaz especifica que necesiten.
    """

    def __init__(self):
        self.collection_name = "assignments"

    def create(self, assignment: Assignment) -> Assignment:
        """Crea una nueva asignacion de cuenta a agente."""
        collection = database_manager.get_collection(self.collection_name)

        doc = assignment.model_dump(by_alias=True, exclude_none=True)
        if "_id" in doc:
            del doc["_id"]
        if "id" in doc:
            del doc["id"]
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].date().isoformat()
        elif isinstance(doc.get("date"), date):
            doc["date"] = doc["date"].isoformat()
        if isinstance(doc.get("assigned_at"), datetime):
            doc["assigned_at"] = doc["assigned_at"].isoformat()
        if isinstance(doc.get("unassigned_at"), datetime):
            doc["unassigned_at"] = doc["unassigned_at"].isoformat()
        doc["createdAt"] = datetime.now()
        doc["updatedAt"] = datetime.now()

        result = collection.insert_one(doc)
        assignment.id = str(result.inserted_id)

        return assignment

    def create_batch(self, assignments: List[Assignment]) -> List[Assignment]:
        """Crea multiples asignaciones en lote."""
        collection = database_manager.get_collection(self.collection_name)

        docs = []
        for assignment in assignments:
            doc = assignment.model_dump(by_alias=True, exclude_none=True)
            if "_id" in doc:
                del doc["_id"]
            if "id" in doc:
                del doc["id"]
            if isinstance(doc.get("date"), datetime):
                doc["date"] = doc["date"].date().isoformat()
            elif isinstance(doc.get("date"), date):
                doc["date"] = doc["date"].isoformat()
            if isinstance(doc.get("assigned_at"), datetime):
                doc["assigned_at"] = doc["assigned_at"].isoformat()
            if isinstance(doc.get("unassigned_at"), datetime):
                doc["unassigned_at"] = doc["unassigned_at"].isoformat()
            doc["createdAt"] = datetime.now()
            doc["updatedAt"] = datetime.now()
            docs.append(doc)

        if docs:
            result = collection.insert_many(docs)
            for i, inserted_id in enumerate(result.inserted_ids):
                assignments[i].id = str(inserted_id)

        return assignments

    def get_active_assignments(self) -> List[Assignment]:
        """Obtiene todas las asignaciones activas del sistema."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({"is_active": True})

        return [self._doc_to_entity(doc) for doc in docs]

    def get_active_by_agent(self, agent_id: str) -> List[Assignment]:
        """Obtiene todas las asignaciones activas de un agente."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "agent_id": agent_id,
            "is_active": True
        })

        return [self._doc_to_entity(doc) for doc in docs]

    def get_active_by_account(self, account_id: str) -> Optional[Assignment]:
        """Obtiene la asignacion activa de una cuenta."""
        collection = database_manager.get_collection(self.collection_name)

        doc = collection.find_one({
            "account_id": account_id,
            "is_active": True
        })

        if doc:
            return self._doc_to_entity(doc)

        return None

    def get_by_date(self, target_date: date) -> List[Assignment]:
        """Obtiene todas las asignaciones de una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({"date": target_date.isoformat()})

        return [self._doc_to_entity(doc) for doc in docs]

    def get_by_agent_and_date(self, agent_id: str, target_date: date) -> List[Assignment]:
        """Obtiene todas las asignaciones de un agente en una fecha especifica."""
        collection = database_manager.get_collection(self.collection_name)

        docs = collection.find({
            "agent_id": agent_id,
            "date": target_date.isoformat()
        })

        return [self._doc_to_entity(doc) for doc in docs]

    def deactivate(self, assignment_id: str) -> Assignment:
        """Desactiva una asignacion."""
        collection = database_manager.get_collection(self.collection_name)

        collection.update_one(
            {"_id": ObjectId(assignment_id)},
            {
                "$set": {
                    "is_active": False,
                    "unassigned_at": datetime.now(),
                    "updatedAt": datetime.now()
                }
            }
        )

        doc = collection.find_one({"_id": ObjectId(assignment_id)})
        return self._doc_to_entity(doc)

    def transfer_accounts(self, from_agent: str, to_agent: str) -> int:
        """Transfiere todas las cuentas activas de un agente a otro."""
        collection = database_manager.get_collection(self.collection_name)

        active_assignments = self.get_active_by_agent(from_agent)

        if not active_assignments:
            return 0

        now = datetime.now()
        assignment_ids = [ObjectId(assignment.id) for assignment in active_assignments if assignment.id]

        collection.update_many(
            {"_id": {"$in": assignment_ids}},
            {
                "$set": {
                    "is_active": False,
                    "unassigned_at": now,
                    "updatedAt": now
                }
            }
        )

        new_docs = []
        for assignment in active_assignments:
            doc = {
                "date": now.date().isoformat(),
                "account_id": assignment.account_id,
                "agent_id": to_agent,
                "balance": assignment.balance,
                "assigned_at": now.isoformat(),
                "is_active": True,
                "createdAt": now,
                "updatedAt": now
            }
            new_docs.append(doc)

        if new_docs:
            collection.insert_many(new_docs)

        return len(active_assignments)

    def _doc_to_entity(self, doc: dict) -> Assignment:
        """Convierte un documento de MongoDB a entidad Assignment."""
        doc_id = str(doc["_id"]) if doc.get("_id") else None

        assignment = Assignment(
            date=datetime.fromisoformat(doc["date"]).date() if isinstance(doc["date"], str) else doc["date"],
            account_id=doc["account_id"],
            agent_id=doc["agent_id"],
            balance=doc["balance"],
            assigned_at=doc["assigned_at"],
            unassigned_at=doc.get("unassigned_at"),
            is_active=doc.get("is_active", True),
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt")
        )

        if doc_id:
            object.__setattr__(assignment, 'id', doc_id)

        return assignment
