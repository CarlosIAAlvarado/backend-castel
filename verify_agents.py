from pymongo import MongoClient
from app.config.settings import settings
from datetime import date

# Conectar a MongoDB
client = MongoClient(settings.mongodb_uri)
db = client[settings.database_name]

# Fecha final del periodo
end_date = date(2025, 10, 7)

# Obtener agentes desde agent_states (lo que usa el API)
states = list(db.agent_states.find({
    'date': end_date.isoformat(),
    'is_in_casterly': True
}))

print("=" * 80)
print("VERIFICACION DE AGENTES FINALES EN CASTERLY ROCK")
print("=" * 80)
print(f"Fecha: {end_date.isoformat()}")
print(f"\nAgentes en Casterly Rock segun agent_states:")
print(f"Total: {len(states)}")
print("\nLista:")
for agent in sorted([s['agent_id'] for s in states]):
    print(f"  - {agent}")

# Comparar con asignaciones activas
assignments = list(db.assignments.find({'is_active': True}))
assigned_agents = set([a['agent_id'] for a in assignments])

print(f"\n\nAgentes con asignaciones activas:")
print(f"Total: {len(assigned_agents)}")
print("\nLista:")
for agent in sorted(assigned_agents):
    print(f"  - {agent}")

# Encontrar diferencias
states_agents = set([s['agent_id'] for s in states])
in_states_not_assigned = states_agents - assigned_agents
in_assigned_not_states = assigned_agents - states_agents

if in_states_not_assigned:
    print(f"\n\n[ALERTA] Agentes en Casterly (states) pero SIN asignacion activa:")
    for agent in sorted(in_states_not_assigned):
        print(f"  - {agent}")

if in_assigned_not_states:
    print(f"\n\n[ALERTA] Agentes CON asignacion activa pero NO en Casterly (states):")
    for agent in sorted(in_assigned_not_states):
        print(f"  - {agent}")

if not in_states_not_assigned and not in_assigned_not_states:
    print("\n\n[OK] Todos los agentes coinciden perfectamente!")

print("\n" + "=" * 80)
