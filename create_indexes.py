"""
Script para crear indices en MongoDB para optimizar el rendimiento de las consultas.
Ejecutar una vez antes de la simulacion.
"""

from app.config.database import database_manager

def create_indexes():
    database_manager.connect()
    db = database_manager.get_database()

    print("Creando indices para optimizar consultas...")

    # Indices para movements
    movements = db['movements']
    movements.create_index([("user", 1), ("updatedTime", 1)])
    movements.create_index([("updatedTime", 1)])
    print("[OK] Indices creados en movements")

    # Indices para balances
    balances = db['balances']
    balances.create_index([("userId", 1), ("createdAt", 1)])
    balances.create_index([("createdAt", 1)])
    print("[OK] Indices creados en balances")

    # Indices para agent_states
    agent_states = db['agent_states']
    agent_states.create_index([("agent_id", 1), ("date", -1)])
    agent_states.create_index([("date", 1)])
    agent_states.create_index([("is_in_casterly", 1), ("date", 1)])
    print("[OK] Indices creados en agent_states")

    # Indices para assignments
    assignments = db['assignments']
    assignments.create_index([("agent_id", 1), ("is_active", 1)])
    assignments.create_index([("account_id", 1), ("is_active", 1)])
    assignments.create_index([("date", 1)])
    print("[OK] Indices creados en assignments")

    # Indices para top16_day
    top16_day = db['top16_day']
    top16_day.create_index([("date", 1), ("rank", 1)])
    top16_day.create_index([("date", 1), ("roi_7d", -1)])
    print("[OK] Indices creados en top16_day")

    # Indices para rotation_log
    rotation_log = db['rotation_log']
    rotation_log.create_index([("date", 1)])
    rotation_log.create_index([("agent_out", 1)])
    rotation_log.create_index([("agent_in", 1)])
    print("[OK] Indices creados en rotation_log")

    database_manager.disconnect()
    print("\n[SUCCESS] Todos los indices creados exitosamente")
    print("El rendimiento de la simulacion deberia mejorar significativamente.")

if __name__ == "__main__":
    create_indexes()
