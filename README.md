# Trading Simulation Platform - Backend

API REST con FastAPI para simulacion de trading con sistema de seleccion, asignacion y rotacion de agentes, incluyendo gestion completa de cuentas de clientes.

## Tecnologias

- Python 3.10+
- FastAPI
- MongoDB (Atlas)
- Pydantic
- Motor (MongoDB async driver)
- Uvicorn (ASGI server)

## Requisitos Previos

- Python 3.10 o superior
- MongoDB Atlas account o MongoDB local
- pip (Python package manager)

## Instalacion

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd backend
```

### 2. Crear entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crear archivo `.env` en la raiz del backend:

```env
# MongoDB
MONGODB_URL=mongodb+srv://usuario:password@cluster.mongodb.net/
MONGODB_DATABASE=trading_simulation

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# CORS
CORS_ORIGINS=http://localhost:4200,http://localhost:3000

# Logging
LOG_LEVEL=INFO
```

## Ejecucion

### Servidor de desarrollo

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Servidor de produccion

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

El servidor estara disponible en: http://localhost:8000

## Documentacion API

FastAPI genera documentacion automatica interactiva:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Arquitectura

El proyecto sigue Clean Architecture con separacion de capas:

```
app/
├── domain/                 # Capa de dominio
│   ├── entities/          # Entidades de negocio
│   └── repositories/      # Interfaces de repositorios
├── application/           # Capa de aplicacion
│   └── services/          # Logica de negocio y casos de uso
├── infrastructure/        # Capa de infraestructura
│   ├── database/          # Configuracion de MongoDB
│   └── repositories/      # Implementaciones de repositorios
├── presentation/          # Capa de presentacion
│   ├── routes/            # Endpoints de la API
│   └── schemas/           # Modelos Pydantic (DTOs)
└── main.py               # Punto de entrada
```

### Capas

1. **Domain**: Entidades de negocio y contratos de repositorios
2. **Application**: Servicios con logica de negocio
3. **Infrastructure**: Implementaciones concretas (MongoDB, etc.)
4. **Presentation**: API REST endpoints y esquemas

## Endpoints Principales

### Simulacion

- `POST /api/simulation/run` - Ejecutar simulacion
- `GET /api/simulation/available-dates` - Obtener fechas disponibles
- `GET /api/simulation/latest` - Obtener ultima simulacion

### Reports

- `GET /api/reports/summary` - Resumen general
- `GET /api/reports/roi-distribution` - Distribucion de ROI
- `GET /api/reports/top-agents` - Top agentes
- `GET /api/reports/top16-timeline` - Timeline Top16

### Client Accounts

- `GET /api/client-accounts` - Listar cuentas
- `GET /api/client-accounts/{id}` - Detalle de cuenta
- `GET /api/client-accounts/timeline` - Timeline de cuentas
- `GET /api/client-accounts/snapshots/{date}` - Snapshot por fecha
- `POST /api/client-accounts/initialize` - Inicializar cuentas
- `POST /api/client-accounts/rebalance` - Rebalancear cuentas

## Estructura de MongoDB

### Colecciones

- `top16_3d`, `top16_5d`, `top16_7d`, `top16_10d`, `top16_15d`, `top16_30d`
- `agent_roi_3d`, `agent_roi_5d`, `agent_roi_7d`, `agent_roi_10d`, `agent_roi_15d`, `agent_roi_30d`
- `agent_states`
- `replacements_log`
- `simulation_summary`
- `cuentas_clientes_trading`
- `historial_asignaciones_clientes`
- `client_accounts_snapshots`
- `client_accounts_rotations`

## Servicios Principales

### DailyOrchestratorService
Orquesta el procesamiento diario de simulaciones:
- Proceso de Dia 1: Inicializacion y distribucion
- Proceso diario: Actualizacion y rotaciones
- Sincronizacion con Client Accounts

### ClientAccountsSimulationService
Gestiona la sincronizacion de cuentas de clientes:
- Inicializacion de cuentas
- Actualizacion de ROI y balances
- Rotaciones de agentes
- Generacion de snapshots

### SelectionService
Maneja la seleccion y ranking de agentes:
- Ranking por ROI
- Seleccion de Top16
- Filtrado de agentes

### ReplacementService
Gestiona reemplazos y rotaciones:
- Registro de rotaciones
- Transferencia de cuentas
- Manejo de ciclos de vida de agentes

## Configuracion de Ventanas de Tiempo

El sistema soporta multiples ventanas de analisis:
- 3 dias
- 5 dias
- 7 dias (default)
- 10 dias
- 15 dias
- 30 dias

## Testing

### Ejecutar tests

```bash
# Tests unitarios
pytest tests/

# Con coverage
pytest --cov=app tests/

# Test especifico
python test_simulation_with_client_accounts.py
```

### Scripts de prueba

- `test_simulation_with_client_accounts.py` - Test completo de simulacion
- `test_client_accounts_endpoints.py` - Test de endpoints

## Variables de Entorno

| Variable | Descripcion | Default |
|----------|-------------|---------|
| `MONGODB_URL` | URL de conexion a MongoDB | - |
| `MONGODB_DATABASE` | Nombre de la base de datos | `trading_simulation` |
| `API_HOST` | Host del servidor | `0.0.0.0` |
| `API_PORT` | Puerto del servidor | `8000` |
| `DEBUG` | Modo debug | `False` |
| `CORS_ORIGINS` | Origenes permitidos para CORS | `*` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

## Logging

El sistema usa logging configurado en multiples niveles:
- `DEBUG`: Informacion detallada
- `INFO`: Eventos generales
- `WARNING`: Advertencias
- `ERROR`: Errores que necesitan atencion

Los logs se muestran en consola con formato estructurado.

## Desarrollo

### Agregar nuevo endpoint

1. Crear ruta en `app/presentation/routes/`
2. Definir esquema Pydantic en `app/presentation/schemas/`
3. Implementar logica en `app/application/services/`
4. Registrar router en `app/main.py`

### Agregar nueva coleccion

1. Definir entidad en `app/domain/entities/`
2. Crear interfaz de repositorio en `app/domain/repositories/`
3. Implementar repositorio en `app/infrastructure/repositories/`
4. Usar en servicios

## Mantenimiento

### Limpiar base de datos

```bash
# Conectar a MongoDB y eliminar colecciones
# Usar con precaucion en produccion
```

### Backup de datos

```bash
# MongoDB dump
mongodump --uri="mongodb+srv://..." --out=backup/

# Restore
mongorestore --uri="mongodb+srv://..." backup/
```

## Troubleshooting

### Error de conexion a MongoDB
- Verificar URL de conexion en `.env`
- Verificar que MongoDB este accesible
- Verificar credenciales

### Puerto 8000 ocupado
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

### Error de importacion
```bash
# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall
```

## Contribucion

1. Crear branch desde `develop`
2. Implementar cambios
3. Agregar tests
4. Hacer commit con mensaje descriptivo
5. Crear Pull Request

## Licencia

Propietario

## Contacto

Para preguntas o soporte, contactar al equipo de desarrollo.
