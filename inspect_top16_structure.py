"""
Script para inspeccionar estructura real de top16_by_day
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
import json

load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('DATABASE_NAME')]

print("[INSPECCION] Estructura de top16_by_day")
print("=" * 60)
print()

# Obtener un documento de ejemplo
doc = db.top16_by_day.find_one()

if doc:
    print("[DOCUMENTO COMPLETO]")
    print(json.dumps(doc, indent=2, default=str))
    print()
    print("-" * 60)
    print()
    print("[CAMPOS DISPONIBLES]")
    for key in doc.keys():
        print(f"  - {key}: {type(doc[key]).__name__} = {doc[key]}")
    print()
else:
    print("[ERROR] No hay documentos en top16_by_day")
    print()

# Contar documentos por fecha
print("[FECHAS EN LA COLECCION]")
pipeline = [
    {"$group": {
        "_id": "$date",
        "count": {"$sum": 1}
    }},
    {"$sort": {"_id": -1}}
]

fechas = list(db.top16_by_day.aggregate(pipeline))
for f in fechas:
    print(f"  - Fecha: {f['_id']} ({f['count']} agentes)")

print()
print("[FIN INSPECCION]")
