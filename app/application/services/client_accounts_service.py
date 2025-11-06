"""
Servicio para la gestion de cuentas de clientes con copytrading.

Este servicio maneja:
- Distribucion inicial de 1000 cuentas entre Top 16 agentes
- Calculo de ROI basado en el desempeno de los agentes
- Re-balanceo cada 7 dias
- Rotacion de agentes cuando fallan
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo.database import Database
from pymongo import UpdateOne, InsertOne
from app.utils.collection_names import get_top16_collection_name

logger = logging.getLogger(__name__)


class ClientAccountsService:
    """Servicio para gestion de cuentas de clientes."""

    def __init__(self, db: Database):
        """
        Inicializa el servicio.

        Args:
            db: Instancia de base de datos MongoDB
        """
        self.db = db
        self.cuentas_trading_col = db.cuentas_clientes_trading
        self.historial_col = db.historial_asignaciones_clientes
        self.snapshot_col = db.distribucion_cuentas_snapshot
        self.rebalanceo_log_col = db.rebalanceo_log
        self.top16_col = db.top16_by_day  # Tabla de Top 16 agentes

    def initialize_client_accounts(
        self, simulation_id: str, num_accounts: int = 1000, num_top_agents: int = 16
    ) -> Dict[str, Any]:
        """
        Inicializa las cuentas de clientes para una simulacion.

        Distribuye equitativamente las cuentas entre los Top N agentes.

        Si ya existen cuentas, las resetea automaticamente para una nueva
        simulacion independiente (mantiene balance_inicial en $1,000).

        Args:
            simulation_id: ID de la simulacion
            num_accounts: Numero de cuentas a distribuir (default: 1000)
            num_top_agents: Numero de mejores agentes a usar (default: 16)

        Returns:
            Dict con resumen de la distribucion inicial
        """
        logger.info(f"Iniciando distribucion de {num_accounts} cuentas para simulacion {simulation_id}")

        existing_accounts = self.cuentas_trading_col.count_documents({})

        if existing_accounts > 0:
            logger.info(
                f"Se encontraron {existing_accounts} cuentas existentes. "
                "Reseteando para nueva simulacion independiente..."
            )
            reset_result = self.reset_simulation_accounts()
            logger.info(f"Reset completado: {reset_result['cuentas_reseteadas']} cuentas reseteadas")

        # 1. Obtener Top N agentes ordenados por ROI
        logger.info("Paso 1: Obteniendo Top agentes...")
        top_agents = self._get_top_agents(simulation_id, num_top_agents)
        logger.info(f"Top agentes obtenidos: {len(top_agents)}")
        if len(top_agents) < num_top_agents:
            raise ValueError(f"Se requieren {num_top_agents} agentes pero solo hay {len(top_agents)} disponibles")

        # 2. Obtener cuentas de clientes disponibles
        logger.info(f"Paso 2: Obteniendo {num_accounts} cuentas de clientes...")
        client_accounts = self._get_client_accounts(num_accounts)
        logger.info(f"Cuentas de clientes obtenidas: {len(client_accounts)}")
        if len(client_accounts) < num_accounts:
            raise ValueError(f"Se requieren {num_accounts} cuentas pero solo hay {len(client_accounts)} disponibles")

        # 3. Distribuir cuentas equitativamente
        logger.info("Paso 3: Distribuyendo cuentas equitativamente...")
        distribution = self._distribute_accounts_equitably(client_accounts, top_agents)
        logger.info(f"Distribucion completada: {len(distribution)} asignaciones")

        # 4. Crear/actualizar registros en cuentas_clientes_trading (bulk upsert)
        fecha_asignacion = datetime.utcnow()
        bulk_operations = []

        for account_data in distribution:
            cuenta_existente = self.cuentas_trading_col.find_one({"cuenta_id": account_data["cuenta_id"]})

            if cuenta_existente:
                bulk_operations.append(
                    UpdateOne(
                        {"cuenta_id": account_data["cuenta_id"]},
                        {
                            "$set": {
                                "agente_actual": account_data["agente_id"],
                                "fecha_asignacion_agente": fecha_asignacion,
                                "roi_agente_al_asignar": account_data["roi_agente"],
                                "updated_at": fecha_asignacion,
                            }
                        },
                    )
                )
            else:
                trading_account = {
                    "cuenta_id": account_data["cuenta_id"],
                    "nombre_cliente": account_data["nombre_cliente"],
                    "balance_inicial": 1000.0,
                    "balance_actual": 1000.0,
                    "roi_total": 0.0,
                    "win_rate": 0.0,
                    "agente_actual": account_data["agente_id"],
                    "fecha_asignacion_agente": fecha_asignacion,
                    "roi_agente_al_asignar": account_data["roi_agente"],
                    "roi_acumulado_con_agente": 0.0,
                    "numero_cambios_agente": 0,
                    "estado": "activo",
                    "created_at": fecha_asignacion,
                    "updated_at": fecha_asignacion,
                }
                bulk_operations.append(InsertOne(trading_account))

        if bulk_operations:
            result = self.cuentas_trading_col.bulk_write(bulk_operations)
            logger.info(
                f"Procesadas {len(bulk_operations)} cuentas "
                f"(insertadas: {result.inserted_count}, actualizadas: {result.modified_count})"
            )

        # 5. Crear registros en historial_asignaciones (bulk insert)
        historial_entries = []
        for account_data in distribution:
            historial_entry = {
                "cuenta_id": account_data["cuenta_id"],
                "nombre_cliente": account_data["nombre_cliente"],
                "agente_id": account_data["agente_id"],
                "simulation_id": simulation_id,
                "fecha_inicio": fecha_asignacion,
                "fecha_fin": None,
                "roi_agente_inicio": account_data["roi_agente"],
                "roi_agente_fin": None,
                "roi_cuenta_ganado": None,
                "balance_inicio": 1000.0,
                "balance_fin": None,
                "motivo_cambio": "inicial",
                "dias_con_agente": None,
                "created_at": fecha_asignacion,
            }
            historial_entries.append(historial_entry)

        # Insertar todo el historial en una sola operacion
        if historial_entries:
            self.historial_col.insert_many(historial_entries)
            logger.info(f"Insertadas {len(historial_entries)} entradas de historial")

        # 6. Crear snapshot de distribucion
        snapshot = self._create_distribution_snapshot(simulation_id, distribution, fecha_asignacion)

        logger.info(f"Distribucion completada: {num_accounts} cuentas asignadas a {num_top_agents} agentes")

        return {
            "simulation_id": simulation_id,
            "total_accounts": num_accounts,
            "total_agents": num_top_agents,
            "accounts_per_agent": self._get_accounts_per_agent_summary(distribution),
            "snapshot_id": str(snapshot.inserted_id),
            "fecha_asignacion": fecha_asignacion.isoformat(),
        }

    def reset_simulation_accounts(self) -> Dict[str, Any]:
        """
        Resetea todas las cuentas para una nueva simulacion independiente.

        Resetea todos los valores EXCEPTO balance_inicial que permanece en $1,000.

        Los siguientes campos se resetean:
        - balance_actual -> vuelve a balance_inicial
        - roi_total -> 0.0
        - roi_acumulado_con_agente -> 0.0
        - numero_cambios_agente -> 0
        - win_rate -> 0.0

        Los siguientes campos NO se modifican:
        - balance_inicial (permanece en $1,000)
        - cuenta_id
        - nombre_cliente
        - created_at

        Returns:
            Dict con resumen del reset (numero de cuentas reseteadas)

        Raises:
            ValueError: Si no hay cuentas para resetear
        """
        logger.info("Iniciando reset de cuentas para nueva simulacion independiente")

        total_cuentas = self.cuentas_trading_col.count_documents({})

        if total_cuentas == 0:
            raise ValueError("No hay cuentas para resetear. Ejecuta initialize primero.")

        logger.info(f"Reseteando {total_cuentas} cuentas...")

        fecha_reset = datetime.utcnow()

        cuentas = list(self.cuentas_trading_col.find({}, {"_id": 1, "balance_inicial": 1}))

        bulk_operations = []
        for cuenta in cuentas:
            bulk_operations.append(
                UpdateOne(
                    {"_id": cuenta["_id"]},
                    {
                        "$set": {
                            "balance_actual": cuenta["balance_inicial"],
                            "roi_total": 0.0,
                            "roi_acumulado_con_agente": 0.0,
                            "numero_cambios_agente": 0,
                            "win_rate": 0.0,
                            "updated_at": fecha_reset,
                        }
                    },
                )
            )

        if bulk_operations:
            result = self.cuentas_trading_col.bulk_write(bulk_operations)
            cuentas_reseteadas = result.modified_count
        else:
            cuentas_reseteadas = 0

        logger.info(f"Reseteadas {cuentas_reseteadas} cuentas exitosamente")

        logger.info("Limpiando historial de asignaciones...")
        self.historial_col.delete_many({})
        logger.info("Historial limpiado")

        logger.info("Limpiando snapshots antiguos...")
        self.snapshot_col.delete_many({})
        logger.info("Snapshots limpiados")

        logger.info("Limpiando logs de rebalanceo...")
        self.rebalanceo_log_col.delete_many({})
        logger.info("Logs de rebalanceo limpiados")

        return {
            "cuentas_reseteadas": cuentas_reseteadas,
            "total_cuentas": total_cuentas,
            "fecha_reset": fecha_reset.isoformat(),
            "balance_inicial_preserved": True,
            "historial_limpiado": True,
            "snapshots_limpiados": True,
        }

    def _get_top16_agents_for_redistribution(
        self, target_date: Optional[str], window_days: int
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Obtiene los agentes del Top 16 para redistribución.

        Args:
            target_date: Fecha objetivo (opcional)
            window_days: Ventana de días

        Returns:
            Tupla de (lista de agentes, fecha usada)
        """
        top16_collection_name = get_top16_collection_name(window_days)
        top16_col = self.db[top16_collection_name]

        logger.info(f"Usando colección: {top16_collection_name}")

        if target_date:
            top16_docs = list(
                top16_col.find({"date": target_date, "is_in_casterly": True})
                .sort("rank", 1)
                .limit(16)
            )
        else:
            latest_date_doc = top16_col.find_one(sort=[("date", -1)])
            if not latest_date_doc:
                raise ValueError(f"No se encontraron agentes en {top16_collection_name}")

            target_date = latest_date_doc["date"]
            top16_docs = list(
                top16_col.find({"date": target_date, "is_in_casterly": True})
                .sort("rank", 1)
                .limit(16)
            )

        if not top16_docs:
            raise ValueError(
                f"No se encontraron agentes del Top16 para la fecha {target_date} "
                f"en {top16_collection_name}"
            )

        logger.info(f"Top16 encontrados: {len(top16_docs)} agentes")
        return top16_docs, target_date

    def _get_active_accounts_for_redistribution(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las cuentas activas para redistribución.

        Returns:
            Lista de cuentas activas

        Raises:
            ValueError: Si no hay cuentas activas
        """
        cuentas = list(self.cuentas_trading_col.find({"estado": "activo"}))

        if not cuentas:
            raise ValueError("No hay cuentas activas para redistribuir")

        logger.info(f"Cuentas activas a redistribuir: {len(cuentas)}")
        return cuentas

    def _calculate_distribution_metrics(
        self, total_cuentas: int, num_agents: int
    ) -> tuple[int, int]:
        """
        Calcula métricas de distribución equitativa.

        Args:
            total_cuentas: Total de cuentas a distribuir
            num_agents: Número de agentes

        Returns:
            Tupla de (cuentas_por_agente, cuentas_extra)
        """
        cuentas_por_agente = total_cuentas // num_agents
        cuentas_extra = total_cuentas % num_agents

        logger.info(
            f"Distribución: {cuentas_por_agente} cuentas por agente, {cuentas_extra} extra"
        )

        return cuentas_por_agente, cuentas_extra

    def _generate_redistribution_bulk_ops(
        self,
        top16_docs: List[Dict[str, Any]],
        cuentas: List[Dict[str, Any]],
        cuentas_por_agente: int,
        cuentas_extra: int,
    ) -> tuple[List, int, int]:
        """
        Genera operaciones bulk para redistribución de cuentas.

        Args:
            top16_docs: Lista de agentes Top 16
            cuentas: Lista de cuentas a redistribuir
            cuentas_por_agente: Cuentas base por agente
            cuentas_extra: Cuentas extra a distribuir

        Returns:
            Tupla de (bulk_operations, cuentas_reasignadas, cuentas_sin_cambio)
        """
        from pymongo import UpdateOne

        bulk_operations = []
        fecha_actual = datetime.utcnow()
        cuenta_index = 0
        cuentas_reasignadas = 0
        cuentas_sin_cambio = 0
        total_cuentas = len(cuentas)

        for idx, top_agent in enumerate(top16_docs):
            agente_id = top_agent["agent_id"]
            roi_agente = top_agent.get("roi_7d", 0.0)

            num_cuentas = cuentas_por_agente + (1 if idx < cuentas_extra else 0)

            for _ in range(num_cuentas):
                if cuenta_index >= total_cuentas:
                    break

                cuenta = cuentas[cuenta_index]
                cuenta_id = cuenta["cuenta_id"]
                agente_anterior = cuenta.get("agente_actual")

                if agente_anterior != agente_id:
                    bulk_operations.append(
                        UpdateOne(
                            {"cuenta_id": cuenta_id},
                            {
                                "$set": {
                                    "agente_actual": agente_id,
                                    "fecha_asignacion_agente": fecha_actual,
                                    "roi_agente_al_asignar": roi_agente,
                                    "roi_acumulado_con_agente": 0.0,
                                    "updated_at": fecha_actual,
                                },
                                "$inc": {"numero_cambios_agente": 1},
                            },
                        )
                    )
                    cuentas_reasignadas += 1
                else:
                    cuentas_sin_cambio += 1

                cuenta_index += 1

        return bulk_operations, cuentas_reasignadas, cuentas_sin_cambio

    def _execute_redistribution_bulk_ops(self, bulk_operations: List) -> None:
        """
        Ejecuta operaciones bulk de redistribución.

        Args:
            bulk_operations: Lista de operaciones UpdateOne
        """
        if bulk_operations:
            result = self.cuentas_trading_col.bulk_write(bulk_operations)
            logger.info(f"Cuentas actualizadas: {result.modified_count}")
        else:
            logger.info("No hubo cambios en las asignaciones")

    def _create_redistribution_historial_entries(
        self, top16_docs: List[Dict[str, Any]]
    ) -> None:
        """
        Crea entradas de historial para cuentas redistribuidas.

        Args:
            top16_docs: Lista de agentes Top 16
        """
        historial_entries = []
        fecha_actual = datetime.utcnow()

        for top_agent in top16_docs:
            agente_id = top_agent["agent_id"]
            roi_agente = top_agent.get("roi_7d", 0.0)

            cuentas_agente = self.cuentas_trading_col.find(
                {"agente_actual": agente_id, "estado": "activo"}
            )

            for cuenta in cuentas_agente:
                historial_entry = {
                    "cuenta_id": cuenta["cuenta_id"],
                    "nombre_cliente": cuenta["nombre_cliente"],
                    "agente_id": agente_id,
                    "simulation_id": "redistribution",
                    "fecha_inicio": fecha_actual,
                    "fecha_fin": None,
                    "roi_agente_inicio": roi_agente,
                    "roi_agente_fin": None,
                    "roi_cuenta_ganado": None,
                    "balance_inicio": cuenta.get("balance_actual", 1000.0),
                    "balance_fin": None,
                    "motivo_cambio": "re-balanceo",
                    "dias_con_agente": None,
                    "created_at": fecha_actual,
                }
                historial_entries.append(historial_entry)

        self.historial_col.update_many(
            {"fecha_fin": None}, {"$set": {"fecha_fin": fecha_actual}}
        )

        if historial_entries:
            self.historial_col.insert_many(historial_entries)
            logger.info(f"Insertadas {len(historial_entries)} entradas en historial")

    def redistribute_accounts_to_top16(self, target_date: Optional[str] = None, window_days: int = 7) -> Dict[str, Any]:
        """
        Redistribuye todas las cuentas existentes entre los agentes del Top 16 actual.

        Este método se ejecuta automáticamente después de una simulación para
        reasignar las cuentas a los mejores agentes del Top16.

        Esta función ha sido refactorizada para reducir complejidad (13 -> ~7).
        Secciones extraídas:
        1. _get_top16_agents_for_redistribution: Obtiene Top 16
        2. _get_active_accounts_for_redistribution: Obtiene cuentas activas
        3. _calculate_distribution_metrics: Calcula distribución
        4. _generate_redistribution_bulk_ops: Genera operaciones bulk
        5. _execute_redistribution_bulk_ops: Ejecuta operaciones
        6. _create_redistribution_historial_entries: Crea historial

        Args:
            target_date: Fecha objetivo (opcional, usa la más reciente si no se especifica)
            window_days: Ventana de días usada en la simulación (determina colección). Default: 7

        Returns:
            Dict con información de la redistribución
        """
        logger.info(f"=== INICIANDO REDISTRIBUCIÓN DE CUENTAS AL TOP16 (VENTANA {window_days}D) ===")

        # 1. Obtener Top 16 agentes actuales
        top16_docs, target_date = self._get_top16_agents_for_redistribution(
            target_date, window_days
        )

        # 2. Obtener todas las cuentas activas
        cuentas = self._get_active_accounts_for_redistribution()
        total_cuentas = len(cuentas)

        # 3. Calcular distribución equitativa
        cuentas_por_agente, cuentas_extra = self._calculate_distribution_metrics(
            total_cuentas, len(top16_docs)
        )

        # 4. Generar operaciones bulk de actualización
        bulk_operations, cuentas_reasignadas, cuentas_sin_cambio = (
            self._generate_redistribution_bulk_ops(
                top16_docs, cuentas, cuentas_por_agente, cuentas_extra
            )
        )

        # 5. Ejecutar operaciones bulk
        self._execute_redistribution_bulk_ops(bulk_operations)

        # 6. Crear entradas de historial
        self._create_redistribution_historial_entries(top16_docs)

        logger.info(
            f"=== REDISTRIBUCIÓN COMPLETADA ===\n"
            f"  Fecha Top16: {target_date}\n"
            f"  Total cuentas: {total_cuentas}\n"
            f"  Cuentas reasignadas: {cuentas_reasignadas}\n"
            f"  Cuentas sin cambio: {cuentas_sin_cambio}\n"
            f"  Agentes Top16: {len(top16_docs)}"
        )

        return {
            "success": True,
            "target_date": target_date,
            "total_cuentas": total_cuentas,
            "cuentas_reasignadas": cuentas_reasignadas,
            "cuentas_sin_cambio": cuentas_sin_cambio,
            "num_agentes_top16": len(top16_docs),
            "cuentas_por_agente": cuentas_por_agente,
        }

    def _get_top_agents(self, simulation_id: str, num_agents: int) -> List[Dict[str, Any]]:
        """
        Obtiene los Top N agentes ordenados por ROI desde la tabla top16_by_day.

        Args:
            simulation_id: ID de la simulacion (no usado, se obtiene la fecha mas reciente)
            num_agents: Numero de agentes a obtener

        Returns:
            Lista de agentes ordenados por ROI descendente
        """
        # Obtener la fecha mas reciente en la tabla top16_by_day
        latest_date_doc = self.top16_col.find_one(sort=[("date", -1)])

        if not latest_date_doc:
            return []

        latest_date = latest_date_doc["date"]

        # Obtener los Top N agentes de esa fecha, ordenados por rank
        agents = list(
            self.top16_col.find({"date": latest_date, "is_in_casterly": True}).sort("rank", 1).limit(num_agents)
        )

        return [
            {
                "agente_id": agent["agent_id"],
                "nombre": agent.get("agent_id", f"Agente {agent['agent_id']}"),
                "roi_7d": agent.get("roi_7d", 0.0) * 100,  # Convertir a porcentaje
                "win_rate": 0.0,  # No disponible en esta tabla
            }
            for agent in agents
        ]

    def _get_client_accounts(self, num_accounts: int) -> List[Dict[str, Any]]:
        """
        Genera cuentas de clientes sinteticas.

        Args:
            num_accounts: Numero de cuentas a generar

        Returns:
            Lista de cuentas de clientes
        """
        from bson import ObjectId

        # Generar nombres de clientes
        nombres = ["Juan", "María", "Pedro", "Ana", "Luis", "Carmen", "José", "Laura", "Carlos", "Isabel"]
        apellidos = [
            "García",
            "Rodríguez",
            "Martínez",
            "López",
            "González",
            "Pérez",
            "Sánchez",
            "Ramírez",
            "Torres",
            "Flores",
        ]

        accounts = []
        for i in range(num_accounts):
            nombre_cliente = f"{nombres[i % len(nombres)]} {apellidos[(i // len(nombres)) % len(apellidos)]}"
            if i >= len(nombres) * len(apellidos):
                nombre_cliente = f"{nombre_cliente} {i // (len(nombres) * len(apellidos)) + 1}"

            accounts.append({"cuenta_id": str(ObjectId()), "nombre_cliente": nombre_cliente})

        return accounts

    def _distribute_accounts_equitably(
        self, accounts: List[Dict[str, Any]], agents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Distribuye cuentas equitativamente entre agentes.

        Algoritmo:
        - Calcula cuentas_por_agente = total_cuentas / total_agentes
        - Distribuye en round-robin para equidad perfecta

        Args:
            accounts: Lista de cuentas a distribuir
            agents: Lista de agentes disponibles

        Returns:
            Lista de asignaciones {cuenta_id, nombre_cliente, agente_id, roi_agente}
        """
        distribution = []
        num_agents = len(agents)

        for idx, account in enumerate(accounts):
            agent_idx = idx % num_agents
            agent = agents[agent_idx]

            distribution.append(
                {
                    "cuenta_id": account["cuenta_id"],
                    "nombre_cliente": account["nombre_cliente"],
                    "agente_id": agent["agente_id"],
                    "roi_agente": agent["roi_7d"],
                }
            )

        return distribution

    def _get_accounts_per_agent_summary(self, distribution: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calcula el resumen de cuentas por agente.

        Args:
            distribution: Lista de asignaciones

        Returns:
            Dict {agente_id: num_cuentas}
        """
        summary = {}
        for assignment in distribution:
            agente_id = assignment["agente_id"]
            summary[agente_id] = summary.get(agente_id, 0) + 1

        return summary

    def _create_distribution_snapshot(
        self, simulation_id: str, distribution: List[Dict[str, Any]], fecha_snapshot: datetime
    ) -> Any:
        """
        Crea un snapshot de la distribucion actual.

        Args:
            simulation_id: ID de la simulacion
            distribution: Lista de asignaciones
            fecha_snapshot: Fecha del snapshot

        Returns:
            Resultado de la insercion
        """
        snapshot = {
            "simulation_id": simulation_id,
            "fecha_snapshot": fecha_snapshot,
            "total_cuentas": len(distribution),
            "distribucion": self._get_accounts_per_agent_summary(distribution),
            "created_at": fecha_snapshot,
        }

        return self.snapshot_col.insert_one(snapshot)

    def update_client_accounts_roi(self, simulation_id: str, window_days: int = 7) -> Dict[str, Any]:
        """
        Actualiza el ROI y Win Rate de todas las cuentas de clientes basado en el ROI actual de sus agentes.

        Formula ROI_Cliente: ROI_Cliente = (ROI_Agente_Actual - ROI_Agente_Al_Asignar)
        Formula Win Rate: Win Rate = (dias_positivos / total_dias) * 100

        Args:
            simulation_id: ID de la simulacion
            window_days: Ventana de días usada en la simulación (determina colección). Default: 7

        Returns:
            Dict con resumen de actualizaciones
        """
        logger.info(f"Actualizando ROI y Win Rate de cuentas para simulacion {simulation_id} (VENTANA {window_days}D)")

        # Obtener colecciones dinámicas
        from app.utils.collection_names import get_roi_collection_name

        top16_collection_name = get_top16_collection_name(window_days)
        roi_collection_name = get_roi_collection_name(window_days)

        top16_col = self.db[top16_collection_name]
        agent_roi_col = self.db[roi_collection_name]

        logger.info(f"Usando colecciones: {top16_collection_name} y {roi_collection_name}")

        # Obtener la fecha mas reciente de la colección dinámica
        latest_date_doc = top16_col.find_one(sort=[("date", -1)])
        if not latest_date_doc:
            logger.warning(f"No hay datos en {top16_collection_name}")
            return {
                "simulation_id": simulation_id,
                "cuentas_actualizadas": 0,
                "fecha_actualizacion": datetime.utcnow().isoformat(),
            }

        latest_date = latest_date_doc["date"]

        # Obtener todos los agentes de la fecha mas reciente en un solo query
        agentes = list(top16_col.find({"date": latest_date}))
        agentes_dict = {ag["agent_id"]: ag.get("roi_7d", 0.0) * 100 for ag in agentes}  # Convertir a porcentaje

        # Obtener todos los agent_id de los agentes
        agent_ids = [ag.get("agent_id") for ag in agentes if ag.get("agent_id")]

        # Query masivo para obtener datos de ROI de todos los agentes
        # Buscar por userId (que coincide con agent_id de top16)
        roi_docs = list(agent_roi_col.find({"target_date": latest_date, "userId": {"$in": agent_ids}}))

        # Crear mapa de agent_id -> win_rate para acceso rapido
        win_rate_map = {}
        for roi_doc in roi_docs:
            user_id = roi_doc.get("userId")  # Este es el agent_id en formato string
            positive_days = roi_doc.get("positive_days", 0)
            daily_rois = roi_doc.get("daily_rois", [])
            total_days = len(daily_rois)

            # Calcular Win Rate: (dias positivos / total dias) como decimal (0.0 a 1.0)
            if total_days > 0:
                win_rate = positive_days / total_days
            else:
                win_rate = 0.0

            win_rate_map[user_id] = win_rate

        # Obtener todas las cuentas activas
        cuentas = list(self.cuentas_trading_col.find({"estado": "activo"}))

        # Preparar operaciones de actualizacion en bulk
        from pymongo import UpdateOne

        bulk_operations = []

        for cuenta in cuentas:
            agente_id = cuenta["agente_actual"]
            roi_agente_actual = agentes_dict.get(agente_id)

            if roi_agente_actual is None:
                logger.warning(f"Agente {agente_id} no encontrado en top16_by_day")
                continue

            roi_agente_al_asignar = cuenta["roi_agente_al_asignar"]

            # Calcular ROI ganado con el agente actual
            roi_acumulado_con_agente = roi_agente_actual - roi_agente_al_asignar

            # Calcular nuevo balance
            balance_inicial = cuenta["balance_inicial"]
            roi_total_anterior = cuenta["roi_total"]
            roi_total_nuevo = roi_total_anterior + roi_acumulado_con_agente

            balance_actual = balance_inicial * (1 + roi_total_nuevo / 100)

            # Obtener Win Rate del agente actual (directamente por agent_id)
            win_rate = win_rate_map.get(agente_id, 0.0)

            # Agregar operacion de actualizacion (incluye Win Rate)
            bulk_operations.append(
                UpdateOne(
                    {"_id": cuenta["_id"]},
                    {
                        "$set": {
                            "roi_acumulado_con_agente": roi_acumulado_con_agente,
                            "roi_total": roi_total_nuevo,
                            "balance_actual": balance_actual,
                            "win_rate": win_rate,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
            )

        # Ejecutar todas las actualizaciones en una sola operacion
        actualizaciones = 0
        if bulk_operations:
            result = self.cuentas_trading_col.bulk_write(bulk_operations)
            actualizaciones = result.modified_count
            logger.info(f"ROI y Win Rate actualizados para {actualizaciones} cuentas")

        return {
            "simulation_id": simulation_id,
            "cuentas_actualizadas": actualizaciones,
            "fecha_actualizacion": datetime.utcnow().isoformat(),
        }

    def get_client_accounts(
        self, skip: int = 0, limit: int = 100, agente_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene lista de cuentas de clientes con paginacion.

        Args:
            skip: Numero de registros a omitir
            limit: Numero maximo de registros a devolver
            agente_id: Filtro opcional por agente

        Returns:
            Lista de cuentas
        """
        query = {"estado": "activo"}
        if agente_id:
            query["agente_actual"] = agente_id

        cuentas = list(self.cuentas_trading_col.find(query).skip(skip).limit(limit).sort("roi_total", -1))

        return [self._format_cuenta_response(cuenta) for cuenta in cuentas]

    def _format_cuenta_response(self, cuenta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formatea una cuenta para respuesta de API.

        Args:
            cuenta: Documento de cuenta

        Returns:
            Dict formateado
        """
        return {
            "cuenta_id": cuenta["cuenta_id"],
            "nombre_cliente": cuenta["nombre_cliente"],
            "balance_inicial": cuenta["balance_inicial"],
            "balance_actual": cuenta["balance_actual"],
            "roi_total": cuenta["roi_total"],
            "win_rate": cuenta["win_rate"],
            "agente_actual": cuenta["agente_actual"],
            "fecha_asignacion_agente": cuenta["fecha_asignacion_agente"].isoformat(),
            "roi_agente_al_asignar": cuenta["roi_agente_al_asignar"],
            "roi_acumulado_con_agente": cuenta.get("roi_acumulado_con_agente", 0.0),
            "numero_cambios_agente": cuenta.get("numero_cambios_agente", 0),
            "estado": cuenta["estado"],
        }

    def get_client_account_by_id(self, cuenta_id: str) -> Dict[str, Any]:
        """
        Obtiene una cuenta de cliente específica con su historial completo.

        Este método combina datos de cuentas_clientes_trading y
        historial_asignaciones_clientes para devolver una respuesta completa.

        Args:
            cuenta_id: ID de la cuenta a buscar

        Returns:
            Dict con datos de cuenta e historial embebido

        Raises:
            ValueError: Si la cuenta no existe
        """
        logger.info(f"Obteniendo detalle de cuenta {cuenta_id}")

        # 1. Buscar cuenta en cuentas_clientes_trading
        cuenta = self.cuentas_trading_col.find_one({"cuenta_id": cuenta_id})

        if not cuenta:
            logger.warning(f"Cuenta {cuenta_id} no encontrada")
            raise ValueError(f"Cuenta {cuenta_id} no encontrada")

        # 2. Obtener historial de asignaciones
        historial = list(
            self.historial_col.find({"cuenta_id": cuenta_id}).sort("fecha_inicio", -1)  # Más reciente primero
        )

        logger.info(f"Historial encontrado: {len(historial)} asignaciones")

        # 3. Generar email desde el nombre del cliente
        email = f"{cuenta['nombre_cliente'].lower().replace(' ', '')}@example.com"

        # 4. Formatear respuesta con mapeo de campos
        return {
            # Campos básicos (renombrados para coincidir con frontend)
            "account_id": cuenta["cuenta_id"],  # cuenta_id -> account_id
            "nombre_cliente": cuenta["nombre_cliente"],
            "email": email,  # Agregado desde tabla maestra
            "balance_inicial": cuenta["balance_inicial"],
            "balance_actual": cuenta["balance_actual"],
            "fecha_creacion": cuenta["created_at"].isoformat(),  # created_at -> fecha_creacion
            "estado": cuenta["estado"],
            "agente_actual": cuenta["agente_actual"],
            "roi_total": cuenta["roi_total"],
            # Campos extra (útiles para el frontend)
            "fecha_asignacion_agente": cuenta["fecha_asignacion_agente"].isoformat(),
            "roi_agente_al_asignar": cuenta["roi_agente_al_asignar"],
            "roi_acumulado_con_agente": cuenta.get("roi_acumulado_con_agente", 0.0),
            "numero_cambios_agente": cuenta.get("numero_cambios_agente", 0),
            "win_rate": cuenta.get("win_rate", 0.0),
            # Historial embebido (renombrado para coincidir con frontend)
            "historial": [
                {
                    "agente_id": h["agente_id"],
                    "fecha_inicio": h["fecha_inicio"].isoformat(),
                    "fecha_fin": h["fecha_fin"].isoformat() if h["fecha_fin"] else None,
                    "roi_inicial": h["roi_agente_inicio"],  # roi_agente_inicio -> roi_inicial
                    "roi_final": h["roi_agente_fin"],  # roi_agente_fin -> roi_final
                    "balance_inicial": h["balance_inicio"],  # balance_inicio -> balance_inicial
                    "balance_final": h["balance_fin"],  # balance_fin -> balance_final
                    "motivo_cambio": h["motivo_cambio"],
                    # Campos extra
                    "roi_cuenta_ganado": h.get("roi_cuenta_ganado"),
                    "dias_con_agente": h.get("dias_con_agente"),
                }
                for h in historial
            ],
        }

    def get_client_accounts_stats(self, simulation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas agregadas de las cuentas de clientes.

        Calcula:
        - Total de cuentas activas
        - Balance total
        - ROI promedio
        - Win rate promedio

        Args:
            simulation_id: ID de la simulación (opcional, por ahora no se usa)

        Returns:
            Dict con estadísticas agregadas
        """
        logger.info(f"Calculando estadísticas de cuentas para simulación {simulation_id}")

        # Pipeline de agregación en MongoDB
        pipeline = [
            # 1. Filtrar solo cuentas activas
            {"$match": {"estado": "activo"}},
            # 2. Calcular agregaciones
            {
                "$group": {
                    "_id": None,
                    "total_cuentas": {"$sum": 1},
                    "balance_total": {"$sum": "$balance_actual"},
                    "roi_promedio": {"$avg": "$roi_total"},
                    "win_rate_promedio": {"$avg": "$win_rate"},
                }
            },
        ]

        # Ejecutar agregación
        result = list(self.cuentas_trading_col.aggregate(pipeline))

        # Si no hay resultados, devolver valores por defecto
        if not result:
            logger.warning("No se encontraron cuentas activas")
            return {
                "simulation_id": simulation_id or "unknown",
                "total_cuentas": 0,
                "balance_total": 0.0,
                "roi_promedio": 0.0,
                "win_rate_promedio": 0.0,
            }

        # Formatear respuesta
        stats = result[0]

        logger.info(
            f"Estadísticas calculadas: {stats['total_cuentas']} cuentas, "
            f"balance total: ${stats['balance_total']:,.2f}"
        )

        return {
            "simulation_id": simulation_id or "unknown",
            "total_cuentas": stats["total_cuentas"],
            "balance_total": round(stats["balance_total"], 2),
            "roi_promedio": round(stats["roi_promedio"], 2),
            "win_rate_promedio": round(stats["win_rate_promedio"] * 100, 2),  # Convertir a porcentaje
        }

    def get_all_client_accounts_formatted(
        self,
        simulation_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 1000,
        agente_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Obtiene lista de cuentas con formato compatible con frontend.

        Diferencia con get_client_accounts():
        - Renombra campos para coincidir con frontend
        - Agrega campo 'email'
        - Convierte fechas a ISO string
        - NO incluye historial (para performance)
        - Devuelve dict con total de registros para paginación
        - Soporta búsqueda por texto

        Args:
            simulation_id: ID de la simulación (opcional)
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros (default: 1000)
            agente_id: Filtro opcional por agente
            search: Término de búsqueda (nombre, cuenta_id o agente)

        Returns:
            Dict con {accounts: [...], total: X, skip: X, limit: X}
        """
        logger.info(f"Obteniendo cuentas (skip={skip}, limit={limit}, agente={agente_id}, search={search})")

        # Construir query
        query = {"estado": "activo"}

        if agente_id:
            query["agente_actual"] = agente_id

        # Agregar búsqueda por texto (case-insensitive)
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"nombre_cliente": search_regex},
                {"cuenta_id": search_regex},
                {"agente_actual": search_regex},
            ]

        # Nota: simulation_id no se usa porque cuentas_clientes_trading
        # no tiene este campo. Todas las cuentas pertenecen a la misma simulación.

        # Obtener total de cuentas (para paginación)
        total_cuentas = self.cuentas_trading_col.count_documents(query)

        # Obtener cuentas
        cuentas = list(
            self.cuentas_trading_col.find(query)
            .skip(skip)
            .limit(limit)
            .sort("roi_total", -1)  # Ordenar por ROI descendente
        )

        logger.info(f"Cuentas encontradas: {len(cuentas)} de {total_cuentas} totales")

        # Formatear cada cuenta
        formatted_accounts = []

        for cuenta in cuentas:
            # Generar email desde el nombre del cliente
            email = f"{cuenta['nombre_cliente'].lower().replace(' ', '')}@example.com"

            formatted_accounts.append(
                {
                    "cuenta_id": cuenta["cuenta_id"],  # Mantener nombre consistente
                    "nombre_cliente": cuenta["nombre_cliente"],
                    "email": email,  # Agregar
                    "balance_inicial": cuenta["balance_inicial"],
                    "balance_actual": cuenta["balance_actual"],
                    "fecha_creacion": cuenta["created_at"].isoformat(),  # Convertir a ISO
                    "estado": cuenta["estado"],
                    "agente_actual": cuenta["agente_actual"],
                    "roi_total": cuenta["roi_total"],
                    # Campos extra (no en modelo frontend pero útiles)
                    "win_rate": cuenta.get("win_rate", 0.0),
                    "numero_cambios_agente": cuenta.get("numero_cambios_agente", 0),
                    # NO incluir historial aquí (performance)
                }
            )

        return {"accounts": formatted_accounts, "total": total_cuentas, "skip": skip, "limit": limit}

    def _calculate_rebalance_metrics(self, cuentas: List[Dict[str, Any]], max_move_percentage: float) -> Dict[str, Any]:
        """
        Calcula métricas iniciales para el re-balanceo.

        Returns:
            Dict con total_cuentas, max_cuentas_a_mover, roi_promedio, cuentas_bajo_promedio
        """
        total_cuentas = len(cuentas)
        max_cuentas_a_mover = int(total_cuentas * max_move_percentage)
        roi_promedio = sum(c["roi_total"] for c in cuentas) / total_cuentas
        cuentas_bajo_promedio = [c for c in cuentas if c["roi_total"] < roi_promedio]

        logger.info(f"ROI promedio: {roi_promedio:.2f}%")
        logger.info(f"Max cuentas a mover: {max_cuentas_a_mover} ({max_move_percentage * 100}%)")
        logger.info(f"Cuentas bajo promedio: {len(cuentas_bajo_promedio)}")

        return {
            "total_cuentas": total_cuentas,
            "max_cuentas_a_mover": max_cuentas_a_mover,
            "roi_promedio": roi_promedio,
            "cuentas_bajo_promedio": cuentas_bajo_promedio,
        }

    def _find_mejor_agente(
        self, agente_actual_id: str, agentes_dict: Dict[str, Dict[str, Any]], top_agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Encuentra el mejor agente alternativo para una cuenta.

        Returns:
            Diccionario del mejor agente, o None si no hay mejor opción
        """
        agente_actual = agentes_dict.get(agente_actual_id)

        # Si el agente actual NO está en top 16, asignar al mejor agente disponible
        if not agente_actual:
            logger.info(
                f"[REBALANCE] Agente actual '{agente_actual_id}' no esta en top 16 - asignando al mejor agente"
            )
            return top_agents[0]  # Mejor agente (rank 1)

        # Encontrar mejor agente (con mayor ROI que no sea el actual)
        for ag in top_agents:
            if ag["agente_id"] != agente_actual_id and ag["roi_7d"] > agente_actual["roi_7d"]:
                return ag

        logger.info(f"[REBALANCE] INFO: No hay mejor agente que '{agente_actual_id}' - skip")
        return None

    def _close_current_assignment(
        self, cuenta: Dict[str, Any], agente_actual_id: str, agente_actual_roi: float, fecha_rebalanceo: datetime
    ) -> None:
        """
        Cierra la asignación actual en el historial.
        """
        try:
            dias_con_agente = (fecha_rebalanceo - cuenta["fecha_asignacion_agente"]).days
        except Exception as e:
            logger.info(f"[REBALANCE] ERROR calculando dias_con_agente: {e}")
            dias_con_agente = 0

        update_values = {
            "fecha_fin": fecha_rebalanceo,
            "roi_agente_fin": agente_actual_roi,
            "roi_cuenta_ganado": cuenta.get("roi_acumulado_con_agente", 0.0),
            "balance_fin": cuenta.get("balance_actual", 0.0),
            "dias_con_agente": dias_con_agente,
        }

        logger.info(
            f"[REBALANCE] Cerrando asignacion - cuenta: {cuenta['cuenta_id']}, agente: {agente_actual_id}, dias: {dias_con_agente}"
        )

        update_result = self.historial_col.update_one(
            {"cuenta_id": cuenta["cuenta_id"], "agente_id": agente_actual_id, "fecha_fin": None},
            {"$set": update_values},
        )

        if update_result.matched_count == 0:
            logger.info(
                f"[REBALANCE] WARNING: No se encontro asignacion activa para cerrar: cuenta_id={cuenta['cuenta_id']}"
            )
        elif update_result.modified_count == 0:
            logger.info("[REBALANCE] WARNING: Asignacion encontrada pero no modificada")

    def _create_assignment_records(
        self,
        cuenta: Dict[str, Any],
        mejor_agente: Dict[str, Any],
        agente_actual_id: str,
        agente_actual_roi: float,
        simulation_id: str,
        fecha_rebalanceo: datetime,
    ) -> tuple[Dict[str, Any], Any, Dict[str, Any]]:
        """
        Crea los registros necesarios para una nueva asignación.

        Returns:
            tuple: (historial_entry, bulk_update, movimiento)
        """
        from pymongo import UpdateOne

        historial_entry = {
            "cuenta_id": cuenta["cuenta_id"],
            "nombre_cliente": cuenta["nombre_cliente"],
            "agente_id": mejor_agente["agente_id"],
            "simulation_id": simulation_id,
            "fecha_inicio": fecha_rebalanceo,
            "fecha_fin": None,
            "roi_agente_inicio": mejor_agente["roi_7d"],
            "roi_agente_fin": None,
            "roi_cuenta_ganado": None,
            "balance_inicio": cuenta["balance_actual"],
            "balance_fin": None,
            "motivo_cambio": "re-balanceo",
            "dias_con_agente": None,
            "created_at": fecha_rebalanceo,
        }

        bulk_update = UpdateOne(
            {"_id": cuenta["_id"]},
            {
                "$set": {
                    "agente_actual": mejor_agente["agente_id"],
                    "fecha_asignacion_agente": fecha_rebalanceo,
                    "roi_agente_al_asignar": mejor_agente["roi_7d"],
                    "roi_acumulado_con_agente": 0.0,
                    "numero_cambios_agente": cuenta.get("numero_cambios_agente", 0) + 1,
                    "updated_at": fecha_rebalanceo,
                }
            },
        )

        movimiento = {
            "cuenta_id": cuenta["cuenta_id"],
            "nombre_cliente": cuenta["nombre_cliente"],
            "agente_origen": agente_actual_id,
            "agente_destino": mejor_agente["agente_id"],
            "roi_cuenta": cuenta["roi_total"],
            "roi_agente_origen": agente_actual_roi,
            "roi_agente_destino": mejor_agente["roi_7d"],
        }

        return historial_entry, bulk_update, movimiento

    def _process_rebalance_for_account(
        self,
        cuenta: Dict[str, Any],
        agentes_dict: Dict[str, Dict[str, Any]],
        top_agents: List[Dict[str, Any]],
        simulation_id: str,
        fecha_rebalanceo: datetime,
    ) -> Optional[tuple[Dict[str, Any], Any, Dict[str, Any]]]:
        """
        Procesa el re-balanceo para una cuenta individual.

        Returns:
            tuple (historial_entry, bulk_update, movimiento) o None si no se debe mover
        """
        agente_actual_id = cuenta["agente_actual"]
        agente_actual = agentes_dict.get(agente_actual_id)

        # Determinar mejor agente y ROI actual
        mejor_agente = self._find_mejor_agente(agente_actual_id, agentes_dict, top_agents)

        if not mejor_agente:
            return None

        agente_actual_roi = agente_actual.get("roi_7d", 0.0) if agente_actual else 0.0

        # Cerrar asignación actual
        self._close_current_assignment(cuenta, agente_actual_id, agente_actual_roi, fecha_rebalanceo)

        # Crear registros para nueva asignación
        return self._create_assignment_records(
            cuenta, mejor_agente, agente_actual_id, agente_actual_roi, simulation_id, fecha_rebalanceo
        )

    def _execute_bulk_operations(
        self, bulk_updates: List[Any], historial_entries: List[Dict[str, Any]]
    ) -> None:
        """
        Ejecuta operaciones en bulk (actualizaciones de cuentas e inserciones en historial).
        """
        if bulk_updates:
            self.cuentas_trading_col.bulk_write(bulk_updates)
            logger.info(f"Actualizadas {len(bulk_updates)} cuentas")

        if historial_entries:
            self.historial_col.insert_many(historial_entries)
            logger.info(f"Insertadas {len(historial_entries)} entradas de historial")

    def _save_rebalance_log(
        self,
        simulation_id: str,
        fecha_rebalanceo: datetime,
        roi_promedio: float,
        roi_promedio_post: float,
        total_cuentas: int,
        cuentas_bajo_promedio: int,
        cuentas_movidas: int,
        movimientos: List[Dict[str, Any]],
    ) -> None:
        """
        Guarda el log de re-balanceo y crea snapshot.
        """
        rebalanceo_log = {
            "simulation_id": simulation_id,
            "fecha_rebalanceo": fecha_rebalanceo,
            "roi_promedio_pre": roi_promedio,
            "roi_promedio_post": roi_promedio_post,
            "total_cuentas": total_cuentas,
            "cuentas_bajo_promedio": cuentas_bajo_promedio,
            "cuentas_movidas": cuentas_movidas,
            "porcentaje_movidas": (cuentas_movidas / total_cuentas) * 100,
            "movimientos": movimientos,
            "created_at": fecha_rebalanceo,
        }

        self.rebalanceo_log_col.insert_one(rebalanceo_log)

        # Crear snapshot
        cuentas_actualizadas = list(self.cuentas_trading_col.find({"estado": "activo"}))
        distribution = self._get_accounts_per_agent_summary(
            [{"agente_id": c["agente_actual"]} for c in cuentas_actualizadas]
        )

        self.snapshot_col.insert_one(
            {
                "simulation_id": simulation_id,
                "fecha_snapshot": fecha_rebalanceo,
                "total_cuentas": total_cuentas,
                "distribucion": distribution,
                "created_at": fecha_rebalanceo,
            }
        )

    def rebalance_accounts(self, simulation_id: str, max_move_percentage: float = 0.30) -> Dict[str, Any]:
        """
        Re-balancea cuentas cada 7 dias para equilibrar ROI.

        Esta función ha sido refactorizada para reducir complejidad (15 -> ~7).

        Algoritmo:
        1. Calcular ROI promedio de todas las cuentas
        2. Identificar cuentas bajo el promedio
        3. Mover cuentas bajo promedio a agentes con mejor ROI
        4. Limite: No mover mas del 30% de cuentas

        Args:
            simulation_id: ID de la simulacion
            max_move_percentage: Porcentaje maximo de cuentas a mover (default: 0.30)

        Returns:
            Dict con resumen del re-balanceo
        """
        logger.info(f"Iniciando re-balanceo para simulacion {simulation_id}")

        # 1. Obtener todas las cuentas ordenadas por ROI (ascendente)
        cuentas = list(self.cuentas_trading_col.find({"estado": "activo"}).sort("roi_total", 1))

        if not cuentas:
            return {"simulation_id": simulation_id, "cuentas_movidas": 0, "mensaje": "No hay cuentas activas"}

        # 2. Obtener Top 16 agentes ordenados por ROI (descendente)
        top_agents = self._get_top_agents(simulation_id, 16)
        if not top_agents:
            return {"simulation_id": simulation_id, "cuentas_movidas": 0, "mensaje": "No hay agentes disponibles"}

        # 3. Calcular métricas de re-balanceo
        metrics = self._calculate_rebalance_metrics(cuentas, max_move_percentage)
        total_cuentas = metrics["total_cuentas"]
        max_cuentas_a_mover = metrics["max_cuentas_a_mover"]
        roi_promedio = metrics["roi_promedio"]
        cuentas_bajo_promedio = metrics["cuentas_bajo_promedio"]

        # 4. Preparar estructuras para procesamiento
        agentes_dict = {ag["agente_id"]: ag for ag in top_agents}
        movimientos = []
        bulk_updates = []
        historial_entries = []
        fecha_rebalanceo = datetime.utcnow()
        cuentas_movidas = 0

        logger.info(f"[REBALANCE] ===== Procesando {len(cuentas_bajo_promedio)} cuentas bajo promedio =====")

        # 5. Procesar cada cuenta bajo promedio
        for cuenta in cuentas_bajo_promedio:
            if cuentas_movidas >= max_cuentas_a_mover:
                logger.info(f"[REBALANCE] Límite alcanzado: {cuentas_movidas}/{max_cuentas_a_mover}")
                break

            result = self._process_rebalance_for_account(
                cuenta, agentes_dict, top_agents, simulation_id, fecha_rebalanceo
            )

            if result:
                historial_entry, bulk_update, movimiento = result
                historial_entries.append(historial_entry)
                bulk_updates.append(bulk_update)
                movimientos.append(movimiento)
                cuentas_movidas += 1

        # 6. Ejecutar operaciones en bulk
        self._execute_bulk_operations(bulk_updates, historial_entries)

        # 7. Calcular estadísticas post-rebalanceo
        cuentas_actualizadas = list(self.cuentas_trading_col.find({"estado": "activo"}))
        roi_promedio_post = sum(c["roi_total"] for c in cuentas_actualizadas) / len(cuentas_actualizadas)

        # 8. Guardar log de re-balanceo y crear snapshot
        self._save_rebalance_log(
            simulation_id,
            fecha_rebalanceo,
            roi_promedio,
            roi_promedio_post,
            total_cuentas,
            len(cuentas_bajo_promedio),
            cuentas_movidas,
            movimientos,
        )

        logger.info(f"Re-balanceo completado: {cuentas_movidas} cuentas movidas")

        return {
            "simulation_id": simulation_id,
            "fecha_rebalanceo": fecha_rebalanceo.isoformat(),
            "roi_promedio_pre": roi_promedio,
            "roi_promedio_post": roi_promedio_post,
            "total_cuentas": total_cuentas,
            "cuentas_bajo_promedio": len(cuentas_bajo_promedio),
            "cuentas_movidas": cuentas_movidas,
            "porcentaje_movidas": (cuentas_movidas / total_cuentas) * 100,
            "max_permitido": max_cuentas_a_mover,
            "movimientos": movimientos[:10],  # Solo primeros 10 para no saturar respuesta
        }

    def rotate_failed_agent(self, simulation_id: str, agente_rotado: str, agente_sustituto: str) -> Dict[str, Any]:
        """
        Rota un agente que ha fallado y redistribuye sus cuentas.

        Criterios de falla:
        - 3 dias consecutivos de perdidas
        - ROI del agente cae a -10% o menos

        Args:
            simulation_id: ID de la simulacion
            agente_rotado: ID del agente que falla
            agente_sustituto: ID del agente que lo reemplaza

        Returns:
            Dict con resumen de la rotacion
        """
        logger.info(f"Rotando agente {agente_rotado} por {agente_sustituto} en simulacion {simulation_id}")

        # 1. Obtener todas las cuentas del agente rotado
        cuentas_del_agente = list(self.cuentas_trading_col.find({"agente_actual": agente_rotado, "estado": "activo"}))

        if not cuentas_del_agente:
            logger.warning(f"No se encontraron cuentas para el agente {agente_rotado}")
            return {
                "simulation_id": simulation_id,
                "agente_rotado": agente_rotado,
                "agente_sustituto": agente_sustituto,
                "cuentas_redistribuidas": 0,
                "mensaje": "No hay cuentas asignadas a este agente",
            }

        num_cuentas = len(cuentas_del_agente)
        logger.info(f"Encontradas {num_cuentas} cuentas del agente {agente_rotado}")

        # 2. Obtener informacion del agente sustituto
        top_agents = self._get_top_agents(simulation_id, 20)
        agente_sustituto_info = None

        for ag in top_agents:
            if ag["agente_id"] == agente_sustituto:
                agente_sustituto_info = ag
                break

        if not agente_sustituto_info:
            raise ValueError(f"Agente sustituto {agente_sustituto} no encontrado en top agentes")

        # 3. Obtener informacion del agente rotado
        agente_rotado_info = None
        for ag in top_agents:
            if ag["agente_id"] == agente_rotado:
                agente_rotado_info = ag
                break

        # 4. Preparar redistribucion
        from pymongo import UpdateOne

        bulk_updates = []
        historial_entries = []
        fecha_rotacion = datetime.utcnow()

        for cuenta in cuentas_del_agente:
            # Cerrar registro actual en historial
            dias_con_agente = (fecha_rotacion - cuenta["fecha_asignacion_agente"]).days

            self.historial_col.update_one(
                {"cuenta_id": cuenta["cuenta_id"], "agente_id": agente_rotado, "fecha_fin": None},
                {
                    "$set": {
                        "fecha_fin": fecha_rotacion,
                        "roi_agente_fin": agente_rotado_info["roi_7d"] if agente_rotado_info else 0.0,
                        "roi_cuenta_ganado": cuenta["roi_acumulado_con_agente"],
                        "balance_fin": cuenta["balance_actual"],
                        "dias_con_agente": dias_con_agente,
                    }
                },
            )

            # Crear nuevo registro en historial
            historial_entries.append(
                {
                    "cuenta_id": cuenta["cuenta_id"],
                    "nombre_cliente": cuenta["nombre_cliente"],
                    "agente_id": agente_sustituto,
                    "simulation_id": simulation_id,
                    "fecha_inicio": fecha_rotacion,
                    "fecha_fin": None,
                    "roi_agente_inicio": agente_sustituto_info["roi_7d"],
                    "roi_agente_fin": None,
                    "roi_cuenta_ganado": None,
                    "balance_inicio": cuenta["balance_actual"],
                    "balance_fin": None,
                    "motivo_cambio": "rotacion",
                    "dias_con_agente": None,
                    "created_at": fecha_rotacion,
                }
            )

            # Actualizar cuenta (IMPORTANTE: mantener roi_total historico)
            bulk_updates.append(
                UpdateOne(
                    {"_id": cuenta["_id"]},
                    {
                        "$set": {
                            "agente_actual": agente_sustituto,
                            "fecha_asignacion_agente": fecha_rotacion,
                            "roi_agente_al_asignar": agente_sustituto_info["roi_7d"],
                            "roi_acumulado_con_agente": 0.0,
                            "numero_cambios_agente": cuenta.get("numero_cambios_agente", 0) + 1,
                            "updated_at": fecha_rotacion,
                        }
                    },
                )
            )

        # 5. Ejecutar actualizaciones en bulk
        if bulk_updates:
            self.cuentas_trading_col.bulk_write(bulk_updates)
            logger.info(f"Actualizadas {len(bulk_updates)} cuentas")

        # 6. Insertar historial en bulk
        if historial_entries:
            self.historial_col.insert_many(historial_entries)
            logger.info(f"Insertadas {len(historial_entries)} entradas de historial")

        # 7. Crear snapshot
        cuentas_actualizadas = list(self.cuentas_trading_col.find({"estado": "activo"}))
        distribution = self._get_accounts_per_agent_summary(
            [{"agente_id": c["agente_actual"]} for c in cuentas_actualizadas]
        )

        self.snapshot_col.insert_one(
            {
                "simulation_id": simulation_id,
                "fecha_snapshot": fecha_rotacion,
                "total_cuentas": len(cuentas_actualizadas),
                "distribucion": distribution,
                "tipo_evento": "rotacion",
                "agente_rotado": agente_rotado,
                "agente_sustituto": agente_sustituto,
                "created_at": fecha_rotacion,
            }
        )

        logger.info(f"Rotacion completada: {num_cuentas} cuentas movidas de {agente_rotado} a {agente_sustituto}")

        return {
            "simulation_id": simulation_id,
            "agente_rotado": agente_rotado,
            "agente_sustituto": agente_sustituto,
            "cuentas_redistribuidas": num_cuentas,
            "fecha_rotacion": fecha_rotacion.isoformat(),
            "roi_agente_rotado": agente_rotado_info["roi_7d"] if agente_rotado_info else None,
            "roi_agente_sustituto": agente_sustituto_info["roi_7d"],
            "distribucion_actual": distribution,
        }

    def save_simulation_snapshot(
        self, simulation_id: str, simulation_date: datetime, window_days: int, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Guarda un snapshot completo de la simulacion de Client Accounts.

        Este snapshot incluye:
        - Todas las cuentas con su estado actual
        - Todo el historial de asignaciones
        - Todos los snapshots de timeline
        - Todos los logs de rebalanceo
        - Metadata de la simulacion (fecha, parametros, metricas)

        Similar a como se guardan las simulaciones de agentes en 'simulations',
        esto permite comparar diferentes simulaciones de Client Accounts.

        Args:
            simulation_id: ID unico de la simulacion
            simulation_date: Fecha de la simulacion
            window_days: Ventana de dias usada para ROI
            metadata: Metadata adicional (metricas, parametros, etc.)

        Returns:
            Dict con informacion del snapshot guardado
        """
        logger.info(f"Guardando snapshot de simulacion: {simulation_id}")

        # 1. Obtener todas las cuentas
        cuentas = list(self.cuentas_trading_col.find({}))
        logger.info(f"Cuentas encontradas: {len(cuentas)}")

        # 2. Obtener todo el historial
        historial = list(self.historial_col.find({}))
        logger.info(f"Registros de historial encontrados: {len(historial)}")

        # 3. Obtener snapshots de timeline
        snapshots = list(self.snapshot_col.find({}))
        logger.info(f"Snapshots de timeline encontrados: {len(snapshots)}")

        # 4. Obtener logs de rebalanceo
        rebalanceo_logs = list(self.rebalanceo_log_col.find({}))
        logger.info(f"Logs de rebalanceo encontrados: {len(rebalanceo_logs)}")

        # 5. Calcular metricas agregadas
        total_cuentas = len(cuentas)
        balance_total = sum(c.get("balance_actual", 0) for c in cuentas)
        roi_promedio = sum(c.get("roi_total", 0) for c in cuentas) / total_cuentas if total_cuentas > 0 else 0
        win_rate_promedio = sum(c.get("win_rate", 0) for c in cuentas) / total_cuentas if total_cuentas > 0 else 0

        # 6. Encontrar mejor y peor cuenta
        mejor_cuenta = max(cuentas, key=lambda c: c.get("roi_total", 0)) if cuentas else None
        peor_cuenta = min(cuentas, key=lambda c: c.get("roi_total", 0)) if cuentas else None

        # 7. Distribucion por agente
        distribucion_agentes = {}
        for cuenta in cuentas:
            agente = cuenta.get("agente_actual")
            if agente:
                if agente not in distribucion_agentes:
                    distribucion_agentes[agente] = {
                        "num_cuentas": 0,
                        "balance_total": 0,
                        "roi_promedio": 0,
                        "balances": [],
                    }
                distribucion_agentes[agente]["num_cuentas"] += 1
                distribucion_agentes[agente]["balance_total"] += cuenta.get("balance_actual", 0)
                distribucion_agentes[agente]["balances"].append(cuenta.get("roi_total", 0))

        # Calcular ROI promedio por agente
        for agente, data in distribucion_agentes.items():
            if data["balances"]:
                data["roi_promedio"] = sum(data["balances"]) / len(data["balances"])
            del data["balances"]  # No guardar array temporal

        # 8. Crear documento de snapshot
        snapshot_doc = {
            "simulation_id": simulation_id,
            "simulation_date": (
                simulation_date.isoformat() if hasattr(simulation_date, "isoformat") else simulation_date
            ),
            "window_days": window_days,
            "created_at": datetime.utcnow(),
            # Metricas agregadas
            "summary": {
                "total_cuentas": total_cuentas,
                "balance_total": balance_total,
                "roi_promedio": roi_promedio,
                "win_rate_promedio": win_rate_promedio,
                "total_asignaciones": len(historial),
                "total_rebalanceos": len(rebalanceo_logs),
                "total_snapshots_timeline": len(snapshots),
            },
            # Mejor y peor cuenta
            "mejor_cuenta": (
                {
                    "cuenta_id": mejor_cuenta.get("cuenta_id"),
                    "nombre_cliente": mejor_cuenta.get("nombre_cliente"),
                    "roi_total": mejor_cuenta.get("roi_total"),
                    "balance_actual": mejor_cuenta.get("balance_actual"),
                    "agente_actual": mejor_cuenta.get("agente_actual"),
                }
                if mejor_cuenta
                else None
            ),
            "peor_cuenta": (
                {
                    "cuenta_id": peor_cuenta.get("cuenta_id"),
                    "nombre_cliente": peor_cuenta.get("nombre_cliente"),
                    "roi_total": peor_cuenta.get("roi_total"),
                    "balance_actual": peor_cuenta.get("balance_actual"),
                    "agente_actual": peor_cuenta.get("agente_actual"),
                }
                if peor_cuenta
                else None
            ),
            # Distribucion por agente
            "distribucion_agentes": distribucion_agentes,
            # Datos completos
            "cuentas": cuentas,
            "historial": historial,
            "snapshots_timeline": snapshots,
            "rebalanceo_logs": rebalanceo_logs,
            # Metadata adicional
            "metadata": metadata or {},
        }

        # 9. Guardar en coleccion client_accounts_simulations
        simulations_col = self.db["client_accounts_simulations"]
        result = simulations_col.insert_one(snapshot_doc)

        logger.info(f"Snapshot guardado exitosamente: {result.inserted_id}")

        return {
            "snapshot_id": str(result.inserted_id),
            "simulation_id": simulation_id,
            "total_cuentas": total_cuentas,
            "balance_total": balance_total,
            "roi_promedio": roi_promedio,
            "fecha_guardado": datetime.utcnow().isoformat(),
        }
