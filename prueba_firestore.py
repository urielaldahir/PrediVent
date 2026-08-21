from firebase_config import db

# Crear un documento de prueba
doc_ref = db.collection("prueba").document("conexion")

doc_ref.set({
    "mensaje": "PrediVent conectado correctamente",
    "estado": "ok"
})

print("Documento creado correctamente en Firestore")