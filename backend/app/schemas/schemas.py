import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from app.models.models import RolUsuario, PropositoAnimal, TipoReporte, FormatoReporte


# ════════════════════════════════════════════════════════
#  USUARIO
# ════════════════════════════════════════════════════════

class UsuarioCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    telefono: Optional[str] = None
    rol: RolUsuario = RolUsuario.GANADERO


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    apellido: Optional[str] = Field(None, min_length=1, max_length=100)
    telefono: Optional[str] = None


class UsuarioResponse(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str
    apellido: str
    telefono: Optional[str]
    rol: RolUsuario
    activo: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class RefreshRequest(BaseModel):
    refresh_token: str


# ════════════════════════════════════════════════════════
#  HATO
# ════════════════════════════════════════════════════════

class HatoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    finca: str = Field(min_length=1, max_length=150)
    ubicacion: Optional[str] = None
    descripcion: Optional[str] = None


class HatoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    finca: Optional[str] = Field(None, min_length=1, max_length=150)
    ubicacion: Optional[str] = None
    descripcion: Optional[str] = None


class HatoResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    finca: str
    ubicacion: Optional[str]
    descripcion: Optional[str]
    activo: bool
    propietario_id: uuid.UUID
    total_animales: Optional[int] = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ════════════════════════════════════════════════════════
#  ANIMAL
# ════════════════════════════════════════════════════════

class AnimalCreate(BaseModel):
    arete: str = Field(min_length=1, max_length=50)
    nombre: Optional[str] = None
    raza: Optional[str] = None
    proposito: Optional[PropositoAnimal] = None
    notas: Optional[str] = None
    hato_id: uuid.UUID


class AnimalUpdate(BaseModel):
    nombre: Optional[str] = None
    raza: Optional[str] = None
    proposito: Optional[PropositoAnimal] = None
    notas: Optional[str] = None


class AnimalResponse(BaseModel):
    id: uuid.UUID
    arete: str
    nombre: Optional[str]
    raza: Optional[str]
    proposito: Optional[PropositoAnimal]
    notas: Optional[str]
    hato_id: uuid.UUID
    hato_nombre: Optional[str] = None
    total_mediciones: Optional[int] = 0
    ultima_medicion: Optional[datetime] = None
    ultimo_peso_kg: Optional[float] = None
    ultimo_bcs: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ════════════════════════════════════════════════════════
#  MEDICION
# ════════════════════════════════════════════════════════

class MorfometriaData(BaseModel):
    alzada_cm: Optional[float] = None
    largo_corporal_cm: Optional[float] = None
    profundidad_toracica_cm: Optional[float] = None
    ancho_caderas_cm: Optional[float] = None
    perimetro_toracico_cm: Optional[float] = None
    longitud_grupa_cm: Optional[float] = None
    ancho_grupa_cm: Optional[float] = None
    bbox_lateral: Optional[List[float]] = None
    bbox_trasera: Optional[List[float]] = None
    keypoints: Optional[dict] = None


class MedicionCreate(BaseModel):
    animal_id: uuid.UUID
    notas: Optional[str] = None


class MedicionResponse(BaseModel):
    id: uuid.UUID
    animal_id: uuid.UUID
    peso_estimado_kg: float
    bcs: float
    confianza: Optional[float]
    img_lateral_url: Optional[str]
    img_trasera_url: Optional[str]
    morfometria: Optional[dict]
    modelo_version: Optional[str]
    procesado_por: Optional[str]
    error_estimacion: Optional[float]
    fecha_medicion: datetime
    notas: Optional[str]

    model_config = {"from_attributes": True}


class MedicionDetalle(MedicionResponse):
    animal: Optional[AnimalResponse] = None


# ════════════════════════════════════════════════════════
#  ANÁLISIS
# ════════════════════════════════════════════════════════

class AnalisisResultado(BaseModel):
    peso_estimado_kg: float
    bcs: float
    confianza: float
    confianza_peso: float
    confianza_bcs: float
    interpretacion_bcs: str
    recomendacion: str
    morfometria: MorfometriaData
    medicion_id: uuid.UUID
    procesado_en_segundos: float


# ════════════════════════════════════════════════════════
#  ESTADÍSTICAS
# ════════════════════════════════════════════════════════

class EstadisticasHato(BaseModel):
    total_animales: int
    peso_promedio_kg: Optional[float]
    bcs_promedio: Optional[float]
    total_mediciones: int
    ultima_medicion: Optional[datetime]
    animales_bajo_bcs: int
    animales_sobre_bcs: int


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


# ════════════════════════════════════════════════════════
#  REPORTE
# ════════════════════════════════════════════════════════

class ReporteCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    tipo: TipoReporte
    formato: FormatoReporte
    hato_id: Optional[uuid.UUID] = None
    animal_id: Optional[uuid.UUID] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None


class ReporteResponse(BaseModel):
    id: uuid.UUID
    titulo: str
    tipo: TipoReporte
    formato: FormatoReporte
    url_archivo: Optional[str]
    parametros: Optional[dict]
    fecha_generado: datetime
    generado_por_id: uuid.UUID
    hato_id: Optional[uuid.UUID]
    animal_id: Optional[uuid.UUID]

    model_config = {"from_attributes": True}


class ValidacionFotoOut(BaseModel):
    es_valida:           bool
    animal_detectado:    bool
    confianza_deteccion: float = Field(ge=0.0, le=1.0)
    area_cobertura:      float = Field(ge=0.0, le=1.0)
    posicion_correcta:   bool
    motivo:              str
    sugerencia:          str

    model_config = {"from_attributes": True}


class ValidacionParOut(BaseModel):
    lateral:    ValidacionFotoOut
    trasera:    ValidacionFotoOut
    par_valido: bool

    model_config = {"from_attributes": True}


# ════════════════════════════════════════════════════════
#  COMPARACIÓN CON FÓRMULAS MORFOMÉTRICAS
# ════════════════════════════════════════════════════════

class ComparacionRequest(BaseModel):
    """Medidas tomadas manualmente por el ganadero con cinta bovinométrica."""
    perimetro_toracico_cm: float = Field(gt=0, le=300)
    longitud_corporal_cm:  float = Field(gt=0, le=300)


class ComparacionResultado(BaseModel):
    medicion_id:             uuid.UUID
    peso_ia_kg:               float
    peso_schoorl_kg:          float
    peso_crevat_kg:           float
    diferencia_schoorl_kg:    float
    diferencia_schoorl_pct:   float
    diferencia_crevat_kg:     float
    diferencia_crevat_pct:    float
    perimetro_toracico_cm:    float
    longitud_corporal_cm:     float

    model_config = {"from_attributes": True}