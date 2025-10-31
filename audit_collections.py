"""
Script de auditoria de colecciones MongoDB.

Verifica:
1. Que colecciones existen en la base de datos
2. Cuantos documentos tiene cada una
3. Tamano aproximado de cada coleccion
4. Ultima fecha de modificacion (si aplica)
"""

from app.config.database import database_manager
from datetime import datetime
import json

print("\n" + "="*80)
print("AUDITORIA DE COLECCIONES MONGODB")
print("="*80)

database_manager.connect()
db = database_manager.get_database()

print(f"\nBase de datos: {db.name}")
print(f"Fecha de auditoria: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

COLECCIONES_ESPERADAS = [
    "agent_roi_3d",
    "agent_roi_5d",
    "agent_roi_7d",
    "agent_roi_10d",
    "agent_roi_15d",
    "agent_roi_30d",
    "agent_states",
    "assignments",
    "balances",
    "client_accounts_snapshots",
    "cuentas_clientes_trading",
    "daily_roi_calculation",
    "distribucion_cuentas_snapshot",
    "historial_asignaciones_clientes",
    "mov07.10",
    "rank_changes",
]

collections_real = sorted(db.list_collection_names())

print(f"\n\nTotal de colecciones en la base de datos: {len(collections_real)}")
print("\n" + "-"*80)

collection_stats = []

for col_name in collections_real:
    col = db[col_name]

    count = col.count_documents({})

    stats = db.command("collstats", col_name)
    size_bytes = stats.get("size", 0)
    size_mb = size_bytes / (1024 * 1024)

    ultima_modificacion = None
    if count > 0:
        try:
            latest_doc = col.find_one(sort=[("updated_at", -1)])
            if latest_doc and "updated_at" in latest_doc:
                ultima_modificacion = latest_doc["updated_at"]
            elif latest_doc and "created_at" in latest_doc:
                ultima_modificacion = latest_doc["created_at"]
            elif latest_doc and "date" in latest_doc:
                ultima_modificacion = latest_doc["date"]
            elif latest_doc and "timestamp" in latest_doc:
                ultima_modificacion = latest_doc["timestamp"]
        except Exception:
            pass

    en_lista_esperada = col_name in COLECCIONES_ESPERADAS

    fecha_str = "N/A"
    if ultima_modificacion:
        if isinstance(ultima_modificacion, datetime):
            fecha_str = ultima_modificacion.strftime('%Y-%m-%d')
        elif isinstance(ultima_modificacion, str):
            try:
                fecha_str = datetime.fromisoformat(ultima_modificacion.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except Exception:
                fecha_str = ultima_modificacion[:10] if len(ultima_modificacion) >= 10 else ultima_modificacion

    collection_stats.append({
        "nombre": col_name,
        "documentos": count,
        "tamano_mb": round(size_mb, 2),
        "ultima_mod": fecha_str,
        "esperada": en_lista_esperada
    })

collection_stats.sort(key=lambda x: x["tamano_mb"], reverse=True)

print("\n{:<40} {:>12} {:>12} {:>15} {:>10}".format(
    "COLECCION", "DOCUMENTOS", "TAMANO (MB)", "ULTIMA MOD", "ESPERADA"
))
print("-"*95)

for stat in collection_stats:
    print("{:<40} {:>12,} {:>12.2f} {:>15} {:>10}".format(
        stat["nombre"],
        stat["documentos"],
        stat["tamano_mb"],
        stat["ultima_mod"],
        "SI" if stat["esperada"] else "NO"
    ))

tamano_total = sum(s["tamano_mb"] for s in collection_stats)
docs_total = sum(s["documentos"] for s in collection_stats)

print("-"*95)
print("{:<40} {:>12,} {:>12.2f}".format(
    "TOTAL",
    docs_total,
    tamano_total
))

print("\n\n" + "="*80)
print("ANALISIS DE COLECCIONES")
print("="*80)

esperadas_encontradas = [s for s in collection_stats if s["esperada"]]
no_esperadas = [s for s in collection_stats if not s["esperada"]]
vacias = [s for s in collection_stats if s["documentos"] == 0]
grandes = [s for s in collection_stats if s["tamano_mb"] > 10]

print(f"\nColecciones esperadas encontradas: {len(esperadas_encontradas)}/{len(COLECCIONES_ESPERADAS)}")
print(f"Colecciones NO esperadas encontradas: {len(no_esperadas)}")
print(f"Colecciones vacias: {len(vacias)}")
print(f"Colecciones grandes (> 10 MB): {len(grandes)}")

if no_esperadas:
    print("\n\nColecciones NO ESPERADAS (no estan en la lista):")
    for stat in no_esperadas:
        print(f"  - {stat['nombre']}: {stat['documentos']:,} docs, {stat['tamano_mb']:.2f} MB")

if vacias:
    print("\n\nColecciones VACIAS (candidatas para eliminacion):")
    for stat in vacias:
        print(f"  - {stat['nombre']}")

faltantes = set(COLECCIONES_ESPERADAS) - set(s["nombre"] for s in collection_stats)
if faltantes:
    print("\n\nColecciones FALTANTES (esperadas pero no encontradas):")
    for col_name in sorted(faltantes):
        print(f"  - {col_name}")

print("\n" + "="*80)
print("RECOMENDACIONES")
print("="*80)

print("\n1. ELIMINAR colecciones vacias:")
for stat in vacias:
    print(f"   db.{stat['nombre']}.drop()")

print("\n2. REVISAR colecciones no esperadas:")
for stat in no_esperadas:
    if stat["documentos"] == 0:
        print(f"   - {stat['nombre']}: VACIA, eliminar")
    else:
        print(f"   - {stat['nombre']}: {stat['documentos']:,} docs, REVISAR si se usa")

print("\n3. MONITOREAR colecciones grandes:")
for stat in grandes:
    print(f"   - {stat['nombre']}: {stat['tamano_mb']:.2f} MB")

print("\n\n" + "="*80)
print("FIN DE LA AUDITORIA")
print("="*80 + "\n")

database_manager.disconnect()
