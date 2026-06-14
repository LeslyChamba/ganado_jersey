import logging
import resend

logger = logging.getLogger(__name__)

# =====================================================================
# 🔐 CONFIGURACIÓN DE CORREO — Resend (reemplaza SMTP bloqueado en Render)
# =====================================================================
RESEND_API_KEY = "re_JGvwaJqm_8Yjki3Gn8fAEw9zp6MNki57v"  
EMAIL_SISTEMA  = "onboarding@resend.dev"  # ← usa este mientras no tengas dominio propio

resend.api_key = RESEND_API_KEY


def enviar_correo_bienvenida(email_destino: str, nombre: str, password_generada: str) -> bool:
    try:
        resend.Emails.send({
            "from":    EMAIL_SISTEMA,
            "to":      [email_destino],
            "subject": "Bienvenido a JER-WEIGHT - Credenciales de Acceso",
            "text": f"""Hola {nombre},

El administrador te ha registrado en el sistema de gestión ganadera JER-WEIGHT.

Tus credenciales de acceso son:
Usuario: {email_destino}
Contraseña: {password_generada}

Por favor, ingresa al sistema y recuerda no compartir esta información.

Saludos,
Equipo JER-WEIGHT"""
        })
        logger.info(f"✅ Correo de bienvenida enviado a {email_destino}")
        return True
    except Exception as e:
        logger.error(f"❌ Error al enviar correo de bienvenida: {e}")
        return False


def enviar_correo_recuperacion(email_destino: str, token: str) -> bool:
    enlace = f"https://ganado-jersey.vercel.app/reset-password?token={token}"
    try:
        resend.Emails.send({
            "from":    EMAIL_SISTEMA,
            "to":      [email_destino],
            "subject": "Recuperación de Contraseña - JER-WEIGHT",
            "text": f"""Hola,

Has solicitado restablecer tu contraseña en el sistema JER-WEIGHT.

Haz clic en el siguiente enlace para proceder con el cambio:
{enlace}

Si tú no solicitaste este cambio, puedes ignorar este mensaje de forma segura.

Saludos,
Equipo JER-WEIGHT"""
        })
        logger.info(f"✅ Correo de recuperación enviado a {email_destino}")
        return True
    except Exception as e:
        logger.error(f"❌ ERROR al enviar correo de recuperación: {e}")
        return False