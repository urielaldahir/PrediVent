import pandas as pd
import firebase_admin
from firebase_admin import firestore

from firebase_config import firestore_db


# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO_EXCEL = "BD_productos_nombres_corregidos.xlsx"
COLECCION = "productos"


# ============================================================
# LEER EXCEL
# ============================================================

print("\n========================================")
print("      CARGA DE PRODUCTOS A FIRESTORE")
print("========================================\n")

try:
    df = pd.read_excel(ARCHIVO_EXCEL)

except Exception as e:
    print("ERROR al leer el Excel:")
    print(e)
    raise SystemExit


print(f"Productos encontrados en Excel: {len(df)}")


# ============================================================
# VALIDAR COLUMNAS
# ============================================================

columnas_requeridas = [
    "id_producto",
    "nombre_producto",
    "descripcion",
    "precio",
    "Cantidad",
    "RutaImagen"
]

faltantes = [
    columna
    for columna in columnas_requeridas
    if columna not in df.columns
]

if faltantes:

    print("\nERROR: faltan columnas en el Excel:")

    for columna in faltantes:
        print(f" - {columna}")

    raise SystemExit


# ============================================================
# REFERENCIA A LA COLECCIÓN
# ============================================================

productos_ref = firestore_db.collection(
    COLECCION
)


# ============================================================
# CARGAR PRODUCTOS
# ============================================================

correctos = 0
errores = 0

for _, fila in df.iterrows():

    try:

        # ----------------------------------------------------
        # ID DEL PRODUCTO
        # ----------------------------------------------------

        id_producto = int(
            fila["id_producto"]
        )

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        nombre = str(
            fila["nombre_producto"]
        ).strip()

        # ----------------------------------------------------
        # DESCRIPCIÓN
        # ----------------------------------------------------

        if pd.isna(fila["descripcion"]):
            descripcion = ""
        else:
            descripcion = str(
                fila["descripcion"]
            ).strip()

        # ----------------------------------------------------
        # PRECIO
        # ----------------------------------------------------

        if pd.isna(fila["precio"]):
            precio = 0.0
        else:
            precio = float(
                fila["precio"]
            )

        # ----------------------------------------------------
        # CANTIDAD
        # ----------------------------------------------------

        if pd.isna(fila["Cantidad"]):
            cantidad = 0
        else:
            cantidad = int(
                fila["Cantidad"]
            )

        # ----------------------------------------------------
        # RUTA DE IMAGEN
        # ----------------------------------------------------

        # Las imágenes todavía no están listas.
        ruta_imagen = ""

        # ----------------------------------------------------
        # PROVEEDOR
        # ----------------------------------------------------

        # Se completará posteriormente.
        id_proveedor = None

        # ----------------------------------------------------
        # DOCUMENTO
        # ----------------------------------------------------

        producto = {
            "id_producto": id_producto,
            "nombre_producto": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "cantidad": cantidad,
            "id_proveedor": id_proveedor,
            "RutaImagen": ruta_imagen
        }

        # ----------------------------------------------------
        # GUARDAR EN FIRESTORE
        # ----------------------------------------------------

        productos_ref.document(
            str(id_producto)
        ).set(producto)

        correctos += 1

        print(
            f"[OK] {id_producto} - {nombre}"
        )

    except Exception as e:

        errores += 1

        print(
            f"[ERROR] Fila "
            f"{fila.get('id_producto', 'DESCONOCIDO')}: "
            f"{e}"
        )


# ============================================================
# RESULTADO
# ============================================================

print("\n========================================")
print("              RESULTADO")
print("========================================")

print(
    f"Productos cargados correctamente: "
    f"{correctos}"
)

print(
    f"Productos con error: "
    f"{errores}"
)

print(
    f"Total procesado: "
    f"{correctos + errores}"
)

print("========================================\n")