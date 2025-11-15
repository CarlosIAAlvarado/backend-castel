from app.config.database import database_manager
from datetime import datetime
import sys
import io

# Force UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database
database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("VERIFICACIÓN DE RANGOS DE DATOS PARA SIMULACIÓN")
print("=" * 80)

# 1. Verificar movements (mov07.10)
print("\n1. MOVEMENTS (mov07.10)")
print("-" * 80)
movements_col = db['mov07.10']

# Obtener primer y último movimiento
first_mov = movements_col.find_one(sort=[("createdAt", 1)])
last_mov = movements_col.find_one(sort=[("createdAt", -1)])

if first_mov and last_mov:
    first_date = first_mov['createdAt'][:10]
    last_date = last_mov['createdAt'][:10]
    total_count = movements_col.count_documents({})

    print(f"Primera fecha con movements: {first_date}")
    print(f"Última fecha con movements: {last_date}")
    print(f"Total de movements: {total_count}")

    # Contar por fecha
    from collections import defaultdict
    dates_count = defaultdict(int)

    for doc in movements_col.find({}, {"createdAt": 1}).limit(10000):
        date_str = doc['createdAt'][:10]
        dates_count[date_str] += 1

    print(f"\nPrimeras 10 fechas con movements:")
    for date_str in sorted(dates_count.keys())[:10]:
        print(f"  {date_str}: {dates_count[date_str]} movements")
else:
    print("⚠️  No hay movements en la colección")

# 2. Verificar balances
print("\n2. BALANCES")
print("-" * 80)
balances_col = db['balances']

# Obtener primer y último balance
first_balance = balances_col.find_one(sort=[("createdAt", 1)])
last_balance = balances_col.find_one(sort=[("createdAt", -1)])

if first_balance and last_balance:
    first_date_b = first_balance['createdAt'][:10] if isinstance(first_balance['createdAt'], str) else str(first_balance['createdAt'])[:10]
    last_date_b = last_balance['createdAt'][:10] if isinstance(last_balance['createdAt'], str) else str(last_balance['createdAt'])[:10]
    total_count_b = balances_col.count_documents({})

    print(f"Primera fecha con balances: {first_date_b}")
    print(f"Última fecha con balances: {last_date_b}")
    print(f"Total de balances: {total_count_b}")

# 3. Recomendación de fechas para simulación
print("\n" + "=" * 80)
print("RECOMENDACIÓN PARA SIMULACIÓN")
print("=" * 80)

if first_mov and last_mov:
    # Para tener 7 días de histórico, empezar 7 días después del primer movimiento
    from datetime import datetime, timedelta

    first_mov_date = datetime.fromisoformat(first_date)
    recommended_start = first_mov_date + timedelta(days=7)
    last_mov_date = datetime.fromisoformat(last_date)

    print(f"\n✅ CONFIGURACIÓN RECOMENDADA:")
    print(f"\nPara window_days=7 (ROI de 7 días):")
    print(f"  start_date: {recommended_start.strftime('%Y-%m-%d')}")
    print(f"  end_date: {last_date}")
    print(f"  window_days: 7")

    print(f"\nPara window_days=3 (ROI de 3 días):")
    recommended_start_3d = first_mov_date + timedelta(days=3)
    print(f"  start_date: {recommended_start_3d.strftime('%Y-%m-%d')}")
    print(f"  end_date: {last_date}")
    print(f"  window_days: 3")

    # Calcular días totales
    days_available_7d = (last_mov_date - recommended_start).days + 1
    days_available_3d = (last_mov_date - recommended_start_3d).days + 1

    print(f"\nDías de simulación disponibles:")
    print(f"  Con window_days=7: {days_available_7d} días")
    print(f"  Con window_days=3: {days_available_3d} días")

    print(f"\n📝 COMANDO CURL PARA EJECUTAR:")
    print(f"""
curl -X POST http://localhost:8000/api/simulation/run \\
  -H "Content-Type: application/json" \\
  -d '{{
    "start_date": "{recommended_start_3d.strftime('%Y-%m-%d')}",
    "end_date": "{last_date}",
    "window_days": 3,
    "update_client_accounts": true
  }}'
""")

print("\n" + "=" * 80)
