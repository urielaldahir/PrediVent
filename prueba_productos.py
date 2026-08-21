from firestore_service import crear_producto, obtener_productos


# Crear producto de prueba
crear_producto(
    id_producto=1,
    id_provedor=1,
    nombre_producto="Producto de prueba",
    cantida=10,
    descripcion="Producto para probar Firestore",
    precio=999,
    ruta_imagen="static/img/Nike Air Max.png"
)

print("Producto creado correctamente.")


# Leer productos
productos = obtener_productos()

print("\nProductos encontrados:")

for producto in productos:
    print(producto)