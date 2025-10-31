import logging
from typing import Optional
from app.domain.events.agent_events import (
    AgentExitedEvent,
    AgentEnteredEvent,
    AgentRotationCompletedEvent,
    AgentFallingConsecutiveDaysEvent
)

logger = logging.getLogger(__name__)


class AgentEventHandlers:
    """
    Handlers especializados para eventos relacionados con agentes.

    Estos handlers pueden realizar logica de negocio adicional
    mas alla del simple logging, como:
    - Actualizar metricas
    - Enviar notificaciones
    - Registrar en base de datos
    - Disparar procesos adicionales
    """

    def __init__(self, rotation_log_repo=None):
        """
        Inicializa los handlers con dependencias opcionales.

        Args:
            rotation_log_repo: Repositorio para registrar rotaciones (opcional)
        """
        self.rotation_log_repo = rotation_log_repo

    def handle_agent_exited(self, event: AgentExitedEvent) -> None:
        """
        Maneja el evento de salida de un agente.

        Acciones:
        - Log detallado
        - Podria enviar notificacion a stakeholders
        - Podria actualizar dashboard en tiempo real
        """
        logger.info(f"Processing AgentExitedEvent for {event.agent_id}")

        # Aqui se podrian agregar acciones adicionales:
        # - Enviar email/notificacion
        # - Actualizar metricas en tiempo real
        # - Disparar alertas si ROI es muy negativo
        if event.roi_total is not None and event.roi_total < -0.15:
            logger.warning(
                f"ALERT: Agent {event.agent_id} exited with significant loss: "
                f"{event.roi_total:.2%}"
            )

    def handle_agent_entered(self, event: AgentEnteredEvent) -> None:
        """
        Maneja el evento de entrada de un agente.

        Acciones:
        - Log detallado
        - Podria enviar notificacion de bienvenida
        - Podria inicializar tracking especial
        """
        logger.info(f"Processing AgentEnteredEvent for {event.agent_id}")

        # Podria disparar inicializacion de tracking
        # o configuracion especial para el nuevo agente

    def handle_rotation_completed(self, event: AgentRotationCompletedEvent) -> None:
        """
        Maneja el evento de rotacion completada.

        Acciones:
        - Registrar en rotation_log (si tiene repositorio)
        - Log detallado
        - Podria actualizar dashboard
        """
        logger.info(
            f"Processing AgentRotationCompletedEvent: "
            f"{event.agent_out} -> {event.agent_in}"
        )

        # Si tenemos repositorio, registrar en BD
        if self.rotation_log_repo:
            try:
                from app.domain.entities.rotation_log import RotationLog
                from app.domain.value_objects.rotation_reason import RotationReason

                rotation = RotationLog(
                    date=event.rotation_date,
                    agent_out=event.agent_out,
                    agent_in=event.agent_in,
                    reason=RotationReason(event.reason),
                    n_accounts=event.n_accounts,
                    total_aum=event.total_aum
                )

                self.rotation_log_repo.create(rotation)
                logger.debug(f"Rotation logged to database for {event.agent_out} -> {event.agent_in}")
            except Exception as e:
                logger.error(f"Failed to log rotation to database: {str(e)}")

    def handle_falling_consecutive_days(self, event: AgentFallingConsecutiveDaysEvent) -> None:
        """
        Maneja el evento de caidas consecutivas (alerta temprana).

        Acciones:
        - Log de advertencia
        - Podria enviar alerta a sistema de monitoreo
        - Podria preparar candidatos de reemplazo
        """
        logger.warning(
            f"Processing AgentFallingConsecutiveDaysEvent: "
            f"{event.agent_id} falling for {event.fall_days} days"
        )

        # Podria disparar proceso de busqueda de reemplazo anticipado
        # si fall_days esta cerca del threshold de salida
        if event.fall_days >= 2:
            logger.info(
                f"Early warning: {event.agent_id} may need replacement soon "
                f"(fall_days: {event.fall_days})"
            )
