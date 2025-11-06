"""
Unit of Work Pattern (Domain Layer).

Define la interfaz abstracta para el patrón Unit of Work.
Permite gestionar transacciones y garantizar consistencia de datos.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UnitOfWork(ABC):
    """
    Interfaz abstracta para Unit of Work Pattern.

    El patrón Unit of Work mantiene un registro de objetos afectados por
    una transacción de negocio y coordina la escritura de cambios.

    Beneficios:
    - ✅ Garantiza integridad transaccional (ACID)
    - ✅ Todo o nada (rollback automático en caso de error)
    - ✅ Reduce acoplamiento entre servicios y repositorios
    - ✅ Facilita testing con mocks

    Ejemplo de uso:
        >>> async with uow:
        ...     await uow.rotations.create(rotation_log)
        ...     await uow.assignments.update(assignment)
        ...     await uow.balances.update(balance)
        ...     await uow.commit()  # Todo se guarda o nada
    """

    @abstractmethod
    async def __aenter__(self):
        """
        Inicia la Unit of Work (contexto async).

        Returns:
            self: La instancia de Unit of Work
        """
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza la Unit of Work.

        Si hubo una excepción, hace rollback automáticamente.

        Args:
            exc_type: Tipo de excepción (None si no hubo error)
            exc_val: Valor de la excepción
            exc_tb: Traceback de la excepción
        """
        pass

    @abstractmethod
    async def commit(self):
        """
        Confirma todos los cambios realizados en la transacción.

        Raises:
            TransactionError: Si falla el commit
        """
        pass

    @abstractmethod
    async def rollback(self):
        """
        Revierte todos los cambios realizados en la transacción.

        Esta operación garantiza que no se persista ningún cambio
        si hubo algún error en cualquier parte de la transacción.
        """
        pass


class TransactionError(Exception):
    """
    Excepción personalizada para errores de transacción.

    Se lanza cuando ocurre un error durante commit o rollback.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        """
        Constructor de TransactionError.

        Args:
            message: Mensaje descriptivo del error
            original_exception: Excepción original que causó el error (opcional)
        """
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message
