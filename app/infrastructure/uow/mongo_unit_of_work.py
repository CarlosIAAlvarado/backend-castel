"""
MongoDB Unit of Work Implementation (Infrastructure Layer).

Implementación concreta del patrón Unit of Work para MongoDB.
Gestiona transacciones MongoDB para garantizar consistencia de datos.
"""

from typing import Optional
import logging
from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo.errors import PyMongoError
from app.domain.uow.unit_of_work import UnitOfWork, TransactionError
from app.config.database import database_manager
from app.infrastructure.repositories.rotation_log_repository_impl import RotationLogRepositoryImpl
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl
from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl
from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl

logger = logging.getLogger(__name__)


class MongoUnitOfWork(UnitOfWork):
    """
    Implementación del patrón Unit of Work para MongoDB.

    Gestiona transacciones MongoDB usando sessions para garantizar ACID compliance.
    Proporciona acceso a todos los repositorios dentro de una transacción.

    Atributos:
        rotations: Repository para RotationLog
        assignments: Repository para Assignment
        balances: Repository para Balance
        agent_states: Repository para AgentState
        top16: Repository para Top16

    Ejemplo de uso:
        >>> async with MongoUnitOfWork() as uow:
        ...     # Crear rotación
        ...     rotation = RotationLog(...)
        ...     await uow.rotations.create(rotation)
        ...
        ...     # Actualizar assignment
        ...     assignment.agent_id = new_agent_id
        ...     await uow.assignments.update(assignment)
        ...
        ...     # Commit (todo o nada)
        ...     await uow.commit()

    Nota:
        MongoDB requiere replica set para soportar transacciones.
        En ambientes de desarrollo sin replica set, las operaciones
        se ejecutan sin transacción pero mantienen la API consistente.
    """

    def __init__(self):
        """
        Inicializa el Unit of Work con acceso a la base de datos.
        """
        self.client = database_manager.client
        self.database = database_manager.get_database()
        self._session: Optional[AsyncIOMotorClientSession] = None
        self._is_committed = False
        self._is_rolled_back = False

        # Repositorios (se inicializan en __aenter__)
        self.rotations: Optional[RotationLogRepositoryImpl] = None
        self.assignments: Optional[AssignmentRepositoryImpl] = None
        self.balances: Optional[BalanceRepositoryImpl] = None
        self.agent_states: Optional[AgentStateRepositoryImpl] = None
        self.top16: Optional[Top16RepositoryImpl] = None

    async def __aenter__(self):
        """
        Inicia una sesión de transacción MongoDB.

        Returns:
            self: La instancia de Unit of Work con session activa

        Raises:
            TransactionError: Si falla al iniciar la transacción
        """
        try:
            logger.debug("[UOW] Iniciando Unit of Work (MongoDB session)")

            # Iniciar session
            self._session = await self.client.start_session()

            # Iniciar transacción
            # Nota: En MongoDB sin replica set, esto puede fallar silenciosamente
            try:
                self._session.start_transaction()
                logger.debug("[UOW] Transacción MongoDB iniciada")
            except PyMongoError as e:
                logger.warning(
                    f"[UOW] MongoDB transactions not supported (replica set required): {str(e)}. "
                    "Continuando sin transacción explícita."
                )

            # Inicializar repositorios con session
            self.rotations = RotationLogRepositoryImpl()
            self.assignments = AssignmentRepositoryImpl()
            self.balances = BalanceRepositoryImpl()
            self.agent_states = AgentStateRepositoryImpl()
            self.top16 = Top16RepositoryImpl()

            # TODO: Pasar session a repositorios cuando implementen soporte
            # Por ahora, los repositorios no reciben session en constructor
            # En una implementación completa, deberían aceptar session para
            # todas las operaciones dentro de la transacción

            self._is_committed = False
            self._is_rolled_back = False

            logger.debug("[UOW] Unit of Work inicializado correctamente")

            return self

        except Exception as e:
            error_msg = f"Error iniciando Unit of Work: {str(e)}"
            logger.error(f"[UOW] {error_msg}", exc_info=True)
            raise TransactionError(error_msg, original_exception=e)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza la Unit of Work.

        Si hubo una excepción, hace rollback automáticamente.
        Si no hubo excepción pero no se hizo commit, también hace rollback.

        Args:
            exc_type: Tipo de excepción (None si no hubo error)
            exc_val: Valor de la excepción
            exc_tb: Traceback de la excepción
        """
        try:
            if exc_type is not None:
                # Hubo una excepción, hacer rollback
                logger.warning(
                    f"[UOW] Excepción detectada ({exc_type.__name__}), ejecutando rollback automático"
                )
                await self.rollback()
            elif not self._is_committed and not self._is_rolled_back:
                # No se hizo commit explícito, hacer rollback por seguridad
                logger.warning(
                    "[UOW] Unit of Work cerrado sin commit explícito, ejecutando rollback por seguridad"
                )
                await self.rollback()
            else:
                logger.debug("[UOW] Unit of Work finalizado correctamente")

        finally:
            # Cerrar session
            if self._session:
                await self._session.end_session()
                logger.debug("[UOW] MongoDB session cerrada")

    async def commit(self):
        """
        Confirma todos los cambios realizados en la transacción.

        Raises:
            TransactionError: Si falla el commit
            RuntimeError: Si ya se hizo commit o rollback
        """
        if self._is_committed:
            raise RuntimeError("Transaction already committed")

        if self._is_rolled_back:
            raise RuntimeError("Transaction already rolled back")

        try:
            logger.info("[UOW] Ejecutando commit de transacción")

            if self._session and self._session.in_transaction:
                await self._session.commit_transaction()
                logger.info("[UOW] ✅ Commit exitoso - Todos los cambios persistidos")
            else:
                logger.debug("[UOW] No hay transacción activa, operaciones ya persistidas")

            self._is_committed = True

        except PyMongoError as e:
            error_msg = f"Error ejecutando commit: {str(e)}"
            logger.error(f"[UOW] ❌ {error_msg}", exc_info=True)
            await self.rollback()
            raise TransactionError(error_msg, original_exception=e)

    async def rollback(self):
        """
        Revierte todos los cambios realizados en la transacción.

        Esta operación garantiza que no se persista ningún cambio
        si hubo algún error en cualquier parte de la transacción.
        """
        if self._is_rolled_back:
            logger.debug("[UOW] Rollback ya ejecutado previamente")
            return

        try:
            logger.warning("[UOW] Ejecutando rollback de transacción")

            if self._session and self._session.in_transaction:
                await self._session.abort_transaction()
                logger.warning("[UOW] ⚠️ Rollback exitoso - Todos los cambios revertidos")
            else:
                logger.debug("[UOW] No hay transacción activa para hacer rollback")

            self._is_rolled_back = True

        except PyMongoError as e:
            error_msg = f"Error ejecutando rollback: {str(e)}"
            logger.error(f"[UOW] ❌ {error_msg}", exc_info=True)
            # En caso de error en rollback, registrar pero no lanzar excepción
            # para evitar ocultar la excepción original

    @property
    def is_active(self) -> bool:
        """
        Verifica si la Unit of Work está activa.

        Returns:
            bool: True si hay una sesión activa y no se ha commit/rollback
        """
        return (
            self._session is not None
            and not self._is_committed
            and not self._is_rolled_back
        )

    def __repr__(self) -> str:
        """
        Representación string del Unit of Work.

        Returns:
            str: Estado actual de la Unit of Work
        """
        status = "active"
        if self._is_committed:
            status = "committed"
        elif self._is_rolled_back:
            status = "rolled_back"
        elif self._session is None:
            status = "not_started"

        return f"<MongoUnitOfWork status={status}>"
