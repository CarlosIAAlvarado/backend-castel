from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

print("=" * 80)
print("VERIFICACION DE TOP 16")
print("=" * 80)

# Obtener última fecha
latest = db.top16_by_day.find_one(sort=[('date', -1)])

if not latest:
    print("No hay datos en top16_by_day")
    exit()

latest_date = latest['date']
print(f"\nUltima fecha: {latest_date}")

# Contar registros
count = db.top16_by_day.count_documents({'date': latest_date})
print(f"Registros en esa fecha: {count}")

# Obtener todos los registros del último día
docs = list(db.top16_by_day.find({'date': latest_date}).sort('rank', 1))

print(f"\nTop {len(docs)} del {latest_date}:")
print("-" * 80)
print(f"{'Rank':<6} {'Agente':<25} {'ROI 7D':<12} {'AUM':<15} {'Casterly'}")
print("-" * 80)

for doc in docs:
    rank = doc.get('rank', 'N/A')
    agent = doc.get('agent_id', 'N/A')
    roi_7d = doc.get('roi_7d', 'N/A')
    aum = float(doc.get('total_aum', 0))
    casterly = doc.get('is_in_casterly', False)
    casterly_str = "SI" if str(casterly).lower() == 'true' else "NO"

    print(f"{str(rank):<6} {agent:<25} {roi_7d:<12} ${aum:>12,.2f} {casterly_str}")

# Verificar si faltan campos
print("\n" + "=" * 80)
print("VERIFICACION DE CAMPOS")
print("=" * 80)

sample = docs[0] if docs else {}
print(f"\nCampos en el documento:")
for key in sample.keys():
    print(f"  - {key}: {type(sample[key]).__name__} = {sample[key]}")

# Verificar si existe roi_30d
has_roi_30d = 'roi_30d' in sample
print(f"\nTiene campo roi_30d: {has_roi_30d}")

# Contar agentes en Casterly
in_casterly = sum(1 for doc in docs if str(doc.get('is_in_casterly', '')).lower() == 'true')
print(f"Agentes en Casterly Rock: {in_casterly}/{len(docs)}")

print("\n" + "=" * 80)
