# main.py
"""
ENTRY POINT — BovineAI Backend
Arquitectura: MVC
  Modelo      → app/models/        (SQLAlchemy ORM)
  Vista       → app/views/         (respuestas JSON estandarizadas)
  Controlador → app/controllers/   (rutas FastAPI)
  Servicios   → app/services/      (lógica de negocio + inferencia)
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import get_settings
from config.database import init_db
from app.controllers.animal_controller import router as animal_router
from app.controllers.analysis_controller import router as analysis_router

# ── Configuración ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("bovineai")
settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🐄 BovineAI iniciando...")
    await init_db()
    logger.info("✓ Base de datos lista")
    # Pre-cargar modelos en memoria al arrancar
    try:
        from app.services.inference_service import ModelRegistry
        ModelRegistry.load_mass_model()
        ModelRegistry.load_bcs_model()
        logger.info("✓ Modelos PyTorch cargados")
    except FileNotFoundError as e:
        logger.warning(f"⚠ Modelos no encontrados: {e} — coloca tus .pt en models_pt/")
    yield
    logger.info("BovineAI apagándose...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="BovineAI API",
    description="Sistema de estimación de masa y condición corporal en bovinos mediante visión computacional",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — permite que el frontend HTML llame a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En producción: especifica el dominio del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos (imágenes guardadas)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ── Registrar routers (Controladores) ─────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(animal_router, prefix=API_PREFIX)
app.include_router(analysis_router, prefix=API_PREFIX)


# ── Manejador global de errores ───────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Error interno del servidor"},
    )


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "app": settings.APP_NAME}


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
