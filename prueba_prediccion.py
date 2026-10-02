from firestore_service import obtener_historial_ventas_producto


ID_PRODUCTO = "1"  # Cambia esto por un ID de producto que tenga ventas


historial = obtener_historial_ventas_producto(ID_PRODUCTO)

print("\n===== HISTORIAL DE VENTAS =====")
print("Número de ventas:", len(historial))

for venta in historial:
    print(
        "Producto:", venta.id_producto,
        "| Cantidad:", venta.cantidad,
        "| Fecha:", venta.fecha,
        "| Precio:", venta.precio_unitario,
        "| Total:", venta.total
    )