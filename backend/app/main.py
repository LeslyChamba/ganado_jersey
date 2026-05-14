import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.database import engine, Base
from app.controllers.admin_controller import router as admin_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.animal_controller import hato_router, animal_router
from app.controllers.analisis_controller import router as analisis_router
from app.controllers.reportes_controller import router as reporte_router
from app.controllers.dashboard_controller import router as dashboard_router
from app.controllers.bovinos_controller import router as bovinos_router
from app.core.model_loader import descargar_modelos

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("jer-weight")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando JER-WEIGHT v{settings.APP_VERSION}")

    Path(settings.UPLOAD_DIR).mkdir(exist_ok=True)
    logger.info(f"📁 Directorio de imágenes: {settings.UPLOAD_DIR}")

    if settings.ENVIRONMENT == "development":
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas verificadas (dev mode)")

    # Cargar modelos en background — no bloquea el arranque del servidor
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, descargar_modelos)
    logger.info("⏳ Modelos cargando en background...")

    yield

    logger.info("🛑 Apagando JER-WEIGHT...")


app = FastAPI(
    title="JER-WEIGHT API",
    description="""
## JER-WEIGHT — Sistema de Estimación de Peso en Vacas Jersey

Estima el **peso corporal** y **condición corporal (BCS)** de vacas Jersey
mediante análisis de imágenes con visión por computadora.

### Flujo principal:
1. Registra el ganadero y su hato
2. Registra las vacas con su arete
3. Toma foto lateral + trasera
4. Obtén peso estimado y BCS al instante

### Tecnologías:
- **Segmentación**: SAM (Segment Anything Model)
- **BCS**: YOLOv8 (foto trasera)
- **Morfometría**: OpenCV
- **Estimación**: XGBoost + Fórmula calibrada Jersey
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# allow_origins=["*"] con allow_credentials=False permite cualquier origen
# Cámbialo a la lista específica cuando todo funcione
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

Path(settings.UPLOAD_DIR).mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

API_PREFIX = "/api/v1"
app.include_router(auth_router,      prefix=API_PREFIX)
app.include_router(admin_router,     prefix=API_PREFIX)
app.include_router(hato_router,      prefix=API_PREFIX)
app.include_router(animal_router,    prefix=API_PREFIX)
app.include_router(analisis_router,  prefix=API_PREFIX)
app.include_router(reporte_router,   prefix=API_PREFIX)
app.include_router(bovinos_router,   prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)


@app.get("/", tags=["Sistema"])
def raiz():
    return {
        "sistema": "JER-WEIGHT",
        "descripcion": "Estimación de Peso en Vacas Jersey",
        "version": settings.APP_VERSION,
        "estado": "activo",
        "docs": "/docs",
    }


@app.get("/health", tags=["Sistema"])
def health_check():
    from sqlalchemy import text
    from app.db.database import SessionLocal
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "sistema": "JER-WEIGHT",
        "database": "conectada" if db_ok else "sin conexión",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/v1/health", tags=["Sistema"])
def health_check_v1():
    from sqlalchemy import text
    from app.db.database import SessionLocal
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "conectada" if db_ok else "sin conexión",
    }