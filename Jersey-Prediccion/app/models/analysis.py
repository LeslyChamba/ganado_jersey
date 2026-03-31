# app/models/analysis.py
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import relationship
import uuid
from config.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    animal_id = Column(String(36), ForeignKey("animals.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Resultados del modelo de masa ──
    masa_estimada_kg = Column(Float, nullable=False)
    masa_margen_error_kg = Column(Float, nullable=True)
    masa_confianza = Column(Float, nullable=True)      # 0.0 – 1.0

    # ── Resultados del modelo BCS ──
    bcs_score = Column(Float, nullable=False)          # 1.0 – 5.0
    bcs_confianza = Column(Float, nullable=True)

    # ── Morfometría (OpenCV) ──
    largo_corporal_cm = Column(Float, nullable=True)
    altura_cruz_cm = Column(Float, nullable=True)
    perimetro_toracico_cm = Column(Float, nullable=True)
    ancho_cadera_cm = Column(Float, nullable=True)

    # ── Imagen ──
    imagen_path = Column(String(255), nullable=True)   # ruta relativa en el servidor
    imagen_hash = Column(String(64), nullable=True)    # SHA-256 para deduplicar

    # ── Metadata extra (keypoints, bounding box, etc.) ──
    metadata_json = Column(JSON, nullable=True)

    # ── Audit ──
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relación N-1 con animal
    animal = relationship("Animal", back_populates="analyses")

    def __repr__(self):
        return (
            f"<Analysis animal={self.animal_id} "
            f"masa={self.masa_estimada_kg}kg bcs={self.bcs_score}>"
        )
