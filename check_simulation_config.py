from app.config.database import database_manager
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

simulation_id = "70885e62-118f-4b60-beec-ad90b926202f"

print("=" * 80)
print("CONFIGURACION DE LA SIMULACION")
print("=" * 80)

sim_doc = db.simulations.find_one({"simulation_id": simulation_id})

if sim_doc:
    print(f"\nNombre: {sim_doc['name']}")
    print(f"ID: {sim_doc['simulation_id']}")
    print(f"\nConfiguracion:")
    for key, value in sim_doc['config'].items():
        print(f"  {key}: {value}")

    # Calcular window_days real
    days_simulated = sim_doc['config'].get('days_simulated')
    print(f"\nDays simulated: {days_simulated}")
    print(f"Dias de rebalanceo esperados (si window_days={days_simulated}):")
    print(f"  Dia {days_simulated} (ultimo dia)")

    # Si fuera window_days=3
    print(f"\nDias de rebalanceo esperados (si window_days=3):")
    print(f"  Dia 3 (2025-06-04)")
    print(f"  Dia 6 (2025-06-07)")
else:
    print("ERROR: No se encontro la simulacion")

print("\n" + "=" * 80)
