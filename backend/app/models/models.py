import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, ForeignKey,
    Enum as SQLEnum, Text, Integer, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.db.database import Base


# ─── Enumeraciones ──────────────────────────────────────────────────────────

class RolUsuario(str, enum.Enum):
    ADMIN    = "admin"
    GANADERO = "ganadero"

class PropositoAnimal(str, enum.Enum):
    CARNE          = "carne"
    LECHE          = "leche"
    DOBLE_PROPOSITO = "doble_proposito"

class TipoReporte(str, enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    HATO       = "HATO"
    GENERAL    = "GENERAL"

class FormatoReporte(str, enum.Enum):
    PDF   = "PDF"
    EXCEL = "EXCEL"

class AccionAuditoria(str, enum.Enum):
    LOGIN           = "login"
    LOGOUT          = "logout"
    CREAR           = "crear"
    MODIFICAR       = "modificar"
    ELIMINAR        = "eliminar"
    GENERAR_REPORTE = "generar_reporte"


# ─── Schema: auth ───────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rol: Mapped[RolUsuario] = mapped_column(
        SQLEnum(RolUsuario, values_callable=lambda x: [e.value for e in x]),
        default=RolUsuario.GANADERO, nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bloqueado_hasta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    hatos: Mapped[List["Hato"]] = relationship("Hato", back_populates="propietario")

    def __repr__(self):
        return f"<Usuario {self.email} ({self.rol})>"


# ─── Schema: ganaderia ──────────────────────────────────────────────────────

class Hato(Base):
    __tablename__ = "hatos"
    __table_args__ = {"schema": "ganaderia"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    finca: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    propietario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.usuarios.id"), nullable=False
    )

    propietario: Mapped["Usuario"] = relationship("Usuario", back_populates="hatos")
    animales: Mapped[List["Animal"]] = relationship("Animal", back_populates="hato")

    def __repr__(self):
        return f"<Hato {self.nombre} - {self.finca}>"


class Animal(Base):
    __tablename__ = "animales"
    __table_args__ = {"schema": "ganaderia"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    arete: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    nombre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raza: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proposito: Mapped[Optional[PropositoAnimal]] = mapped_column(
        SQLEnum(PropositoAnimal, values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    hato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ganaderia.hatos.id"), nullable=False
    )

    hato: Mapped["Hato"] = relationship("Hato", back_populates="animales")
    mediciones: Mapped[List["Medicion"]] = relationship(
        "Medicion", back_populates="animal", order_by="Medicion.fecha_medicion.desc()"
    )

    def __repr__(self):
        return f"<Animal {self.arete} - {self.raza or 'Sin raza'}>"


class Medicion(Base):
    __tablename__ = "mediciones"
    __table_args__ = {"schema": "ganaderia"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    peso_estimado_kg: Mapped[float] = mapped_column(Float, nullable=False)
    bcs: Mapped[float] = mapped_column(Float, nullable=False)
    confianza: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    img_lateral_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    img_trasera_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    morfometria: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    modelo_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    procesado_por: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_estimacion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fecha_medicion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    notas: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ganaderia.animales.id"), nullable=False, index=True
    )

    animal: Mapped["Animal"] = relationship("Animal", back_populates="mediciones")

    def __repr__(self):
        return f"<Medicion {self.animal_id} | {self.peso_estimado_kg}kg BCS:{self.bcs}>"


# ─── Schema: reportes ───────────────────────────────────────────────────────

class Reporte(Base):
    __tablename__ = "reportes"
    __table_args__ = {"schema": "reportes"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[TipoReporte] = mapped_column(
        SQLEnum(TipoReporte, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    formato: Mapped[FormatoReporte] = mapped_column(
        SQLEnum(FormatoReporte, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    url_archivo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parametros: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fecha_generado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    generado_por_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.usuarios.id"), nullable=False
    )
    hato_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ganaderia.hatos.id"), nullable=True
    )
    animal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ganaderia.animales.id"), nullable=True
    )

    generado_por: Mapped["Usuario"] = relationship("Usuario")
    hato: Mapped[Optional["Hato"]] = relationship("Hato")
    animal: Mapped[Optional["Animal"]] = relationship("Animal")

    def __repr__(self):
        return f"<Reporte {self.titulo} ({self.tipo} - {self.formato})>"


# ─── Schema: auditoria ──────────────────────────────────────────────────────

class AuditoriaLog(Base):
    __tablename__ = "logs"
    __table_args__ = {"schema": "auditoria"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.usuarios.id"), nullable=True
    )
    usuario_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    accion: Mapped[AccionAuditoria] = mapped_column(
        SQLEnum(AccionAuditoria, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )
    tabla_afectada: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    registro_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    datos_antes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    datos_despues: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    detalle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    usuario: Mapped[Optional["Usuario"]] = relationship("Usuario")

    def __repr__(self):
        return f"<AuditoriaLog {self.accion} | {self.usuario_email} | {self.fecha}>"