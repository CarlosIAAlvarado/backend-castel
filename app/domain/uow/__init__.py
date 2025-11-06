"""
Unit of Work Pattern (Domain Layer).

Define interfaces para el patrón Unit of Work que garantiza
integridad transaccional en operaciones de múltiples repositorios.
"""

from app.domain.uow.unit_of_work import UnitOfWork, TransactionError

__all__ = ["UnitOfWork", "TransactionError"]
