"""
Constantes de reglas de negocio según especificación del sistema Casterly Rock.

Estas constantes definen los umbrales y parámetros críticos para la
simulación de trading. Los valores están basados en la especificación
oficial del sistema (ESPECIFICACION_SISTEMA_SIMULACION.md).

Referencias:
- Sección 3: REGLAS DE EXPULSIÓN DEL TOP 16
- Sección 4: SELECCIÓN DE AGENTE DE REEMPLAZO
- Sección 10: REGLAS DE NEGOCIO ADICIONALES
"""

# ===== REGLAS DE EXPULSIÓN (Sección 3) =====

STOP_LOSS_THRESHOLD = -0.10
"""
Umbral de Stop Loss: -10%

Según especificación sección 3.2:
Si el ROI de un agente alcanza -10% o peor (ROI ≤ -0.10),
es expulsado inmediatamente del Top 16.

Esta regla tiene prioridad sobre la regla de 3 días consecutivos.
"""

CONSECUTIVE_FALL_THRESHOLD = 3
"""
Umbral de caídas consecutivas: 3 días

Según especificación sección 3.1:
Si un agente tiene 3 días SEGUIDOS con ROI negativo (ROI < 0),
es expulsado inmediatamente del Top 16.

Nota: Días con ROI = 0 (sin operaciones) NO cuentan como pérdida.
"""

# ===== PARÁMETROS DE SIMULACIÓN (Sección 10) =====

MIN_AUM_DEFAULT = 0.01
"""
AUM mínimo por defecto: $0.01

Según especificación (Sección 10.1), los agentes con balance < $0.01
son filtrados y no pueden entrar al Top 16. Este umbral ayuda a
reducir ruido de agentes con balance casi cero.
"""

TOP_N_AGENTS = 16
"""
Número de agentes en el grupo élite Casterly Rock.

Este es el tamaño del Top que se mantiene a lo largo de la simulación.
"""

# ===== VENTANAS DE ROI DISPONIBLES (Sección 7) =====

AVAILABLE_WINDOWS = [3, 5, 7, 10, 15, 30]
"""
Ventanas de días disponibles para calcular ROI en simulaciones.

Según especificación sección 7.1:
Las ventanas permiten filtrar resultados como si la simulación
hubiera durado solo X días en lugar de 30.
"""

DEFAULT_WINDOW_DAYS = 7
"""
Ventana de días por defecto para nuevas simulaciones.

Usado como fallback cuando no se especifica una ventana explícita.
"""

SIMULATION_PERIOD_DAYS = 30
"""
Duración estándar de la simulación: 30 días

Según especificación sección 2:
El sistema simula el comportamiento de agentes durante 30 días,
aunque luego se pueden aplicar filtros para ver otras ventanas.
"""
