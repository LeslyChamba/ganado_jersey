"""
validacion_service.py  — versión ONNX (bajo consumo de RAM)
─────────────────────────────────────────────────────────────
Usa onnxruntime en vez de ultralytics YOLO (~20 MB vs ~80 MB RAM).
Detecta vacas (clase 19 COCO) con yolov8n.onnx para pre-validar encuadre.
El modelo .onnx se exporta automáticamente si no existe.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Umbrales ──────────────────────────────────────────────
CONF_DETECCION_MIN = 0.45
COBERTURA_LATERAL  = 0.25
COBERTURA_TRASERA  = 0.20
RATIO_LATERAL_MIN  = 1.15
CENTRO_TOLERANCIA  = 0.30
CLASE_VACA         = 19        # índice COCO para "cow"

_MODEL_PATH = Path("yolov8n.onnx")
_IMG_SIZE   = 640


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


# ── Pre/post procesado YOLOv8 ONNX ───────────────────────
def _preprocesar(img_bgr: np.ndarray, size: int = _IMG_SIZE):
    h, w    = img_bgr.shape[:2]
    escala  = size / max(h, w)
    nw, nh  = int(w * escala), int(h * escala)
    resized = cv2.resize(img_bgr, (nw, nh))
    canvas  = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[:nh, :nw] = resized
    pad_w = (size - nw) / 2
    pad_h = (size - nh) / 2
    tensor = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return tensor[np.newaxis], escala, pad_w, pad_h, w, h


def _postprocesar(output, escala, pad_w, pad_h, orig_w, orig_h, conf_umbral=0.25):
    preds = output[0]
    if preds.shape[0] == 84:
        preds = preds.T
    cx, cy, bw, bh = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
    cls_scores = preds[:, 4:]
    cls_ids    = cls_scores.argmax(axis=1)
    confs      = cls_scores.max(axis=1)
    mask = confs >= conf_umbral
    if not mask.any():
        return []
    cx, cy, bw, bh = cx[mask], cy[mask], bw[mask], bh[mask]
    confs   = confs[mask]
    cls_ids = cls_ids[mask]
    x1 = ((cx - bw/2 - pad_w) / escala).clip(0, orig_w)
    x2 = ((cx + bw/2 - pad_w) / escala).clip(0, orig_w)
    y1 = ((cy - bh/2 - pad_h) / escala).clip(0, orig_h)
    y2 = ((cy + bh/2 - pad_h) / escala).clip(0, orig_h)
    return _nms(list(zip(confs, x1, y1, x2, y2, cls_ids)))


def _nms(dets, iou_thresh=0.45):
    if not dets:
        return []
    dets = sorted(dets, key=lambda d: d[0], reverse=True)
    resultado = []
    while dets:
        best = dets.pop(0)
        resultado.append(best)
        dets = [d for d in dets if _iou(best, d) < iou_thresh]
    return resultado


def _iou(a, b):
    ix1, iy1 = max(a[1], b[1]), max(a[2], b[2])
    ix2, iy2 = min(a[3], b[3]), min(a[4], b[4])
    inter = max(0, ix2-ix1) * max(0, iy2-iy1)
    ua = (a[3]-a[1])*(a[4]-a[2]) + (b[3]-b[1])*(b[4]-b[2]) - inter
    return inter / ua if ua > 0 else 0.0


# ── Servicio ──────────────────────────────────────────────
class ValidacionService:

    def __init__(self):
        self._session     = None
        self._input_name  = None

    def _cargar_modelo(self):
        if self._session is not None:
            return self._session
        try:
            import onnxruntime as ort

            if not _MODEL_PATH.exists():
                logger.info("Exportando yolov8n.onnx desde ultralytics…")
                from ultralytics import YOLO
                YOLO("yolov8n.pt").export(format="onnx", imgsz=640, simplify=True)

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            self._session    = ort.InferenceSession(
                str(_MODEL_PATH),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            logger.info("yolov8n.onnx cargado con onnxruntime (~20 MB RAM)")
        except Exception as e:
            logger.error("No se pudo cargar yolov8n.onnx: %s", e)
            self._session = None
        return self._session

    @staticmethod
    def _bytes_a_array(imagen_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(imagen_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("No se pudo decodificar la imagen.")
        return img

    def _detectar_vaca(self, img: np.ndarray):
        session = self._cargar_modelo()
        if session is None:
            return None
        tensor, escala, pw, ph, ow, oh = _preprocesar(img)
        output = session.run(None, {self._input_name: tensor})
        dets   = _postprocesar(output[0], escala, pw, ph, ow, oh)
        vacas  = [(c, x1, y1, x2, y2)
                  for c, x1, y1, x2, y2, cls in dets
                  if int(cls) == CLASE_VACA]
        return max(vacas, key=lambda d: d[0]) if vacas else None

    def _validar_lateral(self, img: np.ndarray) -> ResultadoFoto:
        h_img, w_img = img.shape[:2]
        area_img     = h_img * w_img
        try:
            det = self._detectar_vaca(img)
        except Exception as e:
            logger.error("Error inferencia lateral: %s", e)
            return ResultadoFoto(False, False, 0.0, 0.0, False,
                                 "Error interno al analizar la imagen.",
                                 "Intenta nuevamente con otra fotografía.")

        if det is None or det[0] < CONF_DETECCION_MIN:
            conf = det[0] if det else 0.0
            return ResultadoFoto(False, False, round(conf, 3), 0.0, False,
                                 f"No se detectó un bovino en la foto lateral (confianza {conf:.0%}).",
                                 "Asegúrate de que la vaca esté completamente visible de perfil, a 2-4 metros.")

        conf, x1, y1, x2, y2 = det
        ancho     = x2 - x1
        alto      = y2 - y1
        cobertura = (ancho * alto) / area_img
        ratio     = ancho / alto if alto > 0 else 0

        if cobertura < COBERTURA_LATERAL:
            return ResultadoFoto(False, True, round(conf, 3), round(cobertura, 3), False,
                                 f"La vaca ocupa solo el {cobertura:.0%} (mínimo {COBERTURA_LATERAL:.0%}).",
                                 "Acércate más o centra el encuadre.")
        if ratio < RATIO_LATERAL_MIN:
            return ResultadoFoto(False, True, round(conf, 3), round(cobertura, 3), False,
                                 f"La postura no parece perfil lateral (ratio {ratio:.2f}).",
                                 "Colócate exactamente de costado para capturar el perfil completo.")

        return ResultadoFoto(True, True, round(conf, 3), round(cobertura, 3), True,
                             f"Foto lateral apta (confianza {conf:.0%}, cobertura {cobertura:.0%}).", "")

    def _validar_trasera(self, img: np.ndarray) -> ResultadoFoto:
        h_img, w_img = img.shape[:2]
        area_img     = h_img * w_img
        try:
            det = self._detectar_vaca(img)
        except Exception as e:
            logger.error("Error inferencia trasera: %s", e)
            return ResultadoFoto(False, False, 0.0, 0.0, False,
                                 "Error interno al analizar la imagen.",
                                 "Intenta nuevamente con otra fotografía.")

        if det is None or det[0] < CONF_DETECCION_MIN:
            conf = det[0] if det else 0.0
            return ResultadoFoto(False, False, round(conf, 3), 0.0, False,
                                 f"No se detectó un bovino en la foto trasera (confianza {conf:.0%}).",
                                 "Colócate exactamente detrás de la vaca con la grupa centrada.")

        conf, x1, y1, x2, y2 = det
        ancho     = x2 - x1
        alto      = y2 - y1
        cobertura = (ancho * alto) / area_img
        centro_x  = ((x1 + x2) / 2) / w_img

        if cobertura < COBERTURA_TRASERA:
            return ResultadoFoto(False, True, round(conf, 3), round(cobertura, 3), False,
                                 f"La vaca ocupa solo el {cobertura:.0%} (mínimo {COBERTURA_TRASERA:.0%}).",
                                 "Acércate más para que la grupa ocupe el frame.")

        lim_inf = 0.5 - CENTRO_TOLERANCIA
        lim_sup = 0.5 + CENTRO_TOLERANCIA
        if not (lim_inf <= centro_x <= lim_sup):
            return ResultadoFoto(False, True, round(conf, 3), round(cobertura, 3), False,
                                 f"La vaca no está centrada (posición horizontal {centro_x:.0%}).",
                                 "Centra la grupa en el encuadre y dispara desde atrás.")

        return ResultadoFoto(True, True, round(conf, 3), round(cobertura, 3), True,
                             f"Foto trasera apta (confianza {conf:.0%}, cobertura {cobertura:.0%}).", "")

    async def validar_par(self, bytes_lateral: bytes, bytes_trasera: bytes) -> ResultadoPar:
        loop    = asyncio.get_event_loop()
        img_lat = self._bytes_a_array(bytes_lateral)
        img_tra = self._bytes_a_array(bytes_trasera)

        def procesar():
            return self._validar_lateral(img_lat), self._validar_trasera(img_tra)

        res_lat, res_tra = await loop.run_in_executor(None, procesar)
        return ResultadoPar(
            lateral    = res_lat,
            trasera    = res_tra,
            par_valido = res_lat.es_valida and res_tra.es_valida,
        )


validacion_service = ValidacionService()