import uuid, io
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.core.encryption import decrypt
from app.db.database import get_db
from app.models.models import (
    Reporte, Medicion, Animal, Hato, Usuario,
    TipoReporte, FormatoReporte, AccionAuditoria,
)
from app.schemas.schemas import ReporteCreate, ReporteResponse
from app.controllers.auth_controller import get_current_user
from app.services.auditoria_service import registrar_log
from reportlab.lib.colors import HexColor

router = APIRouter(prefix="/reportes", tags=["Reportes"])

# --- PALETA DE COLORES ---
COLOR_PRIMARIO  = HexColor("#081C11")
COLOR_ESMERALDA = HexColor("#1B4332")
COLOR_TEXTO     = HexColor("#1F2937")
COLOR_SUBTITULO = HexColor("#2A5C3A")
GRIS_CLARO      = HexColor("#F3F4F6")
GRIS_LINEA      = HexColor("#E5E7EB")


def _interpretar_bcs(bcs: float) -> str:
    if bcs < 2.0:  return "Caquéctica"
    if bcs < 2.5:  return "Delgada"
    if bcs < 3.75: return "Ideal"
    if bcs < 4.5:  return "Sobre-condicionada"
    return "Obesa"


# ════════════════════════════════════════════════════════════════════════════
#  GENERADORES DE PDF POR TIPO
# ════════════════════════════════════════════════════════════════════════════

def _base_doc(buffer):
    """Crea un SimpleDocTemplate y los estilos base reutilizables."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    VERDE   = colors.HexColor("#2E4D38")

    titulo_s = ParagraphStyle(
        "titulo", fontSize=16, textColor=VERDE,
        spaceAfter=4, fontName="Helvetica-Bold", alignment=TA_CENTER,
    )
    sub_s = ParagraphStyle(
        "sub", fontSize=9, textColor=COLOR_SUBTITULO,
        spaceAfter=2, fontName="Helvetica", alignment=TA_CENTER,
    )
    normal_s = ParagraphStyle(
        "normal", fontSize=9, textColor=colors.black, fontName="Helvetica",
    )
    return doc, titulo_s, sub_s, normal_s


def _encabezado(titulo, ganadero_nombre, filtros_desc, titulo_s, sub_s):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, HRFlowable

    VERDE = colors.HexColor("#2E4D38")
    elems = []
    elems.append(Paragraph("CRIADERO EL PUENTE — JER-WEIGHT", sub_s))
    elems.append(Paragraph(titulo, titulo_s))
    elems.append(Paragraph(
        f"Generado por: {ganadero_nombre}  |  Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        sub_s,
    ))
    if filtros_desc:
        elems.append(Paragraph(f"Filtros: {filtros_desc}", sub_s))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(HRFlowable(width="100%", thickness=1, color=VERDE))
    elems.append(Spacer(1, 0.5*cm))
    return elems


# ── 1. BCS GENERAL ──────────────────────────────────────────────────────────
def _generar_pdf_bcs(titulo, mediciones, ganadero_nombre, filtros_desc) -> bytes:
    """
    Reporte BCS: tabla con distribución de condición corporal.
    Muestra arete, nombre, hato, fecha, BCS, estado BCS y confianza.
    Incluye resumen de distribución por categoría BCS.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    buffer = io.BytesIO()
    doc, titulo_s, sub_s, normal_s = _base_doc(buffer)
    VERDE   = colors.HexColor("#2E4D38")
    VERDE_L = colors.HexColor("#D4ECD9")
    ROJO    = colors.HexColor("#C0392B")

    elementos = _encabezado(titulo, ganadero_nombre, filtros_desc, titulo_s, sub_s)

    if not mediciones:
        elementos.append(Paragraph("No se encontraron registros para los filtros seleccionados.", normal_s))
    else:
        # ── Distribución por categoría BCS ──
        dist = defaultdict(int)
        for m in mediciones:
            dist[_interpretar_bcs(m.bcs)] += 1

        dist_data = [["Categoría BCS", "Cantidad", "Porcentaje"]]
        for categoria, cantidad in sorted(dist.items()):
            pct = f"{cantidad / len(mediciones) * 100:.1f}%"
            dist_data.append([categoria, str(cantidad), pct])

        t_dist = Table(dist_data, colWidths=[6*cm, 3.5*cm, 3.5*cm])
        t_dist.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [VERDE_L, colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#C0B8A8")),
        ]))
        elementos.append(Paragraph("Distribución por Categoría BCS", titulo_s))
        elementos.append(Spacer(1, 0.3*cm))
        elementos.append(t_dist)
        elementos.append(Spacer(1, 0.6*cm))

        # ── Tabla detallada BCS ──
        cabecera = ["Arete", "Nombre", "Hato / Finca", "Fecha", "BCS", "Estado BCS", "Confianza"]
        filas = [cabecera]
        for m in mediciones:
            estado = _interpretar_bcs(m.bcs)
            filas.append([
                m.animal.arete if m.animal else "—",
                (m.animal.nombre or "—") if m.animal else "—",
                (f"{m.animal.hato.nombre} / {m.animal.hato.finca}" if m.animal and m.animal.hato else "—"),
                m.fecha_medicion.strftime("%d/%m/%Y"),
                f"{m.bcs:.2f}",
                estado,
                f"{m.confianza:.0f}%" if m.confianza else "—",
            ])

        col_widths = [2.2*cm, 2.8*cm, 4*cm, 2.2*cm, 1.8*cm, 3.5*cm, 2.2*cm]
        tabla = Table(filas, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  VERDE),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 7.5),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_L]),
            ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#C0B8A8")),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ]))
        for i, m in enumerate(mediciones, start=1):
            if m.bcs < 2.5:
                tabla.setStyle(TableStyle([
                    ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDECEA")),
                    ("TEXTCOLOR",  (5, i), (5, i),  ROJO),
                ]))
        elementos.append(tabla)

    _pie(elementos, sub_s)
    doc.build(elementos)
    return buffer.getvalue()


# ── 2. PESOS ────────────────────────────────────────────────────────────────
def _generar_pdf_pesos(titulo, mediciones, ganadero_nombre, filtros_desc) -> bytes:
    """
    Reporte de Pesos: tabla con peso por animal, peso promedio del hato,
    evolución histórica (última medición vs anterior).
    """
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    buffer = io.BytesIO()
    doc, titulo_s, sub_s, normal_s = _base_doc(buffer)
    VERDE   = colors.HexColor("#2E4D38")
    VERDE_L = colors.HexColor("#D4ECD9")
    AZUL    = colors.HexColor("#1A56DB")
    ROJO    = colors.HexColor("#C0392B")

    elementos = _encabezado(titulo, ganadero_nombre, filtros_desc, titulo_s, sub_s)

    if not mediciones:
        elementos.append(Paragraph("No se encontraron registros para los filtros seleccionados.", normal_s))
    else:
        pesos = [m.peso_estimado_kg for m in mediciones]

        # ── Resumen estadístico ──
        resumen_data = [
            ["Total evaluaciones", "Peso promedio (kg)", "Peso máx. (kg)", "Peso mín. (kg)", "Desv. estándar (kg)"],
            [
                str(len(mediciones)),
                f"{sum(pesos)/len(pesos):.1f}",
                f"{max(pesos):.1f}",
                f"{min(pesos):.1f}",
                f"{_desv_std(pesos):.1f}",
            ],
        ]
        t_res = Table(resumen_data, colWidths=[3.5*cm] * 5)
        t_res.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1, 1), VERDE_L),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.white),
        ]))
        elementos.append(t_res)
        elementos.append(Spacer(1, 0.6*cm))

        # ── Tabla detallada por animal (última medición + variación) ──
        # Agrupar mediciones por animal y ordenar por fecha para calcular variación
        por_animal: dict[str, list] = defaultdict(list)
        for m in sorted(mediciones, key=lambda x: x.fecha_medicion):
            key = str(m.animal_id)
            por_animal[key].append(m)

        cabecera = ["Arete", "Nombre", "Hato / Finca", "Fecha", "Peso (kg)", "Variación (kg)", "BCS"]
        filas = [cabecera]
        for animal_id, meds in por_animal.items():
            ultima = meds[-1]
            variacion = "—"
            if len(meds) >= 2:
                delta = ultima.peso_estimado_kg - meds[-2].peso_estimado_kg
                variacion = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
            filas.append([
                ultima.animal.arete if ultima.animal else "—",
                (ultima.animal.nombre or "—") if ultima.animal else "—",
                (f"{ultima.animal.hato.nombre} / {ultima.animal.hato.finca}" if ultima.animal and ultima.animal.hato else "—"),
                ultima.fecha_medicion.strftime("%d/%m/%Y"),
                f"{ultima.peso_estimado_kg:.1f}",
                variacion,
                f"{ultima.bcs:.2f}",
            ])

        col_widths = [2.2*cm, 2.8*cm, 4*cm, 2.2*cm, 2.3*cm, 2.8*cm, 2*cm]
        tabla = Table(filas, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  VERDE),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 7.5),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_L]),
            ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#C0B8A8")),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ]))
        # Colorear variación positiva en azul, negativa en rojo
        for i, (_, meds) in enumerate(por_animal.items(), start=1):
            if len(meds) >= 2:
                delta = meds[-1].peso_estimado_kg - meds[-2].peso_estimado_kg
                color = AZUL if delta >= 0 else ROJO
                tabla.setStyle(TableStyle([("TEXTCOLOR", (5, i), (5, i), color)]))

        elementos.append(tabla)

    _pie(elementos, sub_s)
    doc.build(elementos)
    return buffer.getvalue()


# ── 3. ALERTAS ──────────────────────────────────────────────────────────────
def _generar_pdf_alertas(titulo, mediciones, ganadero_nombre, filtros_desc) -> bytes:
    """
    Reporte de Alertas: solo animales con BCS < 2.5.
    Tabla con arete, nombre, hato, fecha, peso, BCS y recomendación de acción.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    buffer = io.BytesIO()
    doc, titulo_s, sub_s, normal_s = _base_doc(buffer)
    VERDE   = colors.HexColor("#2E4D38")
    VERDE_L = colors.HexColor("#D4ECD9")
    ROJO    = colors.HexColor("#C0392B")
    ROJO_L  = colors.HexColor("#FDECEA")

    elementos = _encabezado(titulo, ganadero_nombre, filtros_desc, titulo_s, sub_s)

    if not mediciones:
        elementos.append(Paragraph(
            "✓ No se detectaron animales en estado crítico para los filtros seleccionados.",
            normal_s,
        ))
    else:
        elementos.append(Paragraph(
            f"⚠ {len(mediciones)} animal(es) con BCS menor a 2.5 — requieren atención inmediata.",
            normal_s,
        ))
        elementos.append(Spacer(1, 0.4*cm))

        cabecera = ["Arete", "Nombre", "Hato / Finca", "Fecha", "Peso (kg)", "BCS", "Estado", "Acción recomendada"]
        filas = [cabecera]
        for m in mediciones:
            estado = _interpretar_bcs(m.bcs)
            accion = "Revisión urgente" if m.bcs < 2.0 else "Aumentar ración"
            filas.append([
                m.animal.arete if m.animal else "—",
                (m.animal.nombre or "—") if m.animal else "—",
                (f"{m.animal.hato.nombre} / {m.animal.hato.finca}" if m.animal and m.animal.hato else "—"),
                m.fecha_medicion.strftime("%d/%m/%Y"),
                f"{m.peso_estimado_kg:.1f}",
                f"{m.bcs:.2f}",
                estado,
                accion,
            ])

        col_widths = [1.8*cm, 2.2*cm, 4*cm, 2*cm, 1.8*cm, 1.5*cm, 2.3*cm, 3*cm]
        tabla = Table(filas, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  ROJO),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 7.5),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND",     (0, 1), (-1, -1), ROJO_L),
            ("TEXTCOLOR",      (6, 1), (6, -1),  ROJO),
            ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#C0B8A8")),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabla)

    _pie(elementos, sub_s)
    doc.build(elementos)
    return buffer.getvalue()


# ── 4. TENDENCIAS MENSUALES ─────────────────────────────────────────────────
def _generar_pdf_tendencias(titulo, mediciones, ganadero_nombre, filtros_desc) -> bytes:
    """
    Reporte de Tendencias: mediciones agrupadas por mes.
    Muestra cantidad de evaluaciones, peso promedio y BCS promedio por mes.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    buffer = io.BytesIO()
    doc, titulo_s, sub_s, normal_s = _base_doc(buffer)
    VERDE   = colors.HexColor("#2E4D38")
    VERDE_L = colors.HexColor("#D4ECD9")

    elementos = _encabezado(titulo, ganadero_nombre, filtros_desc, titulo_s, sub_s)

    if not mediciones:
        elementos.append(Paragraph("No se encontraron registros para los filtros seleccionados.", normal_s))
    else:
        # ── Agrupar por mes ──
        por_mes: dict[str, list] = defaultdict(list)
        for m in mediciones:
            clave = m.fecha_medicion.strftime("%Y-%m")
            por_mes[clave].append(m)

        cabecera = ["Mes", "Evaluaciones", "Peso prom. (kg)", "BCS prom.", "Peso máx. (kg)", "Peso mín. (kg)", "Alertas BCS<2.5"]
        filas = [cabecera]
        for mes in sorted(por_mes.keys()):
            meds_mes = por_mes[mes]
            pesos_mes = [m.peso_estimado_kg for m in meds_mes]
            bcss_mes  = [m.bcs for m in meds_mes]
            alertas   = sum(1 for m in meds_mes if m.bcs < 2.5)
            mes_label = datetime.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()
            filas.append([
                mes_label,
                str(len(meds_mes)),
                f"{sum(pesos_mes)/len(pesos_mes):.1f}",
                f"{sum(bcss_mes)/len(bcss_mes):.2f}",
                f"{max(pesos_mes):.1f}",
                f"{min(pesos_mes):.1f}",
                str(alertas) if alertas > 0 else "—",
            ])

        col_widths = [3.2*cm, 2.5*cm, 3*cm, 2.3*cm, 2.5*cm, 2.5*cm, 2.7*cm]
        tabla = Table(filas, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  VERDE),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 7.5),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_L]),
            ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#C0B8A8")),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ]))
        # Colorear rojo la columna de alertas cuando hay valores
        for i, mes in enumerate(sorted(por_mes.keys()), start=1):
            alertas = sum(1 for m in por_mes[mes] if m.bcs < 2.5)
            if alertas > 0:
                tabla.setStyle(TableStyle([
                    ("TEXTCOLOR", (6, i), (6, i), colors.HexColor("#C0392B")),
                    ("FONTNAME",  (6, i), (6, i), "Helvetica-Bold"),
                ]))
        elementos.append(tabla)

    _pie(elementos, sub_s)
    doc.build(elementos)
    return buffer.getvalue()


def _pie(elementos, sub_s):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, HRFlowable
    elementos.append(Spacer(1, 0.8*cm))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SUBTITULO))
    elementos.append(Paragraph(
        "JER-WEIGHT — Sistema de estimación de masa y BCS bovino",
        sub_s,
    ))


def _desv_std(valores: list) -> float:
    if len(valores) < 2:
        return 0.0
    media = sum(valores) / len(valores)
    varianza = sum((v - media) ** 2 for v in valores) / len(valores)
    return varianza ** 0.5


# ════════════════════════════════════════════════════════════════════════════
#  DISPATCHER: elige el generador según subtipo
# ════════════════════════════════════════════════════════════════════════════

_GENERADORES = {
    "bcs":        _generar_pdf_bcs,
    "pesos":      _generar_pdf_pesos,
    "alertas":    _generar_pdf_alertas,
    "tendencias": _generar_pdf_tendencias,
}


# ════════════════════════════════════════════════════════════════════════════
#  CONSULTA FILTRADA DE MEDICIONES
# ════════════════════════════════════════════════════════════════════════════

def _consultar_mediciones(
    db: Session,
    current_user: Usuario,
    fecha_desde: Optional[datetime],
    fecha_hasta: Optional[datetime],
    hato_id:     Optional[uuid.UUID],
    raza:        Optional[str],
    bcs_min:     Optional[float],
    bcs_max:     Optional[float],
):
    hato_ids = [
        h.id for h in db.query(Hato.id).filter(
            Hato.propietario_id == current_user.id, Hato.activo == True
        ).all()
    ]
    if not hato_ids:
        return []

    hato_ids_filtro = [hato_id] if (hato_id and hato_id in hato_ids) else hato_ids

    animal_q = db.query(Animal).filter(Animal.hato_id.in_(hato_ids_filtro))
    if raza:
        animal_q = animal_q.filter(Animal.raza.ilike(f"%{raza}%"))
    animales = animal_q.all()
    animal_ids = [a.id for a in animales]
    if not animal_ids:
        return []

    med_q = db.query(Medicion).filter(Medicion.animal_id.in_(animal_ids))
    if fecha_desde:
        med_q = med_q.filter(Medicion.fecha_medicion >= fecha_desde)
    if fecha_hasta:
        med_q = med_q.filter(Medicion.fecha_medicion <= fecha_hasta)
    if bcs_min is not None:
        med_q = med_q.filter(Medicion.bcs >= bcs_min)
    if bcs_max is not None:
        med_q = med_q.filter(Medicion.bcs <= bcs_max)

    return med_q.order_by(Medicion.fecha_medicion.desc()).all()


# ════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/exportar/pdf", response_class=StreamingResponse)
def exportar_pdf(
    # ── NUEVO: subtipo diferencia el tipo de reporte ──────────────────────
    subtipo:     str             = Query("bcs", regex="^(bcs|pesos|alertas|tendencias)$"),
    titulo:      str             = Query("Reporte de Evaluaciones", max_length=200),
    fecha_desde: Optional[datetime]  = Query(None),
    fecha_hasta: Optional[datetime]  = Query(None),
    hato_id:     Optional[uuid.UUID] = Query(None),
    raza:        Optional[str]   = Query(None, max_length=100),
    bcs_min:     Optional[float] = Query(None, ge=1.0, le=5.0),
    bcs_max:     Optional[float] = Query(None, ge=1.0, le=5.0),
    db:          Session         = Depends(get_db),
    current_user: Usuario        = Depends(get_current_user),
):
    mediciones = _consultar_mediciones(
        db, current_user, fecha_desde, fecha_hasta,
        hato_id, raza, bcs_min, bcs_max,
    )

    filtros_parts = []
    if fecha_desde: filtros_parts.append(f"Desde {fecha_desde.strftime('%d/%m/%Y')}")
    if fecha_hasta: filtros_parts.append(f"Hasta {fecha_hasta.strftime('%d/%m/%Y')}")
    if raza:        filtros_parts.append(f"Raza: {raza}")
    if bcs_min is not None or bcs_max is not None:
        filtros_parts.append(f"BCS: {bcs_min or '—'} – {bcs_max or '—'}")
    filtros_desc = " | ".join(filtros_parts) if filtros_parts else "Sin filtros"

    try:
        nombre_limpio = decrypt(current_user.nombre)
    except Exception:
        nombre_limpio = current_user.nombre
    try:
        correo_limpio = decrypt(current_user.email)
    except Exception:
        correo_limpio = current_user.email

    ganadero_nombre = f"{nombre_limpio} {current_user.apellido or ''} | {correo_limpio}".strip()

    # ── Elegir generador según subtipo ────────────────────────────────────
    generador = _GENERADORES.get(subtipo, _generar_pdf_bcs)
    pdf_bytes = generador(titulo, mediciones, ganadero_nombre, filtros_desc)

    # Guardar registro
    reporte = Reporte(
        titulo=titulo, tipo=TipoReporte.GENERAL, formato=FormatoReporte.PDF,
        generado_por_id=current_user.id,
        parametros={
            "subtipo":     subtipo,
            "fecha_desde": fecha_desde.isoformat() if fecha_desde else None,
            "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else None,
            "hato_id":     str(hato_id) if hato_id else None,
            "raza":        raza,
            "bcs_min":     bcs_min,
            "bcs_max":     bcs_max,
            "total_registros": len(mediciones),
        },
    )
    db.add(reporte)
    db.commit()

    registrar_log(
        db=db, accion=AccionAuditoria.GENERAR_REPORTE,
        usuario_id=current_user.id, usuario_email=current_user.email,
        tabla="reportes", registro_id=reporte.id,
        despues={"titulo": titulo, "subtipo": subtipo, "registros": len(mediciones)},
        detalle=f"PDF {subtipo} exportado: {len(mediciones)} evaluaciones",
    )

    nombre_archivo = f"reporte_{subtipo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/historial", response_model=list[ReporteResponse])
def historial_reportes(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(Reporte)
        .filter(Reporte.generado_por_id == current_user.id)
        .order_by(Reporte.fecha_generado.desc())
        .limit(20)
        .all()
    )


@router.post("/", response_model=ReporteResponse, status_code=status.HTTP_201_CREATED)
def crear_reporte(
    datos: ReporteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if datos.hato_id:
        hato = db.query(Hato).filter(
            Hato.id == datos.hato_id, Hato.propietario_id == current_user.id
        ).first()
        if not hato:
            raise HTTPException(status_code=404, detail="Hato no encontrado")
    reporte = Reporte(
        titulo=datos.titulo, tipo=datos.tipo, formato=datos.formato,
        hato_id=datos.hato_id, generado_por_id=current_user.id,
        parametros={
            "fecha_desde": datos.fecha_desde.isoformat() if datos.fecha_desde else None,
            "fecha_hasta": datos.fecha_hasta.isoformat() if datos.fecha_hasta else None,
        },
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


@router.get("/", response_model=list[ReporteResponse])
def listar_reportes(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(Reporte)
        .filter(Reporte.generado_por_id == current_user.id)
        .order_by(Reporte.fecha_generado.desc())
        .all()
    )


@router.delete("/{reporte_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_reporte(
    reporte_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    reporte = db.query(Reporte).filter(
        Reporte.id == reporte_id, Reporte.generado_por_id == current_user.id
    ).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    db.delete(reporte)
    db.commit()