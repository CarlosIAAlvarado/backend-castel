# ADR 003: Implementación de Unit of Work Pattern

## Estado
Aceptado

## Contexto
El sistema necesita garantizar integridad transaccional cuando se realizan múltiples operaciones en diferentes repositorios. Por ejemplo:
- Crear un log de rotación
- Actualizar assignment de un agente
- Modificar balance de cuentas
- Actualizar estado de agente

Sin transacciones, si falla una operación intermedia, el sistema queda en estado inconsistente.

## Decisión
Implementamos **Unit of Work Pattern** para gestionar transacciones y garantizar ACID compliance.

### Implementación

#### 1. Interfaz de Dominio
**Ubicación**: `app/domain/uow/unit_of_work.py`

```python
class UnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self): pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass

    @abstractmethod
    async def commit(self): pass

    @abstractmethod
    async def rollback(self): pass
```

#### 2. Implementación MongoDB
**Ubicación**: `app/infrastructure/uow/mongo_unit_of_work.py`

**Características**:
- Usa MongoDB sessions para transacciones
- Proporciona acceso a todos los repositorios
- Rollback automático en caso de error
- Compatible con MongoDB replica sets

**Atributos disponibles**:
```python
async with MongoUnitOfWork() as uow:
    uow.rotations       # RotationLogRepository
    uow.assignments     # AssignmentRepository
    uow.balances        # BalanceRepository
    uow.agent_states    # AgentStateRepository
    uow.top16           # Top16Repository
```

## Ejemplo de Uso

### Sin Unit of Work (❌ INCORRECTO)
```python
# Si falla el último paso, los anteriores ya se guardaron
await rotation_repo.create(rotation_log)
await assignment_repo.update(assignment)  # ✅ Guardado
await balance_repo.update(balance)        # ❌ FALLA
# Estado inconsistente: rotación y assignment guardados, pero balance no
```

### Con Unit of Work (✅ CORRECTO)
```python
async with MongoUnitOfWork() as uow:
    # Crear rotación
    rotation = RotationLog(...)
    await uow.rotations.create(rotation)

    # Actualizar assignment
    assignment.agent_id = new_agent_id
    await uow.assignments.update(assignment)

    # Actualizar balance
    balance.balance += transfer_amount
    await uow.balances.update(balance)

    # Commit: TODO O NADA
    await uow.commit()

# Si cualquier operación falla, ROLLBACK automático
# Garantiza consistencia de datos
```

## Consecuencias

### Positivas
✅ **Integridad transaccional**: Garantiza ACID compliance
✅ **Rollback automático**: Si algo falla, revierte todo
✅ **Código más limpio**: Transacciones explícitas y claras
✅ **Reduce bugs**: Evita estados inconsistentes
✅ **Testing más fácil**: Mock del Unit of Work completo

### Negativas
⚠️ **Requiere replica set**: MongoDB necesita replica set para transacciones
⚠️ **Performance**: Transacciones tienen overhead (mínimo)
⚠️ **Complejidad**: Requiere entender el patrón

## Casos de Uso Principales

### 1. Rotaciones de Agentes
```python
async with MongoUnitOfWork() as uow:
    # 1. Registrar rotación
    await uow.rotations.create(rotation_log)

    # 2. Transferir cuentas
    for account in accounts:
        account.agent_id = new_agent_id
        await uow.assignments.update(account)

    # 3. Actualizar estado
    old_agent.status = "inactive"
    await uow.agent_states.update(old_agent)

    await uow.commit()
```

### 2. Rebalanceo de Cuentas
```python
async with MongoUnitOfWork() as uow:
    # Redistribuir 1000 cuentas entre 16 agentes
    for agent_id, accounts_to_assign in redistribution.items():
        for account in accounts_to_assign:
            await uow.assignments.update(account)

    await uow.commit()  # Todo o nada
```

### 3. Simulación Diaria con Client Accounts
```python
async with MongoUnitOfWork() as uow:
    # 1. Guardar Top 16
    await uow.top16.bulk_save(top16_agents)

    # 2. Actualizar client accounts
    for account in updated_accounts:
        await uow.assignments.update(account)

    # 3. Registrar snapshot
    await uow.snapshots.create(snapshot)

    await uow.commit()
```

## Limitaciones y Consideraciones

### MongoDB sin Replica Set
Si MongoDB no tiene replica set configurado (ej: desarrollo local):
- Las transacciones fallan silenciosamente
- Las operaciones se ejecutan sin transacción
- Se mantiene la API consistente
- Warning en logs

**Recomendación**: Usar replica set incluso en desarrollo.

### Performance
- Transacciones MongoDB tienen overhead mínimo (~2-5ms)
- Beneficio de consistencia supera el costo
- Para operaciones sin riesgo, usar repositorios directamente

## Alternativas Consideradas

### 1. Transacciones Manuales
- ❌ Propenso a errores
- ❌ Código duplicado
- ❌ Difícil de mantener

### 2. Saga Pattern
- ✅ Útil para microservicios
- ⚠️ Over-engineering para monolito
- 🔮 Posible migración futura

### 3. Sin Transacciones
- ❌ Estados inconsistentes
- ❌ Bugs difíciles de reproducir
- ❌ Pérdida de confianza en datos

## Migración

### Paso 1: Identificar operaciones críticas
- Rotaciones de agentes
- Redistribución de cuentas
- Sincronización de client accounts

### Paso 2: Refactorizar para usar UoW
```python
# Antes
await repo1.save(data1)
await repo2.update(data2)

# Después
async with MongoUnitOfWork() as uow:
    await uow.repo1.save(data1)
    await uow.repo2.update(data2)
    await uow.commit()
```

### Paso 3: Tests
- Testear rollback automático
- Testear commit exitoso
- Testear error handling

## Referencias
- [Unit of Work Pattern - Martin Fowler](https://martinfowler.com/eaaCatalog/unitOfWork.html)
- [MongoDB Transactions](https://docs.mongodb.com/manual/core/transactions/)
- [Python Context Managers](https://docs.python.org/3/library/contextlib.html)

## Fecha
2025-11-04

## Autores
- Claude Code (Sonnet 4.5)
