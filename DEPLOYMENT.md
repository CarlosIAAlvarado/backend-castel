# Despliegue en Render - Backend Casterly Rock

## Variables de Entorno Requeridas

Configura las siguientes variables de entorno en el dashboard de Render:

### Variables Obligatorias

```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=simulacion_casterly_rock
TIMEZONE=America/Bogota
```

### Variables Opcionales

```
API_TITLE=Casterly Rock Simulation API
API_VERSION=1.0.0
API_DESCRIPTION=Sistema de seleccion, asignacion y rotacion de agentes
DEBUG=False
```

## Configuracion en Render

### 1. Crear Web Service

1. Conecta tu repositorio de GitHub
2. Selecciona el directorio `backend`
3. Configura:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 2. Configurar Variables de Entorno

En el dashboard de Render, ve a **Environment** y agrega:

- `MONGODB_URI`: Tu URI de conexion a MongoDB Atlas
- `DATABASE_NAME`: `simulacion_casterly_rock`
- `TIMEZONE`: `America/Bogota`

### 3. Desplegar

Render desplegara automaticamente cuando hagas push a tu rama principal.

## Verificar Despliegue

Una vez desplegado, verifica que funciona:

```bash
# Health check
curl https://tu-app.onrender.com/health

# Database test
curl https://tu-app.onrender.com/database/test

# API root
curl https://tu-app.onrender.com/
```

## Endpoints Disponibles

- `GET /` - Info de la API
- `GET /health` - Health check
- `GET /database/test` - Test de conexion a base de datos
- `POST /api/simulation/run` - Ejecutar simulacion completa
- `GET /api/reports/summary` - KPIs consolidados
- `GET /api/reports/roi-distribution` - Distribucion ROI

## MongoDB Atlas

Asegurate de:

1. Tener un cluster en MongoDB Atlas
2. Configurar Network Access para permitir conexiones desde Render (0.0.0.0/0)
3. Crear un usuario de base de datos con permisos de lectura/escritura
4. Usar la URI de conexion en la variable `MONGODB_URI`

## Requisitos

- Python 3.9+
- MongoDB Atlas
- Render Free Tier o superior
