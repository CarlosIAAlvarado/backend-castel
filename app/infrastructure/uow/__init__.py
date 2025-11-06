"""
Unit of Work Implementations (Infrastructure Layer).

Implementaciones concretas del patrón Unit of Work para diferentes bases de datos.
"""

from app.infrastructure.uow.mongo_unit_of_work import MongoUnitOfWork

__all__ = ["MongoUnitOfWork"]
