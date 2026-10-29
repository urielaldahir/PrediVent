# PrediVent - módulo inicial de promociones

## Archivos agregados
- `promociones_service.py`: persistencia en Firestore, validación de campañas, estados por fechas y propuestas basadas en ventas/inventario.
- `templates/promociones_admin.html`: panel de administración de promociones.
- `app.py`: rutas protegidas para listar, crear borradores, generar propuestas y aprobar/activar/desactivar/eliminar.
- `templates/admin.html`: acceso al módulo desde el panel del administrador.

## Cómo probar
1. Haz respaldo de tu proyecto actual.
2. Copia los archivos de esta versión a tu proyecto (o abre esta carpeta en tu entorno de pruebas).
3. Confirma que `.env` contiene la configuración de Firebase que ya usas; no se incluye por seguridad.
4. Ejecuta `python app.py`.
5. Inicia sesión como administrador y entra a **Promociones**.
6. Crea una campaña con fecha de inicio y fin, guárdala como borrador, apruébala y actívala.

## Importante sobre el alcance de esta entrega
Esta primera integración implementa el panel y la gestión de campañas en Firestore. Las propuestas se calculan mediante reglas y datos de ventas/inventario; no se conecta una API de IA generativa. El guardado de una promoción no modifica el precio base de los productos.

Antes de usar promociones para cobrar ventas reales, falta integrar y probar la aplicación del descuento en el carrito, compra directa y ventas de empleado, incluyendo el registro de redenciones de bienvenida por cliente y reglas de combinación. Por ahora no se debe considerar que los descuentos ya se estén aplicando en el cobro.
