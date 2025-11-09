"""
Dependency Injection Providers for Casterly Rock Simulation.

This module defines provider functions for all repository dependencies.
Uses FastAPI Depends pattern for dependency injection.
"""

from typing import Annotated
from fastapi import Depends
from pymongo.database import Database
from app.config.database import database_manager
from app.domain.repositories.agent_state_repository import AgentStateRepository
from app.domain.repositories.assignment_repository import AssignmentRepository
from app.domain.repositories.balance_repository import BalanceRepository
from app.domain.repositories.movement_repository import MovementRepository
from app.domain.repositories.rotation_log_repository import RotationLogRepository
from app.domain.repositories.top16_repository import Top16Repository
from app.domain.repositories.simulation_repository import SimulationRepository
from app.infrastructure.repositories.agent_state_repository_impl import AgentStateRepositoryImpl
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl
from app.infrastructure.repositories.balance_repository_impl import BalanceRepositoryImpl
from app.infrastructure.repositories.movement_repository_impl import MovementRepositoryImpl
from app.infrastructure.repositories.rotation_log_repository_impl import RotationLogRepositoryImpl
from app.infrastructure.repositories.top16_repository_impl import Top16RepositoryImpl
from app.infrastructure.repositories.simulation_repository_impl import SimulationRepositoryImpl
from app.infrastructure.repositories.daily_roi_repository import DailyROIRepository
from app.infrastructure.repositories.roi_7d_repository import ROI7DRepository
from app.infrastructure.repositories.simulation_status_repository import SimulationStatusRepository
from app.application.services.selection_service import SelectionService
from app.application.services.assignment_service import AssignmentService
from app.application.services.state_classification_service import StateClassificationService
from app.application.services.exit_rules_service import ExitRulesService
from app.application.services.replacement_service import ReplacementService
from app.application.services.daily_orchestrator_service import DailyOrchestratorService
from app.application.services.movement_query_service import MovementQueryService
from app.application.services.balance_query_service import BalanceQueryService
from app.application.services.data_aggregation_service import DataAggregationService
from app.application.services.kpi_calculation_service import KPICalculationService
from app.application.services.daily_roi_calculation_service import DailyROICalculationService
from app.application.services.roi_7d_calculation_service import ROI7DCalculationService
from app.application.services.client_accounts_service import ClientAccountsService
from app.application.services.client_accounts_simulation_service import ClientAccountsSimulationService


def get_agent_state_repository() -> AgentStateRepository:
    """
    Provider for AgentStateRepository.

    Returns:
        AgentStateRepository implementation
    """
    return AgentStateRepositoryImpl()


def get_assignment_repository() -> AssignmentRepository:
    """
    Provider for AssignmentRepository.

    Returns:
        AssignmentRepository implementation
    """
    return AssignmentRepositoryImpl()


def get_balance_repository() -> BalanceRepository:
    """
    Provider for BalanceRepository.

    Returns:
        BalanceRepository implementation
    """
    return BalanceRepositoryImpl()


def get_movement_repository() -> MovementRepository:
    """
    Provider for MovementRepository.

    Returns:
        MovementRepository implementation
    """
    return MovementRepositoryImpl()


def get_rotation_log_repository() -> RotationLogRepository:
    """
    Provider for RotationLogRepository.

    Returns:
        RotationLogRepository implementation
    """
    return RotationLogRepositoryImpl()


def get_top16_repository() -> Top16Repository:
    """
    Provider for Top16Repository.

    Returns:
        Top16Repository implementation
    """
    return Top16RepositoryImpl()


def get_simulation_repository() -> SimulationRepository:
    """
    Provider for SimulationRepository.

    Returns:
        SimulationRepository implementation
    """
    return SimulationRepositoryImpl()


def get_database() -> Database:
    """
    Provider for MongoDB Database instance.

    Returns:
        MongoDB Database instance

    Raises:
        Exception: If database is not connected
    """
    return database_manager.get_database()


def get_daily_roi_repository(
    db: Annotated[Database, Depends(get_database)]
) -> DailyROIRepository:
    """
    Provider for DailyROIRepository.

    Args:
        db: MongoDB Database instance

    Returns:
        DailyROIRepository instance
    """
    return DailyROIRepository(db)


def get_roi_7d_repository(
    db: Annotated[Database, Depends(get_database)]
) -> ROI7DRepository:
    """
    Provider for ROI7DRepository.

    Args:
        db: MongoDB Database instance

    Returns:
        ROI7DRepository instance
    """
    return ROI7DRepository(db)


def get_simulation_status_repository(
    db: Annotated[Database, Depends(get_database)]
) -> SimulationStatusRepository:
    """
    Provider for SimulationStatusRepository.

    Args:
        db: MongoDB Database instance

    Returns:
        SimulationStatusRepository instance
    """
    return SimulationStatusRepository(db)


AgentStateRepositoryDep = Annotated[AgentStateRepository, Depends(get_agent_state_repository)]
AssignmentRepositoryDep = Annotated[AssignmentRepository, Depends(get_assignment_repository)]
BalanceRepositoryDep = Annotated[BalanceRepository, Depends(get_balance_repository)]
MovementRepositoryDep = Annotated[MovementRepository, Depends(get_movement_repository)]
RotationLogRepositoryDep = Annotated[RotationLogRepository, Depends(get_rotation_log_repository)]
Top16RepositoryDep = Annotated[Top16Repository, Depends(get_top16_repository)]
SimulationRepositoryDep = Annotated[SimulationRepository, Depends(get_simulation_repository)]
DatabaseDep = Annotated[Database, Depends(get_database)]
DailyROIRepositoryDep = Annotated[DailyROIRepository, Depends(get_daily_roi_repository)]
ROI7DRepositoryDep = Annotated[ROI7DRepository, Depends(get_roi_7d_repository)]
SimulationStatusRepositoryDep = Annotated[SimulationStatusRepository, Depends(get_simulation_status_repository)]


def get_balance_query_service(
    balance_repo: BalanceRepositoryDep
) -> BalanceQueryService:
    """
    Provider for BalanceQueryService.

    Returns:
        BalanceQueryService with injected dependencies
    """
    return BalanceQueryService(balance_repo)


def get_daily_roi_calculation_service(
    daily_roi_repo: DailyROIRepositoryDep,
    db: DatabaseDep
) -> DailyROICalculationService:
    """
    Provider for DailyROICalculationService.

    Args:
        daily_roi_repo: Repository for DailyROI
        db: MongoDB Database instance

    Returns:
        DailyROICalculationService with injected dependencies
    """
    return DailyROICalculationService(daily_roi_repo, db)


def get_roi_7d_calculation_service(
    roi_7d_repo: ROI7DRepositoryDep,
    daily_roi_service: Annotated[DailyROICalculationService, Depends(get_daily_roi_calculation_service)]
) -> ROI7DCalculationService:
    """
    Provider for ROI7DCalculationService.

    Args:
        roi_7d_repo: Repository for ROI7D
        daily_roi_service: Service for calculating daily ROIs

    Returns:
        ROI7DCalculationService with injected dependencies
    """
    return ROI7DCalculationService(roi_7d_repo, daily_roi_service)


def get_selection_service(
    top16_repo: Top16RepositoryDep,
    balance_repo: BalanceRepositoryDep,
    roi_7d_service: Annotated[ROI7DCalculationService, Depends(get_roi_7d_calculation_service)],
    balance_query_service: Annotated[BalanceQueryService, Depends(get_balance_query_service)]
) -> SelectionService:
    """
    Provider for SelectionService.

    VERSION 2.0: Ahora inyecta ROI7DCalculationService para nueva logica

    Returns:
        SelectionService with injected dependencies
    """
    return SelectionService(top16_repo, balance_repo, roi_7d_service, balance_query_service)


def get_assignment_service(
    assignment_repo: AssignmentRepositoryDep,
    balance_repo: BalanceRepositoryDep,
    selection_service: Annotated[SelectionService, Depends(get_selection_service)]
) -> AssignmentService:
    """
    Provider for AssignmentService.

    Returns:
        AssignmentService with injected dependencies
    """
    return AssignmentService(assignment_repo, balance_repo, selection_service)


def get_state_classification_service(
    state_repo: AgentStateRepositoryDep,
    movement_repo: MovementRepositoryDep,
    balance_repo: BalanceRepositoryDep,
    assignment_repo: AssignmentRepositoryDep,
    daily_roi_service: Annotated[DailyROICalculationService, Depends(get_daily_roi_calculation_service)],
    roi_7d_repo: ROI7DRepositoryDep
) -> StateClassificationService:
    """
    Provider for StateClassificationService.

    VERSION 2.2: Agregado ROI7DRepository

    VERSION 2.0: Agregado DailyROICalculationService

    Returns:
        StateClassificationService with injected dependencies
    """
    return StateClassificationService(state_repo, movement_repo, balance_repo, assignment_repo, daily_roi_service, roi_7d_repo)


def get_exit_rules_service(
    state_repo: AgentStateRepositoryDep,
    assignment_repo: AssignmentRepositoryDep
) -> ExitRulesService:
    """
    Provider for ExitRulesService.

    Returns:
        ExitRulesService with injected dependencies
    """
    return ExitRulesService(state_repo, assignment_repo)


def get_replacement_service(
    rotation_log_repo: RotationLogRepositoryDep,
    assignment_repo: AssignmentRepositoryDep,
    state_repo: AgentStateRepositoryDep,
    top16_repo: Top16RepositoryDep,
    selection_service: Annotated[SelectionService, Depends(get_selection_service)],
    daily_roi_repo: DailyROIRepositoryDep
) -> ReplacementService:
    """
    Provider for ReplacementService.

    Returns:
        ReplacementService with injected dependencies
    """
    return ReplacementService(rotation_log_repo, assignment_repo, state_repo, top16_repo, selection_service, daily_roi_repo)


def get_client_accounts_simulation_service() -> ClientAccountsSimulationService:
    """
    Provider for ClientAccountsSimulationService.

    Returns:
        ClientAccountsSimulationService with injected database
    """
    db = database_manager.get_database()
    return ClientAccountsSimulationService(db)


def get_daily_orchestrator_service(
    selection_service: Annotated[SelectionService, Depends(get_selection_service)],
    assignment_service: Annotated[AssignmentService, Depends(get_assignment_service)],
    state_service: Annotated[StateClassificationService, Depends(get_state_classification_service)],
    exit_rules_service: Annotated[ExitRulesService, Depends(get_exit_rules_service)],
    replacement_service: Annotated[ReplacementService, Depends(get_replacement_service)],
    state_repo: AgentStateRepositoryDep,
    daily_roi_repo: DailyROIRepositoryDep,
    roi_7d_repo: ROI7DRepositoryDep,
    client_accounts_sync_service: Annotated[ClientAccountsSimulationService, Depends(get_client_accounts_simulation_service)]
) -> DailyOrchestratorService:
    """
    Provider for DailyOrchestratorService.

    VERSION 3.0: Agregado ClientAccountsSimulationService

    Returns:
        DailyOrchestratorService with injected dependencies
    """
    return DailyOrchestratorService(
        selection_service,
        assignment_service,
        state_service,
        exit_rules_service,
        replacement_service,
        state_repo,
        daily_roi_repo,
        roi_7d_repo,
        client_accounts_sync_service
    )


SelectionServiceDep = Annotated[SelectionService, Depends(get_selection_service)]
AssignmentServiceDep = Annotated[AssignmentService, Depends(get_assignment_service)]
StateClassificationServiceDep = Annotated[StateClassificationService, Depends(get_state_classification_service)]
ExitRulesServiceDep = Annotated[ExitRulesService, Depends(get_exit_rules_service)]
ReplacementServiceDep = Annotated[ReplacementService, Depends(get_replacement_service)]
DailyOrchestratorServiceDep = Annotated[DailyOrchestratorService, Depends(get_daily_orchestrator_service)]


def get_movement_query_service(
    movement_repo: MovementRepositoryDep
) -> MovementQueryService:
    """
    Provider for MovementQueryService.

    Returns:
        MovementQueryService with injected dependencies
    """
    return MovementQueryService(movement_repo)


def get_data_aggregation_service(
    movement_query_service: Annotated[MovementQueryService, Depends(get_movement_query_service)],
    balance_query_service: Annotated[BalanceQueryService, Depends(get_balance_query_service)]
) -> DataAggregationService:
    """
    Provider for DataAggregationService.

    Returns:
        DataAggregationService with injected dependencies
    """
    return DataAggregationService(movement_query_service, balance_query_service)


MovementQueryServiceDep = Annotated[MovementQueryService, Depends(get_movement_query_service)]
BalanceQueryServiceDep = Annotated[BalanceQueryService, Depends(get_balance_query_service)]
DataAggregationServiceDep = Annotated[DataAggregationService, Depends(get_data_aggregation_service)]


def get_kpi_calculation_service(
    data_aggregation_service: DataAggregationServiceDep
) -> KPICalculationService:
    """
    Provider for KPICalculationService.

    Returns:
        KPICalculationService with injected dependencies
    """
    return KPICalculationService(data_aggregation_service)


KPICalculationServiceDep = Annotated[KPICalculationService, Depends(get_kpi_calculation_service)]
DailyROICalculationServiceDep = Annotated[DailyROICalculationService, Depends(get_daily_roi_calculation_service)]
ROI7DCalculationServiceDep = Annotated[ROI7DCalculationService, Depends(get_roi_7d_calculation_service)]


def get_client_accounts_service(
    db: DatabaseDep
) -> ClientAccountsService:
    """
    Provider for ClientAccountsService.

    Args:
        db: MongoDB Database instance

    Returns:
        ClientAccountsService with injected dependencies
    """
    return ClientAccountsService(db)


ClientAccountsServiceDep = Annotated[ClientAccountsService, Depends(get_client_accounts_service)]
