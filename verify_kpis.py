"""
Script de verificación de KPIs del Resumen Ejecutivo
Valida que todas las fórmulas matemáticas sean correctas
"""

from pymongo import MongoClient
from datetime import date, datetime
import numpy as np

# Conectar a MongoDB (usando la misma configuración que la app)
from app.config.settings import settings

client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

# Período de análisis
start_date = "2025-09-01"
end_date = "2025-10-07"

print("=" * 80)
print("VERIFICACION DE FORMULAS DEL RESUMEN EJECUTIVO")
print("=" * 80)
print(f"Periodo: {start_date} -> {end_date}\n")

# 1. OBTENER DATOS
print("1. RECOPILANDO DATOS...")
print("-" * 80)

# Obtener agent_states del período
agent_states = list(db.agent_states.aggregate([
    {
        "$match": {
            "date": {"$gte": start_date, "$lte": end_date},
            "is_in_casterly": True
        }
    },
    {
        "$group": {
            "_id": "$agent_id",
            "total_roi": {"$sum": "$roi_day"},
            "roi_values": {"$push": "$roi_day"},
            "roi_since_entry_values": {"$push": "$roi_since_entry"},
            "days_in_casterly": {"$sum": 1}
        }
    }
]))

print(f"[OK] Agentes encontrados: {len(agent_states)}")
print(f"[OK] Total dias en Casterly: {sum(a['days_in_casterly'] for a in agent_states)}")

# Obtener asignaciones activas
active_assignments = list(db.assignments.find({"is_active": True}))
print(f"[OK] Asignaciones activas: {len(active_assignments)}")

# Crear mapa de balances
agent_balances = {}
for assignment in active_assignments:
    agent_id = assignment["agent_id"]
    if agent_id in [a["_id"] for a in agent_states]:
        if agent_id not in agent_balances:
            agent_balances[agent_id] = 0.0
        agent_balances[agent_id] += assignment["balance"]

print(f"[OK] Agentes con balance: {len(agent_balances)}")
print(f"[OK] Balance total: ${sum(agent_balances.values()):,.2f}\n")

# 2. VERIFICAR ROI TOTAL (PONDERADO)
print("2. ROI TOTAL (PONDERADO POR BALANCE)")
print("-" * 80)

# IMPORTANTE: Solo incluir agentes con balance > 0 (mismo criterio que el API)
agents_with_balance = [a for a in agent_states if agent_balances.get(a["_id"], 0.0) > 0]

total_balance = sum(agent_balances.values()) if agent_balances else 1.0
weighted_roi = 0.0

print(f"Formula: ROI_Total = SUM(ROI_agent * Balance_agent) / SUM(Balance)")
print(f"Nota: Solo agentes con asignaciones activas (balance > 0)")
print(f"\nCálculo detallado:")

for agent in agents_with_balance:
    agent_id = agent["_id"]
    agent_roi = agent["total_roi"]
    balance = agent_balances.get(agent_id, 0.0)
    weight = balance / total_balance if total_balance > 0 else 0.0
    contribution = agent_roi * weight
    weighted_roi += contribution

    print(f"  {agent_id:20s}: ROI={agent_roi:8.4f} * Weight={weight:6.4f} = {contribution:8.4f}")

# Mostrar agentes excluidos (sin balance)
excluded_agents = [a for a in agent_states if agent_balances.get(a["_id"], 0.0) == 0]
if excluded_agents:
    print(f"\nAgentes excluidos (sin asignaciones activas):")
    for agent in excluded_agents:
        print(f"  {agent['_id']:20s}: ROI={agent['total_roi']:8.4f} (Balance=0)")

print(f"\n[OK] ROI Total Ponderado: {weighted_roi:.4f} ({weighted_roi*100:.2f}%)")
print(f"{'[OK] CORRECTO' if abs(weighted_roi) < 0.01 else '[WARN] REVISAR'}\n")

# 3. VERIFICAR ROI PROMEDIO
print("3. ROI PROMEDIO (SIMPLE)")
print("-" * 80)

total_roi_sum = sum(agent["total_roi"] for agent in agent_states)
avg_roi_simple = total_roi_sum / len(agent_states) if agent_states else 0

print(f"Formula: ROI_Promedio = SUM(ROI_agent) / N")
print(f"\nCálculo:")
print(f"  Suma de ROIs: {total_roi_sum:.4f}")
print(f"  Número de agentes: {len(agent_states)}")
print(f"  Promedio: {total_roi_sum:.4f} / {len(agent_states)} = {avg_roi_simple:.4f}")

print(f"\n[OK] ROI Promedio: {avg_roi_simple:.4f} ({avg_roi_simple*100:.2f}%)")
print(f"{'[OK] CORRECTO' if -0.01 < avg_roi_simple < 0 else '[WARN] REVISAR'}\n")

# 4. VERIFICAR MAX DRAWDOWN
print("4. MAX DRAWDOWN")
print("-" * 80)

print(f"Formula: Max_DD = min((Valle - Pico) / Pico)")
print(f"\nCálculo por agente:")

agent_drawdowns = []
for agent in agent_states:
    roi_series = agent.get("roi_since_entry_values", [])
    if roi_series and len(roi_series) >= 2:
        # Convertir ROI acumulado a serie
        cumulative = [1.0]  # Empezar con 1.0 (100%)
        for roi in roi_series:
            cumulative.append(1.0 + roi)

        # Calcular max drawdown
        peak = cumulative[0]
        max_dd = 0.0
        for value in cumulative:
            if value > peak:
                peak = value
            if peak > 0:
                drawdown = (value - peak) / peak
                if drawdown < max_dd:
                    max_dd = drawdown

        agent_drawdowns.append(max_dd)

        if len(agent_drawdowns) <= 5:  # Mostrar primeros 5
            print(f"  {agent['_id']:20s}: Max DD = {max_dd:.4f} ({max_dd*100:.2f}%)")

if len(agent_drawdowns) > 5:
    print(f"  ... y {len(agent_drawdowns) - 5} agentes más")

max_drawdown_global = min(agent_drawdowns) if agent_drawdowns else 0.0

print(f"\n[OK] Max Drawdown Global: {max_drawdown_global:.4f} ({max_drawdown_global*100:.2f}%)")
print(f"{'[OK] CORRECTO - Drawdown es negativo' if max_drawdown_global <= 0 else '[ERROR] ERROR - Drawdown debe ser negativo'}\n")

# 5. VERIFICAR VOLATILIDAD
print("5. VOLATILIDAD (DESVIACION ESTANDAR)")
print("-" * 80)

all_roi_values = []
for agent in agent_states:
    all_roi_values.extend(agent["roi_values"])

print(f"Formula: Volatilidad = sqrt(SUM(x - mu)^2 / (N-1))  [Varianza Muestral]")
print(f"\nCálculo:")
print(f"  Total de observaciones: {len(all_roi_values)}")

volatility = 0.0
if all_roi_values and len(all_roi_values) > 1:
    mean_roi = sum(all_roi_values) / len(all_roi_values)
    print(f"  Media (mu): {mean_roi:.6f}")

    # Varianza muestral (N-1)
    variance = sum((x - mean_roi) ** 2 for x in all_roi_values) / (len(all_roi_values) - 1)
    volatility = variance ** 0.5

    print(f"  Varianza muestral: {variance:.6f}")
    print(f"  Volatilidad (sigma): {volatility:.6f}")

    print(f"\n[OK] Volatilidad: {volatility:.4f} ({volatility*100:.2f}%)")
    print(f"{'[OK] CORRECTO - Usa N-1' if len(all_roi_values) > 1 else '[WARN] REVISAR'}\n")
else:
    print("[ERROR] No hay suficientes datos\n")

# 6. VERIFICAR WIN RATE
print("6. WIN RATE")
print("-" * 80)

positive_roi_agents = sum(1 for agent in agent_states if agent["total_roi"] > 0)
win_rate = (positive_roi_agents / len(agent_states)) if agent_states else 0

print(f"Formula: Win_Rate = Agentes_con_ROI_positivo / Total_Agentes")
print(f"\nCálculo:")
print(f"  Agentes con ROI > 0: {positive_roi_agents}")
print(f"  Total de agentes: {len(agent_states)}")
print(f"  Win Rate: {positive_roi_agents} / {len(agent_states)} = {win_rate:.4f}")

print(f"\n[OK] Win Rate: {win_rate:.4f} ({win_rate*100:.2f}%)")

if win_rate >= 0.7:
    print("[GREEN] EXCELENTE - Win Rate > 70%")
elif win_rate >= 0.5:
    print("[YELLOW] ACEPTABLE - Win Rate > 50%")
else:
    print("[RED] BAJO - Win Rate < 50%")

print()

# 7. COMPARACION CON API
print("7. COMPARACION CON ENDPOINT /api/reports/summary")
print("-" * 80)

import requests

try:
    response = requests.get("http://localhost:8000/api/reports/summary")
    api_data = response.json()
    api_kpis = api_data["kpis"]

    print("Comparacion de valores:")
    print(f"\n{'Metrica':<20s} {'Calculado':<15s} {'API':<15s} {'Match':<10s}")
    print("-" * 60)

    comparisons = [
        ("ROI Total", weighted_roi, api_kpis["total_roi"]),
        ("ROI Promedio", avg_roi_simple, api_kpis["average_roi"]),
        ("Max Drawdown", max_drawdown_global, api_kpis["max_drawdown"]),
        ("Volatilidad", volatility, api_kpis["volatility"]),
        ("Win Rate", win_rate, api_kpis["win_rate"]),
    ]

    all_match = True
    for name, calc, api in comparisons:
        match = abs(calc - api) < 0.0001
        symbol = "[OK]" if match else "[ERROR]"
        print(f"{name:<20s} {calc:<15.4f} {api:<15.4f} {symbol}")
        if not match:
            all_match = False

    print()
    if all_match:
        print("[OK] TODAS LAS FORMULAS SON CORRECTAS")
    else:
        print("[WARN] HAY DIFERENCIAS - REVISAR CALCULOS")

except Exception as e:
    print(f"[ERROR] Error conectando a API: {e}")

print()
print("=" * 80)
print("FIN DE LA VERIFICACION")
print("=" * 80)
