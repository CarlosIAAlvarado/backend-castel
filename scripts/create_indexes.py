"""
Script para crear indices MongoDB para optimizar el rendimiento del sistema.

Este script crea todos los indices necesarios para:
- Coleccion balances: Optimiza queries de balance por agente y fecha
- Coleccion mov07.10: Optimiza queries de movements por agente y fecha
- Coleccion daily_roi_calculation: Cache temporal de ROI diario
- Coleccion agent_roi_7d: Cache temporal de ROI 7D

IMPORTANTE:
- Ejecutar este script ANTES de la primera simulacion en produccion
- Los indices mejoran el rendimiento 5-10x en queries complejas
- Este script es idempotente (se puede ejecutar multiples veces)

Uso:
    python backend/scripts/create_indexes.py
"""

import sys
from pathlib import Path

# Agregar el directorio raiz del backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from pymongo import ASCENDING, DESCENDING
from app.config.database import database_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_balances_indexes():
    """
    Crea indices para la coleccion balances.

    Indices creados:
    1. agente_id + createdAt: Para queries de balance por agente y fecha
    2. userId + createdAt: Para queries alternativas por userId
    3. createdAt: Para queries por fecha
    """
    try:
        db = database_manager.get_database()
        collection = db["balances"]

        logger.info("Creando indices para coleccion 'balances'...")

        # Indice compuesto: agente_id + createdAt
        collection.create_index(
            [("agente_id", ASCENDING), ("createdAt", ASCENDING)],
            name="idx_balances_agente_date",
            background=True
        )
        logger.info("  - Indice creado: agente_id + createdAt")

        # Indice compuesto: userId + createdAt
        collection.create_index(
            [("userId", ASCENDING), ("createdAt", ASCENDING)],
            name="idx_balances_userId_date",
            background=True
        )
        logger.info("  - Indice creado: userId + createdAt")

        # Indice simple: createdAt
        collection.create_index(
            [("createdAt", ASCENDING)],
            name="idx_balances_date",
            background=True
        )
        logger.info("  - Indice creado: createdAt")

        logger.info("Indices para 'balances' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices para 'balances': {e}")
        raise


def create_movements_indexes():
    """
    Crea indices para la coleccion mov07.10 (movements).

    Indices creados:
    1. agente_id + userId + createdAt: Para JOIN con balances (3 foreign keys)
    2. createdAt: Para queries por fecha
    """
    try:
        db = database_manager.get_database()
        collection = db["mov07.10"]

        logger.info("Creando indices para coleccion 'mov07.10'...")

        # Indice compuesto: agente_id + userId + createdAt (para JOIN)
        collection.create_index(
            [
                ("agente_id", ASCENDING),
                ("userId", ASCENDING),
                ("createdAt", ASCENDING)
            ],
            name="idx_movements_agent_user_date",
            background=True
        )
        logger.info("  - Indice creado: agente_id + userId + createdAt")

        # Indice simple: createdAt
        collection.create_index(
            [("createdAt", ASCENDING)],
            name="idx_movements_date",
            background=True
        )
        logger.info("  - Indice creado: createdAt")

        logger.info("Indices para 'mov07.10' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices para 'mov07.10': {e}")
        raise


def create_daily_roi_indexes():
    """
    Crea indices para la coleccion daily_roi_calculation (temporal).

    CAMBIO VERSION 2.1: Ahora usa userId como clave principal en lugar de agente_id.

    Indices creados:
    1. userId + date (unique): Para busquedas rapidas y prevenir duplicados
    2. date: Para queries por fecha
    """
    try:
        db = database_manager.get_database()
        collection = db["daily_roi_calculation"]

        logger.info("Creando indices para coleccion 'daily_roi_calculation'...")

        # Indice compuesto UNICO: userId + date (CAMBIO VERSION 2.1)
        collection.create_index(
            [("userId", ASCENDING), ("date", ASCENDING)],
            name="idx_daily_roi_userId_date_unique",
            unique=True,
            background=True
        )
        logger.info("  - Indice creado: userId + date (unique)")

        # Indice simple: date
        collection.create_index(
            [("date", ASCENDING)],
            name="idx_daily_roi_date",
            background=True
        )
        logger.info("  - Indice creado: date")

        logger.info("Indices para 'daily_roi_calculation' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices para 'daily_roi_calculation': {e}")
        raise


def create_roi_7d_indexes():
    """
    Crea indices para la coleccion agent_roi_7d (temporal).

    CAMBIO VERSION 2.1: Ahora usa userId como clave principal en lugar de agente_id.

    Indices creados:
    1. userId + target_date (unique): Para busquedas rapidas y prevenir duplicados
    2. target_date + roi_7d_total (desc): Para Top 16 ordenado por ROI
    """
    try:
        db = database_manager.get_database()
        collection = db["agent_roi_7d"]

        logger.info("Creando indices para coleccion 'agent_roi_7d'...")

        # Indice compuesto UNICO: userId + target_date (CAMBIO VERSION 2.1)
        collection.create_index(
            [("userId", ASCENDING), ("target_date", ASCENDING)],
            name="idx_roi_7d_userId_date_unique",
            unique=True,
            background=True
        )
        logger.info("  - Indice creado: userId + target_date (unique)")

        # Indice compuesto: target_date + roi_7d_total (desc) para ranking
        collection.create_index(
            [("target_date", ASCENDING), ("roi_7d_total", DESCENDING)],
            name="idx_roi_7d_ranking",
            background=True
        )
        logger.info("  - Indice creado: target_date + roi_7d_total (desc)")

        logger.info("Indices para 'agent_roi_7d' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices para 'agent_roi_7d': {e}")
        raise


def create_agent_states_indexes():
    """
    Crea indices para la coleccion agent_states.

    Indices creados:
    1. agent_id + date: Para queries de estado por agente y fecha
    2. date + is_in_casterly: Para queries de agentes activos por fecha
    """
    try:
        db = database_manager.get_database()
        collection = db["agent_states"]

        logger.info("Creando indices para coleccion 'agent_states'...")

        # Indice compuesto: agent_id + date
        collection.create_index(
            [("agent_id", ASCENDING), ("date", ASCENDING)],
            name="idx_agent_states_agent_date",
            background=True
        )
        logger.info("  - Indice creado: agent_id + date")

        # Indice compuesto: date + is_in_casterly
        collection.create_index(
            [("date", ASCENDING), ("is_in_casterly", ASCENDING)],
            name="idx_agent_states_date_active",
            background=True
        )
        logger.info("  - Indice creado: date + is_in_casterly")

        logger.info("Indices para 'agent_states' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices para 'agent_states': {e}")
        raise


def create_assignments_indexes():
    """
    Crea indices para la coleccion assignments.

    Indices creados:
    1. agent_id + is_active: Para queries de asignaciones activas por agente
    2. is_active: Para queries de todas las asignaciones activas
    """
    try:
        db = database_manager.get_database()
        collection = db["assignments"]

        logger.info("Creando indices para coleccion 'assignments'...")

        # Indice compuesto: agent_id + is_active
        collection.create_index(
            [("agent_id", ASCENDING), ("is_active", ASCENDING)],
            name="idx_assignments_agent_active",
            background=True
        )
        logger.info("  - Indice creado: agent_id + is_active")

        # Indice simple: is_active
        collection.create_index(
            [("is_active", ASCENDING)],
            name="idx_assignments_active",
            background=True
        )
        logger.info("  - Indice creado: is_active")

        logger.info("Indices para 'assignments' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices para 'assignments': {e}")
        raise


def list_existing_indexes():
    """
    Lista todos los indices existentes en las colecciones principales.
    """
    try:
        db = database_manager.get_database()

        collections = [
            "balances",
            "mov07.10",
            "daily_roi_calculation",
            "agent_roi_7d",
            "agent_states",
            "assignments"
        ]

        logger.info("\n=== INDICES EXISTENTES ===")

        for collection_name in collections:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())

            logger.info(f"\nColeccion: {collection_name}")
            logger.info(f"Total de indices: {len(indexes)}")

            for idx in indexes:
                name = idx.get("name", "N/A")
                keys = idx.get("key", {})
                unique = " (UNIQUE)" if idx.get("unique", False) else ""
                logger.info(f"  - {name}: {dict(keys)}{unique}")

    except Exception as e:
        logger.error(f"Error al listar indices: {e}")
        raise


def main():
    """
    Funcion principal que crea todos los indices necesarios.
    """
    try:
        logger.info("="*80)
        logger.info("SCRIPT DE CREACION DE INDICES MONGODB")
        logger.info("Sistema: Casterly Rock Simulation VERSION 2.0")
        logger.info("="*80)

        # Conectar a la base de datos
        logger.info("\nConectando a MongoDB...")
        database_manager.connect()
        logger.info("Conexion exitosa")

        # Crear indices para cada coleccion
        logger.info("\n" + "="*80)
        create_balances_indexes()

        logger.info("\n" + "="*80)
        create_movements_indexes()

        logger.info("\n" + "="*80)
        create_daily_roi_indexes()

        logger.info("\n" + "="*80)
        create_roi_7d_indexes()

        logger.info("\n" + "="*80)
        create_agent_states_indexes()

        logger.info("\n" + "="*80)
        create_assignments_indexes()

        # Listar todos los indices creados
        logger.info("\n" + "="*80)
        list_existing_indexes()

        # Resumen final
        logger.info("\n" + "="*80)
        logger.info("RESUMEN FINAL")
        logger.info("="*80)
        logger.info("Todos los indices fueron creados exitosamente")
        logger.info("")
        logger.info("Indices creados:")
        logger.info("  - balances: 3 indices")
        logger.info("  - mov07.10: 2 indices")
        logger.info("  - daily_roi_calculation: 2 indices (1 unique)")
        logger.info("  - agent_roi_7d: 2 indices (1 unique)")
        logger.info("  - agent_states: 2 indices")
        logger.info("  - assignments: 2 indices")
        logger.info("")
        logger.info("Total: 13 indices creados")
        logger.info("")
        logger.info("NOTA: Los indices se crean en modo 'background' para no bloquear")
        logger.info("      operaciones existentes. Puede tomar unos minutos completarse.")
        logger.info("="*80)

        # Cerrar conexion
        database_manager.disconnect()
        logger.info("\nConexion cerrada")

    except Exception as e:
        logger.error(f"\nERROR FATAL: {e}")
        logger.error("La creacion de indices fallo. Por favor revise los logs.")
        database_manager.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    main()
