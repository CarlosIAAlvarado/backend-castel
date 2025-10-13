from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['simulacion_casterly_rock']

print("=== VERIFICACION DE DATOS EN MONGODB ===\n")

# Agent States
total = db.agent_states.count_documents({})
print(f"Total agent_states: {total}")

if total > 0:
    with_casterly = db.agent_states.count_documents({'is_in_casterly': True})
    print(f"Con is_in_casterly=True: {with_casterly}")

    dates = list(db.agent_states.distinct('date'))
    print(f"Fechas unicas: {len(dates)}")
    if dates:
        print(f"Rango de fechas: {min(dates)} -> {max(dates)}")

    # Muestra
    sample = db.agent_states.find_one()
    print(f"\nEjemplo de documento:")
    print(f"  Agent ID: {sample.get('agent_id')}")
    print(f"  Date: {sample.get('date')}")
    print(f"  is_in_casterly: {sample.get('is_in_casterly')}")
    print(f"  roi_day: {sample.get('roi_day')}")
    print(f"  roi_since_entry: {sample.get('roi_since_entry')}")

    # Contar por fecha
    print(f"\nEstados por fecha:")
    pipeline = [
        {"$group": {"_id": "$date", "count": {"$sum": 1}, "in_casterly": {"$sum": {"$cond": ["$is_in_casterly", 1, 0]}}}},
        {"$sort": {"_id": 1}},
        {"$limit": 5}
    ]
    for doc in db.agent_states.aggregate(pipeline):
        print(f"  {doc['_id']}: {doc['count']} estados ({doc['in_casterly']} en Casterly)")
else:
    print("  [ERROR] No hay datos en agent_states")

# Assignments
print(f"\nTotal assignments: {db.assignments.count_documents({})}")
active = db.assignments.count_documents({'is_active': True})
print(f"Assignments activas: {active}")

# Top16
print(f"\nTotal top16: {db.top16_day.count_documents({})}")

# Rotations
print(f"Total rotations: {db.rotation_log.count_documents({})}")
