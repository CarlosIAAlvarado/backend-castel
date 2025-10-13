from typing import List, Dict, Any, Tuple
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.application.services.kpi_calculation_service import KPICalculationService
from app.application.services.data_processing_service import DataProcessingService
from app.domain.entities.top16_day import Top16Day
from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl


class SelectionService:
    """
    Servicio para la seleccion y ranking de agentes.

    Responsabilidades:
    - Calcular ROI_7D de todos los agentes
    - Rankear agentes por rendimiento
    - Seleccionar Top 16 diario
    - Guardar ranking en base de datos
    """

    def __init__(self):
        self.top16_repo = Top16RepositoryImpl()
        self.balance_repo = BalanceRepositoryImpl()

    def get_all_agents_from_balances(self, target_date: date) -> List[str]:
        """
        Obtiene la lista de todos los agentes unicos que tienen balances en una fecha.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de agent_ids unicos
        """
        balances = self.balance_repo.get_all_by_date(target_date)

        unique_agents = set()
        for balance in balances:
            # Usar account_id (formato futures-XXX) agregado por migracion
            if balance.account_id:
                unique_agents.add(balance.account_id)

        return list(unique_agents)

    def _calculate_single_agent_roi(
        self,
        agent_id: str,
        target_date: date,
        balances_cache: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Calcula el ROI_7D de un agente individual.
        Metodo auxiliar para procesamiento paralelo.

        Args:
            agent_id: ID del agente
            target_date: Fecha objetivo
            balances_cache: Diccionario de balances pre-cargados

        Returns:
            Diccionario con datos del agente
        """
        try:
            roi_data = KPICalculationService.calculate_roi_7d(
                agent_id=agent_id,
                target_date=target_date,
                balances_cache=balances_cache
            )

            balance_current = roi_data.get("balance_current", 0.0)
            roi_7d = roi_data.get("roi_7d", 0.0)
            total_pnl = roi_data.get("total_pnl_7d", 0.0)

            return {
                "agent_id": agent_id,
                "roi_7d": roi_7d,
                "total_pnl": total_pnl,
                "balance_current": balance_current,
                "n_accounts": 1,
                "total_aum": balance_current
            }

        except Exception as e:
            print(f"Error calculating ROI_7D for agent {agent_id}: {e}")
            return None

    def calculate_all_agents_roi_7d(
        self,
        target_date: date,
        agent_ids: List[str] = None,
        max_workers: int = 30,
        min_aum: float = 0.01
    ) -> List[Dict[str, Any]]:
        """
        Calcula el ROI_7D de todos los agentes en paralelo.

        Optimizado para cargar balances una sola vez y compartirlos entre threads.

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de agentes a evaluar (opcional, si None obtiene todos)
            max_workers: Numero de threads paralelos (default: 30)
            min_aum: Balance minimo requerido para considerar al agente viable (default: 0.01)

        Returns:
            Lista de diccionarios con agent_id, roi_7d, total_pnl, balance, n_accounts, aum
        """
        if agent_ids is None:
            agent_ids = self.get_all_agents_from_balances(target_date)

        from app.application.services.data_processing_service import DataProcessingService
        balances_cache = DataProcessingService.get_all_balances_by_date(target_date)

        agents_data = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_agent = {
                executor.submit(self._calculate_single_agent_roi, agent_id, target_date, balances_cache): agent_id
                for agent_id in agent_ids
            }

            for future in as_completed(future_to_agent):
                result = future.result()
                if result is not None:
                    if result.get("total_aum", 0.0) > min_aum:
                        agents_data.append(result)
                    else:
                        print(f"Filtered out agent {result.get('agent_id')} with total_aum={result.get('total_aum', 0.0)} (< {min_aum})")

        return agents_data

    def rank_agents_by_roi_7d(
        self,
        agents_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rankea agentes por ROI_7D de mayor a menor.

        Args:
            agents_data: Lista de datos de agentes

        Returns:
            Lista ordenada con rank asignado
        """
        sorted_agents = sorted(
            agents_data,
            key=lambda x: x["roi_7d"],
            reverse=True
        )

        for rank, agent in enumerate(sorted_agents, start=1):
            agent["rank"] = rank

        return sorted_agents

    def select_top_16(
        self,
        target_date: date,
        agent_ids: List[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Selecciona los Top 16 agentes con mejor ROI_7D.

        Proceso:
        1. Calcula ROI_7D de todos los agentes
        2. Rankea por rendimiento
        3. Selecciona los primeros 16

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de agentes a evaluar (opcional)

        Returns:
            Tupla con (top_16, all_ranked)
        """
        agents_data = self.calculate_all_agents_roi_7d(target_date, agent_ids)

        if not agents_data:
            return [], []

        ranked_agents = self.rank_agents_by_roi_7d(agents_data)

        top_16 = ranked_agents[:16]

        return top_16, ranked_agents

    def save_top16_to_database(
        self,
        target_date: date,
        top_16: List[Dict[str, Any]],
        casterly_agent_ids: List[str] = None
    ) -> List[Top16Day]:
        """
        Guarda el ranking Top 16 en la base de datos.

        Args:
            target_date: Fecha del ranking
            top_16: Lista de los top 16 agentes
            casterly_agent_ids: IDs de agentes que estan dentro de Casterly Rock (opcional)

        Returns:
            Lista de Top16Day guardados
        """
        if casterly_agent_ids is None:
            casterly_agent_ids = []

        top16_entities = []

        for agent_data in top_16:
            is_in_casterly = agent_data["agent_id"] in casterly_agent_ids

            top16_entity = Top16Day(
                date=target_date,
                rank=agent_data["rank"],
                agent_id=agent_data["agent_id"],
                roi_7d=agent_data["roi_7d"],
                roi_30d=None,
                n_accounts=agent_data.get("n_accounts", 0),
                total_aum=agent_data.get("total_aum", 0.0),
                is_in_casterly=is_in_casterly
            )

            top16_entities.append(top16_entity)

        saved_entities = self.top16_repo.create_batch(top16_entities)

        return saved_entities

    def get_top16_by_date(self, target_date: date) -> List[Top16Day]:
        """
        Obtiene el ranking Top 16 guardado de una fecha.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de Top16Day
        """
        return self.top16_repo.get_by_date(target_date)

    def get_agents_in_casterly(self, target_date: date) -> List[Top16Day]:
        """
        Obtiene solo los agentes que estan dentro de Casterly Rock en una fecha.

        Args:
            target_date: Fecha objetivo

        Returns:
            Lista de Top16Day donde is_in_casterly=True
        """
        return self.top16_repo.get_in_casterly_by_date(target_date)

    def process_daily_selection(
        self,
        target_date: date,
        casterly_agent_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Proceso completo de seleccion diaria:
        1. Calcula ROI_7D de todos los agentes
        2. Rankea por rendimiento
        3. Selecciona Top 16
        4. Guarda en base de datos

        Args:
            target_date: Fecha objetivo
            casterly_agent_ids: IDs de agentes en Casterly Rock (opcional)

        Returns:
            Diccionario con resultados del proceso
        """
        top_16, all_ranked = self.select_top_16(target_date)

        if not top_16:
            return {
                "success": False,
                "message": "No agents found with data",
                "target_date": target_date.isoformat()
            }

        saved_top16 = self.save_top16_to_database(
            target_date=target_date,
            top_16=top_16,
            casterly_agent_ids=casterly_agent_ids
        )

        return {
            "success": True,
            "target_date": target_date.isoformat(),
            "total_agents_evaluated": len(all_ranked),
            "top_16_count": len(saved_top16),
            "top_16": [
                {
                    "rank": t.rank,
                    "agent_id": t.agent_id,
                    "roi_7d": t.roi_7d,
                    "is_in_casterly": t.is_in_casterly
                }
                for t in saved_top16
            ]
        }
