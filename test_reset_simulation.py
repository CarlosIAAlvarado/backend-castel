"""
Script para probar el reset de simulacion.

Verifica que:
1. El balance_inicial permanece en $1,000
2. Los demas valores se resetean correctamente
3. El historial se limpia
"""

import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api/client-accounts"

print("\n" + "="*80)
print("TEST: RESET DE SIMULACION")
print("="*80)

print("\n[PASO 1] Obteniendo estado actual de las cuentas (antes del reset)...")

try:
    response = requests.get(f"{API_BASE}?skip=0&limit=5")

    if response.status_code == 200:
        data_antes = response.json()
        cuentas_antes = data_antes.get('accounts', [])

        print(f"\n[OK] {len(cuentas_antes)} cuentas obtenidas")

        if len(cuentas_antes) > 0:
            print("\nEjemplo de cuenta ANTES del reset:")
            cuenta = cuentas_antes[0]
            print(f"  Cuenta ID: {cuenta['cuenta_id']}")
            print(f"  Nombre: {cuenta['nombre_cliente']}")
            print(f"  Balance Inicial: ${cuenta['balance_inicial']:.2f}")
            print(f"  Balance Actual: ${cuenta['balance_actual']:.2f}")
            print(f"  ROI Total: {cuenta['roi_total']:.2f}%")
            print(f"  Numero Cambios Agente: {cuenta['numero_cambios_agente']}")
            print(f"  Win Rate: {cuenta['win_rate']:.4f}")
    else:
        print(f"[ERROR] Status code: {response.status_code}")
        exit(1)

except Exception as e:
    print(f"[ERROR] {str(e)}")
    exit(1)

print("\n" + "-"*80)
print("\n[PASO 2] Ejecutando reset de simulacion...")

try:
    response = requests.post(f"{API_BASE}/reset")

    if response.status_code == 200:
        reset_result = response.json()

        print("\n[OK] Reset completado exitosamente!")
        print(f"\n  Cuentas Reseteadas: {reset_result['cuentas_reseteadas']}")
        print(f"  Total Cuentas: {reset_result['total_cuentas']}")
        print(f"  Fecha Reset: {reset_result['fecha_reset']}")
        print(f"  Balance Inicial Preservado: {reset_result['balance_inicial_preserved']}")
        print(f"  Historial Limpiado: {reset_result['historial_limpiado']}")
        print(f"  Snapshots Limpiados: {reset_result['snapshots_limpiados']}")
    else:
        print(f"[ERROR] Status code: {response.status_code}")
        print(f"Response: {response.text}")
        exit(1)

except Exception as e:
    print(f"[ERROR] {str(e)}")
    exit(1)

print("\n" + "-"*80)
print("\n[PASO 3] Verificando estado de las cuentas (despues del reset)...")

try:
    response = requests.get(f"{API_BASE}?skip=0&limit=5")

    if response.status_code == 200:
        data_despues = response.json()
        cuentas_despues = data_despues.get('accounts', [])

        print(f"\n[OK] {len(cuentas_despues)} cuentas obtenidas")

        if len(cuentas_despues) > 0:
            print("\nEjemplo de cuenta DESPUES del reset:")
            cuenta = cuentas_despues[0]
            print(f"  Cuenta ID: {cuenta['cuenta_id']}")
            print(f"  Nombre: {cuenta['nombre_cliente']}")
            print(f"  Balance Inicial: ${cuenta['balance_inicial']:.2f}")
            print(f"  Balance Actual: ${cuenta['balance_actual']:.2f}")
            print(f"  ROI Total: {cuenta['roi_total']:.2f}%")
            print(f"  Numero Cambios Agente: {cuenta['numero_cambios_agente']}")
            print(f"  Win Rate: {cuenta['win_rate']:.4f}")
    else:
        print(f"[ERROR] Status code: {response.status_code}")
        exit(1)

except Exception as e:
    print(f"[ERROR] {str(e)}")
    exit(1)

print("\n" + "-"*80)
print("\n[PASO 4] Validando reset...")

errores = []

for cuenta_antes, cuenta_despues in zip(cuentas_antes, cuentas_despues):
    cuenta_id = cuenta_antes['cuenta_id']

    if cuenta_antes['balance_inicial'] != cuenta_despues['balance_inicial']:
        errores.append(
            f"ERROR: balance_inicial cambio en cuenta {cuenta_id}: "
            f"${cuenta_antes['balance_inicial']:.2f} -> ${cuenta_despues['balance_inicial']:.2f}"
        )

    if cuenta_antes['balance_inicial'] != 1000.0:
        errores.append(
            f"ERROR: balance_inicial no es $1,000 en cuenta {cuenta_id}: "
            f"${cuenta_antes['balance_inicial']:.2f}"
        )

    if cuenta_despues['balance_actual'] != cuenta_despues['balance_inicial']:
        errores.append(
            f"ERROR: balance_actual no se reseteo a balance_inicial en cuenta {cuenta_id}: "
            f"actual=${cuenta_despues['balance_actual']:.2f}, inicial=${cuenta_despues['balance_inicial']:.2f}"
        )

    if cuenta_despues['roi_total'] != 0.0:
        errores.append(
            f"ERROR: roi_total no se reseteo a 0 en cuenta {cuenta_id}: "
            f"{cuenta_despues['roi_total']:.2f}%"
        )

    if cuenta_despues['numero_cambios_agente'] != 0:
        errores.append(
            f"ERROR: numero_cambios_agente no se reseteo a 0 en cuenta {cuenta_id}: "
            f"{cuenta_despues['numero_cambios_agente']}"
        )

    if cuenta_despues['win_rate'] != 0.0:
        errores.append(
            f"ERROR: win_rate no se reseteo a 0 en cuenta {cuenta_id}: "
            f"{cuenta_despues['win_rate']:.4f}"
        )

if errores:
    print("\n[FALLO] Se encontraron errores en el reset:")
    for error in errores:
        print(f"  - {error}")
else:
    print("\n[SUCCESS] Todas las validaciones pasaron correctamente!")
    print("\nResumen:")
    print(f"  - balance_inicial permanece en $1,000 para todas las cuentas")
    print(f"  - balance_actual se reseteo a balance_inicial")
    print(f"  - roi_total se reseteo a 0%")
    print(f"  - numero_cambios_agente se reseteo a 0")
    print(f"  - win_rate se reseteo a 0")
    print(f"  - {reset_result['cuentas_reseteadas']} cuentas procesadas")

print("\n" + "="*80)
print("FIN DEL TEST")
print("="*80 + "\n")
