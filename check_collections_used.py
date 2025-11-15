from app.config.database import database_manager
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("VERIFICACION DE COLECCIONES USADAS EN LA SIMULACION")
print("=" * 80)

collections_to_check = [
    "top16_3d",
    "top16_7d",
    "agent_roi_3d",
    "agent_roi_7d"
]

for coll_name in collections_to_check:
    count = db[coll_name].count_documents({})
    print(f"\n{coll_name}: {count} documentos")

    if count > 0:
        # Mostrar fechas disponibles
        dates = db[coll_name].distinct("date")
        print(f"  Fechas: {sorted(dates)}")

        # Mostrar un documento de ejemplo
        sample = db[coll_name].find_one()
        if sample:
            print(f"  Campos: {list(sample.keys())}")

print("\n" + "=" * 80)
