from firestore_service import obtener_historial_ventas_producto


ID_PRODUCTO = "10"


print("\n========================================")
print("       PRUEBA DE HISTORIAL DE VENTAS")
print("========================================\n")


historial = obtener_historial_ventas_producto(
    ID_PRODUCTO
)


print("Ventas encontradas:", len(historial))
print()


for i, venta in enumerate(historial, start=1):

    print(f"--- Venta {i} ---")
    print("Producto:", venta.id_producto)
    print("Cantidad:", venta.cantidad)
    print("Fecha:", venta.fecha)
    print("Precio unitario:", venta.precio_unitario)
    print("Total:", venta.total)
    print()