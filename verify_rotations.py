from pymongo import MongoClient
from app.config.settings import settings
from datetime import date

client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

start_date = date(2025, 9, 1)
end_date = date(2025, 10, 7)

print("=" * 80)
print("VERIFICACION DE ROTACIONES")
print("=" * 80)
print(f"Periodo: {start_date} a {end_date}")

# Total rotation logs (colección correcta: rotation_log singular)
rotation_logs = list(db.rotation_log.find({
    "date": {
        "$gte": start_date.isoformat(),
        "$lte": end_date.isoformat()
    }
}))

print(f"\nTotal rotation logs: {len(rotation_logs)}")

# Contar por tipo de acción
entries = [r for r in rotation_logs if r.get('action') == 'entry']
exits = [r for r in rotation_logs if r.get('action') == 'exit']

print(f"  Entradas (entry): {len(entries)}")
print(f"  Salidas (exit): {len(exits)}")

# Agentes únicos que rotaron
unique_agents_rotated = set([r['agent_id'] for r in rotation_logs])
print(f"\nAgentes unicos que experimentaron rotacion: {len(unique_agents_rotated)}")

# Agentes únicos en el periodo (en agent_states)
unique_agents_period = db.agent_states.distinct('agent_id', {
    "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()},
    "is_in_casterly": True
})

print(f"Agentes unicos en el periodo (agent_states): {len(unique_agents_period)}")

# Calcular diferentes tasas de rotación
print("\n" + "=" * 80)
print("CALCULOS DE TASA DE ROTACION")
print("=" * 80)

# Método 1: Rotaciones por agente
rotations_per_agent = len(rotation_logs) / len(unique_agents_period) if unique_agents_period else 0
print(f"\n1. Rotaciones por agente:")
print(f"   {len(rotation_logs)} rotaciones / {len(unique_agents_period)} agentes = {rotations_per_agent:.2f}")

# Método 2: Tasa de entrada/salida
turnover_rate = (len(exits) / len(unique_agents_period)) * 100 if unique_agents_period else 0
print(f"\n2. Tasa de rotacion (salidas):")
print(f"   ({len(exits)} salidas / {len(unique_agents_period)} agentes) * 100 = {turnover_rate:.2f}%")

# Método 3: Promedio de días por agente
total_days = (end_date - start_date).days + 1
avg_days_per_agent = total_days / rotations_per_agent if rotations_per_agent > 0 else 0
print(f"\n3. Promedio de dias por rotacion:")
print(f"   {total_days} dias / {rotations_per_agent:.2f} = {avg_days_per_agent:.2f} dias")

# Mostrar algunos ejemplos de rotation_logs
print("\n" + "=" * 80)
print("EJEMPLOS DE ROTATION LOGS (primeros 10)")
print("=" * 80)
for i, log in enumerate(rotation_logs[:10]):
    action = log.get('action', 'N/A')
    agent = log.get('agent_id', 'N/A')
    date_val = log.get('date', 'N/A')
    reason = log.get('reason', 'N/A')
    print(f"{i+1}. {date_val} | {agent:20s} | {action:6s} | {reason}")

print("\n" + "=" * 80)
