"""
Script para inicializar las colecciones de cuentas de clientes en MongoDB.
Ejecutar una sola vez para crear las colecciones con validacion de esquema.
"""

import logging
from typing import Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

logger = logging.getLogger(__name__)


def create_cuentas_clientes_trading_collection(db) -> None:
    """
    Crea la coleccion cuentas_clientes_trading con validacion de esquema.

    Esta coleccion guarda la informacion de trading de cada cuenta de cliente.
    """
    collection_name = "cuentas_clientes_trading"

    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "cuenta_id",
                "nombre_cliente",
                "balance_inicial",
                "balance_actual",
                "roi_total",
                "win_rate",
                "agente_actual",
                "fecha_asignacion_agente",
                "roi_agente_al_asignar",
                "estado"
            ],
            "properties": {
                "cuenta_id": {
                    "bsonType": "string",
                    "description": "ID de referencia a cuentas_clientes"
                },
                "nombre_cliente": {
                    "bsonType": "string",
                    "description": "Nombre del cliente"
                },
                "balance_inicial": {
                    "bsonType": "number",
                    "minimum": 0,
                    "description": "Balance inicial (siempre 1000)"
                },
                "balance_actual": {
                    "bsonType": "number",
                    "minimum": 0,
                    "description": "Balance actual calculado"
                },
                "roi_total": {
                    "bsonType": "number",
                    "description": "ROI historico total de la cuenta"
                },
                "roi_historico_anterior": {
                    "bsonType": "number",
                    "description": "ROI acumulado con agentes anteriores (antes del actual)"
                },
                "win_rate": {
                    "bsonType": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Tasa de victorias"
                },
                "agente_actual": {
                    "bsonType": "string",
                    "description": "ID del agente asignado"
                },
                "fecha_asignacion_agente": {
                    "bsonType": "date",
                    "description": "Fecha de ultima asignacion"
                },
                "roi_agente_al_asignar": {
                    "bsonType": "number",
                    "description": "ROI del agente al momento de asignacion"
                },
                "roi_acumulado_con_agente": {
                    "bsonType": "number",
                    "description": "ROI ganado con el agente actual"
                },
                "numero_cambios_agente": {
                    "bsonType": "int",
                    "minimum": 0,
                    "description": "Contador de cambios de agente"
                },
                "simulation_id": {
                    "bsonType": "string",
                    "description": "ID de la simulacion a la que pertenece"
                },
                "estado": {
                    "enum": ["activo", "inactivo"],
                    "description": "Estado de la cuenta"
                }
            }
        }
    }

    try:
        db.create_collection(collection_name, validator=validator)
        logger.info(f"Coleccion {collection_name} creada exitosamente")
    except CollectionInvalid:
        logger.warning(f"Coleccion {collection_name} ya existe")


def create_historial_asignaciones_collection(db) -> None:
    """
    Crea la coleccion historial_asignaciones_clientes.

    Esta coleccion guarda el historial completo de cambios de agente.
    """
    collection_name = "historial_asignaciones_clientes"

    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "cuenta_id",
                "nombre_cliente",
                "agente_id",
                "simulation_id",
                "fecha_inicio",
                "roi_agente_inicio",
                "balance_inicio",
                "motivo_cambio"
            ],
            "properties": {
                "cuenta_id": {
                    "bsonType": "string"
                },
                "nombre_cliente": {
                    "bsonType": "string"
                },
                "agente_id": {
                    "bsonType": "string"
                },
                "simulation_id": {
                    "bsonType": "string"
                },
                "fecha_inicio": {
                    "bsonType": "date"
                },
                "fecha_fin": {
                    "bsonType": ["date", "null"]
                },
                "roi_agente_inicio": {
                    "bsonType": "number"
                },
                "roi_agente_fin": {
                    "bsonType": ["number", "null"]
                },
                "roi_cuenta_ganado": {
                    "bsonType": ["number", "null"]
                },
                "balance_inicio": {
                    "bsonType": "number"
                },
                "balance_fin": {
                    "bsonType": ["number", "null"]
                },
                "motivo_cambio": {
                    "enum": ["inicial", "re-balanceo", "rotacion"],
                    "description": "Razon del cambio"
                },
                "dias_con_agente": {
                    "bsonType": ["int", "null"]
                }
            }
        }
    }

    try:
        db.create_collection(collection_name, validator=validator)
        logger.info(f"Coleccion {collection_name} creada exitosamente")
    except CollectionInvalid:
        logger.warning(f"Coleccion {collection_name} ya existe")


def create_distribucion_snapshot_collection(db) -> None:
    """
    Crea la coleccion distribucion_cuentas_snapshot.

    Esta coleccion guarda snapshots de distribucion por simulacion.
    """
    collection_name = "distribucion_cuentas_snapshot"

    try:
        db.create_collection(collection_name)
        logger.info(f"Coleccion {collection_name} creada exitosamente")
    except CollectionInvalid:
        logger.warning(f"Coleccion {collection_name} ya existe")


def create_rebalanceo_log_collection(db) -> None:
    """
    Crea la coleccion rebalanceo_log.

    Esta coleccion guarda logs de operaciones de re-balanceo.
    """
    collection_name = "rebalanceo_log"

    try:
        db.create_collection(collection_name)
        logger.info(f"Coleccion {collection_name} creada exitosamente")
    except CollectionInvalid:
        logger.warning(f"Coleccion {collection_name} ya existe")


def create_client_accounts_snapshots_collection(db) -> None:
    """
    Crea la coleccion client_accounts_snapshots.

    Esta coleccion guarda snapshots diarios completos del estado de todas las cuentas
    durante la simulacion. Se usa para timeline y replay dia a dia.
    """
    collection_name = "client_accounts_snapshots"

    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "simulation_id",
                "target_date",
                "total_cuentas",
                "balance_total",
                "roi_promedio",
                "win_rate_promedio",
                "distribucion_agentes"
            ],
            "properties": {
                "simulation_id": {
                    "bsonType": "string",
                    "description": "ID de la simulacion"
                },
                "target_date": {
                    "bsonType": "string",
                    "description": "Fecha del snapshot en formato YYYY-MM-DD"
                },
                "total_cuentas": {
                    "bsonType": "int",
                    "minimum": 0,
                    "description": "Total de cuentas activas"
                },
                "balance_total": {
                    "bsonType": "number",
                    "minimum": 0,
                    "description": "Suma de balances de todas las cuentas"
                },
                "roi_promedio": {
                    "bsonType": "number",
                    "description": "ROI promedio de todas las cuentas"
                },
                "win_rate_promedio": {
                    "bsonType": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Win rate promedio de todas las cuentas"
                },
                "distribucion_agentes": {
                    "bsonType": "object",
                    "description": "Diccionario con estadisticas por agente {agente_id: {num_cuentas, balance_total, roi_promedio}}"
                },
                "cuentas_estado": {
                    "bsonType": ["array", "null"],
                    "description": "Array con estado detallado de cada cuenta (opcional, para replay completo)",
                    "items": {
                        "bsonType": "object",
                        "properties": {
                            "cuenta_id": {"bsonType": "string"},
                            "balance": {"bsonType": "number"},
                            "roi": {"bsonType": "number"},
                            "agente": {"bsonType": "string"}
                        }
                    }
                },
                "createdAt": {
                    "bsonType": "date",
                    "description": "Fecha de creacion del snapshot"
                }
            }
        }
    }

    try:
        db.create_collection(collection_name, validator=validator)
        logger.info(f"Coleccion {collection_name} creada exitosamente")
    except CollectionInvalid:
        logger.warning(f"Coleccion {collection_name} ya existe")


def create_indexes(db) -> None:
    """
    Crea todos los indices necesarios en las colecciones.
    """
    logger.info("Creando indices...")

    # Indices para cuentas_clientes_trading
    trading_collection = db.cuentas_clientes_trading
    trading_collection.create_index([("cuenta_id", ASCENDING)], unique=True)
    trading_collection.create_index([("agente_actual", ASCENDING)])
    trading_collection.create_index([("roi_total", DESCENDING)])
    trading_collection.create_index([("created_at", DESCENDING)])
    logger.info("Indices creados en cuentas_clientes_trading")

    # Indices para historial_asignaciones_clientes
    historial_collection = db.historial_asignaciones_clientes
    historial_collection.create_index([
        ("cuenta_id", ASCENDING),
        ("fecha_inicio", DESCENDING)
    ])
    historial_collection.create_index([("agente_id", ASCENDING)])
    historial_collection.create_index([("simulation_id", ASCENDING)])
    logger.info("Indices creados en historial_asignaciones_clientes")

    # Indices para distribucion_cuentas_snapshot
    snapshot_collection = db.distribucion_cuentas_snapshot
    snapshot_collection.create_index([("simulation_id", ASCENDING)])
    snapshot_collection.create_index([("fecha_snapshot", DESCENDING)])
    logger.info("Indices creados en distribucion_cuentas_snapshot")

    # Indices para rebalanceo_log
    rebalanceo_collection = db.rebalanceo_log
    rebalanceo_collection.create_index([("simulation_id", ASCENDING)])
    rebalanceo_collection.create_index([("fecha_rebalanceo", DESCENDING)])
    logger.info("Indices creados en rebalanceo_log")

    # Indices para client_accounts_snapshots
    snapshots_collection = db.client_accounts_snapshots
    snapshots_collection.create_index([
        ("simulation_id", ASCENDING),
        ("target_date", DESCENDING)
    ])
    snapshots_collection.create_index([("target_date", DESCENDING)])
    logger.info("Indices creados en client_accounts_snapshots")


def initialize_client_accounts_collections(mongodb_uri: str, database_name: str) -> None:
    """
    Inicializa todas las colecciones necesarias para el sistema de cuentas de clientes.

    Args:
        mongodb_uri: URI de conexion a MongoDB
        database_name: Nombre de la base de datos
    """
    logger.info("Inicializando colecciones de cuentas de clientes...")

    client = MongoClient(mongodb_uri)
    db = client[database_name]

    # Crear colecciones
    create_cuentas_clientes_trading_collection(db)
    create_historial_asignaciones_collection(db)
    create_distribucion_snapshot_collection(db)
    create_rebalanceo_log_collection(db)
    create_client_accounts_snapshots_collection(db)

    # Crear indices
    create_indexes(db)

    logger.info("Inicializacion completada exitosamente")
    client.close()


if __name__ == "__main__":
    MONGODB_URI = "mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy"
    DATABASE_NAME = "simulacion_casterly_rock"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    initialize_client_accounts_collections(MONGODB_URI, DATABASE_NAME)
