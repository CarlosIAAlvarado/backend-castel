# Auditoría de Colecciones MongoDB

## Fecha: 2025-10-30

---

## RESUMEN EJECUTIVO

Se auditaron **16 colecciones** listadas por el usuario. Se clasificaron según su uso en el código y se generaron recomendaciones de limpieza.

---

## CLASIFICACIÓN DE COLECCIONES

### ✅ COLECCIONES ACTIVAS (SE USAN)

Estas colecciones se usan activamente en el código y **NO deben eliminarse**:

#### 1. **agent_roi_7d** ⭐ CRITICA
- **Uso**: Almacena cálculos de ROI de 7 días (caché)
- **Referencias**:
  - `app/application/services/roi_7d_calculation_service.py` - Crea/actualiza ROI
  - `app/application/services/selection_service.py:477,516` - Lee ROI para selección de agentes
  - `app/presentation/routes/reports_routes.py:88,505` - Genera reportes de KPIs
  - `app/infrastructure/repositories/roi_7d_repository.py` - CRUD completo
- **Criticidad**: ALTA - usado en simulaciones activas
- **Recomendación**: **MANTENER**

#### 2. **agent_roi_3d, agent_roi_5d, agent_roi_10d, agent_roi_15d, agent_roi_30d** ⭐ IMPORTANTES
- **Uso**: Almacenan cálculos de ROI para diferentes ventanas temporales
- **Referencias**:
  - `app/utils/collection_names.py:21-27` - Sistema dinámico de nombres
  - `app/application/services/bulk_roi_calculation_service.py:331` - Cálculo dinámico según ventana
  - `app/presentation/routes/simulation_routes.py:281` - Usado en simulaciones
- **Criticidad**: MEDIA-ALTA - soporte para diferentes configuraciones
- **Recomendación**: **MANTENER** (sistema modular para diferentes períodos)

#### 3. **agent_states** ⭐ CRITICA
- **Uso**: Estados de agentes (activo, fallido, etc.)
- **Referencias**:
  - `app/infrastructure/repositories/agent_state_repository_impl.py` - CRUD completo
  - `app/domain/repositories/agent_state_repository.py` - Interface del repositorio
  - `app/presentation/routes/simulation_routes.py` - Usado en simulaciones
  - `app/presentation/routes/reports_routes.py` - Reportes de estados
- **Criticidad**: ALTA - rastreo crítico de estados
- **Recomendación**: **MANTENER**

#### 4. **daily_roi_calculation** ⭐ CRITICA
- **Uso**: Cálculos diarios de ROI (caché temporal)
- **Referencias**:
  - `app/application/services/daily_roi_calculation_service.py` - Servicio principal
  - `app/infrastructure/repositories/daily_roi_repository.py` - Repositorio
  - `app/application/services/daily_orchestrator_service.py:25,625` - Limpieza en cada ejecución
  - `app/domain/entities/daily_roi.py` - Entidad del dominio
- **Criticidad**: ALTA - caché de cálculos diarios
- **Recomendación**: **MANTENER** (se limpia automáticamente)

#### 5. **balances** ⭐ ACTIVA
- **Uso**: Balances de agentes
- **Referencias**:
  - `app/application/services/bulk_roi_calculation_service.py` - Cálculos de ROI
  - `app/application/services/daily_roi_calculation_service.py` - Cálculos diarios
  - `app/presentation/routes/simulation_routes.py` - Simulaciones
- **Criticidad**: ALTA - datos críticos de balance
- **Recomendación**: **MANTENER**

#### 6. **rank_changes** ⭐ ACTIVA
- **Uso**: Cambios en rankings de agentes
- **Referencias**:
  - `app/infrastructure/repositories/rank_change_repository_impl.py` - Repositorio completo
  - `app/application/services/selection_service.py` - Usado en selección
  - `app/presentation/routes/simulation_routes.py` - Simulaciones
  - `app/presentation/routes/reports_routes.py` - Reportes
- **Criticidad**: MEDIA - análisis de tendencias
- **Recomendación**: **MANTENER**

#### 7. **mov07.10** ⭐ ACTIVA
- **Uso**: Movimientos de trading (colección de datos fuente)
- **Referencias**:
  - `app/infrastructure/repositories/movement_repository_impl.py` - Repositorio
  - `app/application/services/bulk_roi_calculation_service.py` - Cálculos
  - `app/application/services/daily_roi_calculation_service.py` - Procesamiento diario
  - `app/presentation/routes/simulation_routes.py` - Simulaciones
- **Criticidad**: ALTA - datos fuente de operaciones
- **Recomendación**: **MANTENER**

#### 8. **cuentas_clientes_trading** ⭐ CRITICA
- **Uso**: Cuentas de clientes (1000 cuentas con copytrading)
- **Referencias**:
  - `app/application/services/client_accounts_service.py:33` - Servicio principal
  - `app/application/services/client_accounts_simulation_service.py:55` - Simulaciones
  - `app/infrastructure/database/init_client_accounts_collections.py` - Inicialización
- **Criticidad**: CRITICA - microservicio de client accounts
- **Recomendación**: **MANTENER**

#### 9. **historial_asignaciones_clientes** ⭐ CRITICA
- **Uso**: Historial de asignaciones de cuentas a agentes
- **Referencias**:
  - `app/application/services/client_accounts_service.py:34` - Servicio principal
  - `app/application/services/client_accounts_simulation_service.py:56` - Simulaciones
  - `app/presentation/routes/client_accounts_routes.py` - API
  - `app/presentation/routes/simulations_routes.py:200` - Limpieza de simulaciones
- **Criticidad**: CRITICA - auditoría de cambios
- **Recomendación**: **MANTENER**

#### 10. **client_accounts_snapshots** ⭐ CRITICA
- **Uso**: Snapshots diarios de estado de client accounts
- **Referencias**:
  - `app/application/services/client_accounts_simulation_service.py:57` - Creación de snapshots
  - `app/presentation/routes/client_accounts_routes.py:328,412,529` - Endpoints de timeline/snapshots
  - `app/infrastructure/database/init_client_accounts_collections.py:213` - Inicialización
- **Criticidad**: CRITICA - feature de "viaje en el tiempo"
- **Recomendación**: **MANTENER**

#### 11. **distribucion_cuentas_snapshot** ⭐ IMPORTANTE
- **Uso**: Snapshots de distribución de cuentas (legacy/alternativo)
- **Referencias**:
  - `app/application/services/client_accounts_service.py:35` - Usado en servicio
  - `app/presentation/routes/simulations_routes.py:207` - Limpieza
  - `app/infrastructure/database/init_client_accounts_collections.py:185` - Inicialización
- **Criticidad**: MEDIA - podría ser redundante con client_accounts_snapshots
- **Recomendación**: **REVISAR** - posiblemente consolidar con client_accounts_snapshots

---

### ❌ COLECCIONES SIN USO DIRECTO

#### 12. **assignments**
- **Uso en código**: Solo en `app/domain/events/assignment_events.py` (eventos)
- **Referencias**: 1 archivo (eventos/interfaces, no uso directo)
- **Criticidad**: BAJA - parece ser legacy o no implementado
- **Recomendación**: **CANDIDATA PARA ELIMINACIÓN** (si está vacía o no se usa)

---

## RECOMENDACIONES POR ACCIÓN

### 🟢 MANTENER (11 colecciones críticas)

```
agent_roi_3d
agent_roi_5d
agent_roi_7d
agent_roi_10d
agent_roi_15d
agent_roi_30d
agent_states
balances
daily_roi_calculation
rank_changes
mov07.10
cuentas_clientes_trading
historial_asignaciones_clientes
client_accounts_snapshots
```

**Razón**: Se usan activamente en el código de producción.

---

### 🟡 REVISAR (1 colección)

```
distribucion_cuentas_snapshot
```

**Razón**: Podría ser redundante con `client_accounts_snapshots`. Revisar si ambos son necesarios o consolidar.

**Acción sugerida**:
1. Comparar el esquema de ambas colecciones
2. Verificar diferencias funcionales
3. Si son equivalentes, migrar a una sola colección
4. Deprecar la que no se use en el frontend

---

### 🔴 ELIMINAR (1 colección candidata)

```
assignments
```

**Razón**: Solo se menciona en eventos/interfaces pero no tiene uso directo en servicios o rutas.

**Comando de verificación**:
```bash
python audit_collections.py
```

**Si está vacía o con < 100 documentos antiguos**:
```python
db.assignments.drop()
```

---

## SCRIPT DE AUDITORÍA

Para ejecutar la auditoría en tu base de datos:

```bash
cd backend
python audit_collections.py
```

Este script mostrará:
- Número de documentos por colección
- Tamaño en MB
- Última fecha de modificación
- Colecciones vacías (candidatas para eliminación)

---

## ANÁLISIS DE TAMAÑO ESTIMADO

### Colecciones Grandes (probablemente > 10 MB)

1. **mov07.10** - Movimientos de trading (datos fuente)
   - Probablemente la más grande
   - Contiene todos los registros de operaciones

2. **balances** - Balances históricos
   - Crece con cada día de simulación

3. **agent_roi_7d** - Cálculos de ROI
   - Se regenera en cada simulación
   - Puede limpiarse periódicamente

4. **cuentas_clientes_trading** - 1000 cuentas
   - Tamaño fijo (1000 documentos)
   - No debería ser muy grande

### Colecciones Temporales/Caché

Estas se limpian automáticamente:

1. **daily_roi_calculation** - Se limpia al inicio de cada simulación
2. **agent_roi_7d** (y variantes) - Se regeneran en cada ejecución

---

## ESTRATEGIA DE LIMPIEZA

### Paso 1: Ejecutar Auditoría

```bash
python audit_collections.py
```

### Paso 2: Eliminar Colecciones Vacías

Si el script reporta colecciones vacías:

```python
from app.config.database import database_manager

database_manager.connect()
db = database_manager.get_database()

# Solo si están vacías
if db.assignments.count_documents({}) == 0:
    db.assignments.drop()
    print("Eliminada: assignments")

database_manager.disconnect()
```

### Paso 3: Consolidar Snapshots (Opcional)

Si decides consolidar `distribucion_cuentas_snapshot` con `client_accounts_snapshots`:

1. Migrar datos si hay alguno importante
2. Actualizar código para usar solo `client_accounts_snapshots`
3. Eliminar `distribucion_cuentas_snapshot`

---

## RESUMEN DE HALLAZGOS

| Categoría | Cantidad | Acción |
|-----------|----------|--------|
| ✅ Críticas (mantener) | 10 | MANTENER - Uso activo |
| 🟢 Activas (mantener) | 4 | MANTENER - Uso frecuente |
| 🟡 Revisar | 1 | REVISAR - Posible redundancia |
| 🔴 Sin uso directo | 1 | ELIMINAR - Si está vacía |

**Total de colecciones**: 16 listadas
**Recomendación**: Mantener 14, revisar 1, posiblemente eliminar 1

---

## COLECCIONES NO LISTADAS PERO IMPORTANTES

Durante la auditoría, encontré referencias a otras colecciones críticas no listadas:

### **top16_by_day** (variantes: top16_7d, top16_30d, etc.)
- **Uso**: Rankings de Top 16 agentes por día
- **Criticidad**: CRITICA - core del sistema
- **Referencias**: Usado extensivamente en selección y simulaciones

Si esta colección NO está en tu lista, debes agregarla como crítica.

---

## CONCLUSIONES

1. **La mayoría de las colecciones listadas SE USAN** (14 de 16)

2. **assignments** es la única candidata clara para eliminación (si está vacía)

3. **distribucion_cuentas_snapshot** podría consolidarse con **client_accounts_snapshots**

4. El sistema tiene una arquitectura sólida con colecciones bien organizadas

5. Las colecciones de caché (daily_roi_calculation, agent_roi_*) se limpian automáticamente

---

## PRÓXIMOS PASOS

1. ✅ Ejecutar `python audit_collections.py` para ver tamaños reales
2. ✅ Revisar colecciones vacías reportadas por el script
3. ✅ Decidir sobre consolidación de snapshots
4. ✅ Eliminar `assignments` si está vacía
5. ✅ Documentar decisiones tomadas

---

## COMANDO DE AUDITORÍA RÁPIDA

```python
from app.config.database import database_manager

database_manager.connect()
db = database_manager.get_database()

for col_name in db.list_collection_names():
    count = db[col_name].count_documents({})
    print(f"{col_name}: {count:,} documentos")

database_manager.disconnect()
```

---

**Fecha de Auditoría**: 2025-10-30
**Analista**: Claude (Auditoría de Código)
**Método**: Análisis estático de referencias en el código fuente
