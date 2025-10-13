# Backend - Simulación Casterly Rock

Sistema de selección, asignación y rotación de agentes usando FastAPI y MongoDB.

## Requisitos

- Python 3.10+
- MongoDB Atlas

## Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
```

2. Activar entorno virtual:
- Windows: `venv\Scripts\activate`
- Linux/Mac: `source venv/bin/activate`

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno en `.env`

## Ejecución

```bash
uvicorn app.main:app --reload
```

El servidor estará disponible en: http://localhost:8000

## Documentación API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Arquitectura

- Domain: Entidades y repositorios (capa de negocio)
- Application: Servicios y casos de uso
- Infrastructure: Implementaciones concretas (MongoDB)
- Presentation: API REST endpoints
