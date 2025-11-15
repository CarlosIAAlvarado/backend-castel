from app.config.database import database_manager
from datetime import date
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

simulation_id = "70885e62-118f-4b60-beec-ad90b926202f"
end_date = date(2025, 6, 8)
window_days = 3

print("=" * 80)
print("VERIFICACIÓN DE DATOS DE SIMULACIÓN")
print("=" * 80)

# 1. Verificar documento de simulación
print("\n1. DOCUMENTO DE SIMULACIÓN")
print("-" * 80)
sim_doc = db.simulations.find_one({"simulation_id": simulation_id})
if sim_doc:
    print(f"Encontrado: {sim_doc['name']}")
    print(f"  KPIs:")
    for key, value in sim_doc['kpis'].items():
        print(f"    {key}: {value}")
    print(f"  Top 16 final: {len(sim_doc.get('top_16_final', []))} agentes")
    print(f"  Total rotations: {sim_doc.get('rotations_summary', {}).get('total_rotations', 0)}")
else:
    print("NO ENCONTRADO")

# 2. Verificar top16_3d
print("\n2. TOP16_3D")
print("-" * 80)
top16_count = db.top16_3d.count_documents({"date": end_date.isoformat()})
print(f"Registros en top16_3d para {end_date}: {top16_count}")

if top16_count > 0:
    top16_sample = db.top16_3d.find_one({"date": end_date.isoformat()})
    print(f"  Ejemplo: {top16_sample.get('agent_id')} - rank {top16_sample.get('rank')}")

# 3. Verificar agent_roi_3d
print("\n3. AGENT_ROI_3D")
print("-" * 80)
roi_count = db.agent_roi_3d.count_documents({"target_date": end_date.isoformat()})
print(f"Registros en agent_roi_3d para {end_date}: {roi_count}")

if roi_count > 0:
    roi_sample = db.agent_roi_3d.find_one({"target_date": end_date.isoformat()})
    print(f"  Ejemplo: {roi_sample.get('userId')} - ROI {roi_sample.get('roi_7d_total', 0)}")

# 4. Verificar rotation_log
print("\n4. ROTATION_LOG")
print("-" * 80)
rotations = list(db.rotation_log.find({"date": {"$gte": "2025-06-02", "$lte": "2025-06-08"}}))
print(f"Rotaciones encontradas: {len(rotations)}")
for rot in rotations:
    print(f"  {rot['date']}: {rot['agent_out']} -> {rot['agent_in']} (reason: {rot.get('reason', 'N/A')})")

print("\n" + "=" * 80)
