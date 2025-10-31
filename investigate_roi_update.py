"""
Script para investigar por que solo se actualizaron 124 cuentas
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('DATABASE_NAME')]

print("[INVESTIGACION] Por que solo se actualizaron 124 de 1000 cuentas")
print("=" * 60)
print()

# 1. Contar cuentas activas
total_activas = db.cuentas_clientes_trading.count_documents({"estado": "activo"})
print(f"[INFO] Total cuentas activas: {total_activas}")
print()

# 2. Verificar cuantas tienen historial
cuentas_con_historial = 0
cuentas_sin_historial = 0

for cuenta in db.cuentas_clientes_trading.find({"estado": "activo"}):
    cuenta_id = cuenta["cuenta_id"]
    historial_count = db.historial_asignaciones_clientes.count_documents({"cuenta_id": cuenta_id})

    if historial_count > 0:
        cuentas_con_historial += 1
    else:
        cuentas_sin_historial += 1

print(f"[INFO] Cuentas CON historial: {cuentas_con_historial}")
print(f"[INFO] Cuentas SIN historial: {cuentas_sin_historial}")
print()

# 3. Verificar agentes en cuentas vs agentes en top16
print("[INFO] Agentes en top16_by_day:")
agentes_top16 = set()
for doc in db.top16_by_day.find():
    agentes_top16.add(doc["agent_id"])

print(f"  Total agentes en top16: {len(agentes_top16)}")
print(f"  Agentes: {sorted(agentes_top16)}")
print()

print("[INFO] Agentes asignados a cuentas:")
agentes_en_cuentas = set()
for cuenta in db.cuentas_clientes_trading.find({"estado": "activo"}):
    agentes_en_cuentas.add(cuenta["agente_actual"])

print(f"  Total agentes en cuentas: {len(agentes_en_cuentas)}")
print(f"  Agentes: {sorted(agentes_en_cuentas)}")
print()

# Agentes en cuentas que NO estan en top16
agentes_faltantes = agentes_en_cuentas - agentes_top16
if agentes_faltantes:
    print(f"[ALERTA] Agentes en cuentas que NO estan en top16: {agentes_faltantes}")

    # Contar cuantas cuentas tienen estos agentes
    for agente in agentes_faltantes:
        count = db.cuentas_clientes_trading.count_documents({
            "estado": "activo",
            "agente_actual": agente
        })
        print(f"  - {agente}: {count} cuentas")
    print()

# 4. Verificar algunas cuentas que SI se actualizaron
print("[INFO] Cuentas que SI tienen ROI > 0:")
cuentas_con_roi = list(db.cuentas_clientes_trading.find({
    "estado": "activo",
    "roi_total": {"$ne": 0}
}).limit(3))

for cuenta in cuentas_con_roi:
    print(f"  - {cuenta['cuenta_id']}: ROI={cuenta['roi_total']:.4f}, Agente={cuenta['agente_actual']}")

print()

# 5. Verificar cuentas que NO se actualizaron
print("[INFO] Cuentas que NO tienen ROI (muestra):")
cuentas_sin_roi = list(db.cuentas_clientes_trading.find({
    "estado": "activo",
    "roi_total": 0
}).limit(5))

for cuenta in cuentas_sin_roi:
    agente = cuenta['agente_actual']
    historial = db.historial_asignaciones_clientes.find_one({"cuenta_id": cuenta["cuenta_id"]})
    en_top16 = agente in agentes_top16

    print(f"  - {cuenta['cuenta_id']}: Agente={agente}, En_top16={en_top16}, Tiene_historial={historial is not None}")

print()
print("[FIN INVESTIGACION]")
