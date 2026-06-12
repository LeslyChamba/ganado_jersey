import socket
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)

EMAIL_SISTEMA = "lesly15chamba@gmail.com"
PASSWORD_APP = "fyrl hrjj avfq ighb"

def _obtener_ip_v4_gmail():
    """Fuerza la resolución de smtp.gmail.com a IPv4 para evadir el bug de Render."""
    try:
        return socket.gethostbyname('smtp.gmail.com')
    except Exception:
        return 'smtp.gmail.com' # Respaldo si falla la resolución

def enviar_correo_recuperacion(email_destino: str, token: str):
    msg = EmailMessage()
    msg['Subject'] = 'Recuperación de Contraseña - JER-WEIGHT'
    msg['From'] = EMAIL_SISTEMA
    msg['To'] = email_destino

    enlace_reset = f"https://ganado-jersey.vercel.app/reset-password?token={token}"
    msg.set_content(f"Hola,\n\nHas solicitado restablecer tu contraseña en JER-WEIGHT.\nHaz clic aquí: {enlace_reset}")

    try:
        # 🎯 FORZAMOS LA IP IPV4 DIRECTA
        ip_gmail = _obtener_ip_v4_gmail()
        
        with smtplib.SMTP(ip_gmail, 587, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
            smtp.send_message(msg)
        logger.info(f"✅ Correo de recuperación enviado exitosamente a {email_destino}")
        return True
    except Exception as e:
        logger.error(f"❌ ERROR SMTP al recuperar contraseña: {e}")
        return False