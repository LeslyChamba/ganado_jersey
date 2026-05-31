"""
validacion_service.py  — v7.1 OpenCV + detección de silueta bovina
────────────────────────────────────────────────────────────────────
Sin modelo IA. Valida con OpenCV:
  - Brillo y nitidez de la imagen
  - Detección de silueta grande (animal real en el frame)
  - Ratio de aspecto del bounding box (lateral vs trasera)
  - Centrado horizontal (foto trasera)
  - Para lateral: verifica que el bbox sea horizontal (más ancho que alto)
  - Para trasera: verifica que el animal esté centrado
0 MB RAM extra, respuesta <150ms.
"""
import asyncio
import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Umbrales ──────────────────────────────────────────────
COBERTURA_MIN_LAT  = 0.18   # silueta ≥ 18% del frame (lateral)
COBERTURA_MIN_TRA  = 0.12   # silueta ≥ 12% del frame (trasera)
RATIO_LAT_MIN      = 1.05   # bbox más ancho que alto → vista lateral
CENTRO_TOL         = 0.35   # animal centrado ± 35% del centro (trasera)
BRILLO_MIN         = 25
BRILLO_MAX         = 245
NITIDEZ_MIN        = 35.0   # varianza laplaciana


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


def _bytes_a_array(b: bytes) -> np.ndarray:
    arr = np.frombuffer(b, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen.")
    return img


def _detectar_silueta(img: np.ndarray):
    """
    Detecta la silueta más grande de la imagen con OpenCV.
    Retorna (cobertura, ratio_bbox, centro_x_rel) o None si no hay silueta.
    """
    h, w  = img.shape[:2]
    gris  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Reducir ruido
    blur  = cv2.GaussianBlur(gris, (7, 7), 0)

    # Umbral adaptativo — funciona bien con distintas iluminaciones
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 8
    )

    # Morfología para unir partes del animal
    k1 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    cerrado = cv2.morphologyEx(thresh,  cv2.MORPH_CLOSE, k1)
    cerrado = cv2.morphologyEx(cerrado, cv2.MORPH_DILATE, k2)

    cnts, _ = cv2.findContours(cerrado, cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    # Contorno más grande — ignorar ruido pequeño (< 1% del frame)
    mayor = max(cnts, key=cv2.contourArea)
    area  = cv2.contourArea(mayor)
    if area < 0.01 * w * h:
        return None

    x, y, bw, bh = cv2.boundingRect(mayor)
    cobertura = area / (w * h)
    ratio     = bw / bh if bh > 0 else 1.0
    centro_x  = (x + bw / 2) / w   # 0=izquierda, 1=derecha, 0.5=centro

    return cobertura, ratio, centro_x


def _calidad_basica(img: np.ndarray, vista: str):
    """Verifica brillo y nitidez. Retorna (ok, motivo, sugerencia)."""
    gris    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brillo  = float(np.mean(gris))
    nitidez = float(cv2.Laplacian(gris, cv2.CV_64F).var())

    if brillo < BRILLO_MIN:
        return False, f"La foto {vista} está muy oscura (brillo {brillo:.0f}).", \
               "Toma la foto con luz natural difusa o en un lugar bien iluminado."
    if brillo > BRILLO_MAX:
        return False, f"La foto {vista} está sobreexpuesta (brillo {brillo:.0f}).", \
               "Evita apuntar el lente hacia fuentes de luz directa."
    if nitidez < NITIDEZ_MIN:
        return False, f"La foto {vista} está borrosa (nitidez {nitidez:.0f}).", \
               "Mantén el teléfono quieto y espera a que enfoque antes de tomar la foto."
    return True, "", ""


def _validar_lateral(img: np.ndarray) -> ResultadoFoto:
    # 1. Calidad básica
    ok, motivo, sug = _calidad_basica(img, "lateral")
    if not ok:
        return ResultadoFoto(False, False, 0.0, 0.0, False, motivo, sug)

    # 2. Detección de silueta
    sil = _detectar_silueta(img)
    if sil is None:
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "No se detectó un animal en la foto lateral.",
                             "Asegúrate de que la vaca esté completamente visible a 2-4 metros.")

    cobertura, ratio, centro_x = sil

    # 3. Cobertura mínima
    if cobertura < COBERTURA_MIN_LAT:
        return ResultadoFoto(False, True, 0.7, round(cobertura, 3), False,
                             f"La vaca ocupa muy poco del encuadre ({cobertura:.0%}).",
                             "Acércate más al animal o centra el encuadre.")

    # 4. Ratio — para perfil lateral el bbox debe ser más ancho que alto
    if ratio < RATIO_LAT_MIN:
        return ResultadoFoto(False, True, 0.7, round(cobertura, 3), False,
                             f"La foto no parece un perfil lateral (ratio ancho/alto = {ratio:.2f}).",
                             "Colócate exactamente de costado para capturar el perfil completo.")

    confianza = min(0.95, 0.60 + cobertura * 0.5 + (ratio - 1.0) * 0.1)
    return ResultadoFoto(True, True, round(confianza, 2), round(cobertura, 3), True,
                         f"Foto lateral apta (cobertura {cobertura:.0%}, ratio {ratio:.2f}).", "")


def _validar_trasera(img: np.ndarray) -> ResultadoFoto:
    # 1. Calidad básica
    ok, motivo, sug = _calidad_basica(img, "trasera")
    if not ok:
        return ResultadoFoto(False, False, 0.0, 0.0, False, motivo, sug)

    # 2. Detección de silueta
    sil = _detectar_silueta(img)
    if sil is None:
        return ResultadoFoto(False, False, 0.0, 0.0, False,
                             "No se detectó un animal en la foto trasera.",
                             "Colócate exactamente detrás de la vaca con la grupa centrada.")

    cobertura, ratio, centro_x = sil

    # 3. Cobertura mínima
    if cobertura < COBERTURA_MIN_TRA:
        return ResultadoFoto(False, True, 0.7, round(cobertura, 3), False,
                             f"La vaca ocupa muy poco del encuadre ({cobertura:.0%}).",
                             "Acércate más para que la grupa ocupe el frame.")

    # 4. Centrado — la silueta debe estar cerca del centro horizontal
    lim_inf = 0.5 - CENTRO_TOL
    lim_sup = 0.5 + CENTRO_TOL
    if not (lim_inf <= centro_x <= lim_sup):
        return ResultadoFoto(False, True, 0.7, round(cobertura, 3), False,
                             f"La vaca no está centrada horizontalmente ({centro_x:.0%} del ancho).",
                             "Centra la grupa en el encuadre y dispara desde atrás.")

    confianza = min(0.95, 0.60 + cobertura * 0.5)
    return ResultadoFoto(True, True, round(confianza, 2), round(cobertura, 3), True,
                         f"Foto trasera apta (cobertura {cobertura:.0%}, centrado {centro_x:.0%}).", "")


class ValidacionService:
    """Validación con OpenCV puro — 0 MB RAM extra, <150 ms."""

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