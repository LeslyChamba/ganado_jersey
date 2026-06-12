import smtplib
from email.message import EmailMessage

# =====================================================================
#  CONFIGURACIÓN DE CORREO
# =====================================================================
EMAIL_SISTEMA = "lesly15chamba@gmail.com" 
PASSWORD_APP = "fyrl hrjj avfq ighb"  # Tu contraseña de aplicación de 16 letras

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
        # 🚀 CORRECCIÓN: Se usa puerto 587 + starttls() que es totalmente compatible con Render
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()  # Activa el cifrado seguro obligatorio para el puerto 587
            smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
            smtp.send_message(msg)
        print(f"✅ Correo de bienvenida enviado exitosamente a {email_destino}")
    except Exception as e:
        print(f"❌ Error al enviar correo de bienvenida: {e}")

def enviar_correo_recuperacion(email_destino: str, token: str):
    """
    Envía el enlace seguro para el restablecimiento de contraseñas.
    """
    msg = EmailMessage()
    msg['Subject'] = 'Recuperación de Contraseña - JER-WEIGHT'
    msg['From'] = EMAIL_SISTEMA
    msg['To'] = email_destino

    # (Asegúrate de que la ruta coincida con el nombre de tu vista en React, ej: /reset-password o /restablecerpassword)
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
        # CORRECCIÓN: Se usa puerto 587 + starttls() para evitar el bloqueo 'Network is unreachable'
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SISTEMA, PASSWORD_APP)
            smtp.send_message(msg)
        print(f"✅ Correo de recuperación enviado exitosamente a {email_destino}")
    except Exception as e:
        print(f"❌ ERROR SMTP al recuperar contraseña: {e}")