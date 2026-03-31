# BovineAI — Backend MVC

## Arquitectura

```
bovineai/
├── app/
│   ├── models/          ← MODELO: SQLAlchemy ORM (tablas PostgreSQL)
│   │   ├── animal.py
│   │   └── analysis.py
│   │
│   ├── schemas/         ← Pydantic: validación entrada/salida (DTOs)
│   │   ├── animal.py
│   │   └── analysis.py
│   │
│   ├── controllers/     ← CONTROLADOR: rutas FastAPI, orquesta flujo
│   │   ├── animal_controller.py
│   │   └── analysis_controller.py
│   │
│   ├── services/        ← Lógica de negocio + inferencia PyTorch
│   │   ├── inference_service.py   (carga modelos .pt, predice)
│   │   ├── animal_service.py
│   │   └── analysis_service.py
│   │
│   └── views/           ← VISTA: respuestas JSON estructuradas
│       └── response.py
│
├── config/
│   ├── database.py      ← Conexión PostgreSQL (SQLAlchemy async)
│   └── settings.py      ← Variables de entorno (.env)
│
├── models_pt/           ← Tus archivos .pt aquí
│   ├── bcs_model.pt
│   └── mass_model.pt
│
├── uploads/             ← Imágenes temporales
├── main.py              ← Entry point FastAPI
├── requirements.txt
└── .env.example
```

## Flujo de una petición de análisis

```
Frontend (HTML)
    │  POST /api/v1/analysis/  (imagen + metadata)
    ▼
Controller (analysis_controller.py)
    │  Valida schema, llama service
    ▼
Service (analysis_service.py + inference_service.py)
    │  Preprocesa imagen → PyTorch → BCS + masa
    │  Guarda resultado via animal_service
    ▼
Model (analysis.py)
    │  SQLAlchemy ORM → PostgreSQL
    ▼
View (response.py)
    │  Serializa JSON estructurado
    ▼
Frontend recibe resultados
```

## Instalación

```bash
pip install -r requirements.txt
cp .env.example .env   # editar con tus credenciales
alembic upgrade head   # crear tablas en PostgreSQL
uvicorn main:app --reload --port 8000
```

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /api/v1/analysis/ | Analizar imagen de bovino |
| GET | /api/v1/analysis/{id} | Obtener análisis por ID |
| GET | /api/v1/animals/ | Listar todos los animales |
| GET | /api/v1/animals/{animal_id} | Animal + historial |
| POST | /api/v1/animals/ | Registrar animal |
| GET | /api/v1/animals/{animal_id}/evolution | Evolución temporal |
