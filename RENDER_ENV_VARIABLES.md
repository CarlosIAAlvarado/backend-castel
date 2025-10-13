# Variables de Entorno para Render

## Variables de Entorno Requeridas

### 1. MONGODB_URI (REQUERIDA)
**Descripción:** URI de conexión a MongoDB Atlas
**Valor de ejemplo:** `mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority`
**Valor actual en .env:** `mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy`

**IMPORTANTE:** NO uses las credenciales del archivo .env en producción. Crea un usuario nuevo en MongoDB Atlas específico para producción.

### 2. DATABASE_NAME (REQUERIDA)
**Descripción:** Nombre de la base de datos en MongoDB
**Valor de ejemplo:** `simulacion_casterly_rock`
**Valor actual:** `simulacion_casterly_rock`

### 3. TIMEZONE (OPCIONAL)
**Descripción:** Zona horaria para timestamps
**Valor por defecto:** `America/Bogota`
**Valor recomendado:** `America/Bogota`

### 4. API_TITLE (OPCIONAL)
**Descripción:** Título de la API en la documentación
**Valor por defecto:** `Casterly Rock Simulation API`

### 5. API_VERSION (OPCIONAL)
**Descripción:** Versión de la API
**Valor por defecto:** `1.0.0`

### 6. API_DESCRIPTION (OPCIONAL)
**Descripción:** Descripción de la API
**Valor por defecto:** `Sistema de selección, asignación y rotación de agentes`

### 7. DEBUG (OPCIONAL)
**Descripción:** Modo debug para desarrollo
**Valor por defecto:** `False`
**Valor en producción:** `False`

### 8. CORS_ORIGINS (OPCIONAL)
**Descripción:** URLs permitidas del frontend (separadas por coma)
**Valor por defecto:** `*` (permite todas las URLs)
**Valor de ejemplo:** `https://tu-frontend.pages.dev,https://tu-dominio.com`

Para desarrollo puedes usar `*`, pero para producción es más seguro especificar las URLs exactas de tu frontend.

## Configuración en Render

### Paso 1: Crear Web Service

1. Ve a Render Dashboard
2. Click en "New +" > "Web Service"
3. Conecta tu repositorio
4. Configura el servicio

### Paso 2: Build & Deploy Settings

```yaml
Name: casterly-rock-api
Region: Oregon (US West)
Branch: main
Root Directory: backend
Runtime: Python 3

Build Command:
pip install -r requirements.txt

Start Command:
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Paso 3: Environment Variables

Agrega estas variables en la sección "Environment" de Render:

```bash
# REQUERIDAS
MONGODB_URI=mongodb+srv://tu-usuario:tu-password@cluster.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=simulacion_casterly_rock

# OPCIONALES (con valores por defecto)
TIMEZONE=America/Bogota
API_TITLE=Casterly Rock Simulation API
API_VERSION=1.0.0
API_DESCRIPTION=Sistema de selección, asignación y rotación de agentes
DEBUG=False

# CORS - URL del frontend
# Para desarrollo: CORS_ORIGINS=*
# Para producción: CORS_ORIGINS=https://tu-frontend.pages.dev,https://otro-dominio.com
CORS_ORIGINS=https://tu-frontend.pages.dev
```

## Configuración de MongoDB Atlas

### Paso 1: Crear usuario de producción

1. Ve a MongoDB Atlas Dashboard
2. Database Access > Add New Database User
3. Crea usuario con permisos de lectura/escritura
4. Guarda el usuario y contraseña

### Paso 2: Whitelist de IP de Render

1. Ve a Network Access en MongoDB Atlas
2. Add IP Address
3. Agrega: `0.0.0.0/0` (permite cualquier IP)
   - Alternativa más segura: Agrega las IPs específicas de Render

### Paso 3: Obtener Connection String

1. Ve a Clusters > Connect
2. Selecciona "Connect your application"
3. Copia el connection string
4. Reemplaza `<password>` con tu contraseña
5. Usa este string en la variable `MONGODB_URI`

## Estructura del Proyecto Backend

```
backend/
├── app/
│   ├── main.py              <- Punto de entrada FastAPI
│   ├── config/
│   │   ├── settings.py      <- Configuración de variables de entorno
│   │   └── database.py      <- Conexión a MongoDB
│   ├── domain/              <- Lógica de negocio
│   ├── infrastructure/      <- Repositorios y servicios
│   └── presentation/        <- Rutas y controladores
├── requirements.txt         <- Dependencias Python
├── .env.example            <- Ejemplo de variables de entorno
└── .env                    <- Variables locales (NO subir a Git)
```

## Endpoints de la API

### Health Checks
- `GET /` - Información básica de la API
- `GET /health` - Health check
- `GET /database/test` - Test de conexión a MongoDB

### Exploration (Datos)
- `GET /api/exploration/first-days` - Primeros días de datos
- `GET /api/exploration/last-days` - Últimos días de datos
- `GET /api/exploration/date-range` - Rango de fechas disponibles

### Query (Consultas)
- `POST /api/query/daily-balances` - Balances diarios
- `POST /api/query/movements` - Movimientos filtrados

### Simulation (Simulación)
- `POST /api/simulation/run` - Ejecutar simulación

### Reports (Reportes)
- `GET /api/reports/summary` - Resumen general
- `GET /api/reports/top-agents` - Top 16 agentes
- `GET /api/reports/rotation-logs` - Historial de rotaciones
- `GET /api/reports/roi-distribution` - Distribución de ROI

## Configuración CORS

El backend ya está configurado para aceptar peticiones desde cualquier origen:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Acepta todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Para producción (más seguro):** Cambia `allow_origins=["*"]` por:

```python
allow_origins=[
    "https://tu-frontend.pages.dev",
    "https://tu-dominio-custom.com"
]
```

## Dependencias (requirements.txt)

```txt
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
motor>=3.3.2
pymongo>=4.6.0
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
pandas>=2.1.3
numpy>=1.26.2
```

## Checklist de Despliegue

- [ ] Crear usuario de producción en MongoDB Atlas
- [ ] Configurar whitelist de IPs en MongoDB Atlas
- [ ] Obtener connection string de MongoDB
- [ ] Crear Web Service en Render
- [ ] Configurar Build Command
- [ ] Configurar Start Command
- [ ] Agregar variables de entorno en Render
- [ ] Verificar que MONGODB_URI sea correcto
- [ ] Deploy y verificar logs
- [ ] Probar endpoint /health
- [ ] Probar endpoint /database/test
- [ ] Actualizar URL en frontend (environment.prod.ts)

## Comandos Útiles

### Test local
```bash
# Activar entorno virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verificar conexión a MongoDB
```bash
curl http://localhost:8000/database/test
```

### Ver logs en Render
```bash
# En Render Dashboard > Logs
# O usa Render CLI:
render logs -s tu-servicio
```

## Solución de Problemas Comunes

### Error: "Could not connect to MongoDB"
**Solución:**
1. Verifica que MONGODB_URI sea correcta
2. Verifica que la IP esté en whitelist
3. Verifica que el usuario tenga permisos

### Error: "Module not found"
**Solución:**
1. Verifica que requirements.txt esté completo
2. Verifica que el Build Command sea correcto
3. Chequea los logs de build en Render

### Error: "Port already in use"
**Solución:**
- En Render usa: `--port $PORT` (variable automática)
- No hardcodees el puerto

### Error: CORS
**Solución:**
1. Verifica que el middleware CORS esté configurado
2. Agrega el dominio del frontend a allow_origins

## URLs de Ejemplo

### Desarrollo Local:
- Backend: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### Producción Render:
- Backend: `https://tu-servicio.onrender.com`
- Docs: `https://tu-servicio.onrender.com/docs`
- Health: `https://tu-servicio.onrender.com/health`

## Notas de Seguridad

1. **NO subas el archivo .env a Git**
2. **Usa diferentes credenciales para desarrollo y producción**
3. **Limita allow_origins en producción**
4. **Usa contraseñas fuertes en MongoDB**
5. **Habilita autenticación en MongoDB**
6. **Considera usar secrets manager para variables sensibles**

## Plan Free de Render

- **Recursos:** 512 MB RAM, CPU compartido
- **Auto-sleep:** Después de 15 minutos de inactividad
- **Límite:** 750 horas/mes de tiempo activo
- **Nota:** El primer request después de sleep puede tardar 30-60 segundos

Para evitar sleep, considera:
- Upgrade a plan pagado
- Usar servicio de "keep alive" (ping periódico)

---

**Última actualización:** 2025-10-13
