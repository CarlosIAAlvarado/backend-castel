"""
Script para probar la simulacion con Client Accounts habilitado.

Ejecuta una simulacion corta (7 dias) con sincronizacion de cuentas activa.
"""

import requests
import json
from datetime import datetime

# Configuracion
API_URL = "http://localhost:8000/api/simulation/run"

# Parametros de la simulacion
payload = {
    "target_date": "2025-10-07",
    "window_days": 7,
    "update_client_accounts": True,  # ACTIVAR SINCRONIZACION
    "simulation_id": "test_client_accounts_integration",
    "dry_run": False  # Guardar cambios reales
}

print("\n" + "="*80)
print("EJECUTANDO SIMULACION CON CLIENT ACCOUNTS")
print("="*80)
print(f"\nParametros:")
print(f"  target_date: {payload['target_date']}")
print(f"  window_days: {payload['window_days']}")
print(f"  update_client_accounts: {payload['update_client_accounts']}")
print(f"  simulation_id: {payload['simulation_id']}")
print(f"  dry_run: {payload['dry_run']}")
print("\n" + "-"*80)

try:
    print("\n[INFO] Enviando request a la API...")
    print(f"[INFO] URL: {API_URL}")

    start_time = datetime.now()

    response = requests.post(
        API_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=600  # 10 minutos timeout
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n[OK] Request completada en {duration:.2f} segundos")
    print(f"[OK] Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()

        print("\n" + "="*80)
        print("RESULTADO DE LA SIMULACION")
        print("="*80)

        # Informacion basica
        if "simulation_id" in result:
            print(f"\nSimulation ID: {result['simulation_id']}")

        if "config" in result:
            config = result["config"]
            print(f"\nConfiguracion:")
            print(f"  Periodo: {config.get('start_date')} a {config.get('end_date')}")
            print(f"  Window: {config.get('window_days')} dias")
            print(f"  Total dias procesados: {config.get('total_days')}")

        # KPIs
        if "kpis" in result:
            kpis = result["kpis"]
            print(f"\nKPIs:")
            print(f"  ROI Promedio: {kpis.get('avg_roi_top16', 0):.2f}%")
            print(f"  Total Rotaciones: {kpis.get('total_rotations', 0)}")

        # Buscar informacion de Client Accounts en daily_results
        if "daily_results" in result:
            daily_results = result["daily_results"]
            print(f"\n\nResultados Diarios: {len(daily_results)} dias procesados")

            # Buscar el ultimo dia con info de client accounts
            client_accounts_found = False
            for day in reversed(daily_results):
                if "client_accounts_sync" in day:
                    client_accounts_found = True
                    sync_info = day["client_accounts_sync"]

                    print(f"\n" + "-"*80)
                    print(f"CLIENT ACCOUNTS - ULTIMO DIA ({day.get('date')})")
                    print("-"*80)

                    if sync_info.get("success"):
                        print(f"  [OK] Sincronizacion exitosa")
                        print(f"  Cuentas actualizadas: {sync_info.get('cuentas_actualizadas', 0)}")
                        print(f"  Cuentas redistribuidas: {sync_info.get('cuentas_redistribuidas', 0)}")
                        print(f"  Rotaciones procesadas: {sync_info.get('rotaciones_procesadas', 0)}")
                        print(f"  Balance: ${sync_info.get('balance_total_antes', 0):,.2f} -> ${sync_info.get('balance_total_despues', 0):,.2f}")
                        print(f"  ROI: {sync_info.get('roi_promedio_antes', 0):.2f}% -> {sync_info.get('roi_promedio_despues', 0):.2f}%")

                        if sync_info.get('snapshot_id'):
                            print(f"  Snapshot ID: {sync_info['snapshot_id']}")
                    else:
                        print(f"  [ERROR] Sincronizacion fallo")
                        if "error" in sync_info:
                            print(f"  Error: {sync_info['error']}")

                    break

            if not client_accounts_found:
                print(f"\n[WARNING] No se encontro informacion de Client Accounts en los resultados")
                print(f"[WARNING] Verifica que update_client_accounts=true se haya aplicado correctamente")

        print("\n" + "="*80)
        print("[SUCCESS] SIMULACION COMPLETADA")
        print("="*80)

        # Guardar resultado completo en archivo
        with open("simulation_result_full.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n[INFO] Resultado completo guardado en: simulation_result_full.json")

    elif response.status_code == 400:
        error = response.json()
        print(f"\n[ERROR] Bad Request: {error.get('detail', 'Unknown error')}")

    elif response.status_code == 500:
        print(f"\n[ERROR] Internal Server Error")
        print(f"Response: {response.text[:500]}")

    else:
        print(f"\n[ERROR] Unexpected status code: {response.status_code}")
        print(f"Response: {response.text[:500]}")

except requests.exceptions.Timeout:
    print(f"\n[ERROR] Request timeout (> 10 minutos)")
    print(f"[INFO] La simulacion puede estar aun ejecutandose en el backend")

except requests.exceptions.ConnectionError:
    print(f"\n[ERROR] No se pudo conectar al servidor")
    print(f"[INFO] Verifica que el backend este corriendo en {API_URL}")

except Exception as e:
    print(f"\n[ERROR] Error inesperado: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("FIN DEL TEST")
print("="*80 + "\n")
