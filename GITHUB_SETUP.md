# Preparacion para GitHub - Backend

Este documento contiene las instrucciones para preparar el proyecto backend antes de subirlo a GitHub.

## Archivos y Carpetas Excluidos

El `.gitignore` ya esta configurado para excluir:

### Entorno Virtual (carpeta mas pesada)
- `venv/` - Entorno virtual de Python (~100-500MB)
- `env/`, `ENV/`, `.venv/` - Variantes de entorno virtual

### Cache de Python
- `__pycache__/` - Bytecode compilado
- `*.pyc`, `*.pyo` - Archivos compilados
- `.pytest_cache/` - Cache de pytest

### Configuracion y Credenciales
- `.env` - Variables de entorno (CRITICO: contiene credenciales)
- `.env.*` - Variantes de configuracion
- Excepto `.env.example` (plantilla sin credenciales)

### IDE y Editores
- `.vscode/`, `.idea/` - Configuraciones de editores
- `*.swp`, `*.swo` - Archivos temporales de vim

### Archivos del Sistema
- `.DS_Store` (macOS)
- `Thumbs.db` (Windows)
- `desktop.ini` (Windows)

### Testing y Coverage
- `.coverage` - Datos de cobertura
- `htmlcov/` - Reportes HTML de coverage
- `.pytest_cache/` - Cache de pytest

### Logs y Temporales
- `*.log` - Archivos de log
- `logs/` - Directorio de logs
- `tmp/`, `temp/` - Directorios temporales

### Base de Datos Local
- `*.db`, `*.sqlite`, `*.sqlite3` - Bases de datos SQLite

## Crear .env.example

Crea un archivo `.env.example` con la plantilla (sin credenciales reales):

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

## Verificacion Pre-GitHub

Antes de hacer push a GitHub, ejecuta estos comandos:

```bash
# 1. Verificar que .env NO este en el repositorio
git status | grep ".env"
# No debe aparecer .env (solo .env.example)

# 2. Verificar que venv/ NO este en el repositorio
git status | grep "venv"
# No debe aparecer

# 3. Limpiar cache de Python
find . -type d -name "__pycache__" -exec rm -r {} + 2>NUL
# Windows:
for /d /r %d in (__pycache__) do @if exist "%d" rd /s /q "%d"

# 4. Verificar archivos a incluir
git add -n .
# Muestra que archivos se agregarian sin agregarlos realmente

# 5. Verificar tamaño del repositorio
git count-objects -vH
```

## Inicializar Repositorio Git

Si aun no has inicializado Git en este directorio:

```bash
# Navegar al directorio backend
cd "C:\Users\Carlos Alvarado\Documents\CXP\PROYECTO SIMULACION\Desarrollo\Desarrollo-Boceto\backend"

# Inicializar repositorio
git init

# Agregar todos los archivos (respetando .gitignore)
git add .

# Crear primer commit
git commit -m "Initial commit: Trading Simulation Platform Backend"

# Conectar con repositorio remoto
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git

# Push inicial
git branch -M main
git push -u origin main
```

## Verificar Archivos Trackeados

Para verificar que archivos seran incluidos en el repositorio:

```bash
# Ver archivos que seran commiteados
git ls-files

# Ver tamaño de archivos trackeados
git ls-files | xargs -I{} du -sh {} | sort -h

# Verificar que .env NO este incluido (CRITICO)
git ls-files | grep ".env"
# Solo debe aparecer .env.example

# Verificar que venv/ NO este incluido
git ls-files | grep "venv"
# No debe aparecer nada
```

## Tamaño Estimado

Sin `venv/`, `__pycache__/`, logs y `.env`, el repositorio deberia pesar aproximadamente:

- Codigo fuente Python: ~1-3 MB
- Dependencias listadas en requirements.txt: ~5-10 KB
- Configuracion y docs: ~50-100 KB
- Total estimado: **< 5 MB**

Esto esta muy por debajo del limite de 100MB de GitHub.

## Archivos Importantes Incluidos

Los siguientes archivos SI deben estar en el repositorio:

- `requirements.txt` - Dependencias de Python
- `.env.example` - Plantilla de variables de entorno
- `README.md` - Documentacion del proyecto
- `app/` - Todo el codigo fuente
- `.gitignore` - Configuracion de exclusiones
- Scripts de test (`.py`)

## Archivos CRITICOS Excluidos

Estos archivos NUNCA deben estar en GitHub:

- `.env` - Contiene credenciales de MongoDB
- `venv/` - Entorno virtual (muy pesado)
- `*.log` - Logs pueden contener informacion sensible
- `*.db` - Bases de datos locales

## Despues de Clonar

Cuando alguien clone el repositorio, debera ejecutar:

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar .env (copiar desde .env.example)
cp .env.example .env
# Luego editar .env con credenciales reales

# 5. Iniciar servidor
uvicorn app.main:app --reload
```

## Branches Recomendadas

Estructura de branches sugerida:

- `main` - Produccion estable
- `develop` - Desarrollo activo
- `feature/*` - Features especificos
- `hotfix/*` - Fixes urgentes

## requirements.txt

Asegurate de que `requirements.txt` este actualizado:

```bash
# Generar requirements.txt desde entorno actual
pip freeze > requirements.txt

# O mantener solo dependencias principales (recomendado)
# Editar manualmente requirements.txt con solo lo necesario
```

## .gitignore Verificado

El `.gitignore` actual incluye:

```
venv/             # ~100-500MB excluidos
__pycache__/      # ~1-50MB excluidos
.env              # Credenciales excluidas (CRITICO)
*.log             # Logs excluidos
*.pyc             # Bytecode excluido
.pytest_cache/    # Cache de tests excluido
```

## Comandos de Limpieza

Si necesitas limpiar antes de commit:

```bash
# Windows
rmdir /s /q venv
rmdir /s /q __pycache__
del /s /q *.pyc
del /s /q *.log

# Linux/Mac
rm -rf venv
find . -type d -name "__pycache__" -exec rm -r {} +
find . -type f -name "*.pyc" -delete
find . -type f -name "*.log" -delete
```

## Seguridad de Credenciales

### IMPORTANTE: Verificar que .env no este en Git

```bash
# Verificar historial completo de Git
git log --all --full-history -- .env

# Si .env aparece en el historial, es necesario:
# 1. Cambiar TODAS las credenciales en .env
# 2. Limpiar historial de Git o crear repo nuevo
```

### Si accidentalmente commiteaste .env:

```bash
# ANTES de hacer push:
git reset HEAD~1
git add .
git commit -m "Fix: Remove .env from tracking"

# DESPUES de hacer push (mas complejo):
# 1. Cambiar todas las credenciales
# 2. Usar git-filter-branch o BFG Repo-Cleaner
# 3. Force push (peligroso si hay colaboradores)
```

## GitHub Actions (Opcional)

Considera agregar `.github/workflows/` para CI/CD:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/
```

## GitHub Secrets

Para CI/CD, configura secrets en GitHub:
- Settings → Secrets → Actions
- Agregar: `MONGODB_URL`, `MONGODB_DATABASE`, etc.

## .gitattributes (Opcional)

Crear `.gitattributes` para normalizar line endings:

```
# Auto detect text files
* text=auto

# Python files
*.py text eol=lf
*.pyi text eol=lf

# Config files
*.json text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.toml text eol=lf

# Shell scripts
*.sh text eol=lf
*.bash text eol=lf
```

## Checklist Final

Antes de hacer push a GitHub:

- [ ] `.env` NO esta en el repositorio
- [ ] `.env.example` SI esta en el repositorio
- [ ] `venv/` NO esta en el repositorio
- [ ] `__pycache__/` NO esta en el repositorio
- [ ] `requirements.txt` esta actualizado
- [ ] README.md esta completo
- [ ] `.gitignore` esta configurado correctamente
- [ ] Tamaño del repo < 100 MB
- [ ] No hay logs o archivos temporales
- [ ] Codigo compila sin errores

## Notas Finales

1. El proyecto esta listo para GitHub con el `.gitignore` actual
2. NUNCA incluyas credenciales o secretos en Git
3. Usa `.env.example` como plantilla
4. Documenta cualquier configuracion especial en el README
5. Considera usar GitHub Secrets para CI/CD

## Contacto

Para preguntas sobre la configuracion del repositorio, contactar al equipo de desarrollo.
