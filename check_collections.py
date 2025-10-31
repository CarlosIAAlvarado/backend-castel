"""
Script para verificar colecciones disponibles.
"""

from pymongo import MongoClient

MONGODB_URI = "mongodb+srv://calvarado:Andresito111@ivy.beuwz4f.mongodb.net/?retryWrites=true&w=majority&appName=ivy"
DATABASE_NAME = "simulacion_casterly_rock"

client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

print("Colecciones con 'top16' en el nombre:")
print("="*60)

for col_name in sorted(db.list_collection_names()):
    if 'top16' in col_name.lower():
        count = db[col_name].count_documents({})
        sample = db[col_name].find_one()

        print(f"\n{col_name}:")
        print(f"  Documentos: {count}")

        if sample:
            date = sample.get('date', 'N/A')
            print(f"  Fecha ejemplo: {date}")

print("\n" + "="*60)
print("\nColecciones con 'roi' en el nombre:")
print("="*60)

for col_name in sorted(db.list_collection_names()):
    if 'roi' in col_name.lower() and 'top16' not in col_name.lower():
        count = db[col_name].count_documents({})
        print(f"{col_name}: {count} documentos")

client.close()
