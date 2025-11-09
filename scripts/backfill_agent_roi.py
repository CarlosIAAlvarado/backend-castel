"""
Backfill de colecciones agent_roi_*d usando ROI compuesto (multiplicativo).

Calcula y persiste ROI por ventanas [3,5,7,10,15,30] sobre el rango
de la última simulación (system_config.last_simulation) o el rango indicado.

Usa BulkROICalculationService (compuesto) para performance y consistencia
con la especificación.

Uso:
  python backend/scripts/backfill_agent_roi.py \
    [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
    [--windows 3,5,7,10,15,30] [--dry-run]

Notas:
- --dry-run evita guardar en MongoDB (solo calcula).
- Por defecto toma fechas de system_config.last_simulation.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from typing import List

from app.config.database import database_manager
from app.application.services.bulk_roi_calculation_service import (
    BulkROICalculationService,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill agent_roi_*d collections (compound ROI)")
    parser.add_argument("--start", type=str, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument(
        "--windows",
        type=str,
        default="3,5,7,10,15,30",
        help="Lista de ventanas separadas por coma (ej: 7,30)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Calcula sin persistir en MongoDB"
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


def _get_all_user_ids_from_balances(db, start: date, end: date) -> List[str]:
    start_iso = start.isoformat()
    end_iso = end.isoformat()
    balances = db["balances"]
    user_ids = balances.distinct(
        "userId", {"createdAt": {"$gte": start_iso, "$lte": end_iso}}
    )
    # Filtrar nulos/vacíos y normalizar a str
    return [str(u) for u in user_ids if u]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    log = logging.getLogger("backfill_agent_roi")

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
        log.info(f"Rango: {start} -> {end}; ventanas: {windows}; dry_run={args.dry_run}")

        # Agentes (del rango completo para asegurar cobertura)
        user_ids = _get_all_user_ids_from_balances(db, start, end)
        if not user_ids:
            raise RuntimeError("No se encontraron userIds en balances para el rango indicado")
        log.info(f"Agentes únicos encontrados en balances: {len(user_ids)}")

        bulk = BulkROICalculationService(db)
        days = _daterange(start, end)

        for window in windows:
            processed = 0
            log.info(f"=== Ventana {window}D ===")
            for target in days:
                try:
                    bulk.calculate_bulk_roi_7d(
                        user_ids,
                        target,
                        window_days=window,
                        save_to_db=(not args.dry_run),
                    )
                    processed += 1
                    if processed % 5 == 0:
                        log.info(f"  Progreso: {processed}/{len(days)} días procesados")
                except Exception as e:
                    log.error(f"Error en {target} (win={window}): {e}")

            log.info(f"Ventana {window}D completada: {processed} días")

        log.info("Backfill finalizado")

    finally:
        database_manager.disconnect()


if __name__ == "__main__":
    main()

