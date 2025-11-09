"""
Recalcula Top16 por ventana usando ROI compuesto.

Para cada día del rango indicado (o el rango de la última simulación),
calcula el Top 16 con SelectionService (modo ULTRA FAST + ventanas dinámicas)
y persiste en la colección dinámica `top16_{window}d`.

Uso:
  python backend/scripts/recalculate_top16.py \
    [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
    [--windows 3,5,7,10,15,30] [--clear]

Notas:
- --clear limpia previamente la colección `top16_{window}d` antes de recalcular.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from typing import List

from app.config.database import database_manager
from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl
from app.infrastructure.repositories.daily_roi_repository import DailyROIRepository
from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository
from app.application.services.balance_query_service import BalanceQueryService
from app.application.services.daily_roi_calculation_service import DailyROICalculationService
from app.application.services.roi_7d_calculation_service import ROI7DCalculationService
from app.application.services.selection_service import SelectionService
from app.utils.collection_names import get_top16_collection_name


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recalcular Top16 por ventana")
    parser.add_argument("--start", type=str, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument(
        "--windows",
        type=str,
        default="3,5,7,10,15,30",
        help="Lista de ventanas separadas por coma (ej: 7,30)",
    )
    parser.add_argument(
        "--clear", action="store_true", help="Limpia la colección top16_{window}d antes de recalcular"
    )
    return parser.parse_args()


def _daterange(start: date, end: date) -> List[date]:
    cur = start
    out: List[date] = []
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _get_last_simulation_range(db) -> tuple[date, date]:
    cfg = db["system_config"].find_one({"config_key": "last_simulation"})
    if not cfg or "start_date" not in cfg or "end_date" not in cfg:
        raise RuntimeError(
            "No se encontró system_config.last_simulation con start_date/end_date"
        )
    return date.fromisoformat(cfg["start_date"]), date.fromisoformat(cfg["end_date"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    log = logging.getLogger("recalculate_top16")

    args = _parse_args()

    # Conectar DB
    database_manager.connect()
    db = database_manager.get_database()

    try:
        # Rango de fechas
        if args.start and args.end:
            start = date.fromisoformat(args.start)
            end = date.fromisoformat(args.end)
        else:
            start, end = _get_last_simulation_range(db)
        if end < start:
            raise ValueError("end debe ser >= start")

        windows = [int(w.strip()) for w in args.windows.split(",") if w.strip()]
        log.info(f"Rango: {start} -> {end}; ventanas: {windows}; clear={args.clear}")

        # Construir servicios mínimos requeridos por SelectionService
        top16_repo = Top16RepositoryImpl()  # No se usa para guardar dinámico
        balance_repo = BalanceRepositoryImpl()
        daily_repo = DailyROIRepository(db)
        roi7_repo = ROI7DRepository(db)
        daily_service = DailyROICalculationService(daily_repo, db)
        roi7_service = ROI7DCalculationService(roi7_repo, daily_service)
        balance_query_service = BalanceQueryService(balance_repo)
        selection = SelectionService(
            top16_repo, balance_repo, roi7_service, balance_query_service
        )

        # Limpiar colecciones top16 si se solicita
        if args.clear:
            for window in windows:
                col_name = get_top16_collection_name(window)
                repo = Top16RepositoryImpl(col_name)
                deleted = repo.delete_all()
                log.info(f"Limpiada colección '{col_name}': {deleted} documentos eliminados")

        days = _daterange(start, end)
        for window in windows:
            processed = 0
            col_name = get_top16_collection_name(window)
            log.info(f"=== Ventana {window}D (colección: {col_name}) ===")
            for target in days:
                # Calcular Top 16 del día
                top16, ranked = selection.select_top_16(target, agent_ids=None, window_days=window)
                # Guardar Top16 marcando como dentro de Casterly a los seleccionados
                casterly_ids = [a["agent_id"] for a in top16]
                selection.save_top16_to_database(
                    target_date=target, top_16=top16, casterly_agent_ids=casterly_ids, window_days=window
                )
                processed += 1
                if processed % 5 == 0:
                    log.info(f"  Progreso: {processed}/{len(days)} días procesados")

            log.info(f"Ventana {window}D completada: {processed} días")

        log.info("Recalculo de Top16 finalizado")

    finally:
        database_manager.disconnect()


if __name__ == "__main__":
    main()

