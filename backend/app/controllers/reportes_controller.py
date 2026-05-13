import uuid, io
from datetime import datetime, timezone
from typing import Optional

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

# --- PALETA DE COLORES JER-WEIGHT PARA PDF ---
COLOR_PRIMARIO = HexColor("#081C11")     # Verde casi negro (Para Títulos principales)
COLOR_ESMERALDA = HexColor("#1B4332")    # Verde oscuro vibrante (Para fondos de tablas o acentos)
COLOR_TEXTO = HexColor("#1F2937")        # Gris muy oscuro (Para texto normal, mejor que negro puro)
COLOR_SUBTITULO = HexColor("#2A5C3A")    # Verde pálido elegante (Para subtítulos)
GRIS_CLARO = HexColor("#F3F4F6")         # Para fondos de filas intercaladas
GRIS_LINEA = HexColor("#E5E7EB")         # Para líneas separadoras
# ════════════════════════════════════════════════════════════════════════════
#  GENERADOR DE PDF (reportlab)
# ════════════════════════════════════════════════════════════════════════════

def _interpretar_bcs(bcs: float) -> str:
    if bcs < 2.0:   return "Caquéctica"
    if bcs < 2.5:   return "Delgada"
    if bcs < 3.75:  return "Ideal"
    if bcs < 4.5:   return "Sobre-condicionada"
    return "Obesa"


def _generar_pdf(
    titulo: str,
    mediciones: list,
    ganadero_nombre: str,
    filtros_desc: str,
) -> bytes:
    """Genera un PDF con tabla de mediciones y lo retorna como bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    VERDE  = colors.HexColor("#2E4D38")
    VERDE_L= colors.HexColor("#D4ECD9")
    ROJO   = colors.HexColor("#C0392B")
    GRIS   = colors.HexColor("#8B7D6B")

    estilo_titulo = ParagraphStyle(
        "titulo", fontSize=16, textColor=VERDE,
        spaceAfter=4, fontName="Helvetica-Bold", alignment=TA_CENTER,
    )
    estilo_sub = ParagraphStyle(
        "sub", fontSize=9, textColor=COLOR_SUBTITULO,
        spaceAfter=2, fontName="Helvetica", alignment=TA_CENTER,
    )
    estilo_normal = ParagraphStyle(
        "normal", fontSize=9, textColor=colors.black,
        fontName="Helvetica",
    )

    elementos = []

    # Encabezado
    elementos.append(Paragraph("CRIADERO EL PUENTE — JER-WEIGHT", estilo_sub))
    elementos.append(Paragraph(titulo, estilo_titulo))
    elementos.append(Paragraph(
        f"Generado por: {ganadero_nombre}  |  Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        estilo_sub,
    ))
    if filtros_desc:
        elementos.append(Paragraph(f"Filtros: {filtros_desc}", estilo_sub))
    elementos.append(Spacer(1, 0.3*cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=VERDE))
    elementos.append(Spacer(1, 0.5*cm))

    if not mediciones:
        elementos.append(Paragraph(
            "No se encontraron registros para los filtros seleccionados.",
            estilo_normal,
        ))
    else:
        # Resumen estadístico
        pesos = [m.peso_estimado_kg for m in mediciones]
        bcss  = [m.bcs for m in mediciones]
        resumen_data = [
            ["Total evaluaciones", "Peso promedio (kg)", "Peso máx. (kg)", "Peso mín. (kg)", "BCS promedio"],
            [
                str(len(mediciones)),
                f"{sum(pesos)/len(pesos):.1f}",
                f"{max(pesos):.1f}",
                f"{min(pesos):.1f}",
                f"{sum(bcss)/len(bcss):.2f}",
            ],
        ]
        t_resumen = Table(resumen_data, colWidths=[3.5*cm]*5)
        t_resumen.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1,-1), 8),
            ("ALIGN",      (0, 0), (-1,-1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1,-1), VERDE_L),
            ("GRID",       (0, 0), (-1,-1), 0.5, colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1,-1), [VERDE_L, colors.white]),
        ]))
        elementos.append(t_resumen)
        elementos.append(Spacer(1, 0.5*cm))

        # Tabla principal
        cabecera = ["Arete", "Nombre", "Hato", "Fecha", "Peso (kg)", "BCS", "Estado BCS", "Confianza"]
        filas    = [cabecera]
        for m in mediciones:
            bcs_estado = _interpretar_bcs(m.bcs)
            filas.append([
                m.animal.arete if m.animal else "—",
                (m.animal.nombre or "—") if m.animal else "—",
                (m.animal.hato.nombre if m.animal and m.animal.hato else "—"),
                m.fecha_medicion.strftime("%d/%m/%Y"),
                f"{m.peso_estimado_kg:.1f}",
                f"{m.bcs:.2f}",
                bcs_estado,
                f"{m.confianza:.0f}%" if m.confianza else "—",
            ])

        col_widths = [2.2*cm, 2.8*cm, 3*cm, 2.2*cm, 2*cm, 1.5*cm, 3.3*cm, 1.8*cm]
        tabla = Table(filas, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1,  0), VERDE),
            ("TEXTCOLOR",   (0, 0), (-1,  0), colors.white),
            ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 7.5),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_L]),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#C0B8A8")),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0,0), (-1, -1), 4),
        ]))
        # Colorear filas con BCS bajo en rojo claro
        for i, m in enumerate(mediciones, start=1):
            if m.bcs < 2.5:
                tabla.setStyle(TableStyle([
                    ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDECEA")),
                    ("TEXTCOLOR",  (6, i), (6,  i), ROJO),
                ]))
        elementos.append(tabla)

    elementos.append(Spacer(1, 0.8*cm))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SUBTITULO))
    elementos.append(Paragraph(
        "JER-WEIGHT  — Sistema de estimación de masa y BCS bovino ",
        estilo_sub,
    ))

    doc.build(elementos)
    return buffer.getvalue()


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
    """Consulta mediciones con todos los filtros de RF-15."""
    hato_ids = [
        h.id for h in db.query(Hato.id).filter(
            Hato.propietario_id == current_user.id, Hato.activo == True
        ).all()
    ]
    if not hato_ids:
        return []

    if hato_id and hato_id in hato_ids:
        hato_ids_filtro = [hato_id]
    else:
        hato_ids_filtro = hato_ids

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
    titulo:      str            = Query("Reporte de Evaluaciones", max_length=200),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    hato_id:     Optional[uuid.UUID] = Query(None),
    raza:        Optional[str]  = Query(None, max_length=100),
    bcs_min:     Optional[float]= Query(None, ge=1.0, le=5.0),
    bcs_max:     Optional[float]= Query(None, ge=1.0, le=5.0),
    db:          Session        = Depends(get_db),
    current_user: Usuario       = Depends(get_current_user),
):
    """
    RF-15 / HU-12: Genera y descarga un PDF con las evaluaciones
    filtradas por fecha, raza y BCS.
    """
    mediciones = _consultar_mediciones(
        db, current_user, fecha_desde, fecha_hasta,
        hato_id, raza, bcs_min, bcs_max,
    )

    filtros_parts = []
    if fecha_desde: filtros_parts.append(f"Desde {fecha_desde.strftime('%d/%m/%Y')}")
    if fecha_hasta: filtros_parts.append(f"Hasta {fecha_hasta.strftime('%d/%m/%Y')}")
    if raza:        filtros_parts.append(f"Raza: {raza}")
    if bcs_min or bcs_max:
        filtros_parts.append(f"BCS: {bcs_min or '—'} – {bcs_max or '—'}")
    filtros_desc = " | ".join(filtros_parts) if filtros_parts else "Sin filtros"
    
    # 1. Intentar desencriptar de forma segura (A prueba de fallos)
    try:
        nombre_limpio = decrypt(current_user.nombre)
    except Exception:
        nombre_limpio = current_user.nombre  # Si explota, es porque no estaba encriptado

    try:
        correo_limpio = decrypt(current_user.email)
    except Exception:
        correo_limpio = current_user.email   # Lo mismo para el correo

    # 2. Armamos la firma
    ganadero_nombre = f"{nombre_limpio} {current_user.apellido or ''} | {correo_limpio}".strip()
    pdf_bytes = _generar_pdf(titulo, mediciones, ganadero_nombre, filtros_desc)

    # Guardar registro del reporte generado
    reporte = Reporte(
        titulo=titulo, tipo=TipoReporte.GENERAL, formato=FormatoReporte.PDF,
        generado_por_id=current_user.id,
        parametros={
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
        despues={"titulo": titulo, "registros": len(mediciones)},
        detalle=f"PDF exportado: {len(mediciones)} evaluaciones",
    )

    nombre_archivo = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
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
    """Lista los reportes generados por el usuario (historial real)."""
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