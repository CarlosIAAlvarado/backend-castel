"""
Script para crear registros iniciales en historial_asignaciones_clientes
para todas las cuentas que no tienen historial
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('DATABASE_NAME')]

print("[CREACION] Creando historial inicial para cuentas sin historial")
print("=" * 60)
print()

# 1. Obtener ROI de agentes desde top16_by_day
agentes_roi = {}
for doc in db.top16_by_day.find():
    # Convertir roi_7d a porcentaje
    agentes_roi[doc["agent_id"]] = doc["roi_7d"] * 100

print(f"[INFO] Agentes con ROI en top16_by_day: {len(agentes_roi)}")
print()

# 2. Obtener cuentas activas sin historial
cuentas = list(db.cuentas_clientes_trading.find({"estado": "activo"}))
print(f"[INFO] Total cuentas activas: {len(cuentas)}")
print()

# 3. Crear historial para cada cuenta
historial_entries = []
cuentas_procesadas = 0
cuentas_saltadas = 0

for cuenta in cuentas:
    cuenta_id = cuenta["cuenta_id"]

    # Verificar si ya tiene historial
    historial_existente = db.historial_asignaciones_clientes.count_documents({
        "cuenta_id": cuenta_id
    })

    if historial_existente > 0:
        cuentas_saltadas += 1
        continue

    # Obtener agente actual
    agente_id = cuenta["agente_actual"]

    # Obtener ROI del agente (si existe en top16, sino 0.0)
    roi_agente_inicio = agentes_roi.get(agente_id, 0.0)

    # Crear registro de historial
    historial_entry = {
        "cuenta_id": cuenta_id,
        "nombre_cliente": cuenta["nombre_cliente"],
        "agente_id": agente_id,
        "simulation_id": "test_simulation_001",
        "fecha_inicio": cuenta.get("created_at", datetime.now(timezone.utc)),
        "fecha_fin": None,  # null = asignacion actual
        "roi_agente_inicio": roi_agente_inicio,
        "roi_agente_fin": None,
        "roi_cuenta_ganado": None,
        "balance_inicio": cuenta["balance_inicial"],
        "balance_fin": None,
        "motivo_cambio": "inicial",
        "dias_con_agente": None,
        "created_at": cuenta.get("created_at", datetime.now(timezone.utc))
    }

    historial_entries.append(historial_entry)
    cuentas_procesadas += 1

print(f"[INFO] Cuentas a procesar: {cuentas_procesadas}")
print(f"[INFO] Cuentas saltadas (ya tienen historial): {cuentas_saltadas}")
print()

# 4. Insertar todos los registros
if historial_entries:
    result = db.historial_asignaciones_clientes.insert_many(historial_entries)
    print(f"[OK] Insertados {len(result.inserted_ids)} registros en historial")
    print()

    # Mostrar algunos ejemplos
    print("[INFO] Ejemplos de historial creado:")
    for entry in historial_entries[:3]:
        print(f"  - Cuenta: {entry['cuenta_id']}")
        print(f"    Agente: {entry['agente_id']}")
        print(f"    ROI Inicio: {entry['roi_agente_inicio']:.4f}%")
        print(f"    Balance Inicio: ${entry['balance_inicio']:.2f}")
        print()
else:
    print("[INFO] No hay cuentas para procesar")

# 5. Verificar resultado final
total_con_historial = 0
total_sin_historial = 0

for cuenta in db.cuentas_clientes_trading.find({"estado": "activo"}):
    historial_count = db.historial_asignaciones_clientes.count_documents({
        "cuenta_id": cuenta["cuenta_id"]
    })
    if historial_count > 0:
        total_con_historial += 1
    else:
        total_sin_historial += 1

print("[RESULTADO FINAL]")
print(f"  - Cuentas CON historial: {total_con_historial}")
print(f"  - Cuentas SIN historial: {total_sin_historial}")
print()
print("[FIN CREACION]")
