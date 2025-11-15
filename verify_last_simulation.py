from app.config.database import database_manager
from datetime import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("VERIFICACION DE ULTIMA SIMULACION")
print("=" * 80)

# 1. Buscar la simulación más reciente
print("\n1. SIMULACIONES RECIENTES")
print("-" * 80)
simulations = list(db.simulations.find({}).sort("createdAt", -1).limit(3))

if not simulations:
    print("No se encontraron simulaciones")
else:
    for i, sim in enumerate(simulations, 1):
        print(f"\n{i}. Simulacion:")
        print(f"   ID: {sim.get('simulation_id')}")
        print(f"   Nombre: {sim.get('name')}")
        print(f"   Creada: {sim.get('createdAt')}")
        print(f"   Config: {sim.get('config', {}).get('start_date')} a {sim.get('config', {}).get('target_date')}")
        print(f"   Window days: {sim.get('config', {}).get('days_simulated')}")

        # Verificar KPIs
        kpis = sim.get('kpis', {})
        print(f"   Total ROI: {kpis.get('total_roi', 0)}")
        print(f"   Top 16 final: {len(sim.get('top_16_final', []))} agentes")
        print(f"   Total rotations: {sim.get('rotations_summary', {}).get('total_rotations', 0)}")

    # Usar la más reciente para verificaciones
    latest_sim = simulations[0]
    simulation_id = latest_sim.get('simulation_id')

    print("\n" + "=" * 80)
    print(f"USANDO SIMULACION MAS RECIENTE: {simulation_id}")
    print("=" * 80)

    # 2. Verificar eventos de rebalanceo
    print("\n2. EVENTOS DE REBALANCEO")
    print("-" * 80)
    rebal_events = list(db.rebalancing_events.find({"simulation_id": simulation_id}))
    print(f"Eventos encontrados: {len(rebal_events)}")

    if rebal_events:
        for evt in rebal_events:
            print(f"  - Evento: {evt.get('event_id')}")
            print(f"    Fecha: {evt.get('date')}, Dia: {evt.get('day_number')}")
            print(f"    Rotaciones: {evt.get('total_rotations')}")

    # 3. Verificar rotation_log
    print("\n3. ROTATION_LOG")
    print("-" * 80)
    start_date = latest_sim.get('config', {}).get('start_date')
    end_date = latest_sim.get('config', {}).get('target_date')

    rotation_docs = list(db.rotation_log.find({
        "date": {
            "$gte": start_date + "T00:00:00",
            "$lte": end_date + "T23:59:59"
        }
    }))

    print(f"Rotaciones encontradas: {len(rotation_docs)}")

    if rotation_docs:
        for rot in rotation_docs:
            print(f"  - Fecha: {rot.get('date')}")
            print(f"    {rot.get('agent_out')} -> {rot.get('agent_in')}")
            print(f"    Razon: {rot.get('reason')}")

    # 4. Verificar top16_3d
    print("\n4. TOP16_3D")
    print("-" * 80)
    top16_docs = list(db.top16_3d.find({"date": end_date}).limit(5))
    print(f"Registros encontrados para {end_date}: {len(top16_docs)}")

    if top16_docs:
        print("Primeros 3 agentes:")
        for doc in top16_docs[:3]:
            print(f"  Rank {doc.get('rank')}: {doc.get('agent_id')} - ROI: {doc.get('roi_3d', 0)}")

print("\n" + "=" * 80)
