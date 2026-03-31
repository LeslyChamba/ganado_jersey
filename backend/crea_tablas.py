from app.db.database import engine, Base
from app.models.models import Usuario, Hato, Animal, Medicion

Base.metadata.drop_all(bind=engine)
print("Tablas anteriores eliminadas")
Base.metadata.create_all(bind=engine)
print("Tablas nuevas creadas correctamente")