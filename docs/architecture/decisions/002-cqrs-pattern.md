# ADR 002: Implementación de CQRS (Command Query Responsibility Segregation)

## Estado
Aceptado

## Contexto
El `SelectionService` original mezclaba operaciones de lectura (queries) y escritura (commands), violando el principio de responsabilidad única (SRP) y dificultando:
- Optimización independiente de lecturas vs escrituras
- Caching selectivo en queries
- Testing granular
- Escalabilidad horizontal

## Decisión
Implementamos **CQRS Pattern** separando responsabilidades en dos servicios especializados:

### 1. SelectionQueryService (Read Side)
**Ubicación**: `app/application/queries/selection_queries.py`

**Responsabilidades** (Solo LECTURA):
- ✅ Consultar agentes disponibles
- ✅ Calcular ROI de agentes
- ✅ Rankear agentes
- ✅ Filtrar agentes por criterios
- ❌ NO guarda datos

**Métodos principales**:
```python
- get_all_agents_from_balances()
- calculate_single_agent_roi()
- calculate_all_agents_roi()
- rank_agents()
- select_top_n()
- filter_agents_by_aum()
```

### 2. SelectionCommandService (Write Side)
**Ubicación**: `app/application/commands/selection_commands.py`

**Responsabilidades** (Solo ESCRITURA):
- ✅ Guardar Top 16 en base de datos
- ✅ Actualizar rankings
- ✅ Eliminar registros antiguos
- ✅ Bulk operations
- ❌ NO consulta datos

**Métodos principales**:
```python
- save_top16_to_database()
- update_agent_rank()
- delete_top16_for_date()
- bulk_save_top16()
```

## Consecuencias

### Positivas
✅ **SRP mejorado**: Cada servicio tiene una sola razón de cambio
✅ **Optimización independiente**: Queries pueden usar cache, commands garantizan consistencia
✅ **Escalabilidad**: Fácil escalar reads vs writes independientemente
✅ **Testabilidad**: Tests más enfocados y granulares
✅ **Performance**: Queries optimizadas sin afectar integridad de writes

### Negativas
⚠️ **Más archivos**: Dos servicios en lugar de uno
⚠️ **Sincronización**: Si se usan bases de datos separadas (eventual consistency)
⚠️ **Duplicación**: Algunos modelos pueden duplicarse entre query y command

## Beneficios Específicos

### Para Queries
- Caching agresivo sin riesgo
- Read replicas de base de datos
- Índices optimizados para lectura
- Denormalización de datos

### Para Commands
- Validaciones de negocio centralizadas
- Transacciones ACID
- Event sourcing (futuro)
- Audit logs

## Ejemplo de Uso

```python
# Query Service (lectura)
query_service = SelectionQueryService(...)
all_agents = await query_service.calculate_all_agents_roi(date(2025, 10, 7))
top16 = await query_service.select_top_n(all_agents, n=16)

# Command Service (escritura)
command_service = SelectionCommandService(...)
result = await command_service.save_top16_to_database(top16, date(2025, 10, 7))
```

## Alternativas Consideradas

### 1. Mantener servicio único
- ❌ Violaba SRP
- ❌ Difícil optimizar independently
- ❌ Acoplamiento alto

### 2. Event Sourcing completo
- ⚠️ Demasiado complejo para MVP
- ⚠️ Requiere más infraestructura
- ✅ Posible evolución futura

## Migración
El `SelectionService` original se mantiene temporalmente para compatibilidad, pero se recomienda migrar a los nuevos servicios CQRS.

## Referencias
- [CQRS Pattern - Martin Fowler](https://martinfowler.com/bliki/CQRS.html)
- [CQRS Journey - Microsoft](https://docs.microsoft.com/en-us/previous-versions/msp-n-p/jj554200(v=pandp.10))

## Fecha
2025-11-04

## Autores
- Claude Code (Sonnet 4.5)
