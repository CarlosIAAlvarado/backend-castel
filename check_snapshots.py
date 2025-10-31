"""
Script para verificar TODOS los snapshots en la base de datos.
"""

from pymongo import MongoClient
from pprint import pprint

# Configuracion
MONGODB_URI = "mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy"
DATABASE_NAME = "simulacion_casterly_rock"

client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

snapshots_col = db.client_accounts_snapshots

print("\n" + "="*80)
print("REVISANDO TODOS LOS SNAPSHOTS")
print("="*80)

# Ver cuantos hay en total
total = snapshots_col.count_documents({})
print(f"\nTotal snapshots en BD: {total}")

if total > 0:
    # Obtener todos
    all_snapshots = list(snapshots_col.find().sort("target_date", -1))

    print(f"\nUltimos {min(10, len(all_snapshots))} snapshots:")
    print("-"*80)

    for snap in all_snapshots[:10]:
        print(f"\nFecha: {snap['target_date']}")
        print(f"  Simulation ID: {snap['simulation_id']}")
        print(f"  Total cuentas: {snap['total_cuentas']}")
        print(f"  Balance: ${snap['balance_total']:,.2f}")
        print(f"  ROI promedio: {snap['roi_promedio']:.2f}%")
        print(f"  Creado: {snap.get('createdAt', 'N/A')}")

    # Agrupar por simulation_id
    print("\n" + "-"*80)
    print("SNAPSHOTS POR SIMULATION_ID:")
    print("-"*80)

    pipeline = [
        {"$group": {
            "_id": "$simulation_id",
            "count": {"$sum": 1},
            "fechas": {"$push": "$target_date"}
        }},
        {"$sort": {"count": -1}}
    ]

    by_sim_id = list(snapshots_col.aggregate(pipeline))

    for sim in by_sim_id:
        print(f"\nSimulation ID: {sim['_id']}")
        print(f"  Snapshots: {sim['count']}")
        print(f"  Fechas: {sorted(sim['fechas'])}")

else:
    print("\n[WARNING] No hay snapshots en la base de datos")
    print("[INFO] Verifica que la sincronizacion se haya ejecutado correctamente")

print("\n" + "="*80)

client.close()
