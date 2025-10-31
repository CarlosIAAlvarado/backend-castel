"""
Script para actualizar fechas en top16_by_day a la fecha actual
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('DATABASE_NAME')]

print("[ACTUALIZACION] Actualizando fechas en top16_by_day")
print("=" * 60)
print()

# Obtener fecha actual en formato YYYY-MM-DD
fecha_actual = datetime.now(timezone.utc).date().isoformat()

print(f"[INFO] Fecha actual: {fecha_actual}")
print()

# Verificar fechas actuales
fechas_antes = list(db.top16_by_day.distinct("date"))
print(f"[INFO] Fechas antes de actualizar: {fechas_antes}")
print()

# Actualizar todas las fechas a la fecha actual
result = db.top16_by_day.update_many(
    {},  # Todos los documentos
    {"$set": {"date": fecha_actual}}
)

print(f"[OK] Documentos actualizados: {result.modified_count}")
print()

# Verificar fechas después
fechas_despues = list(db.top16_by_day.distinct("date"))
print(f"[INFO] Fechas despues de actualizar: {fechas_despues}")
print()

# Mostrar algunos agentes actualizados
print("[INFO] Agentes actualizados (muestra):")
agentes = list(db.top16_by_day.find().limit(5))
for ag in agentes:
    print(f"  - {ag['agent_id']}: ROI={ag['roi_7d']:.4f}, Date={ag['date']}")

print()
print("[FIN ACTUALIZACION]")
