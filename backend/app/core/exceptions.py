from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

# Configuración básica de logs en consola por si la DB falla
logger = logging.getLogger(__name__)

def registrar_error_auditoria(db: Session, usuario_email: str, modulo: str, accion: str, error: Exception, id_recurso: str = None):
    """
    Función global para persistir errores en el esquema auditoria_errores.
    """
    try:
        # Construimos el query SQL directo para evitar conflictos con modelos ORM
        query = text("""
            INSERT INTO auditoria_errores.log_acciones_fallidas 
            (usuario_email, modulo, accion_intentada, identificador_recurso, codigo_sql_state, mensaje_error)
            VALUES (:email, :modulo, :accion, :id_rec, :code, :msg)
        """)
        
        # SQLSTATE suele estar disponible en errores de base de datos (Psycopg2/SQLAlchemy)
        sql_state = getattr(error, 'code', 'APP_ERR') 
        
        db.execute(query, {
            "email": usuario_email,
            "modulo": modulo,
            "accion": accion,
            "id_rec": id_recurso,
            "code": str(sql_state),
            "msg": str(error)
        })
        db.commit()
        
    except Exception as e:
        # Si falla el guardado en la DB, lo mandamos al log del servidor
        logger.error(f"CRÍTICO: No se pudo guardar el log de error en la DB: {e}")
        db.rollback()

class AuditoriaError(Exception):
    """Excepción personalizada por si quieres lanzar errores específicos"""
    pass