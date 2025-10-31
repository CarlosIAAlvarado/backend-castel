"""
Script de prueba para ClientAccountsSimulationService.

Este script prueba la sincronizacion de cuentas de clientes con la simulacion.
Ejecuta en modo DRY RUN (no guarda cambios) para validar la logica.
"""

import asyncio
import logging
from datetime import date
from pymongo import MongoClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_sync_service():
    """Prueba del servicio de sincronizacion."""

    logger.info("=== INICIANDO PRUEBA DE SINCRONIZACION ===")

    # 1. Conectar a MongoDB
    MONGODB_URI = "mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy"
    DATABASE_NAME = "simulacion_casterly_rock"

    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    logger.info(f"[OK] Conectado a MongoDB: {DATABASE_NAME}")

    # 2. Importar servicio
    from app.application.services.client_accounts_simulation_service import ClientAccountsSimulationService

    service = ClientAccountsSimulationService(db)
    logger.info("[OK] Servicio instanciado correctamente")

    # 3. Verificar que existan cuentas de clientes
    cuentas_count = db.cuentas_clientes_trading.count_documents({})
    logger.info(f"[INFO] Cuentas en BD: {cuentas_count}")

    if cuentas_count == 0:
        logger.warning("[WARNING] No hay cuentas de clientes. Necesitas inicializarlas primero.")
        logger.info("Ejecuta: POST /api/client-accounts/initialize")
        return

    # 4. Detectar automaticamente la ventana de dias de la simulacion actual
    from app.utils.collection_names import get_top16_collection_name, get_all_valid_windows

    logger.info("Detectando ventana de dias de la simulacion mas reciente...")

    valid_windows = get_all_valid_windows()
    window_days = None
    top16_col = None
    latest_date = None

    # Buscar en todas las ventanas y encontrar la que tiene la fecha mas reciente
    for window in valid_windows:
        top16_collection_name = get_top16_collection_name(window)

        if top16_collection_name in db.list_collection_names():
            temp_col = db[top16_collection_name]
            doc_count = temp_col.count_documents({})

            if doc_count > 0:
                # Obtener el documento con fecha mas reciente
                latest_doc = temp_col.find_one(sort=[("date", -1)])

                if latest_doc:
                    doc_date_str = latest_doc.get("date")
                    doc_date = date.fromisoformat(doc_date_str)

                    # Si es la fecha mas reciente que hemos visto, usar esta coleccion
                    if latest_date is None or doc_date > latest_date:
                        latest_date = doc_date
                        window_days = window
                        top16_col = temp_col
                        logger.info(f"Coleccion {top16_collection_name}: {doc_count} docs, fecha mas reciente: {doc_date}")

    if not window_days or not latest_date:
        logger.error("No se encontro ninguna simulacion activa.")
        logger.error("Ejecuta una simulacion primero para generar datos.")
        return

    logger.info(f"Simulacion mas reciente detectada: {window_days}D con fecha {latest_date}")

    # Usar la fecha mas reciente encontrada
    test_date = latest_date
    top16_count = top16_col.count_documents({"date": test_date.isoformat()})
    logger.info(f"Top 16 para {test_date}: {top16_count} agentes")

    # 5. Ejecutar sincronizacion en modo DRY RUN
    logger.info(f"\n{'='*60}")
    logger.info("EJECUTANDO SINCRONIZACION (DRY RUN)")
    logger.info(f"{'='*60}")
    logger.info(f"Usando ventana detectada: {window_days}D")

    try:
        result = await service.sync_with_simulation_day(
            target_date=test_date,
            simulation_id="test_sync_001",
            window_days=window_days,  # Usar ventana detectada
            dry_run=True  # NO guarda cambios
        )

        logger.info(f"\n{'='*60}")
        logger.info("[OK] SINCRONIZACION COMPLETADA")
        logger.info(f"{'='*60}")
        logger.info(f"Fecha: {result.target_date}")
        logger.info(f"Cuentas actualizadas: {result.cuentas_actualizadas}")
        logger.info(f"Cuentas redistribuidas: {result.cuentas_redistribuidas}")
        logger.info(f"Rotaciones procesadas: {result.rotaciones_procesadas}")
        logger.info(f"Balance ANTES: ${result.balance_total_antes:,.2f}")
        logger.info(f"Balance DESPUES: ${result.balance_total_despues:,.2f}")
        logger.info(f"ROI ANTES: {result.roi_promedio_antes:.2f}%")
        logger.info(f"ROI DESPUES: {result.roi_promedio_despues:.2f}%")

        if result.snapshot_id:
            logger.info(f"Snapshot ID: {result.snapshot_id}")

        logger.info(f"\n{'='*60}")
        logger.info("RESULTADO: [OK] PRUEBA EXITOSA")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"\n{'='*60}")
        logger.error("RESULTADO: [ERROR] ERROR EN PRUEBA")
        logger.error(f"{'='*60}")
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise

    finally:
        client.close()
        logger.info("[INFO] Conexion cerrada")


async def test_individual_methods():
    """Prueba metodos individuales del servicio."""

    logger.info("\n=== PRUEBA DE METODOS INDIVIDUALES ===")

    MONGODB_URI = "mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy"
    DATABASE_NAME = "simulacion_casterly_rock"

    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    from app.application.services.client_accounts_simulation_service import ClientAccountsSimulationService

    service = ClientAccountsSimulationService(db)

    try:
        # 1. Test: _get_aggregate_stats
        logger.info("\n[TEST 1] Probando _get_aggregate_stats()...")
        stats = await service._get_aggregate_stats()
        logger.info(f"   [OK] Total cuentas: {stats['total_cuentas']}")
        logger.info(f"   [OK] Balance total: ${stats['balance_total']:,.2f}")
        logger.info(f"   [OK] ROI promedio: {stats['roi_promedio']:.2f}%")

        # 2. Test: _get_top16_for_date
        logger.info("\n[TEST 2] Probando _get_top16_for_date()...")

        # Detectar ventana automaticamente
        from app.utils.collection_names import get_top16_collection_name, get_all_valid_windows

        valid_windows = get_all_valid_windows()
        window_days = None
        test_date = None

        for window in valid_windows:
            top16_col_name = get_top16_collection_name(window)
            if top16_col_name in db.list_collection_names():
                sample_doc = db[top16_col_name].find_one()
                if sample_doc:
                    window_days = window
                    test_date_str = sample_doc.get("date")
                    test_date = date.fromisoformat(test_date_str)
                    logger.info(f"   Detectada ventana: {window_days}D, fecha: {test_date}")
                    break

        if not window_days:
            logger.error("   [ERROR] No se encontro simulacion activa")
            return

        top16 = await service._get_top16_for_date(test_date, window_days=window_days)
        logger.info(f"   [OK] Top 16 encontrados: {len(top16)} agentes")

        if top16:
            logger.info(f"   [OK] Primer agente: {top16[0].get('agent_id')}")
            logger.info(f"   [OK] ROI: {top16[0].get('roi_7d', 0) * 100:.2f}%")

        logger.info("\n[OK] TODOS LOS METODOS FUNCIONAN CORRECTAMENTE")

    except Exception as e:
        logger.error(f"[ERROR] Error en prueba de metodos: {str(e)}", exc_info=True)
        raise

    finally:
        client.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SCRIPT DE PRUEBA - CLIENT ACCOUNTS SIMULATION SERVICE")
    print("="*60 + "\n")

    # Ejecutar pruebas
    asyncio.run(test_sync_service())

    print("\n" + "="*60)
    print("PRUEBAS DE METODOS INDIVIDUALES")
    print("="*60 + "\n")

    asyncio.run(test_individual_methods())

    print("\n" + "="*60)
    print("[OK] TODAS LAS PRUEBAS COMPLETADAS")
    print("="*60 + "\n")
