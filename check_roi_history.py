from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

agent_id = 'futures-JC3'

print("=" * 80)
print(f"HISTORIAL DE ROI PARA {agent_id}")
print("=" * 80)

states = list(db.agent_states.find({'agent_id': agent_id}).sort('date', -1).limit(15))

print(f"\nUltimos 15 estados:")
print(f"{'Fecha':<15} {'roi_since_entry':<20} {'roi_day':<15} {'is_in_casterly'}")
print("-" * 80)

for s in states:
    date_val = s['date']
    roi_since = s['roi_since_entry']
    roi_day = s.get('roi_day', 0)
    in_casterly = s['is_in_casterly']

    print(f"{date_val:<15} {roi_since:>18.8f}  {roi_day:>13.8f}  {str(in_casterly)}")

# Verificar si hay cambio entre hace 7 días y hoy
if len(states) >= 8:
    today = states[0]
    seven_days_ago = states[7]

    roi_change_7d = today['roi_since_entry'] - seven_days_ago['roi_since_entry']

    print("\n" + "=" * 80)
    print("CALCULO ROI 7D")
    print("=" * 80)
    print(f"Hoy ({today['date']}): {today['roi_since_entry']:.8f}")
    print(f"Hace 7 dias ({seven_days_ago['date']}): {seven_days_ago['roi_since_entry']:.8f}")
    print(f"Cambio (ROI 7D): {roi_change_7d:.8f}")

print("\n" + "=" * 80)
