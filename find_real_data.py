from app.config.database import database_manager
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("BUSCANDO DATOS REALES")
print("=" * 80)

# 1. Buscar en top16_7d (quizás se guardó con window_days incorrecto)
print("\n1. TOP16_7D (window_days=7)")
print("-" * 80)
top16_7d_count = db.top16_7d.count_documents({"date": "2025-06-08"})
print(f"Registros: {top16_7d_count}")
if top16_7d_count > 0:
    samples = list(db.top16_7d.find({"date": "2025-06-08"}).limit(3))
    for s in samples:
        print(f"  {s.get('agent_id')} - rank {s.get('rank')}")

# 2. Buscar top16_by_day
print("\n2. TOP16_BY_DAY")
print("-" * 80)
top16_by_day_count = db.top16_by_day.count_documents({"date": "2025-06-08"})
print(f"Registros: {top16_by_day_count}")
if top16_by_day_count > 0:
    samples = list(db.top16_by_day.find({"date": "2025-06-08"}).limit(3))
    for s in samples:
        print(f"  {s.get('agent_id')} - rank {s.get('rank', 'N/A')}")

# 3. Buscar rotaciones con fecha como Date object
print("\n3. ROTATION_LOG (con ISODate)")
print("-" * 80)
from datetime import datetime
rot_date = datetime(2025, 6, 8)
rotations_date = list(db.rotation_log.find({"date": rot_date}))
print(f"Rotaciones con ISODate: {len(rotations_date)}")
for rot in rotations_date:
    print(f"  {rot.get('agent_out')} -> {rot.get('agent_in')}")

# 4. Buscar cualquier rotación en junio 2025
print("\n4. TODAS LAS ROTACIONES EN ROTATION_LOG")
print("-" * 80)
all_rotations = list(db.rotation_log.find({}))
print(f"Total de rotaciones en BD: {len(all_rotations)}")
if len(all_rotations) > 0:
    print("Primeras 3:")
    for rot in all_rotations[:3]:
        print(f"  Fecha: {rot.get('date')}, tipo: {type(rot.get('date'))}")
        print(f"    {rot.get('agent_out')} -> {rot.get('agent_in')}")

print("\n" + "=" * 80)
