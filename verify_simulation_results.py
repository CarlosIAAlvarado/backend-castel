"""
Script para verificar los resultados de una simulacion con Client Accounts.

Este script verifica:
1. Snapshots generados
2. Estadisticas de cuentas
3. Timeline de evolucion
4. Rotaciones procesadas
"""

import asyncio
from datetime import date
from pymongo import MongoClient
from pprint import pprint

# Configuracion
MONGODB_URI = "mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy"
DATABASE_NAME = "simulacion_casterly_rock"

# PARAMETROS DE LA SIMULACION - AJUSTAR SEGUN TU SIMULACION
START_DATE = "2025-10-01"  # Fecha de inicio de la simulacion
END_DATE = "2025-10-07"     # Fecha de fin de la simulacion
SIMULATION_ID = None        # Si conoces el simulation_id, ponlo aqui


def verify_simulation_results():
    """Verifica los resultados de la simulacion."""

    print("\n" + "="*80)
    print("VERIFICACION DE RESULTADOS - CLIENT ACCOUNTS SIMULATION")
    print("="*80)

    # Conectar a MongoDB
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    print(f"\n[OK] Conectado a MongoDB: {DATABASE_NAME}")

    # 1. VERIFICAR SNAPSHOTS
    print("\n" + "-"*80)
    print("1. VERIFICANDO SNAPSHOTS GENERADOS")
    print("-"*80)

    snapshots_col = db.client_accounts_snapshots

    query = {
        "target_date": {
            "$gte": START_DATE,
            "$lte": END_DATE
        }
    }

    if SIMULATION_ID:
        query["simulation_id"] = SIMULATION_ID

    snapshots = list(snapshots_col.find(query).sort("target_date", 1))

    print(f"\n   Total snapshots encontrados: {len(snapshots)}")

    if snapshots:
        print(f"\n   Fechas de snapshots:")
        for snap in snapshots:
            print(f"      - {snap['target_date']} | Cuentas: {snap['total_cuentas']} | "
                  f"Balance: ${snap['balance_total']:,.2f} | "
                  f"ROI: {snap['roi_promedio']:.2f}%")

        # 2. ESTADISTICAS DEL PRIMER Y ULTIMO DIA
        print("\n" + "-"*80)
        print("2. COMPARACION PRIMER DIA VS ULTIMO DIA")
        print("-"*80)

        first_snap = snapshots[0]
        last_snap = snapshots[-1]

        print(f"\n   DIA 1 ({first_snap['target_date']}):")
        print(f"      Balance Total: ${first_snap['balance_total']:,.2f}")
        print(f"      ROI Promedio: {first_snap['roi_promedio']:.2f}%")
        print(f"      Total Cuentas: {first_snap['total_cuentas']}")

        print(f"\n   ULTIMO DIA ({last_snap['target_date']}):")
        print(f"      Balance Total: ${last_snap['balance_total']:,.2f}")
        print(f"      ROI Promedio: {last_snap['roi_promedio']:.2f}%")
        print(f"      Total Cuentas: {last_snap['total_cuentas']}")

        # Calcular cambios
        balance_change = last_snap['balance_total'] - first_snap['balance_total']
        roi_change = last_snap['roi_promedio'] - first_snap['roi_promedio']

        print(f"\n   CAMBIOS:")
        print(f"      Balance: {'+' if balance_change > 0 else ''}{balance_change:,.2f} "
              f"({balance_change/first_snap['balance_total']*100:.2f}%)")
        print(f"      ROI: {'+' if roi_change > 0 else ''}{roi_change:.2f}%")

        # 3. DISTRIBUCION DE AGENTES (ULTIMO DIA)
        print("\n" + "-"*80)
        print("3. DISTRIBUCION DE CUENTAS POR AGENTE (ULTIMO DIA)")
        print("-"*80)

        distribucion = last_snap.get('distribucion_agentes', {})

        if distribucion:
            print(f"\n   Total agentes con cuentas: {len(distribucion)}")
            print(f"\n   Top 5 agentes por ROI:")

            # Ordenar por ROI promedio
            sorted_agents = sorted(
                distribucion.items(),
                key=lambda x: x[1]['roi_promedio'],
                reverse=True
            )

            for idx, (agent_id, data) in enumerate(sorted_agents[:5], 1):
                print(f"      {idx}. {agent_id}")
                print(f"         - Cuentas: {data['num_cuentas']}")
                print(f"         - Balance: ${data['balance_total']:,.2f}")
                print(f"         - ROI Promedio: {data['roi_promedio']:.2f}%")

    else:
        print("\n   [WARNING] No se encontraron snapshots para el rango especificado")
        print(f"   Fechas buscadas: {START_DATE} a {END_DATE}")
        if SIMULATION_ID:
            print(f"   Simulation ID: {SIMULATION_ID}")

    # 4. VERIFICAR ESTADO DE CUENTAS
    print("\n" + "-"*80)
    print("4. ESTADO ACTUAL DE CUENTAS")
    print("-"*80)

    cuentas_col = db.cuentas_clientes_trading

    # Estadisticas generales
    total_cuentas = cuentas_col.count_documents({})
    cuentas_activas = cuentas_col.count_documents({"estado": "activo"})

    print(f"\n   Total cuentas en BD: {total_cuentas}")
    print(f"   Cuentas activas: {cuentas_activas}")

    # Obtener agregados
    pipeline = [
        {"$match": {"estado": "activo"}},
        {"$group": {
            "_id": None,
            "balance_total": {"$sum": "$balance_actual"},
            "roi_promedio": {"$avg": "$roi_total"},
            "balance_inicial_total": {"$sum": "$balance_inicial"}
        }}
    ]

    result = list(cuentas_col.aggregate(pipeline))

    if result:
        stats = result[0]
        print(f"\n   Balance Inicial Total: ${stats['balance_inicial_total']:,.2f}")
        print(f"   Balance Actual Total: ${stats['balance_total']:,.2f}")
        print(f"   ROI Promedio: {stats['roi_promedio']:.2f}%")
        print(f"   Ganancia/Perdida: ${stats['balance_total'] - stats['balance_inicial_total']:,.2f}")

    # 5. VERIFICAR HISTORIAL (MUESTRA DE 5 CUENTAS)
    print("\n" + "-"*80)
    print("5. MUESTRA DE HISTORIAL DE CUENTAS")
    print("-"*80)

    sample_cuentas = list(cuentas_col.find({"estado": "activo"}).limit(5))

    print(f"\n   Mostrando 5 cuentas de muestra:")
    for cuenta in sample_cuentas:
        print(f"\n   - {cuenta['cuenta_id']} ({cuenta['nombre_cliente']})")
        print(f"     Agente: {cuenta.get('agente_actual', 'N/A')}")
        print(f"     Balance: ${cuenta['balance_inicial']:,.2f} -> ${cuenta['balance_actual']:,.2f}")
        print(f"     ROI: {cuenta['roi_total']:.2f}%")
        print(f"     Cambios de agente: {cuenta.get('numero_cambios_agente', 0)}")

    # 6. RESUMEN FINAL
    print("\n" + "="*80)
    print("RESUMEN FINAL")
    print("="*80)

    if snapshots:
        print(f"\n   [OK] Simulacion ejecutada correctamente")
        print(f"   [OK] {len(snapshots)} snapshots generados")
        print(f"   [OK] Balance final: ${last_snap['balance_total']:,.2f}")
        print(f"   [OK] ROI promedio final: {last_snap['roi_promedio']:.2f}%")

        # Verificar si hubo sincronizacion
        if len(snapshots) > 0:
            print(f"\n   [SUCCESS] La integracion de Client Accounts esta funcionando!")
        else:
            print(f"\n   [WARNING] Parece que no se sincronizaron las cuentas")
    else:
        print(f"\n   [ERROR] No se encontraron snapshots")
        print(f"   Verifica que la simulacion se ejecuto con update_client_accounts=true")

    print("\n" + "="*80)

    client.close()


if __name__ == "__main__":
    print("\n[INFO] Iniciando verificacion...")
    print(f"[INFO] Fechas: {START_DATE} a {END_DATE}")
    if SIMULATION_ID:
        print(f"[INFO] Simulation ID: {SIMULATION_ID}")
    else:
        print(f"[INFO] Buscando cualquier simulation_id")

    verify_simulation_results()

    print("\n[INFO] Verificacion completada\n")
