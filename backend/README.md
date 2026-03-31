# 🐄 JER-WEIGHT — Backend

Sistema de Estimación de Peso en Vacas Jersey mediante Visión por Computadora.

## Stack
- **Python 3.11** + **FastAPI** + **PostgreSQL** (vacasTesis)
- **Roboflow** (segmentación de silueta) + **OpenCV** (morfometría)
- Arquitectura **MVC**

---

## ⚡ Levantar el servidor

```bash
# 1. Activar entorno virtual
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

# 2. Instalar dependencias (solo la primera vez)
pip install -r requirements.txt

# 3. Crear tablas (solo la primera vez)
python crear_tablas.py

# 4. Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

Documentación: http://localhost:8000/docs

---

## 📁 Estructura MVC

```
backend/
├── app/
│   ├── main.py                    # Entrada FastAPI
│   ├── core/
│   │   ├── config.py              # Variables de entorno
│   │   └── security.py            # JWT + bcrypt
│   ├── db/
│   │   └── database.py            # Conexión PostgreSQL
│   ├── models/          ← MODELO
│   │   └── models.py              # Usuario, Hato, Animal, Medicion
│   ├── schemas/
│   │   └── schemas.py             # Validaciones Pydantic
│   ├── controllers/     ← CONTROLADOR
│   │   ├── auth_controller.py     # Login / Registro
│   │   ├── animal_controller.py   # CRUD vacas y hatos
│   │   └── analisis_controller.py # ⭐ Análisis de fotos
│   └── services/        ← SERVICIOS
│       ├── vision_service.py      # Roboflow + OpenCV
│       └── estimacion_service.py  # Modelo ML peso + BCS
├── models_pt/                     # Modelos PyTorch entrenados
├── uploads/                       # Fotos subidas
├── crear_tablas.py                # Script para crear/recrear tablas
└── .env                           # Configuración local
```

---

## 🔌 Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/v1/auth/registro` | Registrar ganadero |
| POST | `/api/v1/auth/login` | Login → token JWT |
| POST | `/api/v1/hatos/` | Crear hato |
| POST | `/api/v1/animales/` | Registrar vaca Jersey |
| **POST** | **`/api/v1/analisis/`** | **⭐ Analizar fotos → peso + BCS** |
| GET | `/api/v1/animales/{id}/mediciones` | Historial de la vaca |
| GET | `/api/v1/hatos/{id}/estadisticas` | Estadísticas del hato |
