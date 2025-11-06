# ADR 004: Domain Services para Lógica de Negocio Pura

## Estado
Aceptado

## Contexto
La lógica de negocio compleja que no pertenece naturalmente a una sola entidad estaba dispersa en Application Services, mezclando lógica de negocio pura con I/O operations. Esto dificultaba:
- Testing de lógica de negocio sin mocks de DB
- Reutilización de reglas de negocio
- Claridad sobre qué es lógica de dominio vs coordinación

## Decisión
Creamos **Domain Services** para encapsular lógica de negocio pura que:
- No pertenece a una sola entidad
- No depende de infraestructura (sin I/O, sin DB)
- Es reutilizable en diferentes contextos
- Representa operaciones del dominio

### Domain Services Implementados

#### 1. AgentRotationDomainService
**Ubicación**: `app/domain/services/agent_rotation_domain_service.py`

**Responsabilidades**:
- ✅ Determinar si un agente puede ser rotado
- ✅ Calcular tiempo mínimo de permanencia
- ✅ Evaluar criterios de performance
- ✅ Calcular penalizaciones por rotación
- ✅ Validar reglas de rotación
- ❌ NO accede a base de datos
- ❌ NO hace I/O

**Métodos principales**:
```python
can_agent_be_rotated()                    # Elegibilidad de rotación
calculate_rotation_penalty()              # Penalización de cuentas
calculate_optimal_agent_replacement()     # Reemplazo óptimo
validate_rotation_rules()                 # Validaciones de negocio
```

**Constantes de negocio**:
```python
MIN_DAYS_BEFORE_ROTATION = 3              # Mínimo 3 días antes de rotar
MIN_ROI_THRESHOLD = -0.05                 # ROI mínimo aceptable: -5%
POOR_PERFORMANCE_DAYS = 2                 # Días consecutivos pobres
ROTATION_PENALTY_FACTOR = 0.10            # 10% penalización
```

#### 2. RiskManagementDomainService
**Ubicación**: `app/domain/services/risk_management_domain_service.py`

**Responsabilidades**:
- ✅ Calcular nivel de riesgo de agentes
- ✅ Calcular Sharpe Ratio
- ✅ Calcular Maximum Drawdown
- ✅ Evaluar diversificación de portfolio
- ✅ Calcular tamaño óptimo de posición (Kelly Criterion)
- ❌ NO accede a base de datos
- ❌ NO hace I/O

**Métodos principales**:
```python
calculate_risk_level()                    # RiskLevel (LOW/MEDIUM/HIGH/CRITICAL)
calculate_sharpe_ratio()                  # Sharpe Ratio (risk-adjusted return)
calculate_max_drawdown()                  # Maximum Drawdown
evaluate_portfolio_diversification()      # HHI (Herfindahl-Hirschman Index)
calculate_optimal_position_size()         # Kelly Criterion
```

**Métricas de riesgo**:
```python
ROI_THRESHOLD_LOW_RISK = 0.10             # ROI > 10% = bajo riesgo
DRAWDOWN_THRESHOLD_LOW_RISK = 0.05        # Drawdown < 5%
WIN_RATE_THRESHOLD_LOW_RISK = 0.70        # Win rate > 70%
```

## Diferencia entre Application Services y Domain Services

### Application Service (app/application/services/)
```python
class ReplacementService:
    """Coordina operaciones con I/O"""

    def __init__(self, rotation_repo, assignment_repo, ...):
        self.rotation_repo = rotation_repo        # Depende de repos
        self.assignment_repo = assignment_repo

    async def execute_rotations(self, agents_to_exit):
        # 1. Leer datos de DB
        agents_data = await self.get_agents(agents_to_exit)

        # 2. Lógica de negocio (DELEGAR a Domain Service)
        domain_service = AgentRotationDomainService()
        for agent in agents_data:
            can_rotate, reason = domain_service.can_agent_be_rotated(...)

        # 3. Guardar en DB
        await self.rotation_repo.create(rotation_log)
```

### Domain Service (app/domain/services/)
```python
class AgentRotationDomainService:
    """Solo lógica de negocio pura"""

    # Sin constructor con dependencias
    # Sin I/O operations

    def can_agent_be_rotated(
        self,
        agent_data: Dict[str, Any],
        entry_date: date,
        current_date: date
    ) -> tuple[RotationEligibility, str]:
        """
        Lógica de negocio PURA (sin I/O).
        Fácil de testear sin mocks.
        """
        days_in_top16 = (current_date - entry_date).days

        if days_in_top16 < self.MIN_DAYS_BEFORE_ROTATION:
            return RotationEligibility.NOT_ELIGIBLE_MINIMUM_TIME, "Too soon"

        if agent_data["roi_7d"] >= self.MIN_ROI_THRESHOLD:
            return RotationEligibility.NOT_ELIGIBLE_PERFORMANCE, "Good performance"

        return RotationEligibility.ELIGIBLE, "Eligible for rotation"
```

## Consecuencias

### Positivas
✅ **Testabilidad extrema**: Pure functions sin dependencias externas
✅ **Reutilización**: Misma lógica en diferentes contextos
✅ **Claridad**: Queda claro qué es lógica de dominio
✅ **Performance**: Sin overhead de I/O en unit tests
✅ **Documentación viva**: Reglas de negocio centralizadas

### Negativas
⚠️ **Más archivos**: Separar lógica en services adicionales
⚠️ **Coordinación**: Application Services deben orquestar

## Ejemplo de Uso

### Antes (sin Domain Service)
```python
# Lógica mezclada en Application Service
class ReplacementService:
    async def can_rotate_agent(self, agent_id, target_date):
        # Mezcla I/O con lógica de negocio
        agent = await self.agent_repo.get(agent_id)
        balance = await self.balance_repo.get(agent_id)

        # Lógica de negocio embebida (difícil de testear)
        if agent.roi_7d < -0.05 and agent.days_in_top16 >= 3:
            return True
        return False
```

### Después (con Domain Service)
```python
# Lógica de negocio separada
class AgentRotationDomainService:
    def can_agent_be_rotated(self, agent_data, entry_date, current_date):
        # Lógica pura (fácil de testear)
        days_in_top16 = (current_date - entry_date).days

        if days_in_top16 < self.MIN_DAYS_BEFORE_ROTATION:
            return RotationEligibility.NOT_ELIGIBLE_MINIMUM_TIME, "Too soon"

        if agent_data["roi_7d"] >= self.MIN_ROI_THRESHOLD:
            return RotationEligibility.NOT_ELIGIBLE_PERFORMANCE, "Good performance"

        return RotationEligibility.ELIGIBLE, "Eligible"

# Application Service coordina I/O
class ReplacementService:
    async def can_rotate_agent(self, agent_id, target_date):
        # 1. I/O operation
        agent_data = await self.get_agent_data(agent_id)

        # 2. Domain logic (delegado)
        domain_service = AgentRotationDomainService()
        eligibility, reason = domain_service.can_agent_be_rotated(
            agent_data, agent_data["entry_date"], target_date
        )

        return eligibility == RotationEligibility.ELIGIBLE
```

## Testing

### Domain Service (Unit Test Puro)
```python
def test_agent_eligible_for_rotation():
    """Test sin mocks, sin DB, sin I/O"""
    service = AgentRotationDomainService()

    agent_data = {"roi_7d": -0.08, "negative_days": 3}
    entry_date = date(2025, 10, 1)
    current_date = date(2025, 10, 5)  # 4 días después

    eligibility, reason = service.can_agent_be_rotated(
        agent_data, entry_date, current_date
    )

    assert eligibility == RotationEligibility.ELIGIBLE
    # Sin mocks, sin DB, test instantáneo
```

### Application Service (Integration Test)
```python
@pytest.mark.asyncio
async def test_execute_rotations(mock_rotation_repo, mock_assignment_repo):
    """Test con mocks de repositorios"""
    service = ReplacementService(mock_rotation_repo, mock_assignment_repo)

    # ... test con mocks
```

## Alternativas Consideradas

### 1. Mantener lógica en Application Services
- ❌ Mezcla I/O con lógica de negocio
- ❌ Tests lentos (requieren mocks)
- ❌ Difícil reutilizar lógica

### 2. Lógica en Entities
- ⚠️ Solo funciona si la lógica es de una sola entidad
- ❌ No aplica para lógica que involucra múltiples entidades

### 3. Utility Functions
- ⚠️ Pierde cohesión
- ❌ No representa claramente el dominio

## Referencias
- [Domain Services - DDD - Eric Evans](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf)
- [When to Create a Domain Service](https://enterprisecraftsmanship.com/posts/domain-vs-application-services/)

## Fecha
2025-11-04

## Autores
- Claude Code (Sonnet 4.5)
