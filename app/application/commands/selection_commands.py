"""
Selection Command Service (CQRS Pattern - Command Side).

Responsabilidad: Solo operaciones de ESCRITURA para selección de agentes.
Cumple con CQRS (Command Query Responsibility Segregation).
"""

from typing import List, Dict, Any
from datetime import date
import logging
from app.domain.entities.top16_day import Top16Day
from app.domain.repositories.top16_repository import Top16Repository
from app.utils.collection_names import get_top16_collection_name

logger = logging.getLogger(__name__)


class SelectionCommandService:
    """
    Command Service para selección de agentes (CQRS Pattern).

    RESPONSABILIDAD ÚNICA: Solo operaciones de ESCRITURA.
    -  Guardar Top 16 en base de datos
    -  Actualizar rankings
    -  Persistir selecciones
    -  NO consulta datos (eso es responsabilidad de SelectionQueryService)

    Beneficios CQRS:
    - Separación clara de responsabilidades (SRP)
    - Optimización independiente de escrituras
    - Fácil implementar transacciones sin afectar queries
    - Validaciones de negocio centralizadas en comandos
    """

    def __init__(self, top16_repo: Top16Repository):
        """
        Constructor con inyección de dependencias (DIP).

        Args:
            top16_repo: Repositorio de Top16 (escritura)
        """
        self.top16_repo = top16_repo

    # ==================== COMMANDS (Solo Escritura) ====================

    async def save_top16_to_database(
        self,
        top16_agents: List[Dict[str, Any]],
        target_date: date,
        window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Command: Guarda el ranking de Top 16 en la base de datos.

        Esta es una operación de ESCRITURA pura (Command).
        Realiza validaciones de negocio antes de persistir.

        Args:
            top16_agents: Lista de datos de los Top 16 agentes rankeados
            target_date: Fecha del ranking
            window_days: Ventana de días utilizada (default 7)

        Returns:
            Dict con resultado de la operación:
                - success: bool
                - agents_saved: int
                - collection_name: str
                - errors: List[str] (opcional)

        Raises:
            ValueError: Si top16_agents está vacío o mal formado

        Example:
            >>> result = await command_service.save_top16_to_database(top16, date(2025, 10, 7))
            >>> print(f"Saved {result['agents_saved']} agents to {result['collection_name']}")
        """
        logger.info(f"[COMMAND] Guardando Top 16 en base de datos para {target_date}")

        # Validación de negocio: Top 16 no puede estar vacío
        if not top16_agents:
            error_msg = "Cannot save empty Top 16"
            logger.error(f"[COMMAND] {error_msg}")
            return {"success": False, "agents_saved": 0, "errors": [error_msg]}

        # Validación de negocio: Máximo 16 agentes
        if len(top16_agents) > 16:
            logger.warning(f"[COMMAND] Top 16 tiene {len(top16_agents)} agentes, truncando a 16")
            top16_agents = top16_agents[:16]

        collection_name = get_top16_collection_name(window_days)
        errors = []
        saved_count = 0

        try:
            # Crear entidades Top16Day para cada agente
            for agent in top16_agents:
                try:
                    top16_entity = Top16Day(
                        date=target_date,
                        userId=agent["userId"],
                        roi_7d=agent.get("roi_7d", 0.0),
                        total_pnl=agent.get("total_pnl", 0.0),
                        balance_current=agent.get("balance_current", 0.0),
                        total_trades_7d=agent.get("total_trades_7d", 0),
                        positive_days=agent.get("positive_days", 0),
                        negative_days=agent.get("negative_days", 0),
                        rank=agent.get("rank", 0),
                    )

                    # Guardar en repositorio
                    await self.top16_repo.save(top16_entity, collection_name)
                    saved_count += 1

                    logger.debug(
                        f"[COMMAND] Guardado agente #{agent['rank']}: {agent['userId']} "
                        f"(ROI: {agent['roi_7d']:.2%})"
                    )

                except Exception as e:
                    error_msg = f"Error guardando agente {agent.get('userId', 'unknown')}: {str(e)}"
                    logger.error(f"[COMMAND] {error_msg}")
                    errors.append(error_msg)

            logger.info(
                f"[COMMAND] Top 16 guardado exitosamente: {saved_count}/{len(top16_agents)} agentes "
                f"en colección '{collection_name}'"
            )

            return {
                "success": saved_count > 0,
                "agents_saved": saved_count,
                "collection_name": collection_name,
                "errors": errors if errors else None,
            }

        except Exception as e:
            error_msg = f"Error crítico guardando Top 16: {str(e)}"
            logger.error(f"[COMMAND] {error_msg}", exc_info=True)
            return {
                "success": False,
                "agents_saved": saved_count,
                "collection_name": collection_name,
                "errors": [error_msg],
            }

    async def update_agent_rank(
        self,
        userId: str,
        new_rank: int,
        target_date: date,
        window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Command: Actualiza el ranking de un agente específico.

        Esta es una operación de ESCRITURA pura (Command).

        Args:
            userId: ID del agente
            new_rank: Nuevo ranking (1-16)
            target_date: Fecha del ranking
            window_days: Ventana de días

        Returns:
            Dict con resultado de la operación

        Example:
            >>> result = await command_service.update_agent_rank("agent1", 5, date(2025, 10, 7))
            >>> print(f"Rank updated: {result['success']}")
        """
        logger.info(f"[COMMAND] Actualizando ranking de {userId} a #{new_rank} para {target_date}")

        # Validación de negocio: Rank debe estar entre 1 y 16
        if not 1 <= new_rank <= 16:
            error_msg = f"Invalid rank {new_rank}. Must be between 1 and 16"
            logger.error(f"[COMMAND] {error_msg}")
            return {"success": False, "error": error_msg}

        try:
            collection_name = get_top16_collection_name(window_days)

            # Obtener entidad actual
            existing = await self.top16_repo.get_by_agent_and_date(userId, target_date, collection_name)

            if not existing:
                error_msg = f"Agent {userId} not found in Top 16 for {target_date}"
                logger.warning(f"[COMMAND] {error_msg}")
                return {"success": False, "error": error_msg}

            # Actualizar rank
            existing.rank = new_rank

            # Guardar cambios
            await self.top16_repo.save(existing, collection_name)

            logger.info(f"[COMMAND] Ranking actualizado exitosamente para {userId}")

            return {
                "success": True,
                "userId": userId,
                "new_rank": new_rank,
                "collection_name": collection_name,
            }

        except Exception as e:
            error_msg = f"Error actualizando ranking de {userId}: {str(e)}"
            logger.error(f"[COMMAND] {error_msg}", exc_info=True)
            return {"success": False, "error": error_msg}

    async def delete_top16_for_date(
        self,
        target_date: date,
        window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Command: Elimina todos los registros de Top 16 para una fecha específica.

        Esta es una operación de ESCRITURA pura (Command).
        Útil para reprocesar simulaciones.

        Args:
            target_date: Fecha a limpiar
            window_days: Ventana de días

        Returns:
            Dict con resultado de la operación

        Example:
            >>> result = await command_service.delete_top16_for_date(date(2025, 10, 7))
            >>> print(f"Deleted {result['deleted_count']} records")
        """
        logger.info(f"[COMMAND] Eliminando Top 16 para fecha {target_date}")

        try:
            collection_name = get_top16_collection_name(window_days)

            # Eliminar todos los registros de la fecha
            deleted_count = await self.top16_repo.delete_by_date(target_date, collection_name)

            logger.info(
                f"[COMMAND] Top 16 eliminado: {deleted_count} registros para {target_date} "
                f"en '{collection_name}'"
            )

            return {
                "success": True,
                "deleted_count": deleted_count,
                "target_date": target_date.isoformat(),
                "collection_name": collection_name,
            }

        except Exception as e:
            error_msg = f"Error eliminando Top 16 para {target_date}: {str(e)}"
            logger.error(f"[COMMAND] {error_msg}", exc_info=True)
            return {"success": False, "error": error_msg}

    async def bulk_save_top16(
        self,
        top16_by_date: Dict[date, List[Dict[str, Any]]],
        window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Command: Guarda múltiples Top 16 para diferentes fechas en batch.

        Esta es una operación de ESCRITURA pura (Command).
        Optimizada para procesamiento bulk.

        Args:
            top16_by_date: Dict con fecha como key y lista de Top 16 como value
            window_days: Ventana de días

        Returns:
            Dict con resultado de la operación (total_saved, errors)

        Example:
            >>> top16_data = {
            ...     date(2025, 10, 7): [agent1, agent2, ...],
            ...     date(2025, 10, 8): [agent1, agent2, ...]
            ... }
            >>> result = await command_service.bulk_save_top16(top16_data)
            >>> print(f"Bulk saved {result['total_saved']} agents across {result['dates_processed']} dates")
        """
        logger.info(f"[COMMAND] Guardando Top 16 en batch para {len(top16_by_date)} fechas")

        total_saved = 0
        dates_processed = 0
        errors = []

        for target_date, top16_agents in top16_by_date.items():
            try:
                result = await self.save_top16_to_database(top16_agents, target_date, window_days)

                if result["success"]:
                    total_saved += result["agents_saved"]
                    dates_processed += 1
                else:
                    errors.extend(result.get("errors", []))

            except Exception as e:
                error_msg = f"Error procesando fecha {target_date}: {str(e)}"
                logger.error(f"[COMMAND] {error_msg}")
                errors.append(error_msg)

        logger.info(
            f"[COMMAND] Batch completado: {total_saved} agentes guardados en {dates_processed} fechas"
        )

        return {
            "success": dates_processed > 0,
            "total_saved": total_saved,
            "dates_processed": dates_processed,
            "total_dates": len(top16_by_date),
            "errors": errors if errors else None,
        }
