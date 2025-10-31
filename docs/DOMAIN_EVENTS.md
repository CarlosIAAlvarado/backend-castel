# Domain Events - Event-Driven Architecture

## 📋 Descripción General

Este documento describe la implementación del patrón **Domain Events** en Casterly Rock Simulation, siguiendo principios de **Domain-Driven Design (DDD)** y arquitectura orientada a eventos.

## 🎯 Objetivos

- **Desacoplar servicios**: Los servicios no tienen dependencias directas entre sí
- **Reaccionar a cambios**: Los handlers pueden ejecutar lógica adicional cuando ocurren eventos
- **Extensibilidad**: Fácil agregar nuevos handlers sin modificar código existente
- **Auditabilidad**: Todos los eventos importantes quedan registrados

## 🏗️ Arquitectura

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                      EVENT BUS (Singleton)                   │
│  - subscribe(event_type, handler)                           │
│  - publish(event)                                           │
│  - unsubscribe(event_type, handler)                         │
└─────────────────────────────────────────────────────────────┘
                        ▲              │
                        │              │
           ┌────────────┘              └─────────────┐
           │                                         │
    PUBLISHERS                                  SUBSCRIBERS
   (Services)                                   (Handlers)
           │                                         │
           ▼                                         ▼
┌─────────────────────┐                  ┌─────────────────────┐
│ ReplacementService  │                  │ LoggingEventHandler │
│ - execute_replace() │                  │ - handle_agent_...()│
│   └─> publish(event)│                  │                     │
└─────────────────────┘                  └─────────────────────┘
┌─────────────────────┐                  ┌─────────────────────┐
│ DailyOrchestrator   │                  │ AgentEventHandlers  │
│ - process_day()     │                  │ - handle_rotation() │
│   └─> publish(event)│                  │ - handle_exited()   │
└─────────────────────┘                  └─────────────────────┘
```

### Patrón Publisher/Subscriber (Pub/Sub)

1. **Publishers** (servicios): Publican eventos cuando ocurre algo importante
2. **Event Bus**: Gestiona suscripciones y distribuye eventos
3. **Subscribers** (handlers): Reaccionan a los eventos ejecutando lógica adicional

## 📦 Eventos Disponibles

### Agent Events (`app.domain.events.agent_events`)

| Evento | Cuándo se dispara | Datos principales |
|--------|-------------------|-------------------|
| `AgentExitedEvent` | Agente sale de Casterly Rock | agent_id, exit_date, reason, roi_total |
| `AgentEnteredEvent` | Agente entra a Casterly Rock | agent_id, entry_date, roi_7d |
| `AgentRotationCompletedEvent` | Rotación completada | agent_out, agent_in, reason |
| `AgentStateChangedEvent` | Cambia estado de agente | agent_id, date, old_state, new_state |
| `AgentFallingConsecutiveDaysEvent` | Agente con días consecutivos cayendo | agent_id, fall_days |

### Assignment Events (`app.domain.events.assignment_events`)

| Evento | Cuándo se dispara | Datos principales |
|--------|-------------------|-------------------|
| `AccountsAssignedEvent` | Cuentas asignadas inicialmente | agent_id, account_ids, total_aum |
| `AccountsReassignedEvent` | Cuentas transferidas entre agentes | from_agent_id, to_agent_id, account_ids |

### Simulation Events (`app.domain.events.simulation_events`)

| Evento | Cuándo se dispara | Datos principales |
|--------|-------------------|-------------------|
| `DailyProcessCompletedEvent` | Día de simulación procesado | process_date, agents_in_casterly, rotations_count |
| `SimulationCompletedEvent` | Simulación completa terminada | start_date, end_date, total_rotations |

## 🚀 Uso

### 1. Registrar Handlers al Iniciar la Aplicación

```python
# En main.py o startup
from app.application.event_handlers import register_event_handlers
from app.infrastructure.repositories import rotation_log_repo_impl

# Registrar todos los handlers
register_event_handlers(rotation_log_repo=rotation_log_repo_impl)
```

### 2. Publicar Eventos desde Servicios

```python
from app.domain.events import event_bus, AgentExitedEvent

# En cualquier servicio
def remove_agent(agent_id: str, date: date, reason: str):
    # ... lógica de negocio ...

    # Publicar evento
    event = AgentExitedEvent(
        agent_id=agent_id,
        exit_date=date,
        reason=reason,
        roi_total=-0.08,
        fall_days=3
    )
    event_bus.publish(event)
```

### 3. Crear Handlers Personalizados

```python
from app.domain.events import AgentExitedEvent

def my_custom_handler(event: AgentExitedEvent) -> None:
    """
    Handler personalizado para eventos de salida de agente.
    """
    print(f"Agent {event.agent_id} exited with ROI: {event.roi_total}")
    # Lógica adicional (enviar email, actualizar dashboard, etc.)

# Registrar handler
event_bus.subscribe(AgentExitedEvent, my_custom_handler)
```

## 🧪 Testing

### Testing de Event Bus

```python
from unittest.mock import Mock
from app.domain.events import EventBus, AgentExitedEvent

def test_event_bus():
    bus = EventBus()
    handler = Mock()

    # Registrar handler
    bus.subscribe(AgentExitedEvent, handler)

    # Publicar evento
    event = AgentExitedEvent(
        agent_id="futures-001",
        exit_date=date(2025, 10, 15),
        reason="Consecutive fall days"
    )
    bus.publish(event)

    # Verificar que handler fue llamado
    handler.assert_called_once_with(event)
```

### Testing de Handlers

```python
from app.application.event_handlers import AgentEventHandlers

def test_agent_exited_handler():
    handler = AgentEventHandlers()

    event = AgentExitedEvent(
        agent_id="futures-001",
        exit_date=date(2025, 10, 15),
        reason="Consecutive fall days",
        roi_total=-0.20
    )

    # Handler no debe fallar
    handler.handle_agent_exited(event)
```

## 🔧 Configuración Avanzada

### Handlers con Dependencias

```python
from app.application.event_handlers import AgentEventHandlers

# Handler con repositorio inyectado
agent_handlers = AgentEventHandlers(rotation_log_repo=rotation_log_repo)

event_bus.subscribe(AgentRotationCompletedEvent, agent_handlers.handle_rotation_completed)
```

### Desregistrar Handlers

```python
# Desregistrar handler específico
event_bus.unsubscribe(AgentExitedEvent, my_handler)

# Limpiar todos los handlers de un tipo
event_bus.clear_handlers(AgentExitedEvent)

# Limpiar TODOS los handlers
event_bus.clear_handlers()
```

## 📊 Ventajas del Sistema de Eventos

### ✅ Desacoplamiento
- **ReplacementService** no necesita conocer qué pasa después de una rotación
- Nuevos handlers pueden agregarse sin modificar servicios existentes

### ✅ Single Responsibility Principle (SRP)
- Cada handler tiene una responsabilidad única
- **LoggingEventHandler**: Solo logging
- **AgentEventHandlers**: Lógica de negocio especializada

### ✅ Open/Closed Principle (OCP)
- Sistema abierto para extensión (agregar handlers)
- Cerrado para modificación (no hay que cambiar código existente)

### ✅ Auditabilidad
- Todos los eventos quedan registrados
- Fácil rastrear qué pasó y cuándo

### ✅ Testing
- Fácil mockear handlers
- Event Bus puede limpiarse entre tests
- No afecta lógica de negocio principal

## 🚨 Consideraciones

### Ejecución Sincrónica
- Los handlers se ejecutan **sincrónicamente** en el mismo thread
- Si un handler falla, los demás continúan ejecutándose
- Los errores se loguean pero no detienen el flujo

### Orden de Ejecución
- No hay garantía de orden entre handlers del mismo tipo
- Si el orden importa, usar un único handler o eventos encadenados

### Performance
- Si hay muchos handlers pesados, considerar ejecución asíncrona
- Actualmente todos los handlers son rápidos (logging, DB writes)

## 📚 Referencias

- **Domain Events**: Martin Fowler - https://martinfowler.com/eaaDev/DomainEvent.html
- **DDD**: Eric Evans - Domain-Driven Design
- **Pub/Sub Pattern**: https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern

## 🔄 Flujo Ejemplo: Rotación de Agente

```
1. DailyOrchestratorService detecta que agente debe salir
2. Llama a ReplacementService.execute_replacement()
3. ReplacementService:
   a. Encuentra agente de reemplazo
   b. Transfiere cuentas
   c. Registra en rotation_log
   d. Publica 4 eventos:
      - AgentExitedEvent
      - AgentEnteredEvent
      - AgentRotationCompletedEvent
      - AccountsReassignedEvent

4. Event Bus distribuye cada evento a sus handlers:

   AgentExitedEvent → LoggingEventHandler.handle_agent_exited()
                   → AgentEventHandlers.handle_agent_exited()

   AgentEnteredEvent → LoggingEventHandler.handle_agent_entered()
                    → AgentEventHandlers.handle_agent_entered()

   ... y así con cada evento

5. Cada handler ejecuta su lógica independientemente
6. ReplacementService retorna resultado sin esperar handlers
```

## 📝 Ejemplo Completo

Ver [replacement_service.py:256-302](../app/application/services/replacement_service.py#L256-L302) para ver la implementación completa de publicación de eventos en el flujo de rotación.

Ver [test_domain_events.py](../tests/unit/test_domain_events.py) para ver tests completos del sistema de eventos.
