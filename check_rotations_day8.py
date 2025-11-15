from app.config.database import database_manager
from datetime import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("VERIFICACION DE ROTACIONES - DIA 8 (2025-06-08)")
print("=" * 80)

# 1. Buscar rotaciones del día 8
print("\n1. ROTACIONES REGISTRADAS")
print("-" * 80)
rotations = list(db.rotation_log.find({"date": {"$regex": "2025-06-08"}}))
print(f"Total rotaciones encontradas: {len(rotations)}")

for rot in rotations:
    print(f"\n  Agent OUT: {rot.get('agent_out')}")
    print(f"  Agent IN:  {rot.get('agent_in')}")
    print(f"  Razon:     {rot.get('reason')}")
    print(f"  ROI OUT:   {rot.get('roi_7d_out', rot.get('roi_total_out'))}")
    print(f"  ROI IN:    {rot.get('roi_7d_in')}")

# 2. Verificar top16_3d del día 7 vs día 8
print("\n2. COMPARACION TOP16")
print("-" * 80)

# Top16 del día 7
top16_day7 = list(db.top16_3d.find({"date": "2025-06-07"}).sort("rank", 1))
print(f"\nTop16 día 7: {len(top16_day7)} agentes")
agents_day7 = {doc.get('agent_id') for doc in top16_day7}
print(f"Agentes: {sorted(agents_day7)}")

# Top16 del día 8
top16_day8 = list(db.top16_3d.find({"date": "2025-06-08"}).sort("rank", 1))
print(f"\nTop16 día 8: {len(top16_day8)} agentes")
agents_day8 = {doc.get('agent_id') for doc in top16_day8}
print(f"Agentes: {sorted(agents_day8)}")

# Diferencias
agents_out = agents_day7 - agents_day8
agents_in = agents_day8 - agents_day7

print(f"\nAgentes que SALIERON: {sorted(agents_out)}")
print(f"Agentes que ENTRARON: {sorted(agents_in)}")

# 3. Verificar estados de los agentes que salieron (últimos 3 días)
print("\n3. VERIFICACION REGLA: 3 DIAS CONSECUTIVOS FALL")
print("-" * 80)

for agent_id in agents_out:
    print(f"\n{agent_id}:")

    # Obtener estados de los últimos 3 días
    states = list(db.agent_states.find({
        "agent_id": agent_id,
        "date": {"$in": ["2025-06-06", "2025-06-07", "2025-06-08"]}
    }).sort("date", 1))

    print(f"  Estados últimos 3 días:")
    for state in states:
        print(f"    {state.get('date')}: {state.get('state')} (ROI: {state.get('roi', 0):.4f})")

    # Verificar si todos son FALL
    if len(states) >= 3:
        all_fall = all(s.get('state') == 'FALL' for s in states[-3:])
        print(f"  ¿3 días consecutivos FALL? {all_fall}")

# 4. Verificar stop loss
print("\n4. VERIFICACION REGLA: STOP LOSS (-10%)")
print("-" * 80)

for agent_id in agents_out:
    print(f"\n{agent_id}:")

    # Obtener ROI del día 8
    roi_doc = db.agent_roi_3d.find_one({
        "userId": agent_id,
        "target_date": "2025-06-08"
    })

    if roi_doc:
        roi = roi_doc.get('roi_3d', 0)
        print(f"  ROI_3d: {roi:.4f} ({roi * 100:.2f}%)")
        print(f"  ¿Stop Loss activado? {roi <= -0.10}")

print("\n" + "=" * 80)
