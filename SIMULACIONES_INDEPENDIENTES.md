# Sistema de Simulaciones Independientes

## Descripcion General

El sistema de Client Accounts ahora soporta **simulaciones independientes**, lo que permite ejecutar multiples experimentos de trading con diferentes estrategias y compararlos entre si.

## Concepto Clave: Balance Inicial vs Balance Actual

### Balance Inicial
- **Valor fijo**: Siempre $1,000 por cuenta
- **NO se modifica**: Permanece constante durante toda la vida de la cuenta
- **Proposito**: Punto de referencia para calcular ROI y ganancias

### Balance Actual
- **Valor dinamico**: Se actualiza en cada simulacion
- **Formula**: `balance_actual = balance_inicial * (1 + roi_total / 100)`
- **Proposito**: Refleja el capital actual de la cuenta

## Como Funciona el Reset

### Que SE RESETEA
Cuando inicias una nueva simulacion, los siguientes valores vuelven a cero:

- `balance_actual` → vuelve a `balance_inicial` ($1,000)
- `roi_total` → 0.0%
- `roi_acumulado_con_agente` → 0.0%
- `numero_cambios_agente` → 0
- `win_rate` → 0.0
- `historial_agentes` → se limpia (array vacio)
- `snapshots` → se eliminan
- `logs de rebalanceo` → se eliminan

### Que NO SE MODIFICA
Los siguientes campos permanecen intactos:

- `balance_inicial` → **SIEMPRE $1,000** (permanece fijo)
- `cuenta_id` → identificador unico
- `nombre_cliente` → nombre del titular
- `created_at` → fecha de creacion original

## Flujo de Trabajo

### Opcion 1: Reset Automatico (Recomendado)

El reset se ejecuta **automaticamente** cada vez que llamas a `/initialize`:

```python
# Primera simulacion
POST /api/client-accounts/initialize
{
  "simulation_id": "estrategia_conservadora_001",
  "num_accounts": 1000,
  "num_top_agents": 16
}

# Segunda simulacion (auto-resetea antes de inicializar)
POST /api/client-accounts/initialize
{
  "simulation_id": "estrategia_agresiva_002",
  "num_accounts": 1000,
  "num_top_agents": 16
}
```

**Logs del servidor mostraran**:
```
[INFO] Iniciando distribucion de 1000 cuentas para simulacion estrategia_agresiva_002
[INFO] Se encontraron 1000 cuentas existentes. Reseteando para nueva simulacion independiente...
[INFO] Iniciando reset de cuentas para nueva simulacion independiente
[INFO] Reseteando 1000 cuentas...
[INFO] Reseteadas 1000 cuentas exitosamente
[INFO] Limpiando historial de asignaciones...
[INFO] Historial limpiado
[INFO] Limpiando snapshots antiguos...
[INFO] Snapshots limpiados
[INFO] Reset completado: 1000 cuentas reseteadas
```

### Opcion 2: Reset Manual

Si necesitas resetear manualmente sin inicializar de nuevo:

```python
POST /api/client-accounts/reset
```

**Response**:
```json
{
  "cuentas_reseteadas": 1000,
  "total_cuentas": 1000,
  "fecha_reset": "2025-10-30T10:30:00",
  "balance_inicial_preserved": true,
  "historial_limpiado": true,
  "snapshots_limpiados": true
}
```

## Ejemplo Completo

### Simulacion 1: Estrategia Conservadora (7 dias)

```bash
# Inicializar
POST /api/client-accounts/initialize
{
  "simulation_id": "estrategia_conservadora",
  "num_accounts": 1000,
  "num_top_agents": 16
}

# Ejecutar simulacion por 7 dias
# ... (update-roi, rebalance, etc.)

# Resultado final
# - balance_inicial: $1,000 (sin cambios)
# - balance_actual: $1,050 (promedio)
# - roi_total: 5.0%
# - numero_cambios_agente: 3 (promedio)
```

### Simulacion 2: Estrategia Agresiva (7 dias)

```bash
# Inicializar (auto-resetea)
POST /api/client-accounts/initialize
{
  "simulation_id": "estrategia_agresiva",
  "num_accounts": 1000,
  "num_top_agents": 16
}

# Estado despues del reset automatico:
# - balance_inicial: $1,000 (PERMANECE IGUAL)
# - balance_actual: $1,000 (reseteado)
# - roi_total: 0.0% (reseteado)
# - numero_cambios_agente: 0 (reseteado)

# Ejecutar simulacion por 7 dias con parametros diferentes
# ... (update-roi mas frecuente, rebalance mas agresivo, etc.)

# Resultado final
# - balance_inicial: $1,000 (sin cambios)
# - balance_actual: $1,080 (promedio)
# - roi_total: 8.0%
# - numero_cambios_agente: 7 (promedio)
```

### Comparacion de Resultados

```
| Metrica                | Conservadora | Agresiva | Diferencia |
|------------------------|--------------|----------|------------|
| Balance Inicial        | $1,000       | $1,000   | $0         |
| Balance Final Promedio | $1,050       | $1,080   | +$30       |
| ROI Promedio           | 5.0%         | 8.0%     | +3.0%      |
| Cambios Agente         | 3            | 7        | +4         |
| Win Rate               | 65%          | 58%      | -7%        |
```

**Conclusion**: La estrategia agresiva genera mayor ROI (+3%) pero con mas volatilidad (mas cambios de agente y menor win rate).

## Verificacion del Reset

### Script de Prueba

Ejecuta el script de prueba para verificar que el reset funciona correctamente:

```bash
cd backend
python test_reset_simulation.py
```

**El script verifica**:
1. Balance inicial permanece en $1,000
2. Balance actual se resetea a balance inicial
3. ROI total vuelve a 0%
4. Numero de cambios de agente vuelve a 0
5. Win rate vuelve a 0
6. Historial se limpia

### Output Esperado

```
================================================================================
TEST: RESET DE SIMULACION
================================================================================

[PASO 1] Obteniendo estado actual de las cuentas (antes del reset)...

[OK] 5 cuentas obtenidas

Ejemplo de cuenta ANTES del reset:
  Cuenta ID: 68ffbc3d5fdd913a81542a7f
  Nombre: Juan Garcia
  Balance Inicial: $1000.00
  Balance Actual: $1599.15
  ROI Total: 59.91%
  Numero Cambios Agente: 17
  Win Rate: 0.2857

--------------------------------------------------------------------------------

[PASO 2] Ejecutando reset de simulacion...

[OK] Reset completado exitosamente!

  Cuentas Reseteadas: 1000
  Total Cuentas: 1000
  Fecha Reset: 2025-10-30T10:30:00
  Balance Inicial Preservado: True
  Historial Limpiado: True
  Snapshots Limpiados: True

--------------------------------------------------------------------------------

[PASO 3] Verificando estado de las cuentas (despues del reset)...

[OK] 5 cuentas obtenidas

Ejemplo de cuenta DESPUES del reset:
  Cuenta ID: 68ffbc3d5fdd913a81542a7f
  Nombre: Juan Garcia
  Balance Inicial: $1000.00
  Balance Actual: $1000.00
  ROI Total: 0.00%
  Numero Cambios Agente: 0
  Win Rate: 0.0000

--------------------------------------------------------------------------------

[PASO 4] Validando reset...

[SUCCESS] Todas las validaciones pasaron correctamente!

Resumen:
  - balance_inicial permanece en $1,000 para todas las cuentas
  - balance_actual se reseteo a balance_inicial
  - roi_total se reseteo a 0%
  - numero_cambios_agente se reseteo a 0
  - win_rate se reseteo a 0
  - 1000 cuentas procesadas

================================================================================
FIN DEL TEST
================================================================================
```

## Arquitectura Tecnica

### Servicio: `ClientAccountsService`

#### Nuevo Metodo: `reset_simulation_accounts()`

```python
def reset_simulation_accounts(self) -> Dict[str, Any]:
    """
    Resetea todas las cuentas para una nueva simulacion independiente.

    Mantiene balance_inicial en $1,000.
    Resetea todos los demas valores a cero.
    Limpia historial, snapshots y logs.
    """
```

**Implementacion**:
- Lee todas las cuentas con solo `_id` y `balance_inicial`
- Crea operaciones bulk_write de tipo UpdateOne
- Para cada cuenta, setea `balance_actual = balance_inicial`
- Ejecuta limpieza de colecciones relacionadas

#### Metodo Modificado: `initialize_client_accounts()`

```python
def initialize_client_accounts(
    self,
    simulation_id: str,
    num_accounts: int = 1000,
    num_top_agents: int = 16
) -> Dict[str, Any]:
    """
    Inicializa las cuentas de clientes para una simulacion.

    Si ya existen cuentas, las resetea automaticamente.
    """
```

**Comportamiento Nuevo**:
- Verifica si existen cuentas (`count_documents`)
- Si existen: llama a `reset_simulation_accounts()` antes de continuar
- Si no existen: crea nuevas cuentas con `balance_inicial = $1,000`
- Usa operaciones bulk_write con InsertOne/UpdateOne segun corresponda

### Endpoint REST

```python
POST /api/client-accounts/reset
```

**Response Schema**:
```python
class ResetSimulationResponse(BaseModel):
    cuentas_reseteadas: int
    total_cuentas: int
    fecha_reset: str
    balance_inicial_preserved: bool
    historial_limpiado: bool
    snapshots_limpiados: bool
```

## Casos de Uso

### 1. Comparacion de Estrategias A/B Testing

```python
# Estrategia A: Rebalanceo cada 7 dias
simulacion_a = {
    "simulation_id": "rebalance_semanal",
    "rebalance_frequency": 7
}

# Estrategia B: Rebalanceo cada 3 dias
simulacion_b = {
    "simulation_id": "rebalance_frecuente",
    "rebalance_frequency": 3
}
```

### 2. Testing de Diferentes Top N

```python
# Test 1: Top 16 agentes
POST /api/client-accounts/initialize
{
  "simulation_id": "top16_test",
  "num_accounts": 1000,
  "num_top_agents": 16
}

# Test 2: Top 10 agentes
POST /api/client-accounts/initialize
{
  "simulation_id": "top10_test",
  "num_accounts": 1000,
  "num_top_agents": 10
}
```

### 3. Backtesting Historico

```python
# Simular enero 2024
POST /api/simulation/run
{
    "target_date": "2024-01-31",
    "window_days": 30,
    "update_client_accounts": true,
    "simulation_id": "backtest_enero_2024"
}

# Reset y simular febrero 2024
POST /api/simulation/run
{
    "target_date": "2024-02-29",
    "window_days": 28,
    "update_client_accounts": true,
    "simulation_id": "backtest_febrero_2024"
}
```

## FAQ

### Por que balance_inicial es fijo en $1,000?

El `balance_inicial` actua como **punto de referencia constante** para:
- Calcular ROI: `roi_total = ((balance_actual - balance_inicial) / balance_inicial) * 100`
- Comparar resultados entre simulaciones
- Normalizar metricas de rendimiento

Si el `balance_inicial` cambiara, perderiamos la capacidad de comparar simulaciones de forma consistente.

### Que pasa si quiero capital inicial diferente?

Actualmente el sistema esta disenado para $1,000 por cuenta. Si necesitas capital diferente:

1. **Opcion A**: Modificar el codigo para aceptar un parametro `initial_balance`
2. **Opcion B**: Escalar los resultados matematicamente (ej: multiplicar por 10 para simular $10,000)

### Como comparo multiples simulaciones?

Los snapshots de cada simulacion se identifican por `simulation_id`. Puedes:

1. Ejecutar simulacion A con `simulation_id = "estrategia_a"`
2. Los snapshots se guardan con ese ID
3. Ejecutar simulacion B con `simulation_id = "estrategia_b"`
4. Nuevo reset, nuevos snapshots con diferente ID
5. Comparar resultados via el endpoint `/compare-simulations` (pendiente implementar)

### El reset es reversible?

**NO**. El reset elimina permanentemente:
- Historial de asignaciones
- Snapshots
- Logs de rebalanceo

**Recomendacion**: Exporta los datos importantes antes de resetear.

### Cuantas simulaciones puedo ejecutar?

Ilimitadas. Cada simulacion:
- Resetea las 1000 cuentas a su estado inicial
- Genera nuevos snapshots con su propio `simulation_id`
- No interfiere con datos de simulaciones previas (si guardaste los snapshots)

## Mejoras Futuras

### 1. Endpoint de Comparacion

```python
GET /api/client-accounts/compare-simulations?ids=sim_a,sim_b,sim_c
```

Response:
```json
{
  "simulations": [
    {
      "simulation_id": "sim_a",
      "roi_promedio": 5.0,
      "balance_final": 1050.0
    },
    {
      "simulation_id": "sim_b",
      "roi_promedio": 8.0,
      "balance_final": 1080.0
    }
  ],
  "comparisons": {
    "mejor_roi": "sim_b",
    "mejor_win_rate": "sim_a"
  }
}
```

### 2. Preservar Snapshots Entre Resets

Opcion para mantener snapshots historicos:

```python
POST /api/client-accounts/reset?preserve_snapshots=true
```

### 3. Reset Parcial

Resetear solo ciertas cuentas:

```python
POST /api/client-accounts/reset
{
  "cuenta_ids": ["ACC001", "ACC002", "ACC003"]
}
```

### 4. Capital Inicial Configurable

```python
POST /api/client-accounts/initialize
{
  "simulation_id": "test_10k",
  "num_accounts": 1000,
  "initial_balance": 10000.0
}
```

## Conclusion

El sistema de **simulaciones independientes** permite:

- Ejecutar multiples experimentos con las mismas cuentas
- Comparar estrategias de trading objetivamente
- Mantener un punto de referencia fijo (`balance_inicial = $1,000`)
- Resetear facilmente para nuevas pruebas
- Preservar la integridad de los datos historicos

El `balance_inicial` fijo garantiza que todas las simulaciones sean comparables bajo las mismas condiciones iniciales.
