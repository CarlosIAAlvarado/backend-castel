"""
Script de prueba para verificar que la simulación funciona correctamente
Ejecutar: python test_simulation.py
"""

from app.config.database import database_manager
from datetime import date
from app.application.services.selection_service import SelectionService
from app.application.services.data_processing_service import DataProcessingService

def test_simulation():
    database_manager.connect()

    target_date = date(2025, 9, 1)

    print("=" * 80)
    print("TEST DE SIMULACIÓN")
    print("=" * 80)

    # 1. Obtener agentes con datos completos
    print(f"\n1. Agentes con balance en {target_date}:")
    balances = DataProcessingService.get_all_balances_by_date(target_date)
    agents_with_balance = list(balances.keys())
    print(f"   Total: {len(agents_with_balance)}")

    # 2. Calcular ROI para todos los agentes
    print(f"\n2. Calculando ROI_7D para {len(agents_with_balance)} agentes...")
    service = SelectionService()

    agents_data = service.calculate_all_agents_roi_7d(
        target_date=target_date,
        agent_ids=agents_with_balance,
        min_aum=0.01
    )

    print(f"   Agentes con ROI calculado: {len(agents_data)}")

    if agents_data:
        # Mostrar Top 10
        sorted_agents = sorted(agents_data, key=lambda x: x['roi_7d'], reverse=True)

        print(f"\n3. TOP 10 AGENTES POR ROI_7D:")
        print(f"   {'Rank':<6} {'Agent ID':<20} {'ROI 7D':<12} {'AUM':<12}")
        print("   " + "-" * 60)

        for i, agent in enumerate(sorted_agents[:10], 1):
            print(f"   {i:<6} {agent['agent_id']:<20} {agent['roi_7d']:>10.2f}% {agent['total_aum']:>10.2f}")

        # Contar agentes con ROI != 0
        agents_with_roi = [a for a in agents_data if a['roi_7d'] != 0]
        print(f"\n4. RESUMEN:")
        print(f"   Agentes con ROI != 0: {len(agents_with_roi)}")
        print(f"   Agentes con ROI = 0: {len(agents_data) - len(agents_with_roi)}")

        if len(agents_with_roi) >= 16:
            print(f"\n   ✓ HAY SUFICIENTES AGENTES PARA CASTERLY ROCK (Top 16)")
            print(f"   ✓ La simulación debería funcionar correctamente")
        else:
            print(f"\n   ✗ NO hay suficientes agentes con ROI calculado")
            print(f"   ✗ Se necesitan al menos 16, solo hay {len(agents_with_roi)}")
    else:
        print("\n   ✗ NO SE CALCULÓ ROI PARA NINGÚN AGENTE")

    database_manager.disconnect()

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_simulation()
