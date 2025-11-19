"""
Sistema de cache simple en memoria para optimizar queries frecuentes.

Uso:
    from app.infrastructure.cache.simple_cache import cache

    @cache.memoize(ttl=60)
    def get_active_accounts():
        return list(collection.find({"estado": "activo"}))
"""

import time
import functools
from typing import Callable, Any, Optional
import hashlib
import json


class SimpleCache:
    """
    Cache en memoria simple con TTL (Time To Live).

    Caracteristicas:
    - Cache en memoria (dict)
    - TTL configurable por entrada
    - Invalidacion automatica por tiempo
    - Limpieza automatica de entradas expiradas
    """

    def __init__(self):
        self._cache = {}
        self._timestamps = {}

    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del cache si existe y no ha expirado."""
        if key not in self._cache:
            return None

        timestamp, ttl = self._timestamps.get(key, (0, 0))
        if time.time() - timestamp > ttl:
            # Expirado - eliminar
            del self._cache[key]
            del self._timestamps[key]
            return None

        return self._cache[key]

    def set(self, key: str, value: Any, ttl: int = 60):
        """Guarda un valor en el cache con TTL en segundos."""
        self._cache[key] = value
        self._timestamps[key] = (time.time(), ttl)

    def delete(self, key: str):
        """Elimina una entrada del cache."""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]

    def clear(self):
        """Limpia todo el cache."""
        self._cache.clear()
        self._timestamps.clear()

    def cleanup(self):
        """Elimina entradas expiradas del cache."""
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, ttl) in self._timestamps.items()
            if current_time - timestamp > ttl
        ]
        for key in expired_keys:
            self.delete(key)

    def memoize(self, ttl: int = 60):
        """
        Decorador para cachear resultados de funciones.

        Args:
            ttl: Tiempo de vida del cache en segundos

        Ejemplo:
            @cache.memoize(ttl=300)
            def get_expensive_data():
                return expensive_query()
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generar clave unica basada en funcion + args
                key_data = {
                    "func": func.__name__,
                    "args": str(args),
                    "kwargs": str(sorted(kwargs.items()))
                }
                cache_key = hashlib.md5(
                    json.dumps(key_data, sort_keys=True).encode()
                ).hexdigest()

                # Intentar obtener del cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Ejecutar funcion y cachear resultado
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl=ttl)
                return result

            # Agregar metodo para invalidar cache de esta funcion
            def invalidate():
                # Limpiar todo el cache para esta funcion
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if key.startswith(func.__name__)
                ]
                for key in keys_to_delete:
                    self.delete(key)

            wrapper.invalidate = invalidate
            return wrapper

        return decorator


# Instancia global del cache
cache = SimpleCache()
