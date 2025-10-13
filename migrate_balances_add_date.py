"""
Script de migración: Agregar campo 'date' a balances desde 'createdAt'
También agregar campo 'account_id' desde 'userId'
"""

from app.config.database import database_manager
from datetime import datetime

def migrate_balances():
    """Migra balances agregando campos date y account_id"""

    database_manager.connect()
    db = database_manager.get_database()

    print("=" * 80)
    print("MIGRACIÓN DE BALANCES: Agregar campos date y account_id")
    print("=" * 80)

    collection = db.balances

    # Obtener todos los balances
    balances = list(collection.find({}))
    total = len(balances)

    print(f"\n1. Total de balances a procesar: {total}")

    updated = 0
    errors = 0

    for balance in balances:
        try:
            # Extraer fecha del createdAt
            created_at_str = balance.get("createdAt")
            if not created_at_str:
                print(f"⚠️  Balance {balance['_id']} sin createdAt, usando updatedAt")
                created_at_str = balance.get("updatedAt")

            if not created_at_str:
                print(f"❌ Balance {balance['_id']} sin fechas, omitiendo")
                errors += 1
                continue

            # Parsear fecha ISO
            dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            date_str = dt.date().isoformat()

            # Convertir userId a account_id con formato futures-XXX
            user_id = balance.get("userId", "")

            # Mapeo de formato OKX_XXX a futures-XXX
            # OKX_JH1 -> futures-JH1
            # OKX_JRI1 -> futures-JRI1
            if user_id.startswith("OKX_"):
                account_id = f"futures-{user_id[4:]}"  # Remove "OKX_" prefix
            else:
                account_id = user_id

            # Actualizar documento
            collection.update_one(
                {"_id": balance["_id"]},
                {
                    "$set": {
                        "date": date_str,
                        "account_id": account_id
                    }
                }
            )

            updated += 1

            if updated % 1000 == 0:
                print(f"   Procesados: {updated}/{total}")

        except Exception as e:
            print(f"❌ Error procesando balance {balance.get('_id')}: {e}")
            errors += 1

    print(f"\n2. Resumen:")
    print(f"   - Total procesados: {total}")
    print(f"   - Actualizados: {updated}")
    print(f"   - Errores: {errors}")

    # Verificación
    print(f"\n3. Verificación:")
    with_date = collection.count_documents({"date": {"$exists": True}})
    with_account_id = collection.count_documents({"account_id": {"$exists": True}})

    print(f"   - Balances con campo 'date': {with_date}")
    print(f"   - Balances con campo 'account_id': {with_account_id}")

    # Mostrar fechas únicas
    dates = sorted(collection.distinct("date"))
    print(f"\n4. Fechas disponibles: {len(dates)}")
    if dates:
        print(f"   - Primera fecha: {dates[0]}")
        print(f"   - Última fecha: {dates[-1]}")

        # Contar balances por fecha (primeras 5 fechas)
        print(f"\n5. Balances por fecha (primeras 5):")
        for date_val in dates[:5]:
            count = collection.count_documents({"date": date_val})
            print(f"   - {date_val}: {count} balances")

    database_manager.disconnect()

    print("\n" + "=" * 80)
    print("MIGRACIÓN COMPLETADA")
    print("=" * 80)

if __name__ == "__main__":
    migrate_balances()
