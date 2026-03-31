# app/models/animal.py
from sqlalchemy import Column, String, Enum, DateTime, func
from sqlalchemy.orm import relationship
import enum
import uuid
from config.database import Base





class Animal(Base):
    __tablename__ = "animals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    arete = Column(String(50), unique=True, nullable=False, index=True)  # ID del productor
    notas = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación 1-N con análisis
    analyses = relationship(
        "Analysis",
        back_populates="animal",
        cascade="all, delete-orphan",
        order_by="Analysis.created_at",
    )

    def __repr__(self):
        return f"<Animal arete={self.arete}>"