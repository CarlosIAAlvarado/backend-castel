from app.config.database import database_manager
from datetime import date, datetime, time
import pytz
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("DEBUG: VERIFICAR QUERY DE BALANCES")
print("=" * 80)

# Parametros de prueba
start_date = date(2025, 5, 26)
end_date = date(2025, 6, 2)

print(f"\nBuscando balances desde {start_date} hasta {end_date}")

# Simular la query que hace balance_repo.get_all_by_date_range
tz = pytz.timezone("America/Bogota")
start_dt = tz.localize(datetime.combine(start_date, time.min))
end_dt = tz.localize(datetime.combine(end_date, time.max))

print(f"\nQuery con timezone:")
print(f"  start_dt: {start_dt}")
print(f"  start_dt.isoformat(): {start_dt.isoformat()}")
print(f"  end_dt: {end_dt}")
print(f"  end_dt.isoformat(): {end_dt.isoformat()}")

# Query 1: Como lo hace el código actual
balances_col = db['balances']
query1 = {
    "createdAt": {
        "$gte": start_dt.isoformat(),
        "$lte": end_dt.isoformat()
    }
}
count1 = balances_col.count_documents(query1)
print(f"\nQuery 1 (con timezone ISO): {count1} documentos")

# Query 2: Sin isoformat (datetime directo)
query2 = {
    "createdAt": {
        "$gte": start_dt,
        "$lte": end_dt
    }
}
count2 = balances_col.count_documents(query2)
print(f"Query 2 (datetime directo): {count2} documentos")

# Query 3: Solo el string de fecha (YYYY-MM-DD)
query3 = {
    "createdAt": {
        "$gte": start_date.isoformat(),
        "$lte": end_date.isoformat()
    }
}
count3 = balances_col.count_documents(query3)
print(f"Query 3 (string YYYY-MM-DD): {count3} documentos")

# Query 4: Regex para buscar cualquier cosa en ese rango de fechas
query4 = {
    "createdAt": {
        "$regex": "^2025-0[56]"
    }
}
count4 = balances_col.count_documents(query4)
print(f"Query 4 (regex 2025-05 o 2025-06): {count4} documentos")

# Ver ejemplos de createdAt reales
print(f"\nEjemplos de createdAt en la BD:")
samples = balances_col.find({}, {"createdAt": 1, "userId": 1, "_id": 0}).limit(5)
for i, doc in enumerate(samples, 1):
    created = doc.get("createdAt")
    print(f"  {i}. userId={doc.get('userId')}, createdAt={created}, tipo={type(created).__name__}")

print("\n" + "=" * 80)
