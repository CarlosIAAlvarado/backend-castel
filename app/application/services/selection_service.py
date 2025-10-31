from typing import List, Dict, Any, Tuple
from datetime import date, timedelta
import asyncio
import logging
from app.application.services.roi_7d_calculation_service import ROI7DCalculationService
from app.application.services.balance_query_service import BalanceQueryService
from app.application.services.bulk_roi_calculation_service import BulkROICalculationService
from app.domain.entities.top16_day import Top16Day
from app.domain.entities.roi_7d import ROI7D
from app.domain.repositories.top16_repository import Top16Repository
from app.domain.repositories.balance_repository import BalanceRepository
from app.config.database import database_manager
from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
from app.utils.collection_names import get_top16_collection_name

logger = logging.getLogger(__name__)


class SelectionService:
    """
    Servicio para la seleccion y ranking de agentes.

    VERSION 2.0 - NUEVA LOGICA ROI
    Ahora usa ROI7DCalculationService que calcula ROI basado en movements (closedPnl)
    en lugar de diferencia de balances.

    Responsabilidades:
    - Calcular ROI_7D de todos los agentes usando nueva logica
    - Rankear agentes por rendimiento
    - Seleccionar Top 16 diario
    - Guardar ranking en base de datos
    """

    def __init__(
        self,
        top16_repo: Top16Repository,
        balance_repo: BalanceRepository,
        roi_7d_service: ROI7DCalculationService,
        balance_query_service: BalanceQueryService
    ):
        """
        Constructor con inyeccion de dependencias.

        Args:
            top16_repo: Repositorio de Top16
            balance_repo: Repositorio de balances
            roi_7d_service: Servicio para calcular ROI_7D con nueva logica
            balance_query_service: Servicio de consultas de balances
        """
        self.top16_repo = top16_repo
        self.balance_repo = balance_repo
        self.roi_7d_service = roi_7d_service
        self.balance_query_service = balance_query_service

    def get_all_agents_from_balances(self, target_date: date) -> List[str]:
        """
        Obtiene la lista de todos los agentes únicos que tienen balances en la ventana ROI_7D.

        CAMBIO VERSION 2.2: Ahora busca en toda la ventana de 8 días (target_date - 7 hasta target_date)
        en lugar de solo en target_date.

        Args:
            target_date: Fecha objetivo (final de la ventana)

        Returns:
            Lista de userIds únicos (ej: ["OKX_JH1", "OKX_JH2", ...])
        """
        # Calcular ventana de 8 días
        window_start = target_date - timedelta(days=7)
        window_end = target_date

        logger.info(f"Buscando agentes en ventana: {window_start} -> {window_end}")

        # Buscar balances en toda la ventana
        balances = self.balance_repo.get_all_by_date_range(window_start, window_end)

        unique_agents = set()
        for balance in balances:
            # Usar user_id como identificador único (consistente entre días)
            if balance.user_id:
                unique_agents.add(balance.user_id)

        logger.info(
            f"Found {len(unique_agents)} unique userIds with balances in window "
            f"[{window_start} -> {window_end}]"
        )

        return list(unique_agents)

    async def _calculate_single_agent_roi(
        self,
        userId: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        Calcula el ROI_7D de un agente individual usando la NUEVA LOGICA.

        CAMBIO VERSION 2.1: Ahora usa userId como identificador.

        VERSION 2.0:
        - Usa ROI7DCalculationService en lugar de KPICalculationService
        - Calcula ROI basado en closedPnl de movements
        - Suma ROIs diarios en lugar de diferencia de balances

        Args:
            userId: Identificador único del agente (ej: "OKX_JH1")
            target_date: Fecha objetivo

        Returns:
            Diccionario con datos del agente, o None si falla
        """
        try:
            roi_7d_entity = await self.roi_7d_service.calculate_roi_7d(
                userId, target_date
            )

            if not roi_7d_entity:
                logger.debug(f"No ROI_7D data for userId {userId} on {target_date}")
                return None

            balance_current = self.balance_query_service.get_balance_by_agent_and_date(
                userId, target_date
            )

            return {
                "agent_id": userId,
                "userId": userId,
                "roi_7d": roi_7d_entity.roi_7d_total,
                "total_pnl": roi_7d_entity.total_pnl_7d,
                "balance_current": balance_current if balance_current else 0.0,
                "n_accounts": 1,
                "total_aum": balance_current if balance_current else 0.0,
                "total_trades_7d": roi_7d_entity.total_trades_7d,
                "positive_days": roi_7d_entity.positive_days,
                "negative_days": roi_7d_entity.negative_days
            }

        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.error(f"Error calculating ROI_7D for userId {userId}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.critical(f"Unexpected error calculating ROI_7D for userId {userId}: {e}", exc_info=True)
            raise

    async def calculate_all_agents_roi_7d(
        self,
        target_date: date,
        agent_ids: List[str] = None,
        min_aum: float = 0.01
    ) -> List[Dict[str, Any]]:
        """
        Calcula el ROI_7D de todos los agentes usando la NUEVA LOGICA.

        VERSION 2.0.1 - OPTIMIZADO CON asyncio.gather():
        - Usa ROI7DCalculationService.calculate_for_all_agents()
        - Calcula ROI basado en closedPnl de movements
        - Procesamiento PARALELO con asyncio.gather() (reduce tiempo O(n) -> O(1))
        - Usa cache de daily_roi_calculation

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de agentes a evaluar (opcional, si None obtiene todos)
            min_aum: Balance minimo requerido para considerar al agente viable (default: 0.01)

        Returns:
            Lista de diccionarios con agent_id, roi_7d, total_pnl, balance, n_accounts, aum
        """
        if agent_ids is None:
            agent_ids = self.get_all_agents_from_balances(target_date)

        logger.info(f"Calculating ROI_7D for {len(agent_ids)} agents on {target_date} (PARALLEL)")

        # Crear tareas para todos los agentes (procesamiento paralelo)
        tasks = [
            self._calculate_single_agent_roi(agent_id, target_date)
            for agent_id in agent_ids
        ]

        # Ejecutar todas las tareas en paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados y filtrar
        agents_data = []
        errors_count = 0

        for i, result in enumerate(results):
            # Manejar excepciones capturadas por gather
            if isinstance(result, Exception):
                agent_id = agent_ids[i]
                logger.error(
                    f"Error calculating ROI for agent {agent_id}: {result}",
                    exc_info=result
                )
                errors_count += 1
                continue

            # Filtrar resultados None o con AUM insuficiente
            if result is not None:
                if result.get("total_aum", 0.0) > min_aum:
                    agents_data.append(result)
                else:
                    logger.debug(
                        f"Filtered out agent {result.get('agent_id')} with "
                        f"total_aum={result.get('total_aum', 0.0)} (< {min_aum})"
                    )

        logger.info(
            f"ROI_7D calculation complete (PARALLEL): {len(agents_data)}/{len(agent_ids)} agents "
            f"passed min_aum filter, {errors_count} errors"
        )

        return agents_data

    async def calculate_all_agents_roi_7d_ULTRA_FAST(
        self,
        target_date: date,
        agent_ids: List[str] = None,
        min_aum: float = 0.01,
        window_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        VERSION 4.0 - ULTRA OPTIMIZADO con Bulk Processing + Ventanas Dinámicas.

        Calcula ROI de TODOS los agentes en 2 queries en vez de ~800, con ventana configurable.

        MEJORA DE RENDIMIENTO:
        - Antes: ~15-20 minutos (usando _calculate_single_agent_roi)
        - Ahora: ~2-4 minutos (usando bulk operations)

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de agentes a evaluar (opcional, si None obtiene todos)
            min_aum: Balance minimo requerido (default: 0.01)
            window_days: Ventana de días para ROI (3, 5, 7, 10, 15, 30). Default: 7

        Returns:
            Lista de diccionarios con agent_id, roi_7d, total_pnl, etc.
        """
        if agent_ids is None:
            agent_ids = self.get_all_agents_from_balances(target_date)

        logger.info(f"Calculando ROI_{window_days}D para {len(agent_ids)} agentes (MODO ULTRA RAPIDO)")

        # Crear servicio bulk
        db = database_manager.get_database()
        bulk_service = BulkROICalculationService(db)

        # Calcular ROI para TODOS los agentes de una sola vez
        bulk_results = bulk_service.calculate_bulk_roi_7d(agent_ids, target_date, window_days=window_days)

        # Convertir a formato esperado
        agents_data = []
        for user_id, roi_data in bulk_results.items():
            # Filtrar por min_aum
            if roi_data["balance_current"] > min_aum:
                agents_data.append({
                    "agent_id": user_id,
                    "userId": user_id,
                    "roi_7d": roi_data["roi_7d_total"],
                    "total_pnl": roi_data["total_pnl_7d"],
                    "balance_current": roi_data["balance_current"],
                    "n_accounts": 1,
                    "total_aum": roi_data["balance_current"],
                    "total_trades_7d": roi_data["total_trades_7d"],
                    "positive_days": roi_data["positive_days"],
                    "negative_days": roi_data["negative_days"]
                })

        logger.info(
            f"ROI_{window_days}D calculation complete (ULTRA FAST): {len(agents_data)}/{len(agent_ids)} agents "
            f"passed min_aum filter"
        )

        return agents_data

    def rank_agents_by_roi_7d(
        self,
        agents_data: List[Dict[str, Any]],
        window_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Rankea agentes por ROI de mayor a menor.

        VERSION 2.0: Soporta ventanas dinamicas (3d, 5d, 7d, 10d, 15d, 30d)

        Args:
            agents_data: Lista de datos de agentes
            window_days: Ventana de dias para ROI (default: 7)

        Returns:
            Lista ordenada con rank asignado
        """
        roi_field = f"roi_{window_days}d"
        sorted_agents = sorted(
            agents_data,
            key=lambda x: x.get(roi_field, 0.0),
            reverse=True
        )

        for rank, agent in enumerate(sorted_agents, start=1):
            agent["rank"] = rank

        return sorted_agents

    async def select_top_16(
        self,
        target_date: date,
        agent_ids: List[str] = None,
        window_days: int = 7
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Selecciona los Top 16 agentes con mejor ROI usando NUEVA LOGICA.

        VERSION 5.0 - CON EXPULSION AUTOMATICA:
        - Usa bulk processing para calcular ROI (2 queries en vez de ~800)
        - ROI = suma de ROIs diarios (no diferencia de balances)
        - Soporta ventanas dinámicas (3, 5, 7, 10, 15, 30 días)
        - EXPULSION AUTOMATICA: Agentes con 3 días consecutivos de pérdida son excluidos del Top 16

        Proceso:
        1. Calcula ROI de todos los agentes con BULK OPERATIONS
        2. Filtra agentes con 3 días consecutivos de pérdida (EXPULSION AUTOMATICA)
        3. Rankea por rendimiento
        4. Selecciona los primeros 16

        Args:
            target_date: Fecha objetivo
            agent_ids: Lista de agentes a evaluar (opcional)
            window_days: Ventana de días para ROI (3, 5, 7, 10, 15, 30). Default: 7

        Returns:
            Tupla con (top_16, all_ranked)
        """
        # USA LA VERSION ULTRA RAPIDA
        agents_data = await self.calculate_all_agents_roi_7d_ULTRA_FAST(
            target_date, agent_ids, window_days=window_days
        )

        if not agents_data:
            logger.warning(f"No agents data found for {target_date}")
            return [], []

        # FILTRAR agentes con condiciones de expulsión automática
        agents_eligible = []
        excluded_agents_3day = []
        excluded_agents_stop_loss = []
        roi_field = f"roi_{window_days}d"

        for agent in agents_data:
            agent_id = agent["agent_id"]
            roi = agent.get(roi_field, 0.0)

            # CONDICION 1: Stop Loss de -10%
            if roi < -0.10:
                excluded_agents_stop_loss.append(agent_id)
                logger.warning(
                    f"[EXPULSION_STOP_LOSS] {agent_id} excluido del Top 16 por Stop Loss "
                    f"(ROI: {roi*100:.2f}% < -10%)"
                )
                continue

            # CONDICION 2: 3 días consecutivos de pérdida
            has_three_consecutive = self._check_three_consecutive_losses(agent_id, target_date)
            if has_three_consecutive:
                excluded_agents_3day.append(agent_id)
                logger.warning(
                    f"[EXPULSION_3_DIAS] {agent_id} excluido del Top 16 por 3 días consecutivos de pérdida "
                    f"(ROI: {roi*100:.2f}%)"
                )
                continue

            # Agente pasa todas las validaciones
            agents_eligible.append(agent)

        if excluded_agents_stop_loss:
            logger.info(f"[EXPULSION_STOP_LOSS] Total excluidos: {len(excluded_agents_stop_loss)} - {excluded_agents_stop_loss}")
        if excluded_agents_3day:
            logger.info(f"[EXPULSION_3_DIAS] Total excluidos: {len(excluded_agents_3day)} - {excluded_agents_3day}")

        # Rankear solo los agentes que pasaron el filtro
        ranked_agents = self.rank_agents_by_roi_7d(agents_eligible, window_days=window_days)

        top_16 = ranked_agents[:16]

        if top_16:
            logger.info(
                f"Top 16 selected for {target_date} (window={window_days}d): "
                f"best_roi={top_16[0]['roi_7d']:.4f}, worst_roi={top_16[-1]['roi_7d']:.4f}"
            )
        else:
            logger.warning(f"No agents qualified for Top 16 on {target_date} (window={window_days}d)")

        return top_16, ranked_agents

    def save_top16_to_database(
        self,
        target_date: date,
        top_16: List[Dict[str, Any]],
        casterly_agent_ids: List[str] = None,
        window_days: int = 7
    ) -> List[Top16Day]:
        """
        Guarda el ranking Top 16 en la base de datos con colección dinámica.

        Args:
            target_date: Fecha del ranking
            top_16: Lista de los top 16 agentes
            casterly_agent_ids: IDs de agentes que estan dentro de Casterly Rock (opcional)
            window_days: Ventana de días usada (determina colección destino). Default: 7

        Returns:
            Lista de Top16Day guardados
        """
        if casterly_agent_ids is None:
            casterly_agent_ids = []

        # Crear repositorio con nombre de colección dinámico
        collection_name = get_top16_collection_name(window_days)
        dynamic_repo = Top16RepositoryImpl(collection_name)

        top16_entities = []

        for agent_data in top_16:
            is_in_casterly = agent_data["agent_id"] in casterly_agent_ids

            # Construir el diccionario base para Top16Day
            entity_data = {
                "date": target_date,
                "rank": agent_data["rank"],
                "agent_id": agent_data["agent_id"],
                "n_accounts": agent_data.get("n_accounts", 0),
                "total_aum": agent_data.get("total_aum", 0.0),
                "is_in_casterly": is_in_casterly
            }

            # Agregar el campo de ROI dinámico según la ventana
            roi_field = f"roi_{window_days}d"
            if roi_field in agent_data:
                entity_data[roi_field] = agent_data[roi_field]
            elif "roi_7d" in agent_data:
                # Fallback: si no existe el campo específico, usar roi_7d
                entity_data[roi_field] = agent_data["roi_7d"]

            top16_entity = Top16Day(**entity_data)
            top16_entities.append(top16_entity)

        saved_entities = dynamic_repo.create_batch(top16_entities)

        logger.info(f"Top16 guardado en colección {collection_name} para {target_date}")

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

    def _calculate_roi_total(self, agent_id: str, current_date: date) -> float:
        """
        Calcula el ROI total acumulado del agente desde el inicio hasta la fecha actual.

        Args:
            agent_id: ID del agente
            current_date: Fecha actual

        Returns:
            ROI total como decimal (ej: 0.15 = 15%)
        """
        try:
            # Obtener el balance actual del agente
            db = database_manager.get_database()
            agent_roi_collection = db.agent_roi_7d

            # Buscar el ROI más reciente del agente hasta la fecha actual
            agent_roi_doc = agent_roi_collection.find_one({
                "userId": agent_id,
                "target_date": {"$lte": current_date.isoformat()}
            }, sort=[("target_date", -1)])

            if not agent_roi_doc:
                return 0.0

            # Calcular ROI total: suma de todos los ROIs diarios
            daily_rois = agent_roi_doc.get("daily_rois", [])
            if not daily_rois:
                return 0.0

            # Sumar todos los ROI diarios para obtener el ROI acumulado
            total_roi = sum(day.get("roi", 0.0) for day in daily_rois)

            return total_roi

        except Exception as e:
            logger.error(f"Error calculando ROI total para {agent_id}: {str(e)}")
            return 0.0

    def _check_three_consecutive_losses(self, agent_id: str, current_date: date) -> bool:
        """
        Verifica si un agente tuvo 3 días consecutivos de pérdida.

        Args:
            agent_id: ID del agente
            current_date: Fecha actual

        Returns:
            True si tuvo 3+ días consecutivos de pérdida, False en caso contrario
        """
        try:
            db = database_manager.get_database()
            # Buscar en todas las colecciones de ROI para encontrar el registro más reciente
            # Intentar primero con agent_roi_7d (colección por defecto)
            from app.utils.collection_names import get_roi_collection_name

            # Intentar con diferentes ventanas para encontrar datos del agente
            for window in [7, 3, 5, 10, 15, 30]:
                collection_name = get_roi_collection_name(window)
                agent_roi_collection = db[collection_name]

                agent_roi_doc = agent_roi_collection.find_one({
                    "userId": agent_id,
                    "target_date": current_date.isoformat()
                })

                if agent_roi_doc:
                    break

            if not agent_roi_doc:
                logger.debug(f"No se encontraron datos de ROI para {agent_id} en {current_date}")
                return False

            daily_rois = agent_roi_doc.get("daily_rois", [])
            if len(daily_rois) < 3:
                return False

            # Ordenar por fecha para asegurar orden cronológico
            daily_rois_sorted = sorted(daily_rois, key=lambda x: x["date"])

            # Buscar 3 días consecutivos de pérdida
            consecutive_losses = 0
            max_consecutive_losses = 0

            for day in daily_rois_sorted:
                if day["roi"] < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                else:
                    consecutive_losses = 0

            has_three_consecutive = max_consecutive_losses >= 3

            if has_three_consecutive:
                logger.info(f"[3_DIAS_PERDIDA] {agent_id} tuvo {max_consecutive_losses} días consecutivos de pérdida")

            return has_three_consecutive

        except Exception as e:
            logger.error(f"Error verificando 3 días consecutivos para {agent_id}: {str(e)}")
            return False

    def _determine_rotation_reason(
        self,
        agent_out: Top16Day,
        agent_in: Top16Day,
        current_top16: List[Top16Day],
        current_date: date
    ) -> tuple:
        """
        Determina la razón específica de por qué ocurrió una rotación.

        CONDICIONES DE ROTACIÓN (verificadas en orden de prioridad):
        1. STOP_LOSS: ROI del agente saliente cayó por debajo de -10%
        2. THREE_DAYS_FALL: Agente tuvo 3 o más días consecutivos de pérdida
        3. BETTER_PERFORMER_AVAILABLE: Agente entrante tiene mejor ROI que el saliente
        4. WINDOW_SHIFT_IMPACT: Agente saliente perdió días rentables antiguos de la ventana móvil
        5. DAILY_ROTATION: ROIs similares, rotación por rebalanceo

        Args:
            agent_out: Agente que salió del Top 16
            agent_in: Agente que entró al Top 16
            current_top16: Lista completa del Top 16 actual
            current_date: Fecha actual de la rotación

        Returns:
            Tupla con (reason_code, reason_details)
        """
        from app.domain.entities.rotation_log import RotationReason

        roi_out = agent_out.roi_7d
        roi_in = agent_in.roi_7d

        # PRIORIDAD 1: Stop Loss de -10%
        if roi_out < -0.10:
            reason = RotationReason.STOP_LOSS
            details = (
                f"STOP LOSS activado: {agent_out.agent_id} cayó a {roi_out*100:.2f}% (debajo del límite de -10%). "
                f"Entra {agent_in.agent_id} con {roi_in*100:.2f}%"
            )
            logger.warning(f"[STOP_LOSS] {agent_out.agent_id} con ROI {roi_out*100:.2f}% < -10%")
            return reason, details

        # PRIORIDAD 2: 3 días consecutivos de pérdida
        if self._check_three_consecutive_losses(agent_out.agent_id, current_date):
            reason = RotationReason.THREE_DAYS_FALL
            details = (
                f"Caída por 3 días consecutivos de pérdida: {agent_out.agent_id} ({roi_out*100:.2f}%) "
                f"tuvo 3+ días seguidos negativos. Entra {agent_in.agent_id} con {roi_in*100:.2f}%"
            )
            logger.warning(f"[THREE_DAYS_FALL] {agent_out.agent_id} tuvo 3+ días consecutivos de pérdida")
            return reason, details

        # PRIORIDAD 3: El agente entrante tiene MEJOR ROI que el saliente
        if roi_in > roi_out:
            reason = RotationReason.BETTER_PERFORMER_AVAILABLE
            details = f"Reemplazado por mejor rendimiento: {agent_in.agent_id} con {roi_in*100:.2f}% supera a {agent_out.agent_id} con {roi_out*100:.2f}%"

        # PRIORIDAD 4: El agente saliente tenía buen ROI pero cayó por pérdida de días antiguos
        elif roi_out > roi_in:
            reason = RotationReason.WINDOW_SHIFT_IMPACT
            details = (
                f"{agent_out.agent_id} perdió días rentables antiguos y cayó de {roi_out*100:.2f}% a fuera del Top 16. "
                f"Entra {agent_in.agent_id} con {roi_in*100:.2f}%. "
                f"(Explicacion: El ROI se calcula con ventana movil de 7 dias. Cuando un dia antiguo rentable sale del calculo, "
                f"el ROI actual puede bajar aunque no haya perdido 3 dias seguidos ni llegado a -10%)"
            )

        # PRIORIDAD 5: ROIs similares
        else:
            reason = RotationReason.DAILY_ROTATION
            details = f"Rotación por rebalanceo: {agent_out.agent_id} ({roi_out*100:.2f}%) sale y entra {agent_in.agent_id} ({roi_in*100:.2f}%)"

        return reason, details

    def detect_rotations(
        self,
        previous_top16: List[Top16Day],
        current_top16: List[Top16Day],
        current_date: date
    ) -> List[Dict[str, Any]]:
        """
        Detecta rotaciones comparando Top 16 de dos días consecutivos.

        Identifica qué agentes salieron del Top 16 y qué agentes entraron.
        Las rotaciones se emparejan: cada agente que sale se empareja con uno que entra.

        Args:
            previous_top16: Top 16 del día anterior
            current_top16: Top 16 del día actual
            current_date: Fecha del día actual

        Returns:
            Lista de rotaciones detectadas: [
                {
                    "date": date,
                    "agent_out": "agent_id_saliente",
                    "agent_in": "agent_id_entrante",
                    "reason": "daily_rotation",
                    "roi_7d_out": 0.05,
                    "roi_7d_in": 0.08,
                    "rank_out": 16,
                    "rank_in": 15
                }
            ]
        """
        # Extraer solo agentes que estaban en Casterly Rock
        previous_agents = {
            agent.agent_id: agent
            for agent in previous_top16
            if agent.is_in_casterly
        }

        current_agents = {
            agent.agent_id: agent
            for agent in current_top16
            if agent.is_in_casterly
        }

        # Detectar cambios
        agents_out_ids = set(previous_agents.keys()) - set(current_agents.keys())  # Salieron
        agents_in_ids = set(current_agents.keys()) - set(previous_agents.keys())    # Entraron

        logger.info(f"[DETECT_ROTATIONS] Fecha: {current_date}")
        logger.info(f"[DETECT_ROTATIONS]   Previous Top16 (Casterly): {len(previous_agents)} agentes")
        logger.info(f"[DETECT_ROTATIONS]   Current Top16 (Casterly): {len(current_agents)} agentes")
        logger.info(f"[DETECT_ROTATIONS]   Agentes que SALIERON: {len(agents_out_ids)} - {list(agents_out_ids)}")
        logger.info(f"[DETECT_ROTATIONS]   Agentes que ENTRARON: {len(agents_in_ids)} - {list(agents_in_ids)}")

        # Si no hay cambios, no hay rotaciones
        if not agents_out_ids and not agents_in_ids:
            logger.info(f"[DETECT_ROTATIONS] No se detectaron rotaciones para {current_date}")
            return []

        # Emparejar agentes salientes con entrantes
        rotations = []
        agents_out_list = sorted(agents_out_ids)
        agents_in_list = sorted(agents_in_ids)

        # Crear rotaciones emparejadas
        max_rotations = max(len(agents_out_list), len(agents_in_list))

        for i in range(max_rotations):
            agent_out_id = agents_out_list[i] if i < len(agents_out_list) else None
            agent_in_id = agents_in_list[i] if i < len(agents_in_list) else None

            # Obtener datos de los agentes
            agent_out = previous_agents.get(agent_out_id) if agent_out_id else None
            agent_in = current_agents.get(agent_in_id) if agent_in_id else None

            # Determinar razón específica de la rotación
            if agent_out and agent_in:
                reason, reason_details = self._determine_rotation_reason(
                    agent_out, agent_in, current_top16, current_date
                )
            else:
                from app.domain.entities.rotation_log import RotationReason
                reason = RotationReason.DAILY_ROTATION
                reason_details = "Rotación diaria estándar"

            # Calcular ROI total del agente saliente (desde inicio hasta ahora)
            roi_total_out = self._calculate_roi_total(agent_out_id, current_date) if agent_out_id else 0.0

            rotation = {
                "date": current_date,
                "agent_out": agent_out_id,
                "agent_in": agent_in_id,
                "reason": reason,
                "reason_details": reason_details,
                "roi_7d_out": agent_out.roi_7d if agent_out else None,
                "roi_total_out": roi_total_out,
                "roi_7d_in": agent_in.roi_7d if agent_in else None,
                "rank_out": agent_out.rank if agent_out else None,
                "rank_in": agent_in.rank if agent_in else None,
                "n_accounts": agent_in.n_accounts if agent_in else 0,
                "total_aum": agent_in.total_aum if agent_in else 0.0
            }

            rotations.append(rotation)

        logger.info(
            f"Detectadas {len(rotations)} rotaciones para {current_date}: "
            f"{len(agents_out_ids)} salieron, {len(agents_in_ids)} entraron"
        )

        return rotations

    def detect_rank_changes(
        self,
        previous_top16: List[Top16Day],
        current_top16: List[Top16Day],
        current_date: date
    ) -> List[Dict[str, Any]]:
        """
        Detecta cambios de ranking DENTRO del Top 16.

        A diferencia de detect_rotations (que detecta entradas/salidas),
        este método detecta movimientos de posición de agentes que se
        mantienen en el Top 16 pero cambian de rank.

        Ejemplo:
        - Día anterior: Agente A en rank 1
        - Día actual: Agente A en rank 3
        - Resultado: Rank change de -2 (bajó 2 posiciones)

        Args:
            previous_top16: Top 16 del día anterior
            current_top16: Top 16 del día actual
            current_date: Fecha del día actual

        Returns:
            Lista de cambios de ranking: [
                {
                    "date": date,
                    "agent_id": "agent_id",
                    "previous_rank": 1,
                    "current_rank": 3,
                    "rank_change": -2,
                    "previous_roi": 0.05,
                    "current_roi": 0.03,
                    "roi_change": -0.02,
                    "is_in_casterly": True
                }
            ]
        """
        # Crear mapas de agentes por agent_id
        previous_agents = {
            agent.agent_id: agent
            for agent in previous_top16
            if agent.is_in_casterly
        }

        current_agents = {
            agent.agent_id: agent
            for agent in current_top16
            if agent.is_in_casterly
        }

        # Encontrar agentes que están en ambos días (permanecen en Top 16)
        common_agents = set(previous_agents.keys()) & set(current_agents.keys())

        if not common_agents:
            logger.info(f"No hay agentes comunes entre días para detectar cambios de rank en {current_date}")
            return []

        # Detectar cambios de ranking
        rank_changes = []

        for agent_id in common_agents:
            prev_agent = previous_agents[agent_id]
            curr_agent = current_agents[agent_id]

            # Calcular cambio de ranking (positivo = subió, negativo = bajó)
            # Nota: Un agente que va de rank 5 a rank 3 SUBE (mejora), entonces rank_change = +2
            rank_change = prev_agent.rank - curr_agent.rank

            # Solo registrar si hubo cambio
            if rank_change != 0:
                roi_change = curr_agent.roi_7d - prev_agent.roi_7d

                rank_change_data = {
                    "date": current_date,
                    "agent_id": agent_id,
                    "previous_rank": prev_agent.rank,
                    "current_rank": curr_agent.rank,
                    "rank_change": rank_change,
                    "previous_roi": prev_agent.roi_7d,
                    "current_roi": curr_agent.roi_7d,
                    "roi_change": roi_change,
                    "is_in_casterly": curr_agent.is_in_casterly
                }

                rank_changes.append(rank_change_data)

        # Ordenar por cambio absoluto (los cambios más grandes primero)
        rank_changes.sort(key=lambda x: abs(x["rank_change"]), reverse=True)

        logger.info(
            f"Detectados {len(rank_changes)} cambios de ranking para {current_date}: "
            f"{sum(1 for rc in rank_changes if rc['rank_change'] > 0)} subieron, "
            f"{sum(1 for rc in rank_changes if rc['rank_change'] < 0)} bajaron"
        )

        return rank_changes

    async def process_daily_selection(
        self,
        target_date: date,
        casterly_agent_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Proceso completo de seleccion diaria usando NUEVA LOGICA.

        VERSION 2.0:
        - Usa nueva logica de calculo basada en closedPnl

        Proceso:
        1. Calcula ROI_7D de todos los agentes (nueva logica)
        2. Rankea por rendimiento
        3. Selecciona Top 16
        4. Guarda en base de datos

        Args:
            target_date: Fecha objetivo
            casterly_agent_ids: IDs de agentes en Casterly Rock (opcional)

        Returns:
            Diccionario con resultados del proceso
        """
        logger.info(f"Starting daily selection process for {target_date}")

        top_16, all_ranked = await self.select_top_16(target_date)

        if not top_16:
            logger.warning(f"No agents found with data for {target_date}")
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

        logger.info(
            f"Daily selection complete for {target_date}: "
            f"{len(all_ranked)} agents evaluated, Top 16 saved"
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
