"""
validacion_service.py  — v7.0 OpenCV puro (sin modelo IA)
──────────────────────────────────────────────────────────
Valida encuadre usando solo OpenCV: detección de bordes, ratio,
área de silueta y centrado. 0 MB de RAM extra, respuesta <100ms.

Sin YOLO, sin ONNX, sin segment_anything.
El motor IA (MobileSAM + CNN + YOLO BCS) solo corre al estimar.
"""
import asyncio
import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Umbrales ──────────────────────────────────────────────
COBERTURA_LATERAL_MIN = 0.20   # silueta debe ocupar ≥ 20% del frame
COBERTURA_TRASERA_MIN = 0.15
RATIO_LATERAL_MIN     = 1.10   # imagen lateral debe ser más ancha que alta
BRILLO_MIN            = 30     # imagen no puede ser casi negra
BRILLO_MAX            = 240    # imagen no puede estar sobreexpuesta
NITIDEZ_MIN           = 40.0   # varianza laplaciana mínima (foto borrosa)


@dataclass
class ResultadoFoto:
    es_valida:           bool
    animal_detectado:    bool
    confianza_deteccion: float
    area_cobertura:      float
    posicion_correcta:   bool
    motivo:              str
    sugerencia:          str


@dataclass
class ResultadoPar:
    lateral:    ResultadoFoto
    trasera:    ResultadoFoto
    par_valido: bool


def _bytes_a_array(imagen_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(imagen_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen.")
    return img


def _analizar_imagen(img: np.ndarray) -> dict:
    """
    Extrae métricas básicas de la imagen con OpenCV puro.
    Retorna dict con brillo, nitidez, cobertura_silueta, ratio.
    """
    h, w   = img.shape[:2]
    gris   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Brillo promedio
    brillo = float(np.mean(gris))

    # Nitidez (varianza del laplaciano)
    nitidez = float(cv2.Laplacian(gris, cv2.CV_64F).var())

    # Silueta por umbral adaptativo + morfología
    blur     = cv2.GaussianBlur(gris, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    cerrado  = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    cnts, _ = cv2.findContours(cerrado, cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        mayor  = max(cnts, key=cv2.contourArea)
        area_c = cv2.contourArea(mayor)
        x, y, bw, bh = cv2.boundingRect(mayor)
        cobertura = area_c / (w * h)
        ratio_bbox = bw / bh if bh > 0 else 1.0
    else:
        cobertura  = 0.0
        ratio_bbox = 1.0

    return {
        "brillo":     brillo,
        "nitidez":    nitidez,
        "cobertura":  cobertura,
        "ratio_bbox": ratio_bbox,
        "h": h, "w": w,
    }


def _validar_lateral(img: np.ndarray) -> ResultadoFoto:
    try:
        m = _analizar_imagen(img)
    except Exception as e:
        logger.error("Error analizando foto lateral: %s", e)
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "Error al procesar la imagen.",
                             "Intenta con otra fotografía.")

    # Brillo
    if m["brillo"] < BRILLO_MIN:
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "La foto lateral está muy oscura.",
                             "Toma la foto con mejor iluminación natural.")
    if m["brillo"] > BRILLO_MAX:
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "La foto lateral está sobreexpuesta.",
                             "Evita la luz directa al lente. Busca sombra difusa.")

    # Nitidez
    if m["nitidez"] < NITIDEZ_MIN:
        return ResultadoFoto(False, False, 0.0, round(m["cobertura"], 3), False,
                             "La foto lateral está borrosa.",
                             "Mantén el teléfono quieto y enfoca antes de disparar.")

    # Cobertura
    if m["cobertura"] < COBERTURA_LATERAL_MIN:
        return ResultadoFoto(False, True, 0.8, round(m["cobertura"], 3), False,
                             f"La vaca ocupa muy poco del encuadre ({m['cobertura']:.0%}).",
                             "Acércate más al animal o centra el encuadre.")

    # Ratio — foto lateral debe ser más ancha que alta
    if m["ratio_bbox"] < RATIO_LATERAL_MIN:
        return ResultadoFoto(False, True, 0.8, round(m["cobertura"], 3), False,
                             f"La foto no parece un perfil lateral (ratio {m['ratio_bbox']:.2f}).",
                             "Colócate exactamente de costado para capturar el perfil completo.")

    return ResultadoFoto(True, True, 0.9, round(m["cobertura"], 3), True,
                         "Foto lateral apta.", "")


def _validar_trasera(img: np.ndarray) -> ResultadoFoto:
    try:
        m = _analizar_imagen(img)
    except Exception as e:
        logger.error("Error analizando foto trasera: %s", e)
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "Error al procesar la imagen.",
                             "Intenta con otra fotografía.")

    # Brillo
    if m["brillo"] < BRILLO_MIN:
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "La foto trasera está muy oscura.",
                             "Toma la foto con mejor iluminación natural.")
    if m["brillo"] > BRILLO_MAX:
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "La foto trasera está sobreexpuesta.",
                             "Evita la luz directa al lente.")

    # Nitidez
    if m["nitidez"] < NITIDEZ_MIN:
        return ResultadoFoto(False, False, 0.0, round(m["cobertura"], 3), False,
                             "La foto trasera está borrosa.",
                             "Mantén el teléfono quieto y enfoca antes de disparar.")

    # Cobertura
    if m["cobertura"] < COBERTURA_TRASERA_MIN:
        return ResultadoFoto(False, True, 0.8, round(m["cobertura"], 3), False,
                             f"La vaca ocupa muy poco del encuadre ({m['cobertura']:.0%}).",
                             "Acércate más para que la grupa ocupe el frame.")

    return ResultadoFoto(True, True, 0.9, round(m["cobertura"], 3), True,
                         "Foto trasera apta.", "")


class ValidacionService:
    """
    Validación de encuadre con OpenCV puro.
    No carga ningún modelo de IA — 0 MB de RAM extra, <100 ms.
    """

    @staticmethod
    def _bytes_a_array(imagen_bytes: bytes) -> np.ndarray:
        return _bytes_a_array(imagen_bytes)

    async def validar_par(
        self,
        bytes_lateral: bytes,
        bytes_trasera: bytes,
    ) -> ResultadoPar:
        loop    = asyncio.get_event_loop()
        img_lat = _bytes_a_array(bytes_lateral)
        img_tra = _bytes_a_array(bytes_trasera)

        def procesar():
            return _validar_lateral(img_lat), _validar_trasera(img_tra)

        res_lat, res_tra = await loop.run_in_executor(None, procesar)

        return ResultadoPar(
            lateral    = res_lat,
            trasera    = res_tra,
            par_valido = res_lat.es_valida and res_tra.es_valida,
        )


validacion_service = ValidacionService()