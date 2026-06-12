import socket
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)

# =====================================================================
# 🔐 CONFIGURACIÓN DE CORREO
# =====================================================================
EMAIL_SISTEMA = "lesly15chamba@gmail.com" 
PASSWORD_APP = "fyrl hrjj avfq ighb"  # Contraseña de aplicación de 16 letras de Google


def _obtener_ip_v4_gmail():
    """
    Fuerza la resolución de smtp.gmail.com a IPv4 para evadir el bug 
    de enrutamiento IPv6 interno de la capa gratuita de Render.
    """
    try:
        return socket.gethostbyname('smtp.gmail.com')
    except Exception:
        return 'smtp.gmail.com'


def enviar_correo_bienvenida(email_destino: str, nombre: str, password_generada: str):
    """
    Envía un correo automático de bienvenida al nuevo usuario con sus credenciales.
    """
    msg = EmailMessage()
    msg['Subject'] = 'Bienvenido a JER-WEIGHT - Credenciales de Acceso'
    msg['From'] = EMAIL_SISTEMA
    msg['To'] = email_destino

    contenido = f"""
    Hola {nombre},
    
    El administrador te ha registrado en el sistema de gestión ganadera JER-WEIGHT.
    
    Tus credenciales de acceso son:
    Usuario: {email_destino}
    Contraseña: {password_generada}
    
    Por favor, ingresa al sistema y recuerda no compartir esta información.
    
    Saludos,
    Equipo JER-WEIGHT
    """
    msg.set_content(contenido)

    try:
        ip_gmail = _obtener_ip_v4_gmail()
        with smtplib.SMTP(ip_gmail, 587, timeout=10) as smtp:
            smtp.starttls()  # Cifrado obligatorio compatible con Render
            smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
            smtp.send_message(msg)
        logger.info(f"✅ Correo de bienvenida enviado exitosamente a {email_destino}")
        return True
    except Exception as e:
        logger.error(f"❌ Error al enviar correo de bienvenida: {e}")
        return False


def enviar_correo_recuperacion(email_destino: str, token: str):
    """
    Envía el enlace seguro para el restablecimiento de contraseñas de usuarios.
    """
    msg = EmailMessage()
    msg['Subject'] = 'Recuperación de Contraseña - JER-WEIGHT'
    msg['From'] = EMAIL_SISTEMA
    msg['To'] = email_destino

    enlace_reset = f"https://ganado-jersey.vercel.app/reset-password?token={token}"

    contenido = f"""
    Hola,
    
    Has solicitado restablecer tu contraseña en el sistema JER-WEIGHT.
    
    Haz clic en el siguiente enlace para proceder con el cambio:
    {enlace_reset}
    
    Si tú no solicitaste este cambio, puedes ignorar este mensaje de forma segura.
    
    Saludos,
    Equipo JER-WEIGHT
    """
    msg.set_content(contenido)

    try:
        ip_gmail = _obtener_ip_v4_gmail()
        with smtplib.SMTP(ip_gmail, 587, timeout=10) as smtp:
            smtp.starttls()  # Cifrado obligatorio compatible con Render
            smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
            smtp.send_message(msg)
        logger.info(f"✅ Correo de recuperación enviado exitosamente a {email_destino}")
        return True
    except Exception as e:
        logger.error(f"❌ ERROR SMTP al recuperar contraseña: {e}")
        return False