# Solución al Problema de CORS

## Problema Identificado

El frontend en Vercel (`https://frontend-castel.vercel.app`) no puede acceder al backend en Render (`https://backend-castel.onrender.com`) debido a un error de CORS:

```
Access to XMLHttpRequest at 'https://backend-castel.onrender.com/api/simulation/run'
from origin 'https://frontend-castel.vercel.app' has been blocked by CORS policy:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Causa Raíz

El archivo `render.yaml` no tenía configurada la variable de entorno `CORS_ORIGINS`, lo que causaba que el backend solo aceptara el origen por defecto (`*` en desarrollo, pero limitado en producción).

## Solución Implementada

### 1. Actualización de `render.yaml`

Se agregó la variable de entorno `CORS_ORIGINS` en el archivo `render.yaml`:

```yaml
envVars:
  # ... otras variables ...
  - key: CORS_ORIGINS
    value: https://frontend-castel.vercel.app,http://localhost:4200,http://localhost:8000
```

### 2. Actualización de `.env.example`

Se documentó la configuración de CORS con ejemplos para diferentes entornos:

```env
# CORS Configuration
# Para desarrollo: http://localhost:4200,http://localhost:3000
# Para producción: https://frontend-castel.vercel.app
# Para permitir todos: *
CORS_ORIGINS=https://frontend-castel.vercel.app,http://localhost:4200,http://localhost:3000
```

## Pasos para Aplicar la Solución en Render

### Opción A: Actualizar mediante render.yaml (Recomendado)

1. **Hacer commit de los cambios**:
   ```bash
   git add backend/render.yaml backend/.env.example
   git commit -m "fix: Add CORS configuration for Vercel frontend"
   git push origin main
   ```

2. **Render detectará los cambios automáticamente** y redesplegará el servicio con la nueva configuración.

### Opción B: Actualizar manualmente en el Dashboard de Render

Si prefieres actualizar sin hacer commit:

1. Ve al **Dashboard de Render**: https://dashboard.render.com/
2. Selecciona tu servicio **casterly-rock-api**
3. Ve a la sección **Environment**
4. Agrega una nueva variable de entorno:
   - **Key**: `CORS_ORIGINS`
   - **Value**: `https://frontend-castel.vercel.app,http://localhost:4200,http://localhost:8000`
5. Haz clic en **Save Changes**
6. Render redesplegará automáticamente el servicio

## Verificación

Una vez aplicados los cambios, verifica que el CORS funciona correctamente:

### 1. Verificar en los Logs de Render

Busca esta línea en los logs de inicio:

```
Configuración - CORS Origins: https://frontend-castel.vercel.app,http://localhost:4200,http://localhost:8000
```

### 2. Probar desde el Frontend

1. Abre el frontend: https://frontend-castel.vercel.app
2. Intenta ejecutar una simulación
3. Verifica en la consola del navegador que **NO aparezca el error de CORS**

### 3. Verificar Headers de CORS

Puedes verificar manualmente usando `curl`:

```bash
curl -I -X OPTIONS https://backend-castel.onrender.com/api/simulation/run \
  -H "Origin: https://frontend-castel.vercel.app" \
  -H "Access-Control-Request-Method: POST"
```

Deberías ver estos headers en la respuesta:

```
Access-Control-Allow-Origin: https://frontend-castel.vercel.app
Access-Control-Allow-Methods: *
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
```

## Configuración Actual de CORS en el Código

El middleware de CORS está configurado en `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # Lista de orígenes permitidos
    allow_credentials=True,          # Permite cookies/autenticación
    allow_methods=["*"],             # Permite todos los métodos HTTP
    allow_headers=["*"],             # Permite todos los headers
)
```

## Orígenes Permitidos

Actualmente se permiten los siguientes orígenes:

- ✅ `https://frontend-castel.vercel.app` - Frontend en Vercel (producción)
- ✅ `http://localhost:4200` - Desarrollo local (Angular)
- ✅ `http://localhost:8000` - Desarrollo local (FastAPI)

## Seguridad

⚠️ **IMPORTANTE**: No usar `CORS_ORIGINS=*` en producción. Siempre especificar los orígenes exactos que deben tener acceso al API.

## Tiempo de Aplicación

- **Opción A (render.yaml)**: 2-5 minutos (tiempo de build + deploy)
- **Opción B (Dashboard manual)**: 1-2 minutos (solo redeploy)

## Notas Adicionales

### Si el frontend cambia de URL

Si el frontend se mueve a otra URL (por ejemplo, un dominio personalizado), actualiza la variable `CORS_ORIGINS`:

```yaml
- key: CORS_ORIGINS
  value: https://tu-nuevo-dominio.com,https://frontend-castel.vercel.app,http://localhost:4200
```

### Para múltiples frontends

Si tienes múltiples frontends (staging, producción, etc.), sepáralos con comas:

```yaml
- key: CORS_ORIGINS
  value: https://frontend-prod.vercel.app,https://frontend-staging.vercel.app,http://localhost:4200
```

## Troubleshooting

### El error persiste después de actualizar

1. Verifica que Render haya redesplegado el servicio
2. Limpia la caché del navegador (Ctrl + Shift + R)
3. Verifica en los logs de Render que la variable se esté leyendo correctamente
4. Prueba con `curl` para descartar problemas del navegador

### Error 502 Bad Gateway

Si obtienes un error 502 después de actualizar:

1. Verifica que no haya errores de sintaxis en `render.yaml`
2. Revisa los logs de Render para ver el error exacto
3. Verifica que todas las variables de entorno requeridas estén configuradas

## Estado

- ✅ Archivos actualizados localmente
- ⏳ Pendiente: Push a repositorio y redeploy en Render
- ⏳ Pendiente: Verificación de funcionamiento

---

**Fecha**: 2025-11-04
**Autor**: Claude Code (Sonnet 4.5)
