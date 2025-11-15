from app.config.database import database_manager
from app.config.settings import settings
import sys
import io

# Force UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database first
database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("CONFIGURACIÓN DE BASE DE DATOS")
print("=" * 80)
print(f"MongoDB URI: {settings.mongodb_uri}")
print(f"Database Name: {settings.database_name}")
print()

print("=" * 80)
print("COLECCIONES DISPONIBLES")
print("=" * 80)
collections = db.list_collection_names()
print(f"Total de colecciones: {len(collections)}\n")

for col_name in sorted(collections):
    count = db[col_name].count_documents({})
    print(f"  {col_name}: {count} documentos")

print("\n" + "=" * 80)
print("VERIFICANDO COLECCIÓN 'balances'")
print("=" * 80)

if 'balances' in collections:
    balances_col = db['balances']

    # Obtener un documento de ejemplo
    sample = balances_col.find_one()
    if sample:
        print("\nEjemplo de documento:")
        print(f"  _id: {sample.get('_id')}")
        print(f"  date: {sample.get('date')}")
        print(f"  userId: {sample.get('userId')}")
        print(f"  balance: {sample.get('balance')}")

        # Obtener todas las fechas únicas
        dates = list(balances_col.distinct('date'))
        dates.sort()
        print(f"\nFechas únicas en balances: {len(dates)}")
        if dates:
            print(f"  Primera: {dates[0]}")
            print(f"  Última: {dates[-1]}")
            print(f"\n  Todas las fechas:")
            for date_str in dates:
                count = balances_col.count_documents({'date': date_str})
                agents_count = len(list(balances_col.distinct('userId', {'date': date_str})))
                print(f"    {date_str}: {count} registros, {agents_count} agentes")
    else:
        print("\n⚠️  La colección 'balances' está vacía")
else:
    print("\n⚠️  La colección 'balances' NO EXISTE")

print("\n" + "=" * 80)
