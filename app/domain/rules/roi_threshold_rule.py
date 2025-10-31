from app.domain.rules.exit_rule import ExitRule
from app.domain.entities.agent_state import AgentState


class ROIThresholdRule(ExitRule):
    """
    Regla de salida: Salir si ROI acumulado cae por debajo de un umbral.

    Esta regla evalua el campo roi_since_entry del estado del agente.
    Si roi_since_entry < min_roi, el agente debe salir.

    Nota: roi_since_entry es un valor decimal (ej: -0.10 = -10%)

    Ejemplo:
        rule = ROIThresholdRule(min_roi=-0.10)  # -10%
        if rule.should_exit(agent_state):
            print(rule.get_reason())  # "ROI acumulado por debajo de -10.00%"
    """

    def __init__(self, min_roi: float = -0.10):
        """
        Constructor de la regla.

        Args:
            min_roi: Umbral minimo de ROI acumulado (en decimal)
                    Ejemplo: -0.10 = -10%, -0.05 = -5%
                    Si roi_since_entry < min_roi, el agente sale
                    (default: -0.10 = -10%)
        """
        self.min_roi = min_roi

    def should_exit(self, agent_state: AgentState) -> bool:
        """
        Evalua si el agente debe salir por ROI bajo.

        Args:
            agent_state: Estado actual del agente

        Returns:
            True si roi_since_entry < min_roi, False en caso contrario
        """
        if agent_state.roi_since_entry is None:
            return False

        return agent_state.roi_since_entry < self.min_roi

    def get_reason(self) -> str:
        """
        Retorna la razon de salida.

        Returns:
            Descripcion de la regla aplicada con el umbral en porcentaje
        """
        return f"ROI acumulado por debajo de {self.min_roi:.2%}"
