"""
Script para verificar fechas disponibles en la coleccion de balances
"""

from app.config.database import database_manager
from datetime import datetime

database_manager.connect()
db = database_manager.get_database()

print("=" * 80)
print("VERIFICACION DE FECHAS EN BALANCES")
print("=" * 80)

# Obtener una muestra de documentos
sample = list(db.balances.find().limit(5))

if sample:
    print(f"\n[OK] Encontrados {db.balances.count_documents({})} documentos de balances")
    print("\nEjemplos de documentos:")
    for i, doc in enumerate(sample, 1):
        print(f"\n  Documento {i}:")
        print(f"    userId: {doc.get('userId')}")
        print(f"    date: {doc.get('date')}")
        print(f"    balance: {doc.get('balance')}")
        print(f"    tipo de date: {type(doc.get('date'))}")
else:
    print("[ERROR] No se encontraron documentos de balances")

print("\n" + "=" * 80)
