"""
Script para migrar datos de mov07.10 a movements con el formato correcto.

Convierte:
- user -> account_id
- closedPnl (con coma) -> closed_pnl (con punto)
- createdTime -> date (YYYY-MM-DD)
- Agrega agent_id mapeando desde assignments
"""

from pymongo import MongoClient
from app.config.settings import settings
from datetime import datetime
import sys

def migrate_movements():
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.database_name]

    print("=" * 80)
    print("MIGRACION DE MOVIMIENTOS: mov07.10 -> movements")
    print("=" * 80)

    # 1. Limpiar colección movements
    result = db.movements.delete_many({})
    print(f"\n1. Limpieza: {result.deleted_count:,} documentos eliminados de movements")

    # 2. Obtener todos los documentos de mov07.10
    source_docs = list(db["mov07.10"].find())
    print(f"\n2. Origen: {len(source_docs):,} documentos en mov07.10")

    # 3. Crear mapeo de account_id -> agent_id desde assignments
    assignments = list(db.assignments.find({"is_active": True}))
    account_to_agent = {a["account_id"]: a["agent_id"] for a in assignments}
    print(f"\n3. Mapeo: {len(account_to_agent)} cuentas activas mapeadas")

    # 4. Transformar y migrar
    movements_to_insert = []
    skipped = 0
    errors = []

    for doc in source_docs:
        try:
            account_id = doc.get("user")
            if not account_id:
                skipped += 1
                continue

            # Normalizar account_id al formato futures-XXX
            # OKX_AN1 -> futures-AN1
            # FP1_OKX -> futures-FP1
            # futures-AN1 -> futures-AN1 (ya tiene el formato correcto)
            if not account_id.startswith("futures-"):
                # Remover prefijos OKX_ o sufijos _OKX
                clean_id = account_id.replace("OKX_", "").replace("_OKX", "")
                account_id_normalized = f"futures-{clean_id}"
            else:
                account_id_normalized = account_id

            # Mapear account -> agent
            agent_id = account_to_agent.get(account_id)
            if not agent_id:
                # Intentar con version normalizada
                agent_id = account_to_agent.get(account_id_normalized)

            # Si no hay mapeo en assignments, usar account_id normalizado como agent_id
            # (cada cuenta es su propio agente)
            if not agent_id:
                agent_id = account_id_normalized

            # Convertir closedPnl (coma a punto)
            closed_pnl_str = str(doc.get("closedPnl", "0"))
            closed_pnl = float(closed_pnl_str.replace(",", "."))

            # Extraer fecha de createdTime
            created_time = doc.get("createdTime")
            if isinstance(created_time, str):
                dt = datetime.strptime(created_time, "%Y-%m-%d %H:%M:%S")
            else:
                dt = created_time

            date_str = dt.date().isoformat()

            # Crear documento movements
            movement = {
                "account_id": account_id,
                "agent_id": agent_id,
                "date": date_str,
                "closed_pnl": closed_pnl,
                "symbol": doc.get("symbol"),
                "side": doc.get("side"),
                "qty": doc.get("qty"),
                "created_at": created_time,
                "updated_at": doc.get("updatedTime")
            }

            movements_to_insert.append(movement)

        except Exception as e:
            errors.append(f"Error en doc {doc.get('_id')}: {str(e)}")
            continue

    # 5. Insertar en batch
    if movements_to_insert:
        db.movements.insert_many(movements_to_insert)
        print(f"\n4. Inserción: {len(movements_to_insert):,} movimientos migrados")
    else:
        print(f"\n4. Inserción: 0 movimientos migrados")

    print(f"\n5. Resumen:")
    print(f"   - Documentos procesados: {len(source_docs):,}")
    print(f"   - Migrados exitosamente: {len(movements_to_insert):,}")
    print(f"   - Omitidos (sin mapeo): {skipped:,}")
    print(f"   - Errores: {len(errors)}")

    if errors and len(errors) <= 10:
        print(f"\n6. Errores:")
        for error in errors:
            print(f"   - {error}")

    # 6. Verificar resultado
    dates = sorted(db.movements.distinct("date"))
    if dates:
        print(f"\n7. Verificación:")
        print(f"   - Fechas disponibles: {len(dates)}")
        print(f"   - Rango: {dates[0]} a {dates[-1]}")
        print(f"   - Agentes únicos: {len(db.movements.distinct('agent_id'))}")

    print("\n" + "=" * 80)
    print("MIGRACIÓN COMPLETADA")
    print("=" * 80)

if __name__ == "__main__":
    try:
        migrate_movements()
    except Exception as e:
        print(f"\nERROR FATAL: {str(e)}")
        sys.exit(1)
