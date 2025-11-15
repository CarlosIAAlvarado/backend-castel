from app.config.database import database_manager
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("EVENTOS EXISTENTES EN rebalancing_events")
print("=" * 80)

events = list(db.rebalancing_events.find({}).limit(17))

print(f"\nTotal eventos: {len(events)}\n")

for i, evt in enumerate(events, 1):
    print(f"{i}. Event ID: {evt.get('event_id')}")
    print(f"   Simulation ID: {evt.get('simulation_id')}")
    print(f"   Fecha: {evt.get('date')}, Dia: {evt.get('day_number')}")
    print(f"   Rotaciones: {evt.get('total_rotations')}")
    print()

print("=" * 80)
