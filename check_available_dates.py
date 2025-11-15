from app.config.database import database_manager
from datetime import datetime
from collections import defaultdict
import sys
import io

# Force UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database first
database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("VERIFICACIÓN DE FECHAS DISPONIBLES EN LA BASE DE DATOS")
print("=" * 80)

# 1. Verificar fechas en balances
print("\n1. BALANCES (balances collection)")
print("-" * 80)
balances_col = db['balances']
dates_balances = list(balances_col.distinct('date'))
dates_balances.sort()

if dates_balances:
    print(f"Total de fechas únicas: {len(dates_balances)}")
    print(f"Primera fecha: {dates_balances[0]}")
    print(f"Última fecha: {dates_balances[-1]}")
    print(f"\nTodas las fechas disponibles:")

    # Count agents per date
    for date_str in dates_balances:
        count = balances_col.count_documents({'date': date_str})
        agents = balances_col.distinct('userId', {'date': date_str})
        print(f"  {date_str}: {count} registros, {len(agents)} agentes únicos")
else:
    print("⚠️  NO HAY FECHAS EN LA COLECCIÓN BALANCES")

# 2. Verificar fechas en movements
print("\n2. MOVEMENTS (movements collection)")
print("-" * 80)
movements_col = db['movements']
dates_movements = list(movements_col.distinct('date'))
dates_movements.sort()

if dates_movements:
    print(f"Total de fechas únicas: {len(dates_movements)}")
    print(f"Primera fecha: {dates_movements[0]}")
    print(f"Última fecha: {dates_movements[-1]}")
    print(f"\nPrimeras 10 fechas:")
    for date_str in dates_movements[:10]:
        count = movements_col.count_documents({'date': date_str})
        print(f"  {date_str}: {count} movimientos")
    if len(dates_movements) > 10:
        print(f"  ... ({len(dates_movements) - 10} fechas más)")
else:
    print("⚠️  NO HAY FECHAS EN LA COLECCIÓN MOVEMENTS")

# 3. Verificar system_config
print("\n3. SYSTEM CONFIG (last_simulation)")
print("-" * 80)
config_col = db['system_config']
config = config_col.find_one({'config_key': 'last_simulation'})

if config:
    print(f"Start Date: {config.get('start_date', 'NO DEFINIDO')}")
    print(f"End Date: {config.get('end_date', 'NO DEFINIDO')}")
    print(f"Current Date: {config.get('current_date', 'NO DEFINIDO')}")
    print(f"Status: {config.get('status', 'NO DEFINIDO')}")
    if 'created_at' in config:
        print(f"Creado: {config['created_at']}")
else:
    print("⚠️  NO HAY CONFIGURACIÓN DE ÚLTIMA SIMULACIÓN")

# 4. Verificar fechas en daily_roi_calculation
print("\n4. DAILY ROI CALCULATION (daily_roi_calculation collection)")
print("-" * 80)
daily_roi_col = db['daily_roi_calculation']
dates_roi = list(daily_roi_col.distinct('target_date'))
dates_roi.sort()

if dates_roi:
    print(f"Total de fechas únicas: {len(dates_roi)}")
    print(f"Primera fecha: {dates_roi[0]}")
    print(f"Última fecha: {dates_roi[-1]}")
    print(f"\nFechas con ROI calculado:")
    for date_str in dates_roi:
        count = daily_roi_col.count_documents({'target_date': date_str})
        print(f"  {date_str}: {count} agentes con ROI")
else:
    print("⚠️  NO HAY FECHAS EN LA COLECCIÓN DAILY_ROI_CALCULATION")

# 5. Verificar fechas en top16_7d
print("\n5. TOP16 (top16_7d collection)")
print("-" * 80)
top16_col = db['top16_7d']
dates_top16 = list(top16_col.distinct('date'))
dates_top16.sort()

if dates_top16:
    print(f"Total de fechas únicas: {len(dates_top16)}")
    print(f"Primera fecha: {dates_top16[0]}")
    print(f"Última fecha: {dates_top16[-1]}")
    print(f"\nFechas con Top16 guardado:")
    for date_str in dates_top16:
        count = top16_col.count_documents({'date': date_str})
        print(f"  {date_str}: {count} agentes en Top16")
else:
    print("⚠️  NO HAY FECHAS EN LA COLECCIÓN TOP16_7D")

# 6. Resumen y recomendaciones
print("\n" + "=" * 80)
print("RESUMEN Y RECOMENDACIONES")
print("=" * 80)

if dates_balances:
    print(f"\n✅ FECHAS VÁLIDAS PARA SIMULACIÓN:")
    print(f"   Puedes ejecutar simulaciones desde {dates_balances[0]} hasta {dates_balances[-1]}")
    print(f"\n💡 RECOMENDACIÓN:")
    print(f"   Ejecuta la simulación con start_date={dates_balances[0]}")
else:
    print("\n❌ NO HAY DATOS DE BALANCES")
    print("   Necesitas importar/cargar datos primero antes de ejecutar simulaciones")

print("\n" + "=" * 80)
