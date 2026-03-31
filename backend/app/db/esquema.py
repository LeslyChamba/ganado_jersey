# Ejecuta esto una vez para ver todas tus tablas y columnas
from app.db.database import Base, engine
from sqlalchemy import inspect

inspector = inspect(engine)
for table in inspector.get_table_names():
    print(f"\n=== {table} ===")
    for col in inspector.get_columns(table):
        print(f"  {col['name']}: {col['type']} | nullable={col['nullable']}")
    for fk in inspector.get_foreign_keys(table):
        print(f"  FK: {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}")

