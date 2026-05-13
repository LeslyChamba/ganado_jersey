import smtplib
from email.message import EmailMessage

# =====================================================================
# ⚠️ CONFIGURACIÓN DE CORREO
# En producción, esto debería ir en un archivo .env por seguridad.
# Por ahora, para tu entorno de desarrollo local, puedes ponerlo aquí.
# =====================================================================
EMAIL_SISTEMA = "lesly15chamba@gmail.com" # <-- Cambia esto
PASSWORD_APP = "fyrl hrjj avfq ighb"          # <-- Cambia esto (16 letras)

def enviar_correo_bienvenida(email_destino: str, nombre: str, password_generada: str):
    """
    Envía un correo automático de bienvenida al nuevo usuario.
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
        # Conexión segura al servidor de Gmail
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
            smtp.send_message(msg)
        print(f"✅ Correo de bienvenida enviado exitosamente a {email_destino}")
    except Exception as e:
        print(f"❌ Error al enviar correo de bienvenida: {e}")

def enviar_correo_recuperacion(email_destino: str, token: str):
    msg = EmailMessage()
    msg['Subject'] = 'Recuperación de Contraseña - JER-WEIGHT'
    msg['From'] = EMAIL_SISTEMA
    msg['To'] = email_destino

    enlace_reset = f"http://localhost:5173/reset-password?token={token}"

    contenido = f"""
    Hola,
    Has solicitado restablecer tu contraseña en JER-WEIGHT.
    Haz clic aquí: {enlace_reset}
    """
    msg.set_content(contenido)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
        smtp.send_message(msg)    