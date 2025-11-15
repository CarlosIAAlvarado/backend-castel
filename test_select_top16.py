"""
Test simple de select_top_16 para entender por qué devuelve 0 agentes.
"""
from app.config.database import database_manager
from datetime import date
import sys
import io
import asyncio

# Force UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database
database_manager.connect()
db = database_manager.get_database()

async def test_select_top16():
    print("=" * 80)
    print("TEST: SelectionService.select_top_16()")
    print("=" * 80)

    target_date = date(2025, 6, 2)
    window_days = 3

    print(f"\nParámetros:")
    print(f"  target_date: {target_date}")
    print(f"  window_days: {window_days}")

    try:
        # Importar con dependencias correctas
        from app.application.services.selection_service import SelectionService
        from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
        from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl
        from app.application.services.roi_7d_calculation_service import ROI7DCalculationService
        from app.application.services.balance_query_service import BalanceQueryService
        from app.application.services.daily_roi_calculation_service import DailyROICalculationService
        from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository

        # Crear dependencias
        print("\n1. Creando dependencias...")
        top16_repo = Top16RepositoryImpl(f"top16_{window_days}d")
        balance_repo = BalanceRepositoryImpl()
        daily_roi_service = DailyROICalculationService(db)
        roi_7d_repo = ROI7DRepository(db)  # ✅ Clase correcta
        roi_7d_service = ROI7DCalculationService(roi_7d_repo, daily_roi_service)
        balance_query_service = BalanceQueryService(balance_repo)

        print("   ✅ Dependencias creadas")

        # Crear SelectionService
        print("\n2. Creando SelectionService...")
        selection_service = SelectionService(
            top16_repo,
            balance_repo,
            roi_7d_service,
            balance_query_service
        )
        print("   ✅ SelectionService creado")

        # Ejecutar select_top_16
        print(f"\n3. Ejecutando select_top_16...")
        print(f"   Esto puede tardar unos minutos (calculando ROI de ~50 agentes)...")

        top16, all_ranked = await selection_service.select_top_16(
            target_date=target_date,
            window_days=window_days
        )

        print(f"\n✅ RESULTADO:")
        print(f"   Top 16 encontrados: {len(top16)}")
        print(f"   Total agentes rankeados: {len(all_ranked)}")

        if len(top16) == 0:
            print("\n❌ PROBLEMA: select_top_16() devuelve 0 agentes")
            print("\nDEBUG: Verificando all_ranked...")
            print(f"   Total de agentes antes de filtros: {len(all_ranked)}")

            if len(all_ranked) > 0:
                print(f"\n   Primeros 5 agentes rankeados:")
                for i, agent in enumerate(all_ranked[:5], 1):
                    print(f"   {i}. {agent.get('agent_id')}: ROI={agent.get('roi_7d', 0):.4f}")

                print("\n⚠️  CONCLUSIÓN: Hay agentes rankeados pero todos fueron filtrados")
                print("   Razones posibles:")
                print("   - Todos tienen ROI < -10% (Stop Loss)")
                print("   - Todos tienen 3 días consecutivos de pérdida")
                print("   - Todos tienen AUM < mínimo requerido")
            else:
                print("\n❌  CONCLUSIÓN: calculate_all_agents_roi_7d_ULTRA_FAST() devuelve lista vacía")
                print("   El problema está en el cálculo de ROI")

        else:
            print(f"\n✅ ¡SUCCESS! select_top_16() encontró {len(top16)} agentes")
            print(f"\nTop 5:")
            for i, agent in enumerate(top16[:5], 1):
                roi = agent.get('roi_7d', 0) * 100
                print(f"   {i}. {agent.get('agent_id')}: ROI={roi:.2f}%")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)

# Ejecutar
asyncio.run(test_select_top16())
