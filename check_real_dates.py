from app.config.database import database_manager
import sys
import io
from datetime import datetime

# Force UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database first
database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("FECHAS REALES CON DATOS EN 'balances' (usando createdAt)")
print("=" * 80)

balances_col = db['balances']

# Obtener muestra de documentos y extraer fechas manualmente
# (evitamos agregación porque createdAt puede ser string o fecha)
print("Analizando documentos...")

from collections import defaultdict
from datetime import datetime

dates_data = defaultdict(lambda: {"count": 0, "agents": set()})

# Procesar todos los documentos
for doc in balances_col.find({}, {"createdAt": 1, "userId": 1}):
    created_at = doc.get("createdAt")
    user_id = doc.get("userId")

    if created_at:
        # Convertir a datetime si es necesario
        if isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                continue
        elif isinstance(created_at, datetime):
            dt = created_at
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

print(f"\nTotal de fechas únicas encontradas: {len(results)}\n")

if results:
    print("Fechas con datos:")
    for result in results:
        date_str = result["_id"]
        count = result["count"]
        num_agents = len(result["agents"])
        print(f"  {date_str}: {count} registros, {num_agents} agentes únicos")

    print(f"\n{'='*80}")
    print("RECOMENDACIÓN")
    print("=" * 80)
    first_date = results[0]["_id"]
    last_date = results[-1]["_id"]
    print(f"\n✅ Ejecuta la simulación con fechas entre {first_date} y {last_date}")
    print(f"\nEjemplo de comando:")
    print(f"  POST /api/simulation/run")
    print(f"  {{\n    \"start_date\": \"{first_date}\",\n    \"end_date\": \"{last_date}\"\n  }}")
else:
    print("\n⚠️  No se encontraron fechas en createdAt")

print("\n" + "=" * 80)
