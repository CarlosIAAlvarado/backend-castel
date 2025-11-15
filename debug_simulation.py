"""
Script de diagnóstico para entender por qué select_top_16 devuelve 0 agentes.
"""
from app.config.database import database_manager
from datetime import date, timedelta
import sys
import io
import asyncio

# Force UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database
database_manager.connect()
db = database_manager.get_database()

async def diagnose_simulation():
    print("=" * 80)
    print("DIAGNÓSTICO DE SIMULACIÓN - ¿POR QUÉ 0 AGENTES?")
    print("=" * 80)

    target_date = date(2025, 6, 2)
    window_days = 3

    print(f"\nParámetros de prueba:")
    print(f"  target_date: {target_date}")
    print(f"  window_days: {window_days}")

    window_start = target_date - timedelta(days=window_days - 1)
    print(f"  window_start: {window_start}")

    # 1. Verificar balances
    print("\n" + "=" * 80)
    print("PASO 1: VERIFICAR BALANCES")
    print("=" * 80)

    from datetime import datetime, time
    import pytz
    tz = pytz.timezone("America/Bogota")

    start_dt = tz.localize(datetime.combine(window_start, time.min))
    end_dt = tz.localize(datetime.combine(target_date, time.max))

    balances_count = db.balances.count_documents({
        "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
    })

    print(f"Balances en ventana [{window_start} -> {target_date}]: {balances_count}")

    if balances_count > 0:
        # Obtener agentes únicos
        agents_with_balance = list(db.balances.distinct("userId", {
            "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
        }))
        print(f"Agentes únicos con balance: {len(agents_with_balance)}")
        print(f"Primeros 5: {agents_with_balance[:5]}")

    # 2. Verificar movements
    print("\n" + "=" * 80)
    print("PASO 2: VERIFICAR MOVEMENTS")
    print("=" * 80)

    movements_count = db['mov07.10'].count_documents({
        "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
    })

    print(f"Movements en ventana [{window_start} -> {target_date}]: {movements_count}")

    if movements_count > 0:
        # Obtener agentes únicos con movements
        agents_with_movements = list(db['mov07.10'].distinct("userId", {
            "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
        }))
        print(f"Agentes únicos con movements: {len(agents_with_movements)}")
        print(f"Primeros 5: {agents_with_movements[:5]}")

    # 3. Simular cálculo de ROI para 1 agente
    print("\n" + "=" * 80)
    print("PASO 3: SIMULAR CÁLCULO ROI PARA UN AGENTE")
    print("=" * 80)

    if balances_count > 0 and movements_count > 0:
        # Tomar el primer agente que tenga ambos
        test_agent = None
        for agent in agents_with_balance[:10]:
            if agent in agents_with_movements:
                test_agent = agent
                break

        if test_agent:
            print(f"\nAgente de prueba: {test_agent}")

            # Obtener sus balances
            agent_balances = list(db.balances.find({
                "userId": test_agent,
                "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
            }).sort("createdAt", 1))

            print(f"Balances del agente: {len(agent_balances)}")
            for b in agent_balances:
                print(f"  {b['createdAt'][:10]}: balance={b.get('balance', 'N/A')}")

            # Obtener sus movements
            agent_movements = list(db['mov07.10'].find({
                "userId": test_agent,
                "createdAt": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
            }).sort("createdAt", 1))

            print(f"\nMovements del agente: {len(agent_movements)}")
            for m in agent_movements[:5]:
                print(f"  {m['createdAt'][:10]}: closedPnl={m.get('closedPnl', 'N/A')}")

            # Calcular ROI manualmente
            if agent_balances and agent_movements:
                balance_inicial = agent_balances[0].get('balance', 0)
                total_pnl = sum(float(str(m.get('closedPnl', '0')).replace(',', '.')) for m in agent_movements)
                roi = total_pnl / balance_inicial if balance_inicial > 0 else 0

                print(f"\nCálculo manual de ROI:")
                print(f"  Balance inicial: {balance_inicial}")
                print(f"  Total P&L: {total_pnl}")
                print(f"  ROI: {roi:.4f} ({roi*100:.2f}%)")

    # 4. Probar BulkROICalculationService
    print("\n" + "=" * 80)
    print("PASO 4: PROBAR BulkROICalculationService")
    print("=" * 80)

    try:
        from app.application.services.bulk_roi_calculation_service import BulkROICalculationService

        bulk_service = BulkROICalculationService(db)

        # Usar solo primeros 10 agentes para prueba
        test_agents = agents_with_balance[:10] if balances_count > 0 else []

        if test_agents:
            print(f"\nCalculando ROI para {len(test_agents)} agentes...")
            results = bulk_service.calculate_bulk_roi_7d(
                user_ids=test_agents,
                target_date=target_date,
                window_days=window_days,
                save_to_db=False  # No guardar en BD
            )

            print(f"\nResultados:")
            print(f"  Agentes procesados: {len(test_agents)}")
            print(f"  Agentes con ROI calculado: {len(results)}")

            if results:
                print(f"\nPrimeros 3 resultados:")
                for i, (user_id, roi_data) in enumerate(list(results.items())[:3], 1):
                    print(f"\n  {i}. {user_id}:")
                    print(f"     ROI: {roi_data.get('roi_7d_total', 0):.4f}")
                    print(f"     P&L: {roi_data.get('total_pnl_7d', 0):.2f}")
                    print(f"     Balance: {roi_data.get('balance_current', 0):.2f}")
            else:
                print("\n⚠️  PROBLEMA: BulkROICalculationService devolvió 0 resultados")
                print("     Esto explica por qué select_top_16() devuelve 0 agentes")

    except Exception as e:
        print(f"\n❌ Error al probar BulkROICalculationService: {e}")
        import traceback
        traceback.print_exc()

    # 5. Verificar SelectionService
    print("\n" + "=" * 80)
    print("PASO 5: PROBAR SelectionService.select_top_16()")
    print("=" * 80)

    try:
        from app.application.services.selection_service import SelectionService
        from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
        from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl
        from app.application.services.roi_7d_calculation_service import ROI7DCalculationService
        from app.application.services.balance_query_service import BalanceQueryService
        from app.application.services.daily_roi_calculation_service import DailyROICalculationService
        from app.infrastructure.repositories.roi_7d_repository import ROI7DRepositoryImpl

        # Crear dependencias
        top16_repo = Top16RepositoryImpl("top16_7d")
        balance_repo = BalanceRepositoryImpl()
        daily_roi_service = DailyROICalculationService(db)
        roi_7d_repo = ROI7DRepositoryImpl()
        roi_7d_service = ROI7DCalculationService(roi_7d_repo, daily_roi_service)
        balance_query_service = BalanceQueryService(balance_repo)

        selection_service = SelectionService(
            top16_repo,
            balance_repo,
            roi_7d_service,
            balance_query_service
        )

        print(f"\nEjecutando select_top_16 para {target_date} con window_days={window_days}...")
        top16, all_ranked = await selection_service.select_top_16(
            target_date=target_date,
            window_days=window_days
        )

        print(f"\nResultado:")
        print(f"  Top 16 encontrados: {len(top16)}")
        print(f"  Total agentes rankeados: {len(all_ranked)}")

        if len(top16) == 0:
            print("\n❌ PROBLEMA CONFIRMADO: select_top_16() devuelve 0 agentes")
            print("\nPosibles causas:")
            print("  1. calculate_all_agents_roi_7d_ULTRA_FAST() devuelve lista vacía")
            print("  2. Todos los agentes fueron filtrados por:")
            print("     - Stop Loss (ROI < -10%)")
            print("     - 3 días consecutivos de pérdida")
            print("     - Balance mínimo (min_aum)")
        else:
            print(f"\n✅ ¡select_top_16() funciona! Encontrados {len(top16)} agentes")
            print("\nTop 3:")
            for i, agent in enumerate(top16[:3], 1):
                print(f"  {i}. {agent.get('agent_id')}: ROI={agent.get('roi_7d', 0):.4f}")

    except Exception as e:
        print(f"\n❌ Error al probar SelectionService: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 80)

# Ejecutar
asyncio.run(diagnose_simulation())
