from firebase_config import firestore_db
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time

# ============================================================
# CONFIGURACIÓN
# ============================================================

db = firestore_db

COLECCION_PRODUCTOS = "productos"

# Cache corta para pantallas que vuelven a solicitar la lista completa
# de productos. No se usa para validar inventario en una compra.
_PRODUCTOS_CACHE = None
_PRODUCTOS_CACHE_TIMESTAMP = 0.0
_PRODUCTOS_CACHE_TTL = 30.0
_PRODUCTO_CACHE = {}

# Cachés cortas para catálogos administrativos. Evitan volver a leer
# colecciones completas cuando el usuario navega entre pantallas o
# vuelve a enviar un formulario en pocos segundos.
_CLIENTES_CACHE = None
_CLIENTES_CACHE_TIMESTAMP = 0.0
_EMPLEADOS_CACHE = None
_EMPLEADOS_CACHE_TIMESTAMP = 0.0
_PROVEEDORES_CACHE = None
_PROVEEDORES_CACHE_TIMESTAMP = 0.0
_CATALOGOS_CACHE_TTL = 30.0
_CLIENTE_CACHE = {}
_EMPLEADO_CACHE = {}
_PROVEEDOR_CACHE = {}


def limpiar_cache_productos():
    """Fuerza la próxima consulta de productos a ir a Firestore."""
    global _PRODUCTOS_CACHE, _PRODUCTOS_CACHE_TIMESTAMP, _PRODUCTO_CACHE
    _PRODUCTOS_CACHE = None
    _PRODUCTOS_CACHE_TIMESTAMP = 0.0
    _PRODUCTO_CACHE = {}


def limpiar_cache_clientes():
    global _CLIENTES_CACHE, _CLIENTES_CACHE_TIMESTAMP, _CLIENTE_CACHE
    _CLIENTES_CACHE = None
    _CLIENTES_CACHE_TIMESTAMP = 0.0
    _CLIENTE_CACHE = {}


def limpiar_cache_empleados():
    global _EMPLEADOS_CACHE, _EMPLEADOS_CACHE_TIMESTAMP, _EMPLEADO_CACHE
    _EMPLEADOS_CACHE = None
    _EMPLEADOS_CACHE_TIMESTAMP = 0.0
    _EMPLEADO_CACHE = {}


def limpiar_cache_proveedores():
    global _PROVEEDORES_CACHE, _PROVEEDORES_CACHE_TIMESTAMP, _PROVEEDOR_CACHE
    _PROVEEDORES_CACHE = None
    _PROVEEDORES_CACHE_TIMESTAMP = 0.0
    _PROVEEDOR_CACHE = {}


# ============================================================
# PRODUCTOS
# ============================================================

def obtener_productos():
    """
    Obtiene todos los productos desde Firestore.

    Durante 30 segundos reutiliza la lista ya obtenida para evitar
    gastar ~99 lecturas cada vez que una pantalla vuelve a cargar
    el catálogo. Las operaciones que modifican inventario/productos
    invalidan este cache.
    """
    global _PRODUCTOS_CACHE, _PRODUCTOS_CACHE_TIMESTAMP

    ahora = time.monotonic()

    if (
        _PRODUCTOS_CACHE is not None
        and ahora - _PRODUCTOS_CACHE_TIMESTAMP < _PRODUCTOS_CACHE_TTL
    ):
        return [producto.copy() for producto in _PRODUCTOS_CACHE]

    productos = []

    documentos = (
        db.collection(COLECCION_PRODUCTOS)
        .order_by("id_producto")
        .stream()
    )

    for documento in documentos:
        producto = documento.to_dict()
        productos.append(producto)

    _PRODUCTOS_CACHE = [producto.copy() for producto in productos]
    _PRODUCTOS_CACHE_TIMESTAMP = ahora

    _PRODUCTO_CACHE.clear()
    for producto in productos:
        if producto.get("id_producto") is not None:
            _PRODUCTO_CACHE[str(producto["id_producto"])] = producto.copy()

    return [producto.copy() for producto in productos]

def obtener_producto(id_producto):
    """Obtiene un producto específico usando caché cuando está disponible."""
    global _PRODUCTO_CACHE

    clave = str(id_producto)
    ahora = time.monotonic()

    if (_PRODUCTOS_CACHE is not None
            and ahora - _PRODUCTOS_CACHE_TIMESTAMP < _PRODUCTOS_CACHE_TTL
            and clave in _PRODUCTO_CACHE):
        return _PRODUCTO_CACHE[clave].copy()

    documento = (
        db.collection(COLECCION_PRODUCTOS)
        .document(clave)
        .get()
    )

    if documento.exists:
        producto = documento.to_dict()
        _PRODUCTO_CACHE[clave] = producto.copy()
        return producto

    return None

def obtener_siguiente_id():
    """Obtiene el siguiente ID usando solo la lectura del producto con ID máximo."""
    documentos = (
        db.collection(COLECCION_PRODUCTOS)
        .order_by("id_producto", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )

    for documento in documentos:
        producto = documento.to_dict()
        try:
            return int(producto.get("id_producto", 0)) + 1
        except (TypeError, ValueError):
            return 1

    return 1


def crear_producto(
        id_provedor,
        nombre_producto,
        cantidad,
        descripcion,
        precio,
        ruta_imagen
):
    """
    Guarda un nuevo producto en Firestore.
    """
    id_producto = obtener_siguiente_id()

    producto = {
        "id_producto": id_producto,
        "id_provedor": int(id_provedor),
        "nombre_producto": nombre_producto,
        "cantidad": int(cantidad),
        "descripcion": descripcion,
        "precio": int(precio),
        "RutaImagen": ruta_imagen
    }

    db.collection(COLECCION_PRODUCTOS) \
        .document(str(id_producto)) \
        .set(producto)

    limpiar_cache_productos()

    return producto


def actualizar_producto(
        id_producto,
        id_provedor,
        nombre_producto,
        cantidad,
        descripcion,
        precio,
        ruta_imagen
):
    """
    Actualiza un producto existente.
    """
    producto = {
        "id_producto": int(id_producto),
        "id_provedor": int(id_provedor),
        "nombre_producto": nombre_producto,
        "cantidad": int(cantidad),
        "descripcion": descripcion,
        "precio": int(precio),
        "RutaImagen": ruta_imagen
    }

    db.collection(COLECCION_PRODUCTOS) \
        .document(str(id_producto)) \
        .set(producto)

    limpiar_cache_productos()

    return producto


def eliminar_producto(id_producto):
    """
    Elimina un producto de Firestore.
    """
    db.collection(COLECCION_PRODUCTOS) \
        .document(str(id_producto)) \
        .delete()

    limpiar_cache_productos()


# ============================================================
# USUARIOS
# ============================================================

def obtener_usuario_por_correo(correo):
    """
    Busca un usuario en Firestore por su correo.
    """
    documentos = (
        db.collection("usuarios")
        .where(filter=FieldFilter("correo", "==", correo))
        .limit(1)
        .stream()
    )

    for documento in documentos:
        usuario = documento.to_dict()
        usuario["document_id"] = documento.id
        return usuario

    return None


def _obtener_siguiente_id_por_campo(coleccion, campo):
    """Obtiene max(ID)+1 leyendo solamente el documento con ID más alto."""
    documentos = (
        db.collection(coleccion)
        .order_by(campo, direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )

    for documento in documentos:
        datos = documento.to_dict()
        try:
            return int(datos.get(campo, 0)) + 1
        except (TypeError, ValueError):
            break

    return 1


# ============================================================
# CLIENTES
# ============================================================

def obtener_cliente_por_firebase_uid(firebase_uid):
    """Busca directamente el cliente por el UID de Firebase Authentication."""
    documentos = (
        db.collection("clientes")
        .where(filter=FieldFilter("firebase_uid", "==", firebase_uid))
        .limit(1)
        .stream()
    )

    for documento in documentos:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        _CLIENTE_CACHE[str(cliente.get("id_cliente"))] = cliente.copy()
        return cliente

    return None


def obtener_cliente_por_usuario(usuario_id):
    """
    Busca el cliente relacionado con un usuario.
    """
    documentos = (
        db.collection("clientes")
        .where(filter=FieldFilter("usuario_id", "==", usuario_id))
        .limit(1)
        .stream()
    )

    for documento in documentos:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        return cliente

    return None


def obtener_cliente(id_cliente):
    """Obtiene un cliente por ID usando caché cuando está disponible."""
    clave = str(id_cliente)
    ahora = time.monotonic()

    if (
        _CLIENTES_CACHE is not None
        and ahora - _CLIENTES_CACHE_TIMESTAMP < _CATALOGOS_CACHE_TTL
        and clave in _CLIENTE_CACHE
    ):
        return _CLIENTE_CACHE[clave].copy()

    documento = db.collection("clientes").document(clave).get()

    if documento.exists:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        _CLIENTE_CACHE[clave] = cliente.copy()
        return cliente

    return None


def obtener_clientes():
    """Obtiene todos los clientes con una caché corta de 30 segundos."""
    global _CLIENTES_CACHE, _CLIENTES_CACHE_TIMESTAMP, _CLIENTE_CACHE

    ahora = time.monotonic()

    if (
        _CLIENTES_CACHE is not None
        and ahora - _CLIENTES_CACHE_TIMESTAMP < _CATALOGOS_CACHE_TTL
    ):
        return [cliente.copy() for cliente in _CLIENTES_CACHE]

    clientes = []
    documentos = db.collection("clientes").order_by("id_cliente").stream()

    for documento in documentos:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        clientes.append(cliente)

    _CLIENTES_CACHE = [cliente.copy() for cliente in clientes]
    _CLIENTES_CACHE_TIMESTAMP = ahora
    _CLIENTE_CACHE.clear()

    for cliente in clientes:
        if cliente.get("id_cliente") is not None:
            _CLIENTE_CACHE[str(cliente["id_cliente"])] = cliente.copy()

    return [cliente.copy() for cliente in clientes]

def agregar_cliente(cliente):
    """
    Agrega un cliente desde un formulario.
    """
    clientes_ref = db.collection("clientes")
    nuevo_id = _obtener_siguiente_id_por_campo("clientes", "id_cliente")

    clientes_ref.document(str(nuevo_id)).set({
        "id_cliente": nuevo_id,
        "nombre": cliente.nombre.data,
        "correo": cliente.correo.data,
        "telefono": cliente.numero_telefono.data,
        "contraseña": cliente.contraseña.data
    })

    limpiar_cache_clientes()
    return nuevo_id


def registrar_cliente(
        nombre,
        correo,
        numero_telefono,
        contraseña=None,
        firebase_uid=None
):
    """
    Registra un usuario y su cliente relacionado.

    Para usuarios nuevos autenticados con Firebase, la contraseña NO se
    almacena en Firestore. Firebase Authentication es quien la gestiona.
    El parámetro contraseña se conserva opcionalmente para compatibilidad
    con registros antiguos.
    """

    usuarios_ref = db.collection("usuarios")
    nuevo_id = _obtener_siguiente_id_por_campo("usuarios", "id_usuario")

    usuario_data = {
        "id_usuario": nuevo_id,
        "correo": correo
    }

    if firebase_uid:
        usuario_data["firebase_uid"] = firebase_uid

    # Solo conserva contraseña si se está utilizando el flujo legado.
    if contraseña is not None:
        usuario_data["contraseña"] = contraseña

    usuarios_ref.document(str(nuevo_id)).set(usuario_data)

    cliente_data = {
        "id_cliente": nuevo_id,
        "usuario_id": str(nuevo_id),
        "nombre": nombre,
        "correo": correo,
        "telefono": numero_telefono
    }

    if firebase_uid:
        cliente_data["firebase_uid"] = firebase_uid

    if contraseña is not None:
        cliente_data["contraseña"] = contraseña

    db.collection("clientes").document(str(nuevo_id)).set(cliente_data)
    limpiar_cache_clientes()

    return nuevo_id


def actualizar_cliente(
        id_cliente,
        nombre,
        numero_telefono,
        correo,
        contraseña
):
    """
    Actualiza un cliente existente.
    """
    db.collection("clientes") \
        .document(str(id_cliente)) \
        .update({
            "nombre": nombre,
            "telefono": numero_telefono,
            "correo": correo,
            "contraseña": contraseña
        })

    limpiar_cache_clientes()
    return True


def eliminar_cliente(id_cliente):
    """
    Elimina un cliente de Firestore.
    """
    db.collection("clientes") \
        .document(str(id_cliente)) \
        .delete()
    limpiar_cache_clientes()

def actualizar_perfil_cliente(
        id_cliente,
        nombre,
        correo,
        numero_telefono,
        contraseña
):
    """
    Actualiza el perfil de un cliente.
    """
    documentos = (
        db.collection("clientes")
        .where(filter=FieldFilter("id_cliente", "==", int(id_cliente)))
        .limit(1)
        .stream()
    )

    for documento in documentos:
        documento.reference.update({
            "nombre": nombre,
            "correo": correo,
            "telefono": numero_telefono,
            "contraseña": contraseña
        })

        limpiar_cache_clientes()
        return True

    return False
# ============================================================
# EMPLEADOS
# ============================================================

def obtener_empleado_por_correo(correo):
    """
    Busca un empleado en Firestore por su correo.
    """
    documentos = (
        db.collection("empleados")
        .where(filter=FieldFilter("correo_empleado", "==", correo))
        .limit(1)
        .stream()
    )

    for documento in documentos:
        empleado = documento.to_dict()
        empleado["document_id"] = documento.id
        return empleado

    return None


def obtener_empleados():
    """Obtiene todos los empleados con una caché corta de 30 segundos."""
    global _EMPLEADOS_CACHE, _EMPLEADOS_CACHE_TIMESTAMP, _EMPLEADO_CACHE

    ahora = time.monotonic()

    if (
        _EMPLEADOS_CACHE is not None
        and ahora - _EMPLEADOS_CACHE_TIMESTAMP < _CATALOGOS_CACHE_TTL
    ):
        return [empleado.copy() for empleado in _EMPLEADOS_CACHE]

    documentos = db.collection("empleados").stream()
    empleados = []

    for documento in documentos:
        empleado = documento.to_dict()
        empleado["document_id"] = documento.id
        empleados.append(empleado)

    empleados.sort(key=lambda x: x.get("id_empleado", 0))
    _EMPLEADOS_CACHE = [empleado.copy() for empleado in empleados]
    _EMPLEADOS_CACHE_TIMESTAMP = ahora
    _EMPLEADO_CACHE.clear()

    for empleado in empleados:
        if empleado.get("id_empleado") is not None:
            _EMPLEADO_CACHE[str(empleado["id_empleado"])] = empleado.copy()

    return [empleado.copy() for empleado in empleados]


def obtener_empleado(id_empleado):
    """Obtiene un empleado por ID usando caché cuando está disponible."""
    clave = str(id_empleado)
    ahora = time.monotonic()

    if (
        _EMPLEADOS_CACHE is not None
        and ahora - _EMPLEADOS_CACHE_TIMESTAMP < _CATALOGOS_CACHE_TTL
        and clave in _EMPLEADO_CACHE
    ):
        return _EMPLEADO_CACHE[clave].copy()

    documento = db.collection("empleados").document(clave).get()

    if documento.exists:
        empleado = documento.to_dict()
        empleado["document_id"] = documento.id
        _EMPLEADO_CACHE[clave] = empleado.copy()
        return empleado

    return None

def agregar_empleado(empleado):
    """
    Agrega un nuevo empleado a Firestore.
    La contraseña es administrada por Firebase Authentication.
    """

    empleados_ref = db.collection("empleados")
    nuevo_id = _obtener_siguiente_id_por_campo("empleados", "id_empleado")

    empleados_ref.document(str(nuevo_id)).set({
        "id_empleado": nuevo_id,
        "nombre_empleado": empleado.nombre_empleado,
        "tipo_empleado": empleado.tipo_empleado,
        "correo_empleado": empleado.correo_empleado,
        "telefono": empleado.numero_telefono
    })

    limpiar_cache_empleados()
    return nuevo_id


def actualizar_empleado(
        id_empleado,
        nombre_empleado,
        tipo_empleado,
        correo_empleado,
        numero_telefono
):
    """
    Actualiza los datos de un empleado existente.
    La contraseña es administrada por Firebase Authentication.
    """

    empleado = {
        "id_empleado": int(id_empleado),
        "nombre_empleado": nombre_empleado,
        "tipo_empleado": tipo_empleado,
        "correo_empleado": correo_empleado,
        "telefono": numero_telefono
    }

    db.collection("empleados") \
        .document(str(id_empleado)) \
        .set(empleado)
    limpiar_cache_empleados()

    return empleado


def eliminar_empleado(id_empleado):
    """
    Elimina un empleado de Firestore.
    """
    db.collection("empleados") \
        .document(str(id_empleado)) \
        .delete()
    limpiar_cache_empleados()


# ============================================================
# PROVEEDORES
# ============================================================

def obtener_proveedores():
    """Obtiene todos los proveedores con una caché corta de 30 segundos."""
    global _PROVEEDORES_CACHE, _PROVEEDORES_CACHE_TIMESTAMP, _PROVEEDOR_CACHE

    ahora = time.monotonic()

    if (
        _PROVEEDORES_CACHE is not None
        and ahora - _PROVEEDORES_CACHE_TIMESTAMP < _CATALOGOS_CACHE_TTL
    ):
        return [proveedor.copy() for proveedor in _PROVEEDORES_CACHE]

    documentos = db.collection("proveedores").stream()
    proveedores = []

    for documento in documentos:
        proveedor = documento.to_dict()
        proveedor["document_id"] = documento.id
        proveedores.append(proveedor)

    proveedores.sort(key=lambda x: int(x.get("id_provedor", 0)))
    _PROVEEDORES_CACHE = [proveedor.copy() for proveedor in proveedores]
    _PROVEEDORES_CACHE_TIMESTAMP = ahora
    _PROVEEDOR_CACHE.clear()

    for proveedor in proveedores:
        if proveedor.get("id_provedor") is not None:
            _PROVEEDOR_CACHE[str(proveedor["id_provedor"])] = proveedor.copy()

    return [proveedor.copy() for proveedor in proveedores]


def obtener_proveedor(id_provedor):
    """Obtiene un proveedor específico usando caché cuando está disponible."""
    clave = str(id_provedor)
    ahora = time.monotonic()

    if (
        _PROVEEDORES_CACHE is not None
        and ahora - _PROVEEDORES_CACHE_TIMESTAMP < _CATALOGOS_CACHE_TTL
        and clave in _PROVEEDOR_CACHE
    ):
        return _PROVEEDOR_CACHE[clave].copy()

    documento = db.collection("proveedores").document(clave).get()

    if documento.exists:
        proveedor = documento.to_dict()
        proveedor["document_id"] = documento.id
        _PROVEEDOR_CACHE[clave] = proveedor.copy()
        return proveedor

    return None

def agregar_proveedor(proveedor):
    """
    Agrega un nuevo proveedor a Firestore.
    """
    proveedores_ref = db.collection("proveedores")
    nuevo_id = _obtener_siguiente_id_por_campo("proveedores", "id_provedor")

    proveedores_ref.document(str(nuevo_id)).set({
        "id_provedor": nuevo_id,
        "nombre_provedor": proveedor.nombre_provedor,
        "correo": proveedor.correo,
        "telefono": proveedor.numero_telefono
    })

    limpiar_cache_proveedores()
    return nuevo_id


def actualizar_proveedor(
        id_provedor,
        nombre_provedor,
        correo,
        numero_telefono
):
    """
    Actualiza un proveedor existente.
    """
    proveedor = {
        "id_provedor": int(id_provedor),
        "nombre_provedor": nombre_provedor,
        "correo": correo,
        "telefono": numero_telefono
    }

    db.collection("proveedores") \
        .document(str(id_provedor)) \
        .set(proveedor)
    limpiar_cache_proveedores()

    return proveedor


def eliminar_proveedor(id_provedor):
    """
    Elimina un proveedor de Firestore.
    """
    db.collection("proveedores") \
        .document(str(id_provedor)) \
        .delete()
    limpiar_cache_proveedores()


# ============================================================
# CARRITO
# ============================================================

def obtener_carrito(id_cliente):
    """
    Obtiene el carrito de un cliente desde Firestore.
    """
    documento = (
        db.collection("carritos")
        .document(str(id_cliente))
        .get()
    )

    if documento.exists:
        datos = documento.to_dict()
        return datos.get("productos", [])

    return []


def agregar_al_carrito(id_cliente, id_producto):
    """
    Agrega un producto al carrito del cliente.
    Si ya existe, aumenta su cantidad.
    """
    productos = obtener_carrito(id_cliente)

    encontrado = False

    for producto in productos:

        if int(producto["id_producto"]) == int(id_producto):
            producto["cantidad"] = (
                int(producto.get("cantidad", 0)) + 1
            )
            encontrado = True
            break

    if not encontrado:
        productos.append({
            "id_producto": int(id_producto),
            "cantidad": 1
        })

    db.collection("carritos") \
        .document(str(id_cliente)) \
        .set({
            "id_cliente": int(id_cliente),
            "productos": productos
        })

    return productos


def disminuir_del_carrito(id_cliente, id_producto):
    """
    Disminuye en uno la cantidad de un producto.
    Si llega a cero, lo elimina.
    """
    productos = obtener_carrito(id_cliente)

    nuevos_productos = []

    for producto in productos:

        if int(producto["id_producto"]) == int(id_producto):

            cantidad = int(
                producto.get("cantidad", 0)
            ) - 1

            if cantidad > 0:
                producto["cantidad"] = cantidad
                nuevos_productos.append(producto)

        else:
            nuevos_productos.append(producto)

    db.collection("carritos") \
        .document(str(id_cliente)) \
        .set({
            "id_cliente": int(id_cliente),
            "productos": nuevos_productos
        })

    return nuevos_productos


def vaciar_carrito(id_cliente):
    """
    Vacía completamente el carrito.
    """
    db.collection("carritos") \
        .document(str(id_cliente)) \
        .set({
            "id_cliente": int(id_cliente),
            "productos": []
        })


# ============================================================
# VENTAS
# ============================================================

def registrar_venta(
        id_cliente=None,
        id_producto=None,
        cantidad=0,
        precio_unitario=0,
        id_empleado=None,
        producto_nombre=None,
        cliente_nombre=None,
        empleado_nombre=None
):
    """
    Registra una venta en Firestore.

    Toda venta debe estar asociada a un cliente.

    Si la venta fue realizada por un empleado,
    también se guarda el ID del empleado.
    """

    # ========================================================
    # VALIDAR CLIENTE
    # ========================================================

    if id_cliente is None:

        raise ValueError(
            "No se puede registrar una venta "
            "sin un cliente asociado."
        )

    # ========================================================
    # VALIDAR PRODUCTO
    # ========================================================

    if id_producto is None:

        raise ValueError(
            "No se puede registrar una venta "
            "sin producto."
        )

    # ========================================================
    # VALIDAR CANTIDAD
    # ========================================================

    cantidad = int(cantidad)

    if cantidad <= 0:

        raise ValueError(
            "La cantidad debe ser mayor que cero."
        )

    # ========================================================
    # VALIDAR PRECIO
    # ========================================================

    precio_unitario = float(
        precio_unitario
    )

    if precio_unitario < 0:

        raise ValueError(
            "El precio no puede ser negativo."
        )

    # ========================================================
    # CALCULAR TOTAL
    # ========================================================

    total = (
        cantidad *
        precio_unitario
    )

    # ========================================================
    # CREAR VENTA
    # ========================================================

    venta = {

        "id_cliente": int(
            id_cliente
        ),

        "productoID": str(
            id_producto
        ),

        "cantidad": cantidad,

        "precioUnitario": precio_unitario,

        "total": total,

        "fecha": firestore.SERVER_TIMESTAMP

    }

    # ========================================================
    # EMPLEADO QUE REGISTRÓ LA VENTA
    # ========================================================

    if id_empleado is not None:

        venta["id_empleado"] = int(
            id_empleado
        )

    # ========================================================
    # DATOS DE CONSULTA (SNAPSHOT)
    # ========================================================
    # Guardamos estos nombres junto con la venta para que el
    # historial administrativo no tenga que volver a consultar
    # productos/clientes/empleados para las ventas nuevas.

    if producto_nombre:
        venta["producto_nombre"] = str(
            producto_nombre
        )

    if cliente_nombre:
        venta["cliente_nombre"] = str(
            cliente_nombre
        )

    if empleado_nombre:
        venta["empleado_nombre"] = str(
            empleado_nombre
        )

    # ========================================================
    # GUARDAR EN FIRESTORE
    # ========================================================

    referencia = (
        db.collection("ventas")
        .document()
    )

    referencia.set(
        venta
    )

    return venta


def actualizar_inventario(id_producto, cantidad_vendida):
    """
    Descuenta del inventario la cantidad vendida.
    """
    referencia = (
        db.collection("productos")
        .document(str(id_producto))
    )

    documento = referencia.get()

    if not documento.exists:
        return False

    producto = documento.to_dict()

    cantidad_actual = int(
        producto.get(
            "cantidad",
            producto.get("cantida", 0)
        )
    )

    cantidad_vendida = int(cantidad_vendida)

    if cantidad_vendida > cantidad_actual:
        return False

    nueva_cantidad = cantidad_actual - cantidad_vendida

    referencia.update({
        "cantidad": nueva_cantidad
    })

    limpiar_cache_productos()

    return True

# ============================================================
# HISTORIAL
# ============================================================

class HistorialFirestore:
    def __init__(self, datos):
        self.id_producto = datos.get(
            "productoID",
            datos.get("id_producto")
        )

        try:
            self.cantidad = int(
                datos.get("cantidad", 0)
            )
        except (TypeError, ValueError):
            self.cantidad = 0

        try:
            self.precio_unitario = float(
                datos.get("precioUnitario", 0)
            )
        except (TypeError, ValueError):
            self.precio_unitario = 0.0

        try:
            self.total = float(
                datos.get("total", 0)
            )
        except (TypeError, ValueError):
            self.total = 0.0

        self.id_cliente = datos.get("id_cliente")

        # Fecha real de la venta almacenada en Firestore
        self.fecha = datos.get("fecha")

def obtener_historial_ventas_producto(id_producto):
    """
    Obtiene las ventas de un producto desde Firestore.
    """
    ventas = []

    documentos = (
        db.collection("ventas")
        .where(
            filter=FieldFilter(
                "productoID",
                "==",
                str(id_producto)
            )
        )
        .stream()
    )

    for documento in documentos:
        venta = documento.to_dict()
        ventas.append(
            HistorialFirestore(venta)
        )

    return ventas

def obtener_historial_cliente(id_cliente):

    """
    Obtiene todas las compras realizadas
    por un cliente desde Firestore.
    """

    historial = []

    documentos = (
        db.collection("ventas")
        .where(
            filter=FieldFilter(
                "id_cliente",
                "==",
                int(id_cliente)
            )
        )
        .stream()
    )

    for documento in documentos:

        venta = documento.to_dict()

        venta["document_id"] = documento.id

        historial.append(venta)

    # ========================================================
    # ORDENAR POR FECHA
    # MÁS RECIENTE PRIMERO
    # ========================================================

    def fecha_venta(venta):

        fecha = venta.get("fecha")

        if fecha is None:
            return datetime.min

        return fecha

    historial.sort(
        key=fecha_venta,
        reverse=True
    )

    return historial

def obtener_historial_ventas(filtro="todas"):
    """
    Obtiene el historial de ventas.

    Para "mensual" y "anual" el filtro se realiza directamente
    en Firestore para no descargar ventas que después se van a
    descartar en Python.
    """

    consulta = db.collection("ventas")

    # --------------------------------------------------------
    # FILTRO DE FECHAS EN FIRESTORE
    # --------------------------------------------------------

    if filtro in ("mensual", "anual"):

        zona_local = ZoneInfo("America/Mexico_City")
        ahora = datetime.now(zona_local)

        if filtro == "mensual":
            inicio_local = ahora.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            if inicio_local.month == 12:
                fin_local = inicio_local.replace(
                    year=inicio_local.year + 1,
                    month=1
                )
            else:
                fin_local = inicio_local.replace(
                    month=inicio_local.month + 1
                )

        else:
            inicio_local = ahora.replace(
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            fin_local = inicio_local.replace(
                year=inicio_local.year + 1
            )

        inicio_utc = inicio_local.astimezone(ZoneInfo("UTC"))
        fin_utc = fin_local.astimezone(ZoneInfo("UTC"))

        consulta = (
            consulta
            .where(
                filter=FieldFilter(
                    "fecha",
                    ">=",
                    inicio_utc
                )
            )
            .where(
                filter=FieldFilter(
                    "fecha",
                    "<",
                    fin_utc
                )
            )
        )

    # Ordenar en Firestore evita traer resultados sin orden para
    # después ordenarlos en Python.
    consulta = consulta.order_by(
        "fecha",
        direction=firestore.Query.DESCENDING
    )

    historial = []

    for documento in consulta.stream():
        venta = documento.to_dict()

        # Las ventas antiguas o incompletas pueden no tener fecha.
        if venta.get("fecha") is None:
            continue

        venta["document_id"] = documento.id
        historial.append(venta)

    return historial

