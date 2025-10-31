"""
Script para verificar el formato de distribucion_agentes en snapshots
"""
from app.config.database import database_manager
import json

# Conectar a MongoDB
database_manager.connect()
db = database_manager.get_database()

# Obtener un snapshot reciente
snapshots_col = db.client_accounts_snapshots
snapshot = snapshots_col.find_one(
    {"simulation_id": "test_client_accounts_integration"},
    sort=[("target_date", -1)]
)

if snapshot:
    print("=" * 80)
    print("FORMATO DE DISTRIBUCION_AGENTES")
    print("=" * 80)
    print(f"\nFecha: {snapshot['target_date']}")
    print(f"Total cuentas: {snapshot['total_cuentas']}")
    print("\nDistribucion agentes:")
    print(f"Tipo: {type(snapshot['distribucion_agentes'])}")
    print(f"\nContenido:")
    print(json.dumps(snapshot['distribucion_agentes'], indent=2, default=str))

    print("\n" + "=" * 80)
    print("ITERACION DE DISTRIBUCION_AGENTES")
    print("=" * 80)

    for agente, count in snapshot['distribucion_agentes'].items():
        print(f"Agente: {agente}")
        print(f"  Tipo de count: {type(count)}")
        print(f"  Valor de count: {count}")
        print()
else:
    print("No se encontró ningún snapshot")

database_manager.disconnect()
