import pandas as pd
from firebase_config import firestore_db


# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO_EXCEL = "BD_productos_firestore_limpia.xlsx"
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
# REFERENCIA A FIRESTORE
# ============================================================

productos_ref = firestore_db.collection(COLECCION)


# ============================================================
# CARGAR PRODUCTOS
# ============================================================

correctos = 0
errores = 0

for _, fila in df.iterrows():

    try:
        id_producto = int(fila["id_producto"])

        nombre = str(fila["nombre_producto"]).strip()

        if pd.isna(fila["descripcion"]):
            descripcion = ""
        else:
            descripcion = str(fila["descripcion"]).strip()

        if pd.isna(fila["precio"]):
            precio = 0.0
        else:
            precio = float(fila["precio"])

        if pd.isna(fila["Cantidad"]):
            cantidad = 0
        else:
            cantidad = int(fila["Cantidad"])

        # IMPORTANTE:
        # Ahora sí se toma la URL de imagen directamente del Excel.
        if pd.isna(fila["RutaImagen"]):
            ruta_imagen = ""
        else:
            ruta_imagen = str(fila["RutaImagen"]).strip()

        # Por ahora se conserva la lógica anterior del proyecto:
        # el proveedor se completa posteriormente.
        id_proveedor = None

        producto = {
            "id_producto": id_producto,
            "nombre_producto": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "cantidad": cantidad,
            "id_proveedor": id_proveedor,
            "RutaImagen": ruta_imagen
        }

        productos_ref.document(str(id_producto)).set(producto)

        correctos += 1
        print(f"[OK] {id_producto} - {nombre}")

    except Exception as e:
        errores += 1
        print(
            f"[ERROR] Fila "
            f"{fila.get('id_producto', 'DESCONOCIDO')}: {e}"
        )


# ============================================================
# RESULTADO
# ============================================================

print("\n========================================")
print("              RESULTADO")
print("========================================")

print(f"Productos cargados correctamente: {correctos}")
print(f"Productos con error: {errores}")
print(f"Total procesado: {correctos + errores}")

print("========================================\n")
