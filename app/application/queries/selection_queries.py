"""
Selection Query Service (CQRS Pattern - Query Side).

Responsabilidad: Solo operaciones de LECTURA para selección de agentes.
Cumple con CQRS (Command Query Responsibility Segregation).
"""

from typing import List, Dict, Any, Optional
from datetime import date, timedelta
import asyncio
import logging
from app.application.services.roi_7d_calculation_service import ROI7DCalculationService
from app.application.services.balance_query_service import BalanceQueryService
from app.domain.strategies.ranking_strategy import RankingStrategy, ROIRankingStrategy
from app.domain.repositories.balance_repository import BalanceRepository

logger = logging.getLogger(__name__)


class SelectionQueryService:
    """
    Query Service para selección de agentes (CQRS Pattern).

    RESPONSABILIDAD ÚNICA: Solo operaciones de LECTURA.
    - ✅ Consultar agentes disponibles
    - ✅ Calcular ROI de agentes
    - ✅ Rankear agentes
    - ✅ Filtrar agentes por criterios
    - ❌ NO guarda datos (eso es responsabilidad de SelectionCommandService)

    Beneficios CQRS:
    - Separación clara de responsabilidades (SRP)
    - Optimización independiente de lecturas
    - Fácil caching en queries sin afectar comandos
    - Testabilidad mejorada
    """

    def __init__(
        self,
        balance_repo: BalanceRepository,
        roi_7d_service: ROI7DCalculationService,
        balance_query_service: BalanceQueryService,
        ranking_strategy: Optional[RankingStrategy] = None
    ):
        """
        Constructor con inyección de dependencias (DIP).

        Args:
            balance_repo: Repositorio de balances (solo lectura)
            roi_7d_service: Servicio para calcular ROI_7D
            balance_query_service: Servicio de consultas de balances
            ranking_strategy: Estrategia de ranking (OCP)
        """
        self.balance_repo = balance_repo
        self.roi_7d_service = roi_7d_service
        self.balance_query_service = balance_query_service
        self.ranking_strategy = ranking_strategy or ROIRankingStrategy()

    # ==================== QUERIES (Solo Lectura) ====================

    def get_all_agents_from_balances(self, target_date: date) -> List[str]:
        """
        Query: Obtiene todos los agentes con balances en la ventana de 8 días.

        Esta es una operación de LECTURA pura (Query).

        Args:
            target_date: Fecha objetivo (final de la ventana)

        Returns:
            Lista de userIds únicos

        Example:
            >>> query_service = SelectionQueryService(...)
            >>> agents = query_service.get_all_agents_from_balances(date(2025, 10, 7))
            >>> print(f"Found {len(agents)} agents")
        """
        window_start = target_date - timedelta(days=7)
        window_end = target_date

        logger.info(f"[QUERY] Buscando agentes en ventana: {window_start} -> {window_end}")

        balances = self.balance_repo.get_all_by_date_range(window_start, window_end)

        unique_agents = set()
        for balance in balances:
            if balance.user_id:
                unique_agents.add(balance.user_id)

        logger.info(
            f"[QUERY] Found {len(unique_agents)} unique agents with balances in window "
            f"[{window_start} -> {window_end}]"
        )

        return list(unique_agents)

    async def calculate_single_agent_roi(self, userId: str, target_date: date) -> Dict[str, Any]:
        """
        Query: Calcula el ROI_7D de un agente individual.

        Esta es una operación de LECTURA pura (Query).
        Usa cache interno de ROI7DCalculationService.

        Args:
            userId: ID del agente
            target_date: Fecha objetivo

        Returns:
            Dict con datos de ROI del agente o None si falla

        Example:
            >>> roi_data = await query_service.calculate_single_agent_roi("agent1", date(2025, 10, 7))
            >>> print(f"ROI: {roi_data['roi_7d']}")
        """
        try:
            logger.debug(f"[QUERY] Calculando ROI para agente: {userId}")

            # Calcular ROI usando servicio
            roi_entity = await self.roi_7d_service.calculate_roi_7d(userId, target_date)

            if not roi_entity:
                logger.warning(f"[QUERY] No se pudo calcular ROI para {userId} en {target_date}")
                return None

            # Obtener balance actual
            balance_current = self.balance_query_service.get_balance_by_agent_and_date(userId, target_date)

            if balance_current is None:
                logger.warning(f"[QUERY] No se encontró balance para {userId} en {target_date}")
                return None

            # Construir diccionario con datos del agente
            agent_data = {
                "userId": roi_entity.userId,
                "roi_7d": roi_entity.roi_7d_total,
                "total_pnl": roi_entity.total_pnl_7d,
                "balance_current": balance_current,
                "total_trades_7d": roi_entity.total_trades_7d,
                "positive_days": roi_entity.positive_days,
                "negative_days": roi_entity.negative_days,
            }

            logger.debug(
                f"[QUERY] ROI calculado para {userId}: {roi_entity.roi_7d_total:.2%}, "
                f"PnL: ${roi_entity.total_pnl_7d:.2f}"
            )

            return agent_data

        except Exception as e:
            logger.error(f"[QUERY] Error calculando ROI para {userId}: {str(e)}")
            return None

    async def calculate_all_agents_roi(
        self, target_date: date, agent_ids: Optional[List[str]] = None, window_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Query: Calcula ROI para todos los agentes en paralelo.

        Esta es una operación de LECTURA pura (Query).
        Usa asyncio.gather para procesamiento paralelo.

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de IDs de agentes (opcional, si None busca todos)
            window_days: Días de ventana (default 7)

        Returns:
            Lista de diccionarios con datos de ROI de cada agente

        Example:
            >>> all_roi = await query_service.calculate_all_agents_roi(date(2025, 10, 7))
            >>> print(f"Calculated ROI for {len(all_roi)} agents")
        """
        if agent_ids is None:
            agent_ids = self.get_all_agents_from_balances(target_date)

        logger.info(f"[QUERY] Calculando ROI de {len(agent_ids)} agentes en paralelo...")

        # Calcular ROI de todos los agentes en paralelo
        tasks = [self.calculate_single_agent_roi(agent_id, target_date) for agent_id in agent_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filtrar resultados válidos (no None)
        valid_results = [r for r in results if r is not None]

        logger.info(f"[QUERY] ROI calculado exitosamente para {len(valid_results)}/{len(agent_ids)} agentes")

        return valid_results

    def rank_agents(
        self,
        agents_data: List[Dict[str, Any]],
        strategy: Optional[RankingStrategy] = None
    ) -> List[Dict[str, Any]]:
        """
        Query: Rankea agentes usando la estrategia de ranking configurada.

        Esta es una operación de LECTURA pura (Query).
        Usa Strategy Pattern (OCP) para permitir diferentes criterios de ranking.

        Args:
            agents_data: Lista de datos de agentes
            strategy: Estrategia de ranking (opcional, usa default si None)

        Returns:
            Lista de agentes ordenados por ranking con campo 'rank' agregado

        Example:
            >>> ranked = query_service.rank_agents(agents_data)
            >>> print(f"Top agent: {ranked[0]['userId']} with ROI {ranked[0]['roi_7d']}")
        """
        ranking_strategy = strategy or self.ranking_strategy

        logger.info(
            f"[QUERY] Rankeando {len(agents_data)} agentes usando estrategia: "
            f"{ranking_strategy.get_strategy_name()}"
        )

        # Ordenar por estrategia (descendente)
        sorted_agents = sorted(agents_data, key=ranking_strategy.get_sort_key, reverse=True)

        # Agregar ranking (1-indexed)
        for idx, agent in enumerate(sorted_agents, start=1):
            agent["rank"] = idx

        logger.info(
            f"[QUERY] Ranking completado. Top 3: "
            f"1) {sorted_agents[0]['userId'] if sorted_agents else 'N/A'}, "
            f"2) {sorted_agents[1]['userId'] if len(sorted_agents) > 1 else 'N/A'}, "
            f"3) {sorted_agents[2]['userId'] if len(sorted_agents) > 2 else 'N/A'}"
        )

        return sorted_agents

    async def select_top_n(
        self,
        agents_data: List[Dict[str, Any]],
        n: int = 16,
        strategy: Optional[RankingStrategy] = None
    ) -> List[Dict[str, Any]]:
        """
        Query: Selecciona los Top N agentes por rendimiento.

        Esta es una operación de LECTURA pura (Query).

        Args:
            agents_data: Lista de datos de agentes
            n: Número de agentes a seleccionar (default 16)
            strategy: Estrategia de ranking (opcional)

        Returns:
            Lista con Top N agentes rankeados

        Example:
            >>> top16 = await query_service.select_top_n(all_agents, n=16)
            >>> print(f"Selected {len(top16)} top agents")
        """
        logger.info(f"[QUERY] Seleccionando Top {n} agentes...")

        # Rankear todos los agentes
        ranked_agents = self.rank_agents(agents_data, strategy)

        # Seleccionar Top N
        top_n = ranked_agents[:n]

        logger.info(
            f"[QUERY] Top {n} seleccionados exitosamente. "
            f"ROI promedio: {sum(a.get('roi_7d', 0) for a in top_n) / len(top_n):.2%}"
        )

        return top_n

    def filter_agents_by_aum(
        self,
        agents_data: List[Dict[str, Any]],
        min_aum: float = 1000.0
    ) -> List[Dict[str, Any]]:
        """
        Query: Filtra agentes por AUM (Assets Under Management) mínimo.

        Esta es una operación de LECTURA pura (Query).

        Args:
            agents_data: Lista de datos de agentes
            min_aum: AUM mínimo requerido (default $1000)

        Returns:
            Lista de agentes que cumplen el filtro de AUM

        Example:
            >>> filtered = query_service.filter_agents_by_aum(agents_data, min_aum=5000.0)
            >>> print(f"Agents with AUM >= $5000: {len(filtered)}")
        """
        logger.info(f"[QUERY] Filtrando agentes con AUM >= ${min_aum}")

        filtered_agents = [
            agent for agent in agents_data if agent.get("balance_current", 0.0) >= min_aum
        ]

        logger.info(
            f"[QUERY] {len(filtered_agents)}/{len(agents_data)} agentes pasan filtro de AUM >= ${min_aum}"
        )

        return filtered_agents

    def filter_agents_by_positive_roi(self, agents_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Query: Filtra agentes con ROI positivo.

        Esta es una operación de LECTURA pura (Query).

        Args:
            agents_data: Lista de datos de agentes

        Returns:
            Lista de agentes con ROI > 0

        Example:
            >>> profitable = query_service.filter_agents_by_positive_roi(agents_data)
            >>> print(f"Profitable agents: {len(profitable)}")
        """
        logger.info("[QUERY] Filtrando agentes con ROI positivo")

        filtered_agents = [agent for agent in agents_data if agent.get("roi_7d", 0.0) > 0]

        logger.info(
            f"[QUERY] {len(filtered_agents)}/{len(agents_data)} agentes tienen ROI positivo"
        )

        return filtered_agents
