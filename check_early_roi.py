from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

agent_id = 'futures-JC3'

print("=" * 80)
print(f"VERIFICACION DE ROI TEMPRANO PARA {agent_id}")
print("=" * 80)

# Obtener estados del 2025-09-01 al 2025-09-20
states = list(db.agent_states.find({
    'agent_id': agent_id,
    'date': {'$gte': '2025-09-01', '$lte': '2025-09-20'}
}).sort('date', 1))

print(f"\nTotal estados encontrados: {len(states)}")
print(f"\n{'#':<4} {'Fecha':<15} {'roi_since_entry':<20} {'roi_day':<15} {'Casterly'}")
print("-" * 80)

for i, s in enumerate(states[:20]):
    date_val = s['date']
    roi_since = s['roi_since_entry']
    roi_day = s.get('roi_day', 0)
    in_casterly = 'SI' if s['is_in_casterly'] else 'NO'

    print(f"{i+1:<4} {date_val:<15} {roi_since:>18.8f}  {roi_day:>13.8f}  {in_casterly}")

# Calcular ROI 7D y 30D para el período completo (2025-09-01 a 2025-10-07)
all_states = list(db.agent_states.find({
    'agent_id': agent_id
}).sort('date', 1))

if len(all_states) >= 8:
    # ROI 7D: comparar 2025-10-07 con 2025-09-30
    last_state = all_states[-1]
    state_7d_back = [s for s in all_states if s['date'] == '2025-09-30']

    if state_7d_back:
        roi_7d = last_state['roi_since_entry'] - state_7d_back[0]['roi_since_entry']
        print(f"\n{'=' * 80}")
        print("ROI 7D CALCULADO (2025-09-30 a 2025-10-07)")
        print(f"{'=' * 80}")
        print(f"  2025-10-07: {last_state['roi_since_entry']:.8f}")
        print(f"  2025-09-30: {state_7d_back[0]['roi_since_entry']:.8f}")
        print(f"  Cambio (ROI 7D): {roi_7d:.8f} ({roi_7d * 100:.4f}%)")

print("\n" + "=" * 80)
