from app.config.database import database_manager

database_manager.connect()
db = database_manager.get_database()

collections_to_clean = [
    "agent_states",
    "assignments",
    "rotation_log",
    "daily_roi_calculation",
    "cuentas_clientes_trading",
    "historial_asignaciones_clientes",
    "client_accounts_snapshots",
    "client_accounts_simulations",
    "agent_roi_3d",
    "agent_roi_7d",
    "top16_3d",
    "top16_7d",
    "rank_changes",
    "simulations",
    "rebalancing_events"
]

print("Limpiando colecciones para test...")
for coll_name in collections_to_clean:
    result = db[coll_name].delete_many({})
    print(f"  {coll_name}: {result.deleted_count} documentos eliminados")

print("\nColecciones limpiadas exitosamente!")
