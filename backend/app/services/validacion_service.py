"""
validacion_service.py
─────────────────────
Servicio LIGERO de pre-validación de imágenes.
Usa el modelo estándar de YOLOv8n enfocado SOLO en la clase 19 (vaca)
para verificar encuadre, cobertura y posición antes del pipeline pesado.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# ── Umbrales de validación ────────────────────────────────────────────────────
CONF_DETECCION_MIN  = 0.45   # confianza mínima YOLOv8 para aceptar detección
COBERTURA_LATERAL   = 0.25   # el animal debe ocupar ≥ 25 % del área de la imagen
COBERTURA_TRASERA   = 0.20   # el animal debe ocupar ≥ 20 % del área de la imagen
RATIO_LATERAL_MIN   = 1.15   # bbox debe ser más ancho que alto (vista perfil)
CENTRO_TOLERANCIA   = 0.30   # eje X del bbox debe estar entre 35 % y 65 % (trasera)

# ── Ruta al modelo de detección genérico ──────────────────────────────────────
# YOLO descargará automáticamente este modelo ultraligero la primera vez
_MODEL_PATH = "yolov8n.pt"


@dataclass
class ResultadoFoto:
    """Resultado de la validación de UNA foto."""
    es_valida:           bool
    animal_detectado:    bool
    confianza_deteccion: float   # 0-1
    area_cobertura:      float   # 0-1  (proporción del área de la imagen)
    posicion_correcta:   bool
    motivo:              str     # mensaje corto para mostrar en UI
    sugerencia:          str     # qué hacer si falla


@dataclass
class ResultadoPar:
    """Resultado de la validación del PAR de fotos (lateral + trasera)."""
    lateral:    ResultadoFoto
    trasera:    ResultadoFoto
    par_valido: bool             # True solo si AMBAS son válidas


class ValidacionService:
    """Servicio singleton de pre-validación de imágenes."""

    def __init__(self):
        self._modelo: YOLO | None = None

    # ── Carga perezosa del modelo ─────────────────────────────────────────────
    def _cargar_modelo(self) -> YOLO:
        if self._modelo is None:
            logger.info("Cargando modelo YOLOv8 estándar para validación de encuadre…")
            self._modelo = YOLO(_MODEL_PATH)
            # Nota: NO usamos .fuse() aquí para evitar el bug con clases/segmentos
        return self._modelo

    # ── Decodificar bytes → numpy array ──────────────────────────────────────
    @staticmethod
    def _bytes_a_array(imagen_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(imagen_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("No se pudo decodificar la imagen.")
        return img

    # ── Inferencia YOLOv8 (síncrona, se llama en executor) ───────────────────
    def _inferir(self, img: np.ndarray):
        modelo = self._cargar_modelo()
        # imgsz=640 es suficiente para detección; verbose=False evita logs
        # classes=[19] obliga a YOLO a buscar ÚNICAMENTE vacas (cow)
        resultados = modelo.predict(img, imgsz=640, conf=0.25, classes=[19], verbose=False)
        return resultados[0]

    # ── Extraer la detección de vaca con mayor confianza ─────────────────────
    @staticmethod
    def _mejor_deteccion(resultado):
        """
        Devuelve (conf, x1, y1, x2, y2) de la caja con mayor confianza,
        o None si no hay detecciones.
        """
        boxes = resultado.boxes
        if boxes is None or len(boxes) == 0:
            return None

        confs  = boxes.conf.cpu().numpy()
        xyxys  = boxes.xyxy.cpu().numpy()

        idx_max = int(np.argmax(confs))
        conf    = float(confs[idx_max])
        x1, y1, x2, y2 = xyxys[idx_max]
        
        return conf, float(x1), float(y1), float(x2), float(y2)

    # ── Validar foto lateral ──────────────────────────────────────────────────
    def _validar_lateral(self, img: np.ndarray) -> ResultadoFoto:
        h_img, w_img = img.shape[:2]
        area_img     = h_img * w_img

        try:
            resultado = self._inferir(img)
        except Exception as e:
            logger.error("Error en inferencia lateral: %s", e)
            return ResultadoFoto(
                es_valida=False, animal_detectado=False,
                confianza_deteccion=0.0, area_cobertura=0.0,
                posicion_correcta=False,
                motivo="Error interno al analizar la imagen.",
                sugerencia="Intenta nuevamente con otra fotografía."
            )

        det = self._mejor_deteccion(resultado)

        # ── Sin detección ────────────────────────────────────────────────────
        if det is None or det[0] < CONF_DETECCION_MIN:
            conf = det[0] if det else 0.0
            return ResultadoFoto(
                es_valida=False, animal_detectado=False,
                confianza_deteccion=round(conf, 3), area_cobertura=0.0,
                posicion_correcta=False,
                motivo=f"No se detectó un bovino en la foto lateral (confianza {conf:.0%}).",
                sugerencia="Asegúrate de que la vaca esté completamente visible de perfil, a 2-4 metros de distancia."
            )

        conf, x1, y1, x2, y2 = det
        ancho_bbox  = x2 - x1
        alto_bbox   = y2 - y1
        area_bbox   = ancho_bbox * alto_bbox
        cobertura   = area_bbox / area_img
        ratio       = ancho_bbox / alto_bbox if alto_bbox > 0 else 0

        # ── Cobertura insuficiente ───────────────────────────────────────────
        if cobertura < COBERTURA_LATERAL:
            return ResultadoFoto(
                es_valida=False, animal_detectado=True,
                confianza_deteccion=round(conf, 3),
                area_cobertura=round(cobertura, 3),
                posicion_correcta=False,
                motivo=f"La vaca ocupa solo el {cobertura:.0%} de la imagen (mínimo {COBERTURA_LATERAL:.0%}).",
                sugerencia="Acércate más al animal o centra el encuadre para que llene el frame."
            )

        # ── Relación de aspecto incorrecta (no es vista lateral) ────────────
        if ratio < RATIO_LATERAL_MIN:
            return ResultadoFoto(
                es_valida=False, animal_detectado=True,
                confianza_deteccion=round(conf, 3),
                area_cobertura=round(cobertura, 3),
                posicion_correcta=False,
                motivo=f"La postura no parece ser un perfil lateral (ratio {ratio:.2f}).",
                sugerencia="Colócate exactamente de costado a la vaca para capturar el perfil completo."
            )

        # ── VÁLIDA ───────────────────────────────────────────────────────────
        return ResultadoFoto(
            es_valida=True, animal_detectado=True,
            confianza_deteccion=round(conf, 3),
            area_cobertura=round(cobertura, 3),
            posicion_correcta=True,
            motivo=f"Foto lateral apta (confianza {conf:.0%}, cobertura {cobertura:.0%}).",
            sugerencia=""
        )

    # ── Validar foto trasera ──────────────────────────────────────────────────
    def _validar_trasera(self, img: np.ndarray) -> ResultadoFoto:
        h_img, w_img = img.shape[:2]
        area_img     = h_img * w_img

        try:
            resultado = self._inferir(img)
        except Exception as e:
            logger.error("Error en inferencia trasera: %s", e)
            return ResultadoFoto(
                es_valida=False, animal_detectado=False,
                confianza_deteccion=0.0, area_cobertura=0.0,
                posicion_correcta=False,
                motivo="Error interno al analizar la imagen.",
                sugerencia="Intenta nuevamente con otra fotografía."
            )

        det = self._mejor_deteccion(resultado)

        # ── Sin detección ────────────────────────────────────────────────────
        if det is None or det[0] < CONF_DETECCION_MIN:
            conf = det[0] if det else 0.0
            return ResultadoFoto(
                es_valida=False, animal_detectado=False,
                confianza_deteccion=round(conf, 3), area_cobertura=0.0,
                posicion_correcta=False,
                motivo=f"No se detectó un bovino en la foto trasera (confianza {conf:.0%}).",
                sugerencia="Colócate exactamente detrás de la vaca con la grupa centrada en el encuadre."
            )

        conf, x1, y1, x2, y2 = det
        ancho_bbox  = x2 - x1
        alto_bbox   = y2 - y1
        area_bbox   = ancho_bbox * alto_bbox
        cobertura   = area_bbox / area_img

        # Centro horizontal del bbox relativo al ancho de la imagen (0-1)
        centro_x    = ((x1 + x2) / 2) / w_img

        # ── Cobertura insuficiente ───────────────────────────────────────────
        if cobertura < COBERTURA_TRASERA:
            return ResultadoFoto(
                es_valida=False, animal_detectado=True,
                confianza_deteccion=round(conf, 3),
                area_cobertura=round(cobertura, 3),
                posicion_correcta=False,
                motivo=f"La vaca ocupa solo el {cobertura:.0%} de la imagen (mínimo {COBERTURA_TRASERA:.0%}).",
                sugerencia="Acércate más al animal o centra el encuadre para que la grupa ocupe el frame."
            )

        # ── Animal no centrado (sugiere que no es vista trasera) ────────────
        limite_inf = 0.5 - CENTRO_TOLERANCIA   # 0.20
        limite_sup = 0.5 + CENTRO_TOLERANCIA   # 0.80
        if not (limite_inf <= centro_x <= limite_sup):
            return ResultadoFoto(
                es_valida=False, animal_detectado=True,
                confianza_deteccion=round(conf, 3),
                area_cobertura=round(cobertura, 3),
                posicion_correcta=False,
                motivo=f"La vaca no está centrada en la foto trasera (posición horizontal {centro_x:.0%}).",
                sugerencia="Centra la grupa de la vaca en el encuadre y dispara desde atrás."
            )

        # ── VÁLIDA ───────────────────────────────────────────────────────────
        return ResultadoFoto(
            es_valida=True, animal_detectado=True,
            confianza_deteccion=round(conf, 3),
            area_cobertura=round(cobertura, 3),
            posicion_correcta=True,
            motivo=f"Foto trasera apta (confianza {conf:.0%}, cobertura {cobertura:.0%}).",
            sugerencia=""
        )

    # ── Método público: valida el par (llamado desde el endpoint) ─────────────
    # ── Método público: valida el par (llamado desde el endpoint) ─────────────
    async def validar_par(
        self,
        bytes_lateral: bytes,
        bytes_trasera: bytes,
    ) -> ResultadoPar:
        """
        Valida las dos fotos secuencialmente en un solo hilo
        para evitar colisiones de memoria en el modelo YOLOv8.
        """
        loop = asyncio.get_event_loop()

        img_lateral = self._bytes_a_array(bytes_lateral)
        img_trasera = self._bytes_a_array(bytes_trasera)

        # Función interna para procesar una tras otra sin pelear por el modelo
        def procesar_secuencial():
            res_lat = self._validar_lateral(img_lateral)
            res_tra = self._validar_trasera(img_trasera)
            return res_lat, res_tra

        # Ejecutamos la tarea (no bloquea FastAPI, pero ejecuta secuencialmente)
        resultado_lateral, resultado_trasera = await loop.run_in_executor(None, procesar_secuencial)

        par_valido = resultado_lateral.es_valida and resultado_trasera.es_valida

        return ResultadoPar(
            lateral    = resultado_lateral,
            trasera    = resultado_trasera,
            par_valido = par_valido,
        )

# ── Singleton exportado ───────────────────────────────────────────────────────
validacion_service = ValidacionService()