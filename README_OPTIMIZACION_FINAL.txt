PrediVent - OPTIMIZACION FINAL DE LECTURAS FIRESTORE

Este paquete integra de una sola vez las optimizaciones trabajadas para reducir
el consumo de lecturas de Firestore sin cambiar la finalidad del sistema.

CAMBIOS INCLUIDOS
1. Catalogo de productos con cache de 30 segundos.
2. obtener_producto() reutiliza el cache cuando el producto ya fue cargado.
3. Inventario/productos invalidan cache cuando se crean, editan, eliminan o se modifica inventario.
4. Historial mensual/anual filtra las ventas directamente en Firestore.
5. Ventas nuevas guardan snapshots: producto_nombre, cliente_nombre y empleado_nombre.
6. Historial administrativo usa esos snapshots y solo consulta documentos antiguos que no los tienen.
7. Alta de clientes, empleados y proveedores usa max(ID)+1 con una sola lectura en vez de leer toda la coleccion.
8. Cache de 30 segundos para listas de clientes, empleados y proveedores.
9. obtener_cliente(), obtener_empleado() y obtener_proveedor() reutilizan esas caches cuando es posible.
10. Login de cliente nuevo busca directamente por firebase_uid y normalmente reduce dos lecturas a una.
11. Compatibilidad: clientes antiguos sin firebase_uid siguen usando el flujo anterior como respaldo.
12. Venta realizada por empleado reutiliza los clientes/productos ya cargados y el nombre del empleado de la sesion; evita una lectura adicional del empleado.
13. Checkout reutiliza los productos ya validados para registrar las ventas.
14. Se conservaron las consultas con FieldFilter para evitar la advertencia de sintaxis antigua de Firestore.
15. Se conserva el endpoint correcto AgregarEmpleado en el historial administrativo.

IMPORTANTE
- No incluye .env, credenciales Firebase, .git ni .venv.
- Antes de probar, coloca tu .env y la credencial Firebase en sus ubicaciones habituales.
- La optimizacion de caches dura 30 segundos; despues se vuelve a consultar Firestore.
- El cambio de IDs usa max(ID)+1 en lugar de buscar huecos.
- No se modifico la logica del modelo de prediccion.
- Mientras la cuota de Firestore este agotada, no hagas pruebas repetitivas de login/catalogo.
