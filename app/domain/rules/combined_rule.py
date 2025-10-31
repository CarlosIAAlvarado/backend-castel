from typing import List
from app.domain.rules.exit_rule import ExitRule
from app.domain.entities.agent_state import AgentState


class CombinedRule(ExitRule):
    """
    Regla compuesta: Evalua multiples reglas con operadores logicos AND u OR.

    Permite combinar varias reglas de salida usando logica booleana:
    - AND: Todas las reglas deben cumplirse
    - OR: Al menos una regla debe cumplirse

    Ejemplo AND (todas las reglas deben cumplirse):
        rules = [
            ConsecutiveFallRule(min_fall_days=3),
            ROIThresholdRule(min_roi=-0.05)
        ]
        combined = CombinedRule(rules, operator="AND")
        # El agente sale solo si tiene 3+ dias de caida Y ROI < -5%

    Ejemplo OR (al menos una regla debe cumplirse):
        rules = [
            ConsecutiveFallRule(min_fall_days=3),
            ROIThresholdRule(min_roi=-0.10)
        ]
        combined = CombinedRule(rules, operator="OR")
        # El agente sale si tiene 3+ dias de caida O ROI < -10%
    """

    def __init__(self, rules: List[ExitRule], operator: str = "OR"):
        """
        Constructor de la regla compuesta.

        Args:
            rules: Lista de reglas a combinar
            operator: Operador logico "AND" u "OR" (default: "OR")

        Raises:
            ValueError: Si rules esta vacio o operator es invalido
        """
        if not rules:
            raise ValueError("La lista de reglas no puede estar vacia")

        self.rules = rules
        self.operator = operator.upper()

        if self.operator not in ["AND", "OR"]:
            raise ValueError(f"Operador invalido: {operator}. Use 'AND' u 'OR'")

    def should_exit(self, agent_state: AgentState) -> bool:
        """
        Evalua si el agente debe salir segun la combinacion de reglas.

        Args:
            agent_state: Estado actual del agente

        Returns:
            - Si operator="AND": True si TODAS las reglas se cumplen
            - Si operator="OR": True si AL MENOS UNA regla se cumple
        """
        if self.operator == "AND":
            return all(rule.should_exit(agent_state) for rule in self.rules)
        else:  # OR
            return any(rule.should_exit(agent_state) for rule in self.rules)

    def get_reason(self) -> str:
        """
        Retorna la razon de salida combinada.

        Returns:
            String con todas las razones unidas por el operador
        """
        reasons = [rule.get_reason() for rule in self.rules]
        return f" {self.operator} ".join(reasons)

    def get_triggered_reasons(self, agent_state: AgentState) -> List[str]:
        """
        Retorna solo las razones de las reglas que se activaron.

        Util para saber exactamente que reglas se cumplieron.

        Args:
            agent_state: Estado actual del agente

        Returns:
            Lista de razones de las reglas que se cumplieron
        """
        triggered = []
        for rule in self.rules:
            if rule.should_exit(agent_state):
                triggered.append(rule.get_reason())
        return triggered
