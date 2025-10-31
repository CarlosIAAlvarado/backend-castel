from app.domain.rules.exit_rule import ExitRule
from app.domain.entities.agent_state import AgentState


class ConsecutiveFallRule(ExitRule):
    """
    Regla de salida: Salir despues de N dias consecutivos de caida.

    Esta regla evalua el campo fall_days del estado del agente.
    Si fall_days >= min_fall_days, el agente debe salir.

    Ejemplo:
        rule = ConsecutiveFallRule(min_fall_days=3)
        if rule.should_exit(agent_state):
            print(rule.get_reason())  # "Caida consecutiva por 3 dias"
    """

    def __init__(self, min_fall_days: int = 3):
        """
        Constructor de la regla.

        Args:
            min_fall_days: Numero minimo de dias consecutivos en caida
                          para que el agente deba salir (default: 3)
        """
        if min_fall_days < 1:
            raise ValueError("min_fall_days debe ser mayor o igual a 1")

        self.min_fall_days = min_fall_days

    def should_exit(self, agent_state: AgentState) -> bool:
        """
        Evalua si el agente debe salir por dias consecutivos de caida.

        Args:
            agent_state: Estado actual del agente

        Returns:
            True si fall_days >= min_fall_days, False en caso contrario
        """
        return agent_state.fall_days >= self.min_fall_days

    def get_reason(self) -> str:
        """
        Retorna la razon de salida.

        Returns:
            Descripcion de la regla aplicada
        """
        return f"Caida consecutiva por {self.min_fall_days} dias"
