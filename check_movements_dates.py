from app.config.database import database_manager
import sys
import io
from datetime import datetime
from collections import defaultdict

# Force UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database first
database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("FECHAS EN MOVEMENTS (colección mov07.10)")
print("=" * 80)

movements_col = db['mov07.10']

print("\nAnalizando documentos de movements...")

# Obtener un documento de ejemplo primero
sample = movements_col.find_one()
print("\nEjemplo de documento:")
if sample:
    for key, value in sample.items():
        print(f"  {key}: {value}")

dates_data = defaultdict(lambda: {"count": 0, "agents": set()})

# Procesar todos los documentos - buscar campos de fecha
for doc in movements_col.find({}, {"date": 1, "userId": 1, "createdAt": 1, "timestamp": 1}).limit(1000):
    user_id = doc.get("userId")

    # Intentar diferentes campos de fecha
    date_value = doc.get("date") or doc.get("createdAt") or doc.get("timestamp")

    if date_value:
        # Convertir a datetime si es necesario
        if isinstance(date_value, str):
            try:
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except:
                continue
        elif isinstance(date_value, datetime):
            dt = date_value
        else:
            continue

        date_str = dt.strftime("%Y-%m-%d")
        dates_data[date_str]["count"] += 1
        if user_id:
            dates_data[date_str]["agents"].add(user_id)

# Convertir a lista y ordenar
results = [
    {"_id": date_str, "count": data["count"], "agents": list(data["agents"])}
    for date_str, data in dates_data.items()
]
results.sort(key=lambda x: x["_id"])

print(f"\n\nTotal de fechas únicas encontradas: {len(results)}\n")

if results:
    print("Fechas con movements:")
    for result in results[:20]:  # Solo mostrar primeras 20
        date_str = result["_id"]
        count = result["count"]
        num_agents = len(result["agents"])
        print(f"  {date_str}: {count} movements (primeros 1000), {num_agents} agentes únicos")

    if len(results) > 20:
        print(f"  ... y {len(results) - 20} fechas más")

    print(f"\n  Primera fecha: {results[0]['_id']}")
    print(f"  Última fecha: {results[-1]['_id']}")
else:
    print("\n⚠️  No se encontraron fechas en movements")
    print("\n❌ PROBLEMA: Sin datos de movements, no se puede calcular ROI")
    print("   El ROI se calcula usando closedPnl de los movements")

print("\n" + "=" * 80)
