# Guía de Logging - Trading Simulation Platform

## Resumen

Este proyecto usa un sistema de logging profesional con dos componentes:

1. **Logging estándar de Python** - Para la mayoría de los mensajes
2. **ConsoleLogger con colores** - Para mensajes importantes que siempre deben destacar

## Cómo Usar Logging

### Logging Estándar (Recomendado para 90% de los casos)

```python
import logging

logger = logging.getLogger("trading_simulation.nombre_del_modulo")

# Niveles de logging
logger.debug("Mensaje de debug detallado")       # Solo se ve con LOG_LEVEL=DEBUG
logger.info("Mensaje informativo")               # Se ve con LOG_LEVEL=INFO
logger.warning("Advertencia importante")         # Se ve siempre
logger.error("Error que necesita atención")      # Se ve siempre
logger.critical("Error crítico del sistema")     # Se ve siempre
```

### ConsoleLogger con Colores (Para mensajes importantes)

```python
from app.infrastructure.config.console_logger import ConsoleLogger as log

# Mensajes con colores
log.info("Servidor iniciado", context="[STARTUP]")        # Verde
log.success("Operación exitosa", context="[DATABASE]")    # Verde brillante
log.warning("Advertencia", context="[REBALANCE]")         # Amarillo
log.error("Error encontrado", context="[API]")            # Rojo
log.critical("Error crítico", context="[SYSTEM]")         # Rojo brillante + bold
log.debug("Info de debug", context="[DEBUG]")             # Cyan

# Separadores visuales
log.separator("=", 80)  # Línea de 80 caracteres
```

## Ejemplos de Uso por Situación

### Inicio de Simulación

```python
from app.infrastructure.config.console_logger import ConsoleLogger as log
import logging

logger = logging.getLogger("trading_simulation.simulation_routes")

# Mensaje destacado en consola
log.separator("=", 80)
log.success(f"Simulación iniciada - window_days={window_days}", context="[SIMULATION]")
log.separator("=", 80)

# Detalles en logging estándar
logger.info(f"Configuración: target_date={target_date}, update_client_accounts={update_ca}")
logger.debug(f"Parámetros completos: {request.dict()}")
```

### Loop de Procesamiento

```python
logger.info(f"Procesando {len(date_range)} días: {date_range[0]} -> {date_range[-1]}")

for idx, current_date in enumerate(date_range, 1):
    logger.info(f"Día {idx}/{len(date_range)} - Procesando: {current_date}")
    # Procesar...
    logger.debug(f"Detalles: balance={balance}, roi={roi}")
```

### Manejo de Errores

```python
try:
    result = procesar_datos()
    logger.info(f"Datos procesados exitosamente: {len(result)} registros")
except ValueError as e:
    logger.error(f"Error de validación: {str(e)}")
    raise
except Exception as e:
    logger.critical(f"Error inesperado en procesamiento: {str(e)}")
    raise
```

### Operaciones de Base de Datos

```python
logger.info(f"Guardando {len(documents)} documentos en MongoDB")
collection.insert_many(documents)
logger.debug(f"IDs insertados: {[str(doc['_id']) for doc in documents]}")
```

## Niveles de Logging

| Nivel | Cuándo Usar | Se Ve En |
|-------|-------------|----------|
| `DEBUG` | Información detallada para debugging | Solo con `LOG_LEVEL=DEBUG` |
| `INFO` | Información general del flujo de la aplicación | Desarrollo y producción |
| `WARNING` | Situaciones inusuales pero manejables | Siempre |
| `ERROR` | Errores que afectan funcionalidad | Siempre |
| `CRITICAL` | Errores que pueden detener la aplicación | Siempre |

## Configuración de Nivel de Logging

### En Desarrollo (ver todo en consola)

```bash
# .env
LOG_LEVEL=DEBUG
```

### En Producción (solo mensajes importantes)

```bash
# .env
LOG_LEVEL=INFO
```

## Archivos de Log

Los logs se guardan automáticamente en:

```
backend/logs/app_YYYYMMDD.log
```

Ejemplo: `logs/app_20251104.log`

Los archivos de log incluyen:
- Timestamp completo
- Nivel de logging
- Nombre del módulo
- Mensaje

Formato:
```
2025-11-04 14:30:25 - [INFO] - trading_simulation.simulation_routes - Simulación iniciada
2025-11-04 14:30:26 - [DEBUG] - trading_simulation.daily_orchestrator - Procesando día 2025-10-05
2025-11-04 14:30:27 - [WARNING] - trading_simulation.client_accounts - Balance bajo promedio detectado
```

## Buenas Prácticas

### ✅ HACER

```python
# Usar f-strings para mensajes dinámicos
logger.info(f"Procesados {count} registros en {elapsed}s")

# Incluir contexto relevante
logger.error(f"Error al procesar cuenta {account_id}: {error}")

# Usar niveles apropiados
logger.debug("Variable x = 123")  # Solo para debugging
logger.info("Operación completada")  # Flujo normal
logger.warning("Cuenta sin saldo")  # Situación inusual
logger.error("Conexión a DB falló")  # Error real
```

### ❌ NO HACER

```python
# NO usar print()
print("Mensaje")  # ❌ PROHIBIDO

# NO loggear datos sensibles
logger.info(f"Password: {password}")  # ❌ NUNCA

# NO loggear en exceso en loops
for i in range(10000):
    logger.info(f"Procesando {i}")  # ❌ Demasiado verbose

# NO usar logging para debugging permanente
logger.debug("Entré a la función")  # ❌ Innecesario
logger.debug("Variable x ahora es 5")  # ❌ Demasiado detalle
```

### ✅ MEJOR

```python
# Loggear resúmenes en loops
logger.info(f"Procesando {total} elementos...")
for i in range(total):
    # Procesar...
    if i % 100 == 0:
        logger.debug(f"Progreso: {i}/{total}")
logger.info(f"Completado: {total} elementos procesados")

# Usar try-except para contexto
try:
    result = operacion_compleja()
    logger.info("Operación exitosa")
except Exception as e:
    logger.error(f"Error en operación: {str(e)}")
    raise
```

## Migración desde print()

Si encuentras un `print()` en el código, reemplázalo así:

```python
# Antes
print(f"[INFO] Procesando datos...")
print(f"[DEBUG] Variable x: {x}")
print(f"[ERROR] Falló la operación")

# Después
logger.info("Procesando datos...")
logger.debug(f"Variable x: {x}")
logger.error("Falló la operación")
```

## Ejemplo Completo

```python
from fastapi import APIRouter
import logging
from app.infrastructure.config.console_logger import ConsoleLogger as log

logger = logging.getLogger("trading_simulation.mi_modulo")
router = APIRouter()

@router.post("/procesar")
async def procesar_datos(datos: dict):
    log.success("Iniciando procesamiento", context="[API]")

    try:
        logger.info(f"Recibidos {len(datos)} elementos")

        # Validación
        if not datos:
            logger.warning("Datos vacíos recibidos")
            return {"error": "No hay datos"}

        # Procesamiento
        resultados = []
        for idx, item in enumerate(datos):
            logger.debug(f"Procesando item {idx}: {item}")
            resultado = procesar_item(item)
            resultados.append(resultado)

        logger.info(f"Procesamiento completado: {len(resultados)} resultados")
        log.success(f"Éxito: {len(resultados)} elementos procesados", context="[API]")

        return {"resultados": resultados}

    except ValueError as e:
        logger.error(f"Error de validación: {str(e)}")
        raise
    except Exception as e:
        logger.critical(f"Error inesperado: {str(e)}")
        raise
```

## Monitoreo de Logs

### Ver logs en tiempo real

```bash
# Linux/Mac
tail -f backend/logs/app_20251104.log

# Windows PowerShell
Get-Content backend/logs/app_20251104.log -Wait -Tail 50
```

### Filtrar logs por nivel

```bash
# Solo errores
grep "ERROR" backend/logs/app_20251104.log

# Solo de un módulo específico
grep "simulation_routes" backend/logs/app_20251104.log
```

## Soporte

Para preguntas sobre logging, contactar al equipo de desarrollo.

**Última actualización:** 2025-11-04
