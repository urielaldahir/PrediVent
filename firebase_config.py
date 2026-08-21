import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")

cred = credentials.Certificate(firebase_credentials)

firebase_admin.initialize_app(cred)

firestore_db = firestore.client()

print("Firebase conectado correctamente")
print("Firestore listo:", firestore_db)