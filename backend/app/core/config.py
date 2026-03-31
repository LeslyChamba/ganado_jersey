from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # Base
    APP_NAME: str = "JER-WEIGHT"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Seguridad
    SECRET_KEY: str = "dev_secret_key_cambia_esto"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Base de datos — soporta ambos formatos (DB_* y POSTGRES_*)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "vacasTesis"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "vacas2026"

    # Alias opcionales (por compatibilidad)
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""

    # Modelos ML
    MASS_MODEL_PATH: str = "models_pt/mass_model.pt"
    BCS_MODEL_PATH: str = "models_pt/bcs_model.pt"

    # Inferencia
    DEVICE: str = "cpu"
    IMG_SIZE: int = 224

    # Almacenamiento
    STORAGE_TYPE: str = "local"
    UPLOAD_DIR: str = "uploads"
    IMAGE_MAX_SIZE_MB: int = 10

    # Roboflow
    ROBOFLOW_API_KEY: str = ""
    ROBOFLOW_PROJECT_CATTLE: str = "live_cattle"
    ROBOFLOW_MODEL_VERSION: int = 1

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def DATABASE_URL(self) -> str:
        # Usa DB_* como fuente principal
        user = self.DB_USER or self.POSTGRES_USER
        password = self.DB_PASSWORD or self.POSTGRES_PASSWORD
        host = self.DB_HOST or self.POSTGRES_HOST or "localhost"
        port = self.DB_PORT or self.POSTGRES_PORT or 5432
        db = self.DB_NAME or self.POSTGRES_DB
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def MAX_IMAGE_SIZE_BYTES(self) -> int:
        return self.IMAGE_MAX_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignora variables extra en el .env


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
