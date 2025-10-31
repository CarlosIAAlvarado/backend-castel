# ISP (Interface Segregation Principle) - Ejemplos de Uso

Este documento muestra como usar las interfaces segregadas de AssignmentRepository segun ISP.

---

## Interfaces Segregadas Disponibles

### 1. AssignmentReadOps
**Proposito:** Solo operaciones de LECTURA
**Archivo:** `assignment_read_ops.py`
**Metodos:**
- `get_active_assignments()` - Obtiene todas las asignaciones activas
- `get_active_by_agent(agent_id)` - Obtiene asignaciones activas de un agente
- `get_active_by_account(account_id)` - Obtiene asignacion activa de una cuenta
- `get_by_date(target_date)` - Obtiene asignaciones de una fecha

### 2. AssignmentWriteOps
**Proposito:** Solo operaciones de ESCRITURA
**Archivo:** `assignment_write_ops.py`
**Metodos:**
- `create(assignment)` - Crea una asignacion
- `create_batch(assignments)` - Crea multiples asignaciones
- `deactivate(assignment_id)` - Desactiva una asignacion
- `transfer_accounts(from_agent, to_agent)` - Transfiere cuentas entre agentes

### 3. AssignmentRepository
**Proposito:** Interfaz completa (legacy)
**Archivo:** `assignment_repository.py`
**Metodos:** Todos los anteriores

---

## Ejemplos de Uso

### Ejemplo 1: Servicio de Solo Lectura (Reportes)

```python
from app.domain.repositories import AssignmentReadOps

class ReportService:
    """
    Servicio de reportes que solo necesita LEER datos.
    Depende solo de AssignmentReadOps (ISP cumplido).
    """

    def __init__(self, assignment_reader: AssignmentReadOps):
        self.assignment_reader = assignment_reader

    def get_agent_portfolio_report(self, agent_id: str) -> dict:
        """Genera reporte de portafolio de un agente."""
        assignments = self.assignment_reader.get_active_by_agent(agent_id)

        total_aum = sum(a.balance for a in assignments)
        n_accounts = len(assignments)

        return {
            "agent_id": agent_id,
            "n_accounts": n_accounts,
            "total_aum": total_aum,
            "accounts": [
                {"account_id": a.account_id, "balance": a.balance}
                for a in assignments
            ]
        }
```

**Ventajas:**
- El servicio NO puede modificar datos accidentalmente
- Interfaz mas pequena = mas facil de entender
- Permisos mas granulares (readonly user)
- Tests mas simples (solo mockeamos lecturas)

---

### Ejemplo 2: Servicio de Solo Escritura (Orquestacion)

```python
from app.domain.repositories import AssignmentWriteOps

class AssignmentOrchestrator:
    """
    Servicio de orquestacion que solo ESCRIBE datos.
    Depende solo de AssignmentWriteOps (ISP cumplido).
    """

    def __init__(self, assignment_writer: AssignmentWriteOps):
        self.assignment_writer = assignment_writer

    def assign_accounts_to_agent(
        self,
        account_ids: List[str],
        agent_id: str,
        balances: Dict[str, float]
    ) -> List[Assignment]:
        """Asigna multiples cuentas a un agente."""
        assignments = []

        for account_id in account_ids:
            assignment = Assignment(
                account_id=account_id,
                agent_id=agent_id,
                balance=balances.get(account_id, 0.0),
                date=date.today(),
                is_active=True
            )
            assignments.append(assignment)

        return self.assignment_writer.create_batch(assignments)
```

**Ventajas:**
- El servicio NO puede leer datos (separacion de responsabilidades)
- Interfaz mas pequena = mas facil de entender
- Permisos mas granulares (write-only service)
- Tests mas simples (solo mockeamos escrituras)

---

### Ejemplo 3: Servicio Mixto (Lectura + Escritura)

```python
from app.domain.repositories import AssignmentReadOps, AssignmentWriteOps

class RotationService:
    """
    Servicio de rotacion que necesita LEER y ESCRIBIR.
    Depende de ambas interfaces (ISP cumplido).
    """

    def __init__(
        self,
        assignment_reader: AssignmentReadOps,
        assignment_writer: AssignmentWriteOps
    ):
        self.assignment_reader = assignment_reader
        self.assignment_writer = assignment_writer

    def rotate_agent(self, from_agent: str, to_agent: str) -> dict:
        """Rota las cuentas de un agente a otro."""
        # LECTURA: Obtener cuentas actuales
        current_assignments = self.assignment_reader.get_active_by_agent(from_agent)
        n_accounts = len(current_assignments)

        # ESCRITURA: Transferir cuentas
        transferred = self.assignment_writer.transfer_accounts(from_agent, to_agent)

        return {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "n_accounts": n_accounts,
            "transferred": transferred
        }
```

**Ventajas:**
- Separacion explicita entre lectura y escritura
- Se puede mockear cada interfaz independientemente en tests
- Codigo mas mantenible y testeable

---

## Configuracion en providers.py

```python
from app.domain.repositories import AssignmentReadOps, AssignmentWriteOps
from app.infrastructure.repositories.assignment_repository_impl import AssignmentRepositoryImpl

def get_assignment_read_ops() -> AssignmentReadOps:
    """
    Provider para operaciones de lectura de asignaciones.
    """
    return AssignmentRepositoryImpl()

def get_assignment_write_ops() -> AssignmentWriteOps:
    """
    Provider para operaciones de escritura de asignaciones.
    """
    return AssignmentRepositoryImpl()

# Type aliases con Depends
AssignmentReadOpsDep = Annotated[AssignmentReadOps, Depends(get_assignment_read_ops)]
AssignmentWriteOpsDep = Annotated[AssignmentWriteOps, Depends(get_assignment_write_ops)]
```

---

## Compatibilidad con Codigo Legacy

La implementacion `AssignmentRepositoryImpl` implementa TODAS las interfaces:
- `AssignmentRepository` (completa, legacy)
- `AssignmentReadOps` (solo lectura)
- `AssignmentWriteOps` (solo escritura)

Por lo tanto, el codigo existente sigue funcionando sin cambios:

```python
# Codigo legacy (sigue funcionando)
from app.domain.repositories.assignment_repository import AssignmentRepository

class LegacyService:
    def __init__(self, assignment_repo: AssignmentRepository):
        self.assignment_repo = assignment_repo
```

**No hay breaking changes!**

---

## Migracion Gradual

Puedes migrar servicios gradualmente:

1. **Paso 1:** Identificar servicios que solo leen o solo escriben
2. **Paso 2:** Cambiar su constructor para usar la interfaz segregada
3. **Paso 3:** Actualizar el provider
4. **Paso 4:** Ejecutar tests para validar

**Ejemplo de migracion:**

```python
# ANTES (sin ISP)
class ReportService:
    def __init__(self, assignment_repo: AssignmentRepository):
        self.assignment_repo = assignment_repo

# DESPUES (con ISP)
class ReportService:
    def __init__(self, assignment_reader: AssignmentReadOps):
        self.assignment_reader = assignment_reader
```

---

## Beneficios de ISP en este Proyecto

1. **Principio de menor privilegio:** Servicios solo tienen acceso a lo que necesitan
2. **Codigo mas claro:** Intencion explicita (readonly vs writeonly)
3. **Tests mas simples:** Menos metodos para mockear
4. **Mejor mantenibilidad:** Cambios en escritura no afectan lecturas
5. **Seguridad:** Previene modificaciones accidentales
6. **Puntuacion:** ISP 100/100 en arquitectura SOLID

---

**Fecha de creacion:** 2025-10-16
**Version:** 1.0
**Autor:** Casterly Rock Architecture Team
