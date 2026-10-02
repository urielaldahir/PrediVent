from datetime import datetime, timedelta, timezone

from firebase_config import firestore_db


COLECCION = "ventas"
ID_PRODUCTO = "10"

# Cantidades de prueba para 30 días.
# Se dejan variaciones intencionales para que los modelos
# tengan un patrón que analizar.
CANTIDADES = [
    3, 4, 2, 5, 4,
    6, 5, 7, 4, 6,
    8, 5, 7, 6, 9,
    5, 8, 7, 10, 6,
    9, 8, 11, 7, 10,
    9, 12, 8, 11, 10,
    13, 9
]

PRECIO_UNITARIO = 399.0

# Zona horaria de Guadalajara (UTC-6).
ZONA_HORARIA = timezone(timedelta(hours=-6))


print("\n========================================")
print("       HISTORIAL DE VENTAS DE PRUEBA")
print("========================================\n")


# ---------------------------------------------------------
# 1. ELIMINAR HISTORIAL DE PRUEBA ANTERIOR
# ---------------------------------------------------------

print("Buscando datos de prueba anteriores...")

documentos = (
    firestore_db
    .collection(COLECCION)
    .where("productoID", "==", ID_PRODUCTO)
    .stream()
)

eliminados = 0

for documento in documentos:

    datos = documento.to_dict()

    if datos.get("es_prueba") is True:

        documento.reference.delete()
        eliminados += 1


print(f"Registros de prueba eliminados: {eliminados}")


# ---------------------------------------------------------
# 2. GENERAR LOS 30 DÍAS HISTÓRICOS
# ---------------------------------------------------------

hoy = datetime.now(ZONA_HORARIA).date()

fecha_inicio = hoy - timedelta(days=len(CANTIDADES))

creados = 0


print("\nGenerando historial...\n")


for indice, cantidad in enumerate(CANTIDADES):

    fecha = fecha_inicio + timedelta(days=indice)

    fecha_venta = datetime(
        fecha.year,
        fecha.month,
        fecha.day,
        12,
        0,
        0,
        tzinfo=ZONA_HORARIA
    )

    total = cantidad * PRECIO_UNITARIO

    venta = {
        "id_cliente": 2,
        "productoID": ID_PRODUCTO,
        "cantidad": cantidad,
        "precioUnitario": PRECIO_UNITARIO,
        "total": total,
        "fecha": fecha_venta,
        "es_prueba": True
    }

    firestore_db.collection(COLECCION).add(venta)

    creados += 1

    print(
        f"[OK] {fecha} | "
        f"{cantidad} unidades | "
        f"${total:.2f}"
    )


print("\n========================================")
print("              RESULTADO")
print("========================================")
print(f"Registros creados: {creados}")
print(f"Producto: {ID_PRODUCTO}")
print(f"Días históricos: {len(CANTIDADES)}")
print("========================================\n")

print("Historial de prueba generado correctamente.")
print("Puedes abrir ahora el módulo de predicción.")