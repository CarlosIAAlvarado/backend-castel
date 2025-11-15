from app.config.database import database_manager
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("DEBUG: VERIFICACION DE COLECCIONES")
print("=" * 80)

# Ver un documento de cada colección
print("\n1. SAMPLE DE top16_3d:")
print("-" * 80)
sample_3d = db.top16_3d.find_one()
if sample_3d:
    print(f"  Fecha: {sample_3d.get('date')}")
    print(f"  Campos: {list(sample_3d.keys())}")
    print(f"  window_days: {sample_3d.get('window_days', 'NO EXISTE')}")
    print(f"  roi_3d: {sample_3d.get('roi_3d', 'NO EXISTE')}")
    print(f"  roi_7d: {sample_3d.get('roi_7d', 'NO EXISTE')}")
else:
    print("  No hay documentos")

print("\n2. SAMPLE DE top16_7d:")
print("-" * 80)
sample_7d = db.top16_7d.find_one()
if sample_7d:
    print(f"  Fecha: {sample_7d.get('date')}")
    print(f"  Campos: {list(sample_7d.keys())}")
    print(f"  window_days: {sample_7d.get('window_days', 'NO EXISTE')}")
    print(f"  roi_3d: {sample_7d.get('roi_3d', 'NO EXISTE')}")
    print(f"  roi_7d: {sample_7d.get('roi_7d', 'NO EXISTE')}")
else:
    print("  No hay documentos")

print("\n3. COUNTS POR FECHA:")
print("-" * 80)
print("\ntop16_3d:")
for date in ["2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06", "2025-06-07", "2025-06-08"]:
    count = db.top16_3d.count_documents({"date": date})
    print(f"  {date}: {count} documentos")

print("\ntop16_7d:")
for date in ["2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06", "2025-06-07", "2025-06-08"]:
    count = db.top16_7d.count_documents({"date": date})
    print(f"  {date}: {count} documentos")

print("\n" + "=" * 80)
