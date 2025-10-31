"""
Script para crear índices en MongoDB y optimizar consultas.

IMPORTANTE: Este script es SEGURO y NO afecta los datos existentes.
Solo crea índices para acelerar las búsquedas.

Ejecutar con: python -m backend.create_indexes
"""

import logging
from pymongo import ASCENDING, DESCENDING
from app.config.database import database_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_all_indexes():
    """
    Crea todos los índices necesarios para optimizar la simulación.

    Los índices aceleran búsquedas pero NO cambian los datos.
    Es seguro ejecutar este script múltiples veces (MongoDB ignora índices duplicados).
    """
    try:
        # Conectar a MongoDB primero
        database_manager.connect()
        db = database_manager.get_database()

        logger.info("=" * 60)
        logger.info("CREANDO INDICES PARA OPTIMIZAR SIMULACION")
        logger.info("=" * 60)

        # ============================================================
        # 1. BALANCES - Índice en createdAt (consultas frecuentes)
        # ============================================================
        logger.info("\n[1/8] Creando índice en balances.createdAt...")
        try:
            result = db.balances.create_index([("createdAt", ASCENDING)], name="idx_createdAt_balances")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        # ============================================================
        # 2. MOVEMENTS - Índice en createdAt
        # ============================================================
        logger.info("\n[2/8] Creando índice en mov07.10.createdAt...")
        try:
            result = db["mov07.10"].create_index([("createdAt", ASCENDING)], name="idx_createdAt_movements")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        # Índice compuesto en userId + createdAt para búsquedas de agente específico
        logger.info("\n[3/8] Creando índice compuesto en mov07.10.userId + createdAt...")
        try:
            result = db["mov07.10"].create_index([
                ("userId", ASCENDING),
                ("createdAt", ASCENDING)
            ], name="idx_userId_createdAt_movements")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        # ============================================================
        # 3. ROTATION_LOG - Índice en date (consultas por rango de fechas)
        # ============================================================
        logger.info("\n[4/8] Creando índice en rotation_log.date...")
        try:
            result = db.rotation_log.create_index([("date", ASCENDING)], name="idx_date_rotation")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        # ============================================================
        # 4. TOP16_BY_DAY - Índices para consultas rápidas
        # ============================================================
        logger.info("\n[5/8] Creando índice en top16_by_day.date...")
        try:
            result = db.top16_by_day.create_index([("date", ASCENDING)], name="idx_date_top16")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        logger.info("\n[6/8] Creando índice compuesto en top16_by_day.date + rank...")
        try:
            result = db.top16_by_day.create_index([
                ("date", ASCENDING),
                ("rank", ASCENDING)
            ], name="idx_date_rank_top16")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        # ============================================================
        # 5. AGENT_ROI_7D - Índices críticos para cálculos
        # ============================================================
        logger.info("\n[7/8] Creando índice compuesto en agent_roi_7d.userId + target_date...")
        try:
            result = db.agent_roi_7d.create_index([
                ("userId", ASCENDING),
                ("target_date", ASCENDING)
            ], name="idx_userId_targetDate_roi7d")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        logger.info("\n[8/8] Creando índice en agent_roi_7d.target_date...")
        try:
            result = db.agent_roi_7d.create_index([("target_date", ASCENDING)], name="idx_targetDate_roi7d")
            logger.info(f"✓ Índice creado: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✓ Índice ya existe (omitiendo)")
            else:
                raise

        # ============================================================
        # RESUMEN FINAL
        # ============================================================
        logger.info("\n" + "=" * 60)
        logger.info("INDICES CREADOS EXITOSAMENTE")
        logger.info("=" * 60)

        # Mostrar todos los índices creados
        logger.info("\nÍndices en balances:")
        for index in db.balances.list_indexes():
            logger.info(f"  - {index['name']}: {index.get('key', {})}")

        logger.info("\nÍndices en mov07.10:")
        for index in db["mov07.10"].list_indexes():
            logger.info(f"  - {index['name']}: {index.get('key', {})}")

        logger.info("\nÍndices en rotation_log:")
        for index in db.rotation_log.list_indexes():
            logger.info(f"  - {index['name']}: {index.get('key', {})}")

        logger.info("\nÍndices en top16_by_day:")
        for index in db.top16_by_day.list_indexes():
            logger.info(f"  - {index['name']}: {index.get('key', {})}")

        logger.info("\nÍndices en agent_roi_7d:")
        for index in db.agent_roi_7d.list_indexes():
            logger.info(f"  - {index['name']}: {index.get('key', {})}")

        logger.info("\n✓ Optimización completada. La simulación ahora será más rápida.")
        logger.info("✓ NO se modificaron datos, solo se agregaron índices de búsqueda.\n")

        return True

    except Exception as e:
        logger.error(f"Error al crear índices: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    create_all_indexes()
