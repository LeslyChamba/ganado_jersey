import os
import logging
import requests

logger = logging.getLogger(__name__)

# =====================================================================
# 🔐 CONFIGURACIÓN DE CORREO — Brevo API REST
# =====================================================================
BREVO_API_KEY  = os.environ.get("BREVO_API_KEY", "")
EMAIL_SISTEMA  = "lesly15chamba@gmail.com"
NOMBRE_SISTEMA = "JER-WEIGHT"


def _enviar_brevo(email_destino: str, nombre_destino: str, asunto: str, contenido: str) -> bool:
    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key":      BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "sender": {"name": NOMBRE_SISTEMA, "email": EMAIL_SISTEMA},
                "to":     [{"email": email_destino, "name": nombre_destino}],
                "subject":     asunto,
                "textContent": contenido,
            },
            timeout=15,
        )
        logger.info(f"Brevo response: {response.status_code} | {response.text}")
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"❌ Error Brevo: {e}")
        return False


def enviar_correo_bienvenida(email_destino: str, nombre: str, password_generada: str) -> bool:
    contenido = f"""Hola {nombre},

El administrador te ha registrado en el sistema de gestión ganadera JER-WEIGHT.

Tus credenciales de acceso son:
Usuario: {email_destino}
Contraseña: {password_generada}

Por favor, ingresa al sistema y recuerda no compartir esta información.

Saludos,
Equipo JER-WEIGHT"""

    ok = _enviar_brevo(
        email_destino,
        nombre,
        "Bienvenido a JER-WEIGHT - Credenciales de Acceso",
        contenido,
    )
    if ok:
        logger.info(f"✅ Correo de bienvenida enviado a {email_destino}")
    return ok


def enviar_correo_recuperacion(email_destino: str, token: str) -> bool:
    enlace = f"https://ganado-jersey.vercel.app/reset-password?token={token}"
    contenido = f"""Hola,

Has solicitado restablecer tu contraseña en el sistema JER-WEIGHT.

Haz clic en el siguiente enlace para proceder con el cambio:
{enlace}

Si tú no solicitaste este cambio, puedes ignorar este mensaje de forma segura.

Saludos,
Equipo JER-WEIGHT"""

    ok = _enviar_brevo(
        email_destino,
        "Usuario",
        "Recuperación de Contraseña - JER-WEIGHT",
        contenido,
    )
    if ok:
        logger.info(f"✅ Correo de recuperación enviado a {email_destino}")
    return ok