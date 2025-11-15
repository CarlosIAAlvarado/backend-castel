from app.config.database import database_manager
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

end_date = "2025-06-08"

print("=" * 80)
print("VERIFICACION DE COLECCIONES")
print("=" * 80)

# Verificar en que coleccion estan los datos
collections_to_check = ["top16_3d", "top16_5d", "top16_7d", "top16_10d", "top16_15d", "top16_30d"]

print("\nBuscando datos del 2025-06-08 en todas las colecciones top16:")
print("-" * 80)

for coll_name in collections_to_check:
    count = db[coll_name].count_documents({"date": end_date})
    print(f"{coll_name}: {count} registros")

    if count > 0:
        sample = db[coll_name].find_one({"date": end_date})
        print(f"  Ejemplo: {sample.get('agent_id')} - rank {sample.get('rank')}")

# Verificar agent_roi
print("\nBuscando datos ROI del 2025-06-08:")
print("-" * 80)
roi_collections = ["agent_roi_3d", "agent_roi_5d", "agent_roi_7d"]

for coll_name in roi_collections:
    count = db[coll_name].count_documents({"target_date": end_date})
    print(f"{coll_name}: {count} registros")

print("\n" + "=" * 80)
