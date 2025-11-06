# ADR 001: Adopción de Clean Architecture

## Estado
Aceptado

## Contexto
El proyecto de simulación de trading requiere una arquitectura que permita:
- Escalabilidad a medida que crece el negocio
- Testabilidad alta para garantizar calidad
- Mantenibilidad a largo plazo
- Independencia de frameworks y bases de datos
- Separación clara de responsabilidades

## Decisión
Adoptamos **Clean Architecture** como patrón arquitectónico principal, con separación en 4 capas:

1. **Presentation Layer** (`app/presentation/`):
   - FastAPI routes (API REST)
   - DTOs (Pydantic models)
   - HTTP middleware

2. **Application Layer** (`app/application/`):
   - Services (casos de uso)
   - Event Handlers
   - Query Services (CQRS)
   - Command Services (CQRS)

3. **Domain Layer** (`app/domain/`):
   - Entities (Pydantic)
   - Repository Interfaces (ABC)
   - Domain Events
   - Business Rules
   - Strategies (OCP)
   - Domain Services

4. **Infrastructure Layer** (`app/infrastructure/`):
   - Repository Implementations (MongoDB)
   - Database configuration
   - Dependency Injection
   - External services

## Consecuencias

### Positivas
✅ **Independencia de frameworks**: La lógica de negocio no depende de FastAPI
✅ **Testabilidad**: Capas internas testables sin dependencias externas
✅ **Flexibilidad**: Fácil cambiar MongoDB por otra base de datos
✅ **Mantenibilidad**: Separación clara de responsabilidades
✅ **Escalabilidad**: Arquitectura lista para crecer

### Negativas
⚠️ **Curva de aprendizaje**: Desarrolladores nuevos necesitan entender la arquitectura
⚠️ **Más código**: Requiere más archivos y abstracciones
⚠️ **Over-engineering inicial**: Puede parecer excesivo para proyectos pequeños

## Alternativas Consideradas

### 1. Arquitectura en 3 capas (tradicional)
- ❌ Menos flexible
- ❌ Mayor acoplamiento
- ❌ Difícil de testear

### 2. Arquitectura Hexagonal
- ✅ Similar a Clean Architecture
- ⚠️ Menos conocida en el equipo

## Referencias
- [The Clean Architecture - Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Clean Architecture in Python](https://www.thedigitalcatonline.com/blog/2016/11/14/clean-architectures-in-python-a-step-by-step-example/)

## Fecha
2025-11-04

## Autores
- Equipo de Desarrollo
- Claude Code (Sonnet 4.5)
