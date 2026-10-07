import pandas as pd
from firebase_admin import firestore

from firebase_config import firestore_db


ARCHIVO_EXCEL = "ventas_historicas_ficticias_PrediVent.xlsx"
COLECCION_VENTAS = "ventas"
COLECCION_PRODUCTOS = "productos"


print("\n==============================================")
print("     CARGA DE HISTORIAL SINTÉTICO")
print("==============================================\n")


# ============================================================
# LEER EXCEL
# ============================================================

try:
    df = pd.read_excel(
        ARCHIVO_EXCEL,
        sheet_name="Ventas"
    )
except Exception as e:
    print("ERROR al leer el Excel:")
    print(e)
    raise SystemExit


columnas_requeridas = [
    "document_id",
    "id_cliente",
    "productoID",
    "cantidad",
    "fecha"
]

faltantes = [
    columna
    for columna in columnas_requeridas
    if columna not in df.columns
]

if faltantes:
    print("ERROR: faltan columnas:")
    for columna in faltantes:
        print(f" - {columna}")
    raise SystemExit


print(
    f"Registros encontrados en Excel: {len(df)}"
)


# ============================================================
# CARGAR PRODUCTOS DESDE FIRESTORE
# ============================================================

print("\nConsultando precios actuales de productos...")


productos = {}

documentos = (
    firestore_db
    .collection(COLECCION_PRODUCTOS)
    .stream()
)

for documento in documentos:

    producto = documento.to_dict()

    if producto.get("id_producto") is None:
        continue

    try:
        id_producto = str(
            int(producto["id_producto"])
        )
    except (TypeError, ValueError):
        continue

    try:
        precio = float(
            producto.get("precio", 0)
        )
    except (TypeError, ValueError):
        precio = 0.0

    productos[id_producto] = precio


print(
    f"Productos encontrados en Firestore: "
    f"{len(productos)}"
)


# ============================================================
# CARGAR VENTAS
# ============================================================

correctos = 0
errores = 0
omitidos = 0


for _, fila in df.iterrows():

    try:

        document_id = str(
            fila["document_id"]
        ).strip()

        id_producto = str(
            int(fila["productoID"])
        )

        cantidad = int(
            fila["cantidad"]
        )

        id_cliente = int(
            fila["id_cliente"]
        )

        fecha = pd.to_datetime(
            fila["fecha"]
        ).to_pydatetime()

        # ----------------------------------------------------
        # VALIDACIONES
        # ----------------------------------------------------

        if cantidad <= 0:
            omitidos += 1
            continue

        if id_producto not in productos:
            print(
                f"[OMITIDO] Producto "
                f"{id_producto} no existe."
            )
            omitidos += 1
            continue

        precio_unitario = productos[
            id_producto
        ]

        total = (
            cantidad *
            precio_unitario
        )

        # ----------------------------------------------------
        # DOCUMENTO FIRESTORE
        # ----------------------------------------------------

        venta = {

            "id_cliente":
                id_cliente,

            "productoID":
                id_producto,

            "cantidad":
                cantidad,

            "precioUnitario":
                precio_unitario,

            "total":
                total,

            "fecha":
                fecha
        }

        (
            firestore_db
            .collection(COLECCION_VENTAS)
            .document(document_id)
            .set(venta)
        )

        correctos += 1

        if correctos % 250 == 0:
            print(
                f"[OK] {correctos} registros cargados..."
            )

    except Exception as e:

        errores += 1

        print(
            f"[ERROR] Documento "
            f"{fila.get('document_id', 'DESCONOCIDO')}: "
            f"{e}"
        )


# ============================================================
# RESULTADO
# ============================================================

print("\n==============================================")
print("                 RESULTADO")
print("==============================================")

print(
    f"Registros cargados: {correctos}"
)

print(
    f"Registros omitidos: {omitidos}"
)

print(
    f"Registros con error: {errores}"
)

print(
    f"Total procesado: "
    f"{correctos + omitidos + errores}"
)

print("\nEl inventario NO fue modificado.")
print("Los precios fueron obtenidos desde Firestore.")
print("Los registros corresponden a historial sintético.")
print("==============================================\n")
