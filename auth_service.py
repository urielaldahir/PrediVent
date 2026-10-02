import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import requests
from dotenv import load_dotenv
from firebase_admin import auth

import os

load_dotenv()

FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM", MAIL_USERNAME)

CODIGO_EXPIRA_MINUTOS = 10


def _hash_codigo(codigo):
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def _codigo_valido(codigo, codigo_hash, creado_en):
    if not codigo_hash or not creado_en:
        return False

    ahora = datetime.now(timezone.utc)

    if creado_en.tzinfo is None:
        creado_en = creado_en.replace(tzinfo=timezone.utc)

    if ahora - creado_en > timedelta(minutes=CODIGO_EXPIRA_MINUTOS):
        return False

    return secrets.compare_digest(_hash_codigo(codigo), codigo_hash)


def enviar_codigo_verificacion(correo, codigo):
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        raise RuntimeError(
            "Faltan MAIL_USERNAME y MAIL_PASSWORD en el archivo .env"
        )

    mensaje = EmailMessage()
    mensaje["Subject"] = "Código de verificación - PrediVent"
    mensaje["From"] = MAIL_FROM
    mensaje["To"] = correo
    mensaje.set_content(
        f"""Hola,\n\n"
        f"Tu código de verificación de PrediVent es: {codigo}\n\n"
        f"Este código tiene una vigencia de {CODIGO_EXPIRA_MINUTOS} minutos.\n"
        f"Si no solicitaste crear una cuenta, puedes ignorar este correo.\n\n"
        f"PrediVent"
        """
    )

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20) as servidor:
        servidor.starttls()
        servidor.login(MAIL_USERNAME, MAIL_PASSWORD)
        servidor.send_message(mensaje)


def crear_usuario_firebase(correo, contraseña):
    """Crea el usuario en Firebase Authentication."""
    return auth.create_user(
        email=correo,
        password=contraseña,
        email_verified=False
    )


def marcar_correo_verificado(uid):
    """Marca el correo como verificado en Firebase Authentication."""
    return auth.update_user(uid, email_verified=True)


def obtener_usuario_firebase(correo):
    try:
        return auth.get_user_by_email(correo)
    except auth.UserNotFoundError:
        return None


def generar_y_guardar_codigo(db, correo, uid, datos_registro):
    codigo = f"{secrets.randbelow(1_000_000):06d}"

    db.collection("verificaciones_email").document(uid).set({
        "correo": correo,
        "uid": uid,
        "codigo_hash": _hash_codigo(codigo),
        "creado_en": datetime.now(timezone.utc),
        "datos_registro": datos_registro
    })

    enviar_codigo_verificacion(correo, codigo)


def verificar_codigo(db, uid, codigo):
    referencia = db.collection("verificaciones_email").document(uid)
    documento = referencia.get()

    if not documento.exists:
        return False, "No existe una verificación pendiente."

    datos = documento.to_dict()

    if not _codigo_valido(
        codigo,
        datos.get("codigo_hash"),
        datos.get("creado_en")
    ):
        return False, "El código es incorrecto o ya expiró."

    referencia.delete()
    marcar_correo_verificado(uid)

    return True, datos.get("datos_registro", {})


def iniciar_sesion_firebase(correo, contraseña):
    """Valida correo/contraseña mediante Firebase Auth REST API."""
    if not FIREBASE_WEB_API_KEY:
        raise RuntimeError("Falta FIREBASE_WEB_API_KEY en el archivo .env")

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        f"accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    )

    respuesta = requests.post(
        url,
        json={
            "email": correo,
            "password": contraseña,
            "returnSecureToken": True
        },
        timeout=15
    )

    if respuesta.ok:
        return True, respuesta.json()

    try:
        error = respuesta.json().get("error", {}).get("message", "")
    except ValueError:
        error = ""

    return False, error

def enviar_correo_recuperacion(correo):
    """Genera un enlace de recuperación de contraseña y lo envía por correo."""

    if not MAIL_USERNAME or not MAIL_PASSWORD:
        raise RuntimeError(
            "Faltan MAIL_USERNAME y MAIL_PASSWORD en el archivo .env"
        )

    # Generar enlace oficial de recuperación de Firebase
    enlace = auth.generate_password_reset_link(correo)

    mensaje = EmailMessage()
    mensaje["Subject"] = "Restablecer contraseña - PrediVent"
    mensaje["From"] = MAIL_FROM
    mensaje["To"] = correo

    mensaje.set_content(
        f"""Hola,

Recibimos una solicitud para restablecer la contraseña de tu cuenta de PrediVent.

Para crear una nueva contraseña, entra al siguiente enlace:

{enlace}

Si tú no solicitaste este cambio, puedes ignorar este correo.

PrediVent
"""
    )

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20) as servidor:
        servidor.starttls()
        servidor.login(MAIL_USERNAME, MAIL_PASSWORD)
        servidor.send_message(mensaje)