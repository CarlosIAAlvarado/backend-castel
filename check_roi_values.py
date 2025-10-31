"""
Script para verificar los valores de ROI en la base de datos
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import date

async def check_roi_values():
    # Conectar a MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["trading_simulation"]

    # Verificar Top16 para la fecha 2025-10-05
    target_date = "2025-10-05"
    window_days = 3

    top16_col = db[f"top16_{window_days}d"]

    print(f"\n{'='*80}")
    print(f"VERIFICANDO ROI EN TOP16 PARA FECHA: {target_date}")
    print(f"{'='*80}\n")

    # Obtener todos los agentes del Top16 para esa fecha
    agents = await top16_col.find({
        "date": target_date,
        "is_in_casterly": True
    }).sort("rank", 1).limit(16).to_list(length=16)

    if not agents:
        print(f"❌ No se encontraron agentes en top16_{window_days}d para la fecha {target_date}")
        return

    print(f"✅ Encontrados {len(agents)} agentes en el Top16\n")

    roi_field = f"roi_{window_days}d"

    print(f"{'Rank':<6} {'Agent ID':<20} {roi_field:<15} {'ROI %':<10}")
    print("-" * 60)

    for agent in agents:
        agent_id = agent.get("agent_id", "N/A")
        rank = agent.get("rank", "N/A")
        roi_decimal = agent.get(roi_field, None)

        if roi_decimal is not None:
            roi_percent = roi_decimal * 100
            print(f"{rank:<6} {agent_id:<20} {roi_decimal:<15.6f} {roi_percent:<10.2f}%")
        else:
            print(f"{rank:<6} {agent_id:<20} {'CAMPO NO EXISTE':<15} {'N/A':<10}")

    print("\n" + "="*80)
    print("VERIFICANDO CUENTA CL0001")
    print("="*80 + "\n")

    cuentas_col = db["cuentas_clientes_trading"]
    cuenta = await cuentas_col.find_one({"cuenta_id": "CL0001"})

    if cuenta:
        print(f"Cuenta ID: {cuenta.get('cuenta_id')}")
        print(f"Agente Actual: {cuenta.get('agente_actual')}")
        print(f"ROI Agente al Asignar: {cuenta.get('roi_agente_al_asignar')}%")
        print(f"ROI Total: {cuenta.get('roi_total')}%")
        print(f"Balance Actual: ${cuenta.get('balance_actual')}")
        print(f"Fecha Asignación: {cuenta.get('fecha_asignacion_agente')}")
    else:
        print("❌ No se encontró la cuenta CL0001")

    client.close()

if __name__ == "__main__":
    asyncio.run(check_roi_values())
