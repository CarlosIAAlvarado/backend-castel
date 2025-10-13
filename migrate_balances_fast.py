"""
Script de migración OPTIMIZADO: Agregar campo 'date' a balances desde 'createdAt'
Usa bulk operations para mayor velocidad
"""

from app.config.database import database_manager
from datetime import datetime
from pymongo import UpdateOne

def migrate_balances_fast():
    """Migra balances agregando campos date y account_id usando bulk operations"""

    database_manager.connect()
    db = database_manager.get_database()

    print("=" * 80)
    print("MIGRACIÓN RÁPIDA DE BALANCES: Agregar campos date y account_id")
    print("=" * 80)

    collection = db.balances

    # Obtener todos los balances
    balances = list(collection.find({}))
    total = len(balances)

    print(f"\n1. Total de balances a procesar: {total}")

    bulk_operations = []
    errors = 0

    for balance in balances:
        try:
            # Extraer fecha del createdAt
            created_at_str = balance.get("createdAt")
            if not created_at_str:
                created_at_str = balance.get("updatedAt")

            if not created_at_str:
                errors += 1
                continue

            # Parsear fecha ISO
            dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            date_str = dt.date().isoformat()

            # Convertir userId a account_id con formato futures-XXX
            user_id = balance.get("userId", "")

            # Mapeo de formato OKX_XXX a futures-XXX
            if user_id.startswith("OKX_"):
                account_id = f"futures-{user_id[4:]}"
            else:
                account_id = user_id

            # Agregar operación al bulk
            bulk_operations.append(
                UpdateOne(
                    {"_id": balance["_id"]},
                    {"$set": {"date": date_str, "account_id": account_id}}
                )
            )

        except Exception as e:
            print(f"❌ Error procesando balance {balance.get('_id')}: {e}")
            errors += 1

    # Ejecutar bulk update
    if bulk_operations:
        print(f"\n2. Ejecutando bulk update de {len(bulk_operations)} operaciones...")
        result = collection.bulk_write(bulk_operations, ordered=False)
        print(f"   ✅ Actualizados: {result.modified_count}")

    print(f"\n3. Resumen:")
    print(f"   - Total procesados: {total}")
    print(f"   - Actualizados: {len(bulk_operations)}")
    print(f"   - Errores: {errors}")

    # Verificación
    print(f"\n4. Verificación:")
    with_date = collection.count_documents({"date": {"$exists": True}})
    with_account_id = collection.count_documents({"account_id": {"$exists": True}})

    print(f"   - Balances con campo 'date': {with_date}")
    print(f"   - Balances con campo 'account_id': {with_account_id}")

    # Mostrar fechas únicas
    dates = sorted(collection.distinct("date"))
    print(f"\n5. Fechas disponibles: {len(dates)}")
    if dates:
        print(f"   - Primera fecha: {dates[0]}")
        print(f"   - Última fecha: {dates[-1]}")

        # Contar balances por fecha en el rango de simulación
        print(f"\n6. Balances por fecha (rango simulación 2025-09-01 a 2025-10-07):")
        sim_dates = [d for d in dates if "2025-09" in d or "2025-10" in d]
        for date_val in sim_dates[:10]:
            count = collection.count_documents({"date": date_val})
            print(f"   - {date_val}: {count} balances")

    database_manager.disconnect()

    print("\n" + "=" * 80)
    print("MIGRACIÓN COMPLETADA")
    print("=" * 80)

if __name__ == "__main__":
    migrate_balances_fast()
