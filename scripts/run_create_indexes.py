"""
Script auxiliar para ejecutar create_indexes.py con variables de entorno
"""
import sys
import os
from pathlib import Path

# Agregar el directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Cargar variables de entorno desde backend/.env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

print(f"✓ Variables de entorno cargadas desde: {env_path}")
print(f"✓ MONGODB_URI: {os.getenv('MONGODB_URI')[:50]}...")
print(f"✓ DATABASE_NAME: {os.getenv('DATABASE_NAME')}")
print()

# Ahora sí importar y ejecutar el script original
from scripts.create_indexes import main

if __name__ == "__main__":
    main()
