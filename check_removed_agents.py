from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

print("=" * 80)
print("VERIFICACION DE AGENTES REMOVIDOS")
print("=" * 80)

for agent_id in ['futures-CMC2', 'futures-CP1']:
    states = list(db.agent_states.find({'agent_id': agent_id}).sort('date', -1).limit(10))

    print(f"\n{agent_id}:")
    print(f"  Total estados: {db.agent_states.count_documents({'agent_id': agent_id})}")
    print("  Ultimos 10 estados:")

    for s in states:
        status = "EN CASTERLY" if s['is_in_casterly'] else "FUERA"
        print(f"    {s['date']}: {status:15s} ROI={s['roi_since_entry']:+.6f}")

    # Encontrar última fecha en Casterly
    last_in_casterly = db.agent_states.find_one({
        'agent_id': agent_id,
        'is_in_casterly': True
    }, sort=[('date', -1)])

    if last_in_casterly:
        print(f"  Ultima fecha EN Casterly: {last_in_casterly['date']}")
    else:
        print(f"  Nunca estuvo en Casterly en este periodo")

print("\n" + "=" * 80)
