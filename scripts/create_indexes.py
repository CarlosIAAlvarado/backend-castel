"""
Script para crear indices MongoDB para optimizar el rendimiento del sistema.

VERSION 4.0 - VENTANAS DINAMICAS + OPTIMIZACION ULTRA RAPIDA

Este script crea todos los indices necesarios para:
- Coleccion balances: Optimiza queries de balance por agente y fecha
- Coleccion mov07.10: Optimiza queries de movements por agente y fecha
- Coleccion daily_roi_calculation: Cache temporal de ROI diario
- Colecciones agent_roi_Xd (3d, 5d, 7d, 10d, 15d, 30d): Cache temporal de ROI con ventanas dinámicas
- Colecciones top16_Xd (3d, 5d, 7d, 10d, 15d, 30d): Rankings Top 16 con ventanas dinámicas
- Coleccion agent_states: Estados de agentes en Casterly Rock
- Coleccion assignments: Asignaciones de cuentas a agentes

IMPORTANTE:
- Ejecutar este script ANTES de la primera simulacion en produccion
- Los indices mejoran el rendimiento 10-100x en queries complejas
- Este script es idempotente (se puede ejecutar multiples veces)
- Los indices se crean en modo 'background' para no bloquear operaciones existentes

MEJORAS VERSION 4.0:
- Agregados indices para TODAS las colecciones dinámicas de ROI (3d, 5d, 10d, 15d, 30d)
- Agregados indices para TODAS las colecciones dinámicas de Top16 (3d, 5d, 7d, 10d, 15d, 30d)
- Total de 41 indices creados vs 13 en versión anterior
- Optimizado para simulaciones con ventanas dinámicas de tiempo

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


def create_dynamic_roi_indexes():
    """
    Crea indices para TODAS las colecciones dinámicas de ROI (3d, 5d, 10d, 15d, 30d).

    VERSION 4.0 - VENTANAS DINAMICAS

    Indices creados para cada colección:
    1. userId + target_date (unique): Para búsquedas rápidas y prevenir duplicados
    2. target_date + roi_Xd_total (desc): Para rankings ordenados por ROI
    """
    try:
        db = database_manager.get_database()

        # Colecciones dinámicas de ROI (además de agent_roi_7d que ya se crea arriba)
        roi_collections = ["agent_roi_3d", "agent_roi_5d", "agent_roi_10d", "agent_roi_15d", "agent_roi_30d"]

        for collection_name in roi_collections:
            logger.info(f"Creando indices para coleccion '{collection_name}'...")
            collection = db[collection_name]

            # Extraer ventana de días del nombre (ej: "agent_roi_3d" -> "3d")
            window_suffix = collection_name.split("_")[-1]  # "3d", "5d", etc.
            roi_field = f"roi_{window_suffix}_total"  # "roi_3d_total", "roi_5d_total", etc.

            # Indice compuesto UNICO: userId + target_date
            collection.create_index(
                [("userId", ASCENDING), ("target_date", ASCENDING)],
                name=f"idx_{collection_name}_userId_date_unique",
                unique=True,
                background=True
            )
            logger.info(f"  - Indice creado: userId + target_date (unique)")

            # Indice compuesto: target_date + roi_Xd_total (desc) para ranking
            collection.create_index(
                [("target_date", ASCENDING), (roi_field, DESCENDING)],
                name=f"idx_{collection_name}_ranking",
                background=True
            )
            logger.info(f"  - Indice creado: target_date + {roi_field} (desc)")

            logger.info(f"Indices para '{collection_name}' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices dinámicos de ROI: {e}")
        raise


def create_top16_dynamic_indexes():
    """
    Crea indices para TODAS las colecciones dinámicas de Top16 (3d, 5d, 7d, 10d, 15d, 30d).

    VERSION 4.0 - VENTANAS DINAMICAS

    Indices creados para cada colección:
    1. date + rank: Para consultas de ranking por fecha
    2. date + is_in_casterly: Para filtrar agentes activos en Casterly Rock
    3. agent_id + date: Para historial de un agente específico
    """
    try:
        db = database_manager.get_database()

        # Colecciones dinámicas de Top16
        top16_collections = ["top16_3d", "top16_5d", "top16_7d", "top16_10d", "top16_15d", "top16_30d"]

        for collection_name in top16_collections:
            logger.info(f"Creando indices para coleccion '{collection_name}'...")
            collection = db[collection_name]

            # Indice compuesto: date + rank
            collection.create_index(
                [("date", ASCENDING), ("rank", ASCENDING)],
                name=f"idx_{collection_name}_date_rank",
                background=True
            )
            logger.info(f"  - Indice creado: date + rank")

            # Indice compuesto: date + is_in_casterly
            collection.create_index(
                [("date", ASCENDING), ("is_in_casterly", ASCENDING)],
                name=f"idx_{collection_name}_date_active",
                background=True
            )
            logger.info(f"  - Indice creado: date + is_in_casterly")

            # Indice compuesto: agent_id + date (para historial)
            collection.create_index(
                [("agent_id", ASCENDING), ("date", ASCENDING)],
                name=f"idx_{collection_name}_agent_date",
                background=True
            )
            logger.info(f"  - Indice creado: agent_id + date")

            logger.info(f"Indices para '{collection_name}' creados exitosamente")

    except Exception as e:
        logger.error(f"Error al crear indices dinámicos de Top16: {e}")
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

    VERSION 4.0 - VENTANAS DINAMICAS
    Incluye todas las colecciones dinámicas de ROI y Top16.
    """
    try:
        db = database_manager.get_database()

        # Colecciones base
        collections = [
            "balances",
            "mov07.10",
            "daily_roi_calculation",
            "agent_roi_7d",
        ]

        # Agregar colecciones dinámicas de ROI
        collections.extend(["agent_roi_3d", "agent_roi_5d", "agent_roi_10d", "agent_roi_15d", "agent_roi_30d"])

        # Agregar colecciones dinámicas de Top16
        collections.extend(["top16_3d", "top16_5d", "top16_7d", "top16_10d", "top16_15d", "top16_30d"])

        # Agregar colecciones adicionales
        collections.extend(["agent_states", "assignments"])

        logger.info("\n=== INDICES EXISTENTES ===")

        for collection_name in collections:
            try:
                collection = db[collection_name]
                indexes = list(collection.list_indexes())

                logger.info(f"\nColeccion: {collection_name}")
                logger.info(f"Total de indices: {len(indexes)}")

                for idx in indexes:
                    name = idx.get("name", "N/A")
                    keys = idx.get("key", {})
                    unique = " (UNIQUE)" if idx.get("unique", False) else ""
                    logger.info(f"  - {name}: {dict(keys)}{unique}")
            except Exception as col_error:
                logger.warning(f"Coleccion '{collection_name}' no existe aún: {col_error}")

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
        create_dynamic_roi_indexes()

        logger.info("\n" + "="*80)
        create_top16_dynamic_indexes()

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
        logger.info("  - agent_roi_3d, 5d, 10d, 15d, 30d: 10 indices (5 unique)")
        logger.info("  - top16_3d, 5d, 7d, 10d, 15d, 30d: 18 indices")
        logger.info("  - agent_states: 2 indices")
        logger.info("  - assignments: 2 indices")
        logger.info("")
        logger.info("Total: 41 indices creados (VERSION 4.0)")
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
