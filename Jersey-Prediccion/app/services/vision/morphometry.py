# app/services/vision/morphometry.py
"""
MÓDULO DE VISIÓN COMPUTACIONAL — BovineAI
==========================================
Pipeline completo sin barra de referencia:

  Escala → altura promedio raza Jersey (123 cm)
           detectada desde la propia silueta segmentada

  1. Segmentar silueta del bovino (GrabCut + morfología)
  2. Medir altura de la silueta en píxeles
  3. Calcular factor px/cm usando altura promedio Jersey
  4. Extraer lc, pt, altura_cruz, ancho_cadera en cm reales
  5. Calcular features normalizadas para XGBoost

Protocolo de foto requerido:
  - Vista lateral completa (izquierda o derecha)
  - El animal ocupa al menos 50% del alto del frame
  - El cuerpo completo es visible (de pezuñas a lomo)
"""

import cv2
import numpy as np
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# CONSTANTES DE RAZA JERSEY
# Fuente: estándares zootécnicos raza Jersey adulta
# ══════════════════════════════════════════════════════════

JERSEY_ALTURA_PROMEDIO_CM  = 123.0   # altura a la cruz promedio (cm)
JERSEY_ALTURA_MIN_CM       = 112.0   # mínimo esperable en adultas
JERSEY_ALTURA_MAX_CM       = 135.0   # máximo esperable en adultas

# Fracción del alto de imagen que ocupa la vaca en una foto bien tomada
# (cuerpo completo, del suelo al lomo, con pequeño margen arriba/abajo)
ANIMAL_FRAME_FRACTION      = 0.72    # ajusta si tus fotos tienen más/menos margen


# ══════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════

@dataclass
class ScaleResult:
    pixels_per_cm: float      # factor de conversión px → cm
    animal_height_px: float   # altura de la silueta en píxeles
    assumed_height_cm: float  # altura real asumida (JERSEY_ALTURA_PROMEDIO_CM)
    method: str               # siempre "jersey_average_height"
    warning: str              # mensaje de advertencia si aplica


@dataclass
class MorphometryResult:
    # ── Medidas en centímetros ──────────────────────────
    largo_corporal_cm: float
    altura_cruz_cm: float
    perimetro_toracico_cm: float
    ancho_cadera_cm: float

    # ── Features normalizadas para XGBoost ─────────────
    area_norm: float       # área silueta / área total imagen
    ratio_lh: float        # largo_px / alto_px  (forma del animal)
    perimeter_norm: float  # perímetro_px / alto_px

    # ── Metadatos de calidad ────────────────────────────
    pixels_per_cm: float
    confidence: float      # 0–1  (qué tan limpia fue la segmentación)
    scale_warning: str     # vacío si todo bien
    debug_image: np.ndarray


# ══════════════════════════════════════════════════════════
# 1. CÁLCULO DE ESCALA — altura promedio Jersey
# ══════════════════════════════════════════════════════════

def estimate_scale_from_breed(
    animal_height_px: float,
    assumed_height_cm: float = JERSEY_ALTURA_PROMEDIO_CM,
) -> ScaleResult:
    """
    Calcula píxeles/cm usando la altura promedio de la raza Jersey.

    La lógica es directa:
        px_per_cm = altura_silueta_px / altura_promedio_jersey_cm

    El error máximo esperado es ±4% porque la variación natural
    de altura en Jersey adultas es ±5 cm sobre 123 cm.

    Parámetros:
        animal_height_px:   altura de la silueta en píxeles
                            (medida desde pezuñas hasta el lomo)
        assumed_height_cm:  altura real asumida (default: 123 cm Jersey)
    """
    if animal_height_px <= 0:
        # Caso extremo: silueta no detectada, fallback por tamaño de imagen
        logger.error("Altura de silueta = 0. La segmentación falló.")
        return ScaleResult(
            pixels_per_cm=1.0,
            animal_height_px=0.0,
            assumed_height_cm=assumed_height_cm,
            method="jersey_average_height",
            warning="SEGMENTACIÓN FALLIDA — medidas no confiables",
        )

    px_per_cm = animal_height_px / assumed_height_cm

    # Verificar que el resultado es plausible
    # (una imagen típica de 1080px con vaca bien encuadrada → ~6–9 px/cm)
    warning = ""
    if px_per_cm < 2.0:
        warning = (
            "Escala muy baja (vaca muy pequeña en frame). "
            "La vaca debe ocupar al menos 50% del alto de la imagen."
        )
    elif px_per_cm > 20.0:
        warning = (
            "Escala muy alta (vaca demasiado cerca). "
            "Asegúrate de que el cuerpo completo sea visible."
        )

    if warning:
        logger.warning(f"Escala fuera de rango: {px_per_cm:.2f} px/cm — {warning}")

    return ScaleResult(
        pixels_per_cm=round(px_per_cm, 4),
        animal_height_px=round(animal_height_px, 1),
        assumed_height_cm=assumed_height_cm,
        method="jersey_average_height",
        warning=warning,
    )


# ══════════════════════════════════════════════════════════
# 2. SEGMENTACIÓN DE SILUETA BOVINA
# ══════════════════════════════════════════════════════════

def segment_animal(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Segmenta la silueta del bovino.
    Estrategia en cascada:
        1. GrabCut (más preciso, requiere contraste animal/fondo)
        2. Umbral adaptativo Otsu (fallback robusto)
        3. Bounding box completo (último recurso)

    Retorna:
        mask:    uint8 (0/255), máscara binaria de la silueta
        contour: contorno principal del animal
    """
    h, w = image.shape[:2]

    # ── GrabCut con ROI central ──────────────────────────────────────────
    # Margen: excluye bordes donde suele estar el fondo
    mx, my = int(w * 0.07), int(h * 0.07)
    rect = (mx, my, w - 2 * mx, h - 2 * my)

    mask_gc = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(image, mask_gc, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        mask_bin = np.where((mask_gc == 2) | (mask_gc == 0), 0, 255).astype(np.uint8)
        # Verificar que GrabCut encontró algo razonable (>5% de píxeles)
        if mask_bin.sum() / 255 < (h * w * 0.05):
            raise ValueError("GrabCut produjo máscara vacía")
    except Exception as e:
        logger.warning(f"GrabCut falló ({e}). Usando Otsu.")
        mask_bin = _otsu_segmentation(image)

    # ── Limpieza morfológica ──────────────────────────────────────────────
    # close: une partes del cuerpo separadas por el pelaje o sombras
    # open:  elimina ruido pequeño del fondo
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k_close)
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_OPEN,  k_open)

    # ── Contorno más grande = el animal ──────────────────────────────────
    contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.warning("Sin contornos. Usando imagen completa como fallback.")
        fallback = np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]])
        return mask_bin, fallback

    main_contour = max(contours, key=cv2.contourArea)

    # Máscara limpia: solo el contorno principal relleno
    mask_clean = np.zeros((h, w), np.uint8)
    cv2.drawContours(mask_clean, [main_contour], -1, 255, -1)

    return mask_clean, main_contour


def _otsu_segmentation(image: np.ndarray) -> np.ndarray:
    """Segmentación por umbral de Otsu — más robusta que GrabCut en fondos complejos."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (25, 25), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return thresh


# ══════════════════════════════════════════════════════════
# 3. EXTRACCIÓN DE MEDIDAS MORFOMÉTRICAS
# ══════════════════════════════════════════════════════════

def extract_morphometrics(
    image: np.ndarray,
    mask: np.ndarray,
    contour: np.ndarray,
) -> MorphometryResult:
    """
    Extrae medidas morfométricas desde la máscara segmentada.

    Paso 1: mide la altura de la silueta en px
    Paso 2: calcula escala usando altura promedio Jersey
    Paso 3: mide lc, pt, cadera en px → convierte a cm

    Anatomía de referencia (vista lateral):
        ┌────────────────── lomo ───────────────────┐
        │  cuello  │   tórax   │   lomo   │  grupa  │
        │  20-35%  │  35-55%   │  55-75%  │  75-90% │
        └──────────────────── vientre ──────────────┘
    """
    h_img, w_img = image.shape[:2]
    x, y, bw, bh = cv2.boundingRect(contour)

    # ── Paso 1: altura de la silueta ─────────────────────────────────────
    # Usamos la altura máxima del contorno en la zona del lomo (20–60% del largo)
    # que corresponde aproximadamente a la altura a la cruz
    x1_lomo = x + int(bw * 0.20)
    x2_lomo = x + int(bw * 0.60)
    altura_silueta_px, _ = _max_height_in_range(mask, x1_lomo, x2_lomo)

    # Si la silueta es muy pequeña, usar el bounding box completo
    if altura_silueta_px < bh * 0.5:
        altura_silueta_px = float(bh)

    # ── Paso 2: escala desde altura Jersey ───────────────────────────────
    scale = estimate_scale_from_breed(altura_silueta_px)
    px = scale.pixels_per_cm

    # ── Paso 3: medidas en cm ─────────────────────────────────────────────

    # Largo corporal: ancho del bounding box
    lc_px  = float(bw)
    lc_cm  = lc_px / px

    # Altura a la cruz: altura máxima en zona del lomo anterior
    altura_cruz_cm = altura_silueta_px / px  # ≈ JERSEY_ALTURA_PROMEDIO_CM por diseño

    # Perímetro torácico: sección transversal estimada en zona pectoral (~30% del largo)
    x_pecho         = x + int(bw * 0.30)
    chest_height_px = _column_height(mask, x_pecho)
    y_mid_pecho     = y + int(bh * 0.45)
    chest_depth_px  = _row_width_at(mask, y_mid_pecho)

    # Aproximación elíptica del perímetro torácico
    # Fórmula de Ramanujan para perímetro de elipse
    a = chest_height_px / 2.0   # semi-eje vertical (alto del pecho)
    b = chest_depth_px  / 2.0   # semi-eje horizontal (profundidad del pecho)
    pt_px = np.pi * (3*(a+b) - np.sqrt((3*a + b)*(a + 3*b)))
    pt_cm = pt_px / px

    # Ancho de cadera: altura de la silueta en zona coxal (~77% del largo)
    x_cadera        = x + int(bw * 0.77)
    cadera_height_px = _column_height(mask, x_cadera)
    ancho_cadera_cm  = cadera_height_px / px

    # ── Features normalizadas para XGBoost ───────────────────────────────
    total_area    = float(cv2.contourArea(contour))
    bbox_area     = float(bw * bh) if bw * bh > 0 else 1.0
    area_norm     = total_area / float(w_img * h_img)
    ratio_lh      = lc_px / float(bh) if bh > 0 else 1.0
    perimeter_px  = float(cv2.arcLength(contour, True))
    perimeter_norm = perimeter_px / float(bh) if bh > 0 else 1.0

    # ── Confianza de segmentación ─────────────────────────────────────────
    # Qué fracción del bounding box ocupa la silueta (bien segmentado → 65–85%)
    fill_ratio = total_area / bbox_area if bbox_area > 0 else 0.0
    confidence = float(np.clip(fill_ratio, 0.0, 1.0))

    # ── Imagen de debug ───────────────────────────────────────────────────
    debug_img = _draw_annotations(
        image.copy(), mask, contour, scale,
        lc_px, altura_silueta_px, chest_height_px,
        x, y, bw, bh, x_pecho, x_cadera,
    )

    return MorphometryResult(
        largo_corporal_cm    = round(lc_cm,           1),
        altura_cruz_cm       = round(altura_cruz_cm,  1),
        perimetro_toracico_cm= round(pt_cm,           1),
        ancho_cadera_cm      = round(ancho_cadera_cm, 1),
        area_norm            = round(area_norm,        5),
        ratio_lh             = round(ratio_lh,         4),
        perimeter_norm       = round(perimeter_norm,   4),
        pixels_per_cm        = round(px,               4),
        confidence           = round(confidence,       3),
        scale_warning        = scale.warning,
        debug_image          = debug_img,
    )


# ══════════════════════════════════════════════════════════
# HELPERS DE MEDICIÓN
# ══════════════════════════════════════════════════════════

def _column_height(mask: np.ndarray, x: int) -> float:
    """Altura de la silueta (en px) en la columna vertical x."""
    x = int(np.clip(x, 0, mask.shape[1] - 1))
    ys = np.where(mask[:, x] > 0)[0]
    return float(ys[-1] - ys[0]) if len(ys) >= 2 else 0.0


def _row_width_at(mask: np.ndarray, y: int) -> float:
    """Ancho de la silueta (en px) en la fila horizontal y."""
    y = int(np.clip(y, 0, mask.shape[0] - 1))
    xs = np.where(mask[y, :] > 0)[0]
    return float(xs[-1] - xs[0]) if len(xs) >= 2 else 0.0


def _max_height_in_range(
    mask: np.ndarray, x1: int, x2: int
) -> tuple[float, int]:
    """
    Encuentra la columna con mayor altura en el rango [x1, x2].
    Retorna (max_height_px, x_de_esa_columna).
    """
    max_h = 0.0
    best_x = x1
    for xi in range(x1, min(x2, mask.shape[1])):
        h = _column_height(mask, xi)
        if h > max_h:
            max_h = h
            best_x = xi
    return max_h, best_x


# ══════════════════════════════════════════════════════════
# 4. IMAGEN DE DEBUG
# ══════════════════════════════════════════════════════════

def _draw_annotations(
    image, mask, contour, scale,
    lc_px, altura_px, chest_h_px,
    x, y, bw, bh, x_pecho, x_cadera,
) -> np.ndarray:
    """
    Dibuja sobre la imagen:
      - Silueta coloreada (verde semitransparente)
      - Contorno del animal
      - Flecha de largo corporal
      - Línea de altura a la cruz
      - Línea de zona pectoral y cadera
      - Información de escala y confianza
    """
    px = scale.pixels_per_cm

    # Silueta semitransparente
    overlay = image.copy()
    colored = np.zeros_like(image)
    colored[mask > 0] = [30, 200, 80]
    cv2.addWeighted(colored, 0.28, overlay, 0.72, 0, overlay)
    image = overlay

    # Contorno
    cv2.drawContours(image, [contour], -1, (40, 255, 120), 2)

    # Bounding box (tenue)
    cv2.rectangle(image, (x, y), (x + bw, y + bh), (200, 180, 60), 1)

    # ── Largo corporal ────────────────────────────────────────────────────
    arrow_y = y + bh + 18
    cv2.arrowedLine(image, (x, arrow_y), (x + bw, arrow_y),
                    (0, 210, 255), 2, tipLength=0.015)
    cv2.arrowedLine(image, (x + bw, arrow_y), (x, arrow_y),
                    (0, 210, 255), 2, tipLength=0.015)
    cv2.putText(image, f"LC: {lc_px/px:.0f} cm",
                (x + bw // 2 - 45, arrow_y + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 210, 255), 2)

    # ── Altura a la cruz ──────────────────────────────────────────────────
    cv2.line(image, (x_pecho, y), (x_pecho, y + int(altura_px)),
             (255, 120, 30), 2)
    cv2.putText(image, f"AC: {altura_px/px:.0f} cm",
                (x_pecho + 6, y + int(altura_px // 2)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 120, 30), 1)

    # ── Zona pectoral ─────────────────────────────────────────────────────
    cv2.line(image, (x_pecho - 10, y + int(bh * 0.15)),
             (x_pecho - 10, y + int(bh * 0.15) + int(chest_h_px)),
             (255, 60, 200), 1)

    # ── Zona cadera ───────────────────────────────────────────────────────
    hip_h = _column_height(mask, x_cadera)
    cv2.line(image, (x_cadera, y + int(bh * 0.1)),
             (x_cadera, y + int(bh * 0.1) + int(hip_h)),
             (180, 80, 255), 2)
    cv2.putText(image, "CADERA",
                (x_cadera + 5, y + int(bh * 0.1) + int(hip_h // 2)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 80, 255), 1)

    # ── Info de escala (esquina superior izquierda) ───────────────────────
    color_escala = (60, 220, 60) if not scale.warning else (30, 160, 255)
    cv2.putText(image,
                f"Escala: {px:.2f} px/cm  [{scale.method}]",
                (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color_escala, 2)
    cv2.putText(image,
                f"Altura silueta: {scale.animal_height_px:.0f}px "
                f"= {scale.assumed_height_cm:.0f}cm (Jersey promedio)",
                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color_escala, 1)

    if scale.warning:
        cv2.putText(image, f"AVISO: {scale.warning[:60]}",
                    (10, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 80, 255), 1)

    return image


# ══════════════════════════════════════════════════════════
# 5. FUNCIÓN PRINCIPAL — entrada pública del módulo
# ══════════════════════════════════════════════════════════

def process_image(
    image_bytes: bytes,
    # Los parámetros de color/referencia se ignoran en esta versión
    # Se mantienen por compatibilidad con la firma anterior
    scale_color: str = "green",
    reference_cm: float = JERSEY_ALTURA_PROMEDIO_CM,
) -> MorphometryResult:
    """
    Pipeline completo: bytes de imagen → MorphometryResult.

    Escala calculada automáticamente desde la altura promedio
    de la raza Jersey (123 cm). No requiere barra de referencia.

    Uso:
        from app.services.vision.morphometry import process_image
        result = process_image(image_bytes)
        # result.largo_corporal_cm, result.perimetro_toracico_cm, etc.
    """
    # Decodificar
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("No se pudo decodificar la imagen. Verifica el formato.")

    # Redimensionar si es demasiado grande (acelera sin perder precisión)
    image = _resize_safe(image, max_dim=1280)

    # Pipeline
    mask, contour = segment_animal(image)
    result        = extract_morphometrics(image, mask, contour)

    if result.scale_warning:
        logger.warning(f"Advertencia de escala: {result.scale_warning}")

    logger.info(
        f"Morfometría → LC:{result.largo_corporal_cm}cm  "
        f"AC:{result.altura_cruz_cm}cm  PT:{result.perimetro_toracico_cm}cm  "
        f"Cadera:{result.ancho_cadera_cm}cm  "
        f"Confianza:{result.confidence:.2f}  "
        f"Escala:{result.pixels_per_cm:.3f}px/cm"
    )
    return result


def _resize_safe(image: np.ndarray, max_dim: int = 1280) -> np.ndarray:
    h, w = image.shape[:2]
    if max(h, w) <= max_dim:
        return image
    factor = max_dim / max(h, w)
    return cv2.resize(image, (int(w * factor), int(h * factor)),
                      interpolation=cv2.INTER_AREA)


def save_debug_image(result: MorphometryResult, path: str) -> None:
    """Guarda la imagen con anotaciones para verificación visual."""
    cv2.imwrite(path, result.debug_image)


# ══════════════════════════════════════════════════════════
# FUNCIÓN CON BOUNDING BOX DE YOLO
# ══════════════════════════════════════════════════════════

def process_image_with_bbox(
    image_bytes: bytes,
    bbox: list | None = None,
) -> MorphometryResult:
    """
    Igual que process_image() pero si YOLO detectó la vaca,
    recorta la imagen al bounding box antes de segmentar.
    Esto mejora la segmentación porque elimina el fondo extra.

    Parámetros:
        image_bytes: bytes de la imagen original
        bbox:        [x1, y1, x2, y2] en píxeles desde YOLO, o None
    """
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("No se pudo decodificar la imagen.")

    image = _resize_safe(image, max_dim=1280)

    if bbox is not None:
        h_img, w_img = image.shape[:2]
        x1 = max(0,     int(bbox[0]) - 20)   # margen de 20px
        y1 = max(0,     int(bbox[1]) - 20)
        x2 = min(w_img, int(bbox[2]) + 20)
        y2 = min(h_img, int(bbox[3]) + 20)
        image = image[y1:y2, x1:x2]
        logger.info(f"Imagen recortada al bbox YOLO: ({x1},{y1}) → ({x2},{y2})")

    mask, contour = segment_animal(image)
    result        = extract_morphometrics(image, mask, contour)

    if result.scale_warning:
        logger.warning(f"Escala: {result.scale_warning}")

    logger.info(
        f"Morfometría → LC:{result.largo_corporal_cm}cm "
        f"AC:{result.altura_cruz_cm}cm PT:{result.perimetro_toracico_cm}cm "
        f"Conf:{result.confidence:.2f}"
    )
    return result
