# Cambios de checkout PrediVent

## Funcionalidad integrada
- Dirección de entrega editable desde el perfil y durante el checkout.
- La dirección usada en una compra se guarda como dirección predeterminada del cliente.
- Métodos de pago simulados: efectivo, transferencia y tarjeta. No se realizan cargos.
- Folio único por pedido y colección Firestore `pedidos`.
- Ticket con folio, fecha, dirección, método de pago, estado, detalle y total; permite imprimir.
- Los registros individuales de `ventas` se conservan para el historial y las predicciones, ahora relacionados mediante `folio_pedido`.
- Los flujos de carrito, compra directa y compra de promoción utilizan el mismo procesador de pedido.
- Validación previa de existencia y stock de todas las líneas antes de descontar inventario.

## Archivos modificados
- `app.py`
- `firestore_service.py`
- `forms.py`
- `templates/confirmar_compra.html`
- `templates/compra_exitosa.html`
- `templates/perfil.html`
- `templates/editar_perfil.html`
- `templates/detalle_promocion.html`

## Antes de ejecutar
Este paquete no incluye secretos ni credenciales. Copia desde tu respaldo original:
1. Tu archivo `.env` a la raíz del proyecto.
2. El JSON de cuenta de servicio de Firebase a la ruta indicada por `FIREBASE_CREDENTIALS` en `.env`.

No subas esos archivos a GitHub.

## Pruebas recomendadas
1. Inicia sesión con un cliente y abre Perfil > Editar perfil. Guarda una dirección.
2. Compra un producto con Comprar ahora. Verifica el formulario de dirección y método de pago.
3. Compra desde el carrito.
4. Compra una promoción (sin usar el botón Agregar al carrito para esa prueba).
5. Revisa Firestore: `clientes` debe tener `direccion`; `pedidos` debe contener el folio; `ventas` debe conservar un documento por producto con `folio_pedido`.
6. Imprime el ticket desde la pantalla de compra exitosa.
7. Comprueba que el inventario disminuya y que el historial siga mostrando las ventas.

## Alcance de pago
Los métodos de pago son demostrativos. No se almacena información de tarjetas ni se conecta con una pasarela real.
