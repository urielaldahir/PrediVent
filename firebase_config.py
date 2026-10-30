import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
ruta_credenciales = os.path.join(BASE_DIR, firebase_credentials)

if not os.path.exists(ruta_credenciales):
    raise FileNotFoundError(
        f"No se encontró el archivo JSON de Firebase: {ruta_credenciales}"
    )

cred = credentials.Certificate(ruta_credenciales)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

firestore_db = firestore.client()

print("Firebase conectado correctamente")
print("Firestore listo:", firestore_db)