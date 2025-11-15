from app.config.database import database_manager
from datetime import date, timedelta
import asyncio

# Connect to database first
database_manager.connect()
db = database_manager.get_database()
target = date(2025, 9, 25)
window_start = target - timedelta(days=7)

balances_col = db['balances']

count_window = balances_col.count_documents({
    'date': {'$gte': window_start.isoformat(), '$lte': target.isoformat()}
})
count_target = balances_col.count_documents({'date': target.isoformat()})

agents = list(balances_col.distinct('userId', {'date': target.isoformat()}))

print(f'Balances en ventana {window_start} -> {target}: {count_window}')
print(f'Balances en fecha {target}: {count_target}')
print(f'Agentes únicos en {target}: {len(agents)}')
print(f'Primeros 5: {agents[:5] if len(agents) >= 5 else agents}')

# Check system_config for start_date
config_col = db['system_config']
config = config_col.find_one({'config_key': 'last_simulation'})
if config:
    print(f"\nsystem_config.start_date: {config.get('start_date', 'NO ENCONTRADO')}")
    print(f"system_config.end_date: {config.get('end_date', 'NO ENCONTRADO')}")
