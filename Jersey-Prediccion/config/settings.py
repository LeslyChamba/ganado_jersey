# config/settings.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "BovineAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "bovineai"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # Modelo XGBoost — generado con train_final_model.py
    MASS_MODEL_PATH: str = "models_pt/mass_model.json"

    # Imagen
    IMAGE_MAX_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"
    ALLOWED_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "webp"]

    # Visión computacional — escala por altura promedio Jersey
    # Cambia este valor si trabajas con animales de otra edad/talla
    # Vacas adultas Jersey: 118–135 cm. Promedio: 123 cm.
    JERSEY_ALTURA_PROMEDIO_CM: float = 123.0
    CONFIDENCE_THRESHOLD: float = 0.50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
