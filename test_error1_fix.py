from app.config.database import database_manager
from datetime import date
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

database_manager.connect()
db = database_manager.get_database()

simulation_id = "70885e62-118f-4b60-beec-ad90b926202f"

print("=" * 80)
print("PRUEBA DE FIX PARA ERROR #1: DOCUMENTO DE SIMULACION VACIO")
print("=" * 80)

# Obtener el documento de simulacion
sim_doc = db.simulations.find_one({"simulation_id": simulation_id})
if not sim_doc:
    print("ERROR: No se encontro la simulacion")
    exit(1)

print(f"\nSimulacion: {sim_doc['name']}")
start_date = date.fromisoformat(sim_doc['config']['start_date'])
end_date = date.fromisoformat(sim_doc['config']['target_date'])
window_days = sim_doc['config'].get('days_simulated', 7)

print(f"Periodo: {start_date} a {end_date}")
print(f"Window days: {window_days}")

# PRUEBA 1: _get_top16_final
print("\n" + "=" * 80)
print("PRUEBA 1: _get_top16_final")
print("=" * 80)

from app.utils.collection_names import get_top16_collection_name
top16_collection_name = get_top16_collection_name(window_days)
print(f"\nBuscando en coleccion: {top16_collection_name}")

top16_docs = list(db[top16_collection_name].find({
    "date": end_date.isoformat()
}).sort("rank", 1))

print(f"Documentos encontrados: {len(top16_docs)}")

# Fallback a top16_7d
if not top16_docs and window_days != 7:
    print(f"\nNo se encontro en {top16_collection_name}, intentando con top16_7d...")
    top16_docs = list(db["top16_7d"].find({
        "date": end_date.isoformat()
    }).sort("rank", 1))
    print(f"Documentos encontrados en top16_7d: {len(top16_docs)}")

if top16_docs:
    print("\nPrimeros 3 agentes:")
    for doc in top16_docs[:3]:
        roi_field = f"roi_{window_days}d"
        roi_value = doc.get(roi_field, doc.get("roi_7d", 0.0))
        print(f"  Rank {doc.get('rank')}: {doc.get('agent_id')} - ROI: {roi_value}")

# PRUEBA 2: _get_rotations_summary
print("\n" + "=" * 80)
print("PRUEBA 2: _get_rotations_summary")
print("=" * 80)

print(f"\nBuscando rotaciones entre {start_date.isoformat()} y {end_date.isoformat()}")

# Query original (probablemente fallaba)
rotation_docs_old = list(db.rotation_log.find({
    "date": {
        "$gte": start_date.isoformat(),
        "$lte": end_date.isoformat()
    }
}))
print(f"Query original (sin timestamp): {len(rotation_docs_old)} rotaciones")

# Query nueva (con timestamp)
rotation_docs_new = list(db.rotation_log.find({
    "date": {
        "$gte": start_date.isoformat(),
        "$lte": (end_date.isoformat() + "T23:59:59")
    }
}))
print(f"Query nueva (con timestamp): {len(rotation_docs_new)} rotaciones")

if rotation_docs_new:
    print("\nRotaciones encontradas:")
    for rot in rotation_docs_new:
        print(f"  Fecha: {rot.get('date')}")
        print(f"    {rot.get('agent_out')} -> {rot.get('agent_in')}")
        print(f"    Razon: {rot.get('reason', 'N/A')}")

# RESUMEN
print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)

if len(top16_docs) == 16:
    print("EXITO: Se encontraron los 16 agentes del Top 16 final")
else:
    print(f"FALLO: Solo se encontraron {len(top16_docs)} agentes (esperado: 16)")

if len(rotation_docs_new) == 2:
    print("EXITO: Se encontraron las 2 rotaciones esperadas")
elif len(rotation_docs_new) > 0:
    print(f"PARCIAL: Se encontraron {len(rotation_docs_new)} rotaciones (esperado: 2)")
else:
    print("FALLO: No se encontraron rotaciones")

print("\n" + "=" * 80)
