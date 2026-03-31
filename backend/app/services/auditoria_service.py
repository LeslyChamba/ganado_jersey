from sqlalchemy.orm import Session
from app.models.models import AuditoriaLog, AccionAuditoria
from typing import Optional
import uuid

def registrar_log(
    db: Session,
    accion: AccionAuditoria,
    usuario_id: Optional[uuid.UUID] = None,
    usuario_email: Optional[str] = None,
    tabla: Optional[str] = None,
    registro_id=None,
    antes: Optional[dict] = None,
    despues: Optional[dict] = None,
    ip: Optional[str] = None,
    detalle: Optional[str] = None
):
    log = AuditoriaLog(
        usuario_id=usuario_id,
        usuario_email=usuario_email,
        accion=accion,
        tabla_afectada=tabla,
        registro_id=str(registro_id) if registro_id else None,
        datos_antes=antes,
        datos_despues=despues,
        ip_address=ip,
        detalle=detalle
    )
    db.add(log)
    db.commit()