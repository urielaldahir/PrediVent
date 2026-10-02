from firebase_config import firestore_db
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# ============================================================
# CONFIGURACIÓN
# ============================================================

db = firestore_db

COLECCION_PRODUCTOS = "productos"


# ============================================================
# PRODUCTOS
# ============================================================

def obtener_productos():
    """
    Obtiene todos los productos desde Firestore.
    """
    productos = []

    documentos = (
        db.collection(COLECCION_PRODUCTOS)
        .order_by("id_producto")
        .stream()
    )

    for documento in documentos:
        producto = documento.to_dict()
        productos.append(producto)

    return productos

def obtener_producto(id_producto):
    """
    Obtiene un producto específico.
    """
    documento = (
        db.collection(COLECCION_PRODUCTOS)
        .document(str(id_producto))
        .get()
    )

    if documento.exists:
        return documento.to_dict()

    return None

def obtener_siguiente_id():
    """
    Obtiene el primer ID disponible empezando desde 1.
    """
    productos = obtener_productos()

    ids = {
        int(producto["id_producto"])
        for producto in productos
        if producto.get("id_producto") is not None
    }

    siguiente_id = 1

    while siguiente_id in ids:
        siguiente_id += 1

    return siguiente_id

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

    return producto


def eliminar_producto(id_producto):
    """
    Elimina un producto de Firestore.
    """
    db.collection(COLECCION_PRODUCTOS) \
        .document(str(id_producto)) \
        .delete()


# ============================================================
# USUARIOS
# ============================================================

def obtener_usuario_por_correo(correo):
    """
    Busca un usuario en Firestore por su correo.
    """
    documentos = (
        db.collection("usuarios")
        .where("correo", "==", correo)
        .limit(1)
        .stream()
    )

    for documento in documentos:
        usuario = documento.to_dict()
        usuario["document_id"] = documento.id
        return usuario

    return None


# ============================================================
# CLIENTES
# ============================================================

def obtener_cliente_por_usuario(usuario_id):
    """
    Busca el cliente relacionado con un usuario.
    """
    documentos = (
        db.collection("clientes")
        .where("usuario_id", "==", usuario_id)
        .limit(1)
        .stream()
    )

    for documento in documentos:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        return cliente

    return None


def obtener_cliente(id_cliente):
    """
    Obtiene un cliente por su ID desde Firestore.
    """
    documento = (
        db.collection("clientes")
        .document(str(id_cliente))
        .get()
    )

    if documento.exists:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        return cliente

    return None


def obtener_clientes():
    """
    Obtiene todos los clientes desde Firestore.
    """
    clientes = []

    documentos = (
        db.collection("clientes")
        .order_by("id_cliente")
        .stream()
    )

    for documento in documentos:
        cliente = documento.to_dict()
        cliente["document_id"] = documento.id
        clientes.append(cliente)

    return clientes


def agregar_cliente(cliente):
    """
    Agrega un cliente desde un formulario.
    """
    clientes_ref = db.collection("clientes")

    documentos = clientes_ref.stream()

    ids = []

    for documento in documentos:
        try:
            ids.append(int(documento.id))
        except ValueError:
            pass

    nuevo_id = max(ids) + 1 if ids else 1

    clientes_ref.document(str(nuevo_id)).set({
        "id_cliente": nuevo_id,
        "nombre": cliente.nombre.data,
        "correo": cliente.correo.data,
        "telefono": cliente.numero_telefono.data,
        "contraseña": cliente.contraseña.data
    })

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

    documentos = usuarios_ref.stream()

    ids = []

    for documento in documentos:
        try:
            ids.append(int(documento.id))
        except ValueError:
            pass

    nuevo_id = max(ids) + 1 if ids else 1

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

    return True


def eliminar_cliente(id_cliente):
    """
    Elimina un cliente de Firestore.
    """
    db.collection("clientes") \
        .document(str(id_cliente)) \
        .delete()

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
        .where("id_cliente", "==", int(id_cliente))
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
        .where("correo_empleado", "==", correo)
        .limit(1)
        .stream()
    )

    for documento in documentos:
        empleado = documento.to_dict()
        empleado["document_id"] = documento.id
        return empleado

    return None


def obtener_empleados():
    """
    Obtiene todos los empleados desde Firestore.
    """
    empleados_ref = db.collection("empleados")
    documentos = empleados_ref.stream()

    empleados = []

    for documento in documentos:
        empleado = documento.to_dict()
        empleados.append(empleado)

    empleados.sort(
        key=lambda x: x.get("id_empleado", 0)
    )

    return empleados


def obtener_empleado(id_empleado):
    """
    Obtiene un empleado por su ID desde Firestore.
    """
    documento = (
        db.collection("empleados")
        .document(str(id_empleado))
        .get()
    )

    if documento.exists:
        empleado = documento.to_dict()
        empleado["document_id"] = documento.id
        return empleado

    return None


def agregar_empleado(empleado):
    """
    Agrega un nuevo empleado a Firestore.
    La contraseña es administrada por Firebase Authentication.
    """

    empleados_ref = db.collection("empleados")

    documentos = empleados_ref.stream()

    ids = []

    for documento in documentos:
        try:
            ids.append(int(documento.id))
        except ValueError:
            pass

    nuevo_id = max(ids) + 1 if ids else 1

    empleados_ref.document(str(nuevo_id)).set({
        "id_empleado": nuevo_id,
        "nombre_empleado": empleado.nombre_empleado,
        "tipo_empleado": empleado.tipo_empleado,
        "correo_empleado": empleado.correo_empleado,
        "telefono": empleado.numero_telefono
    })

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

    return empleado


def eliminar_empleado(id_empleado):
    """
    Elimina un empleado de Firestore.
    """
    db.collection("empleados") \
        .document(str(id_empleado)) \
        .delete()


# ============================================================
# PROVEEDORES
# ============================================================

def obtener_proveedores():
    """
    Obtiene todos los proveedores desde Firestore.
    """
    documentos = (
        db.collection("proveedores")
        .stream()
    )

    proveedores = []

    for documento in documentos:
        proveedor = documento.to_dict()
        proveedores.append(proveedor)

    proveedores.sort(
        key=lambda x: int(x.get("id_provedor", 0))
    )

    return proveedores


def obtener_proveedor(id_provedor):
    """
    Obtiene un proveedor específico desde Firestore.
    """
    documento = (
        db.collection("proveedores")
        .document(str(id_provedor))
        .get()
    )

    if documento.exists:
        proveedor = documento.to_dict()
        proveedor["document_id"] = documento.id
        return proveedor

    return None


def agregar_proveedor(proveedor):
    """
    Agrega un nuevo proveedor a Firestore.
    """
    proveedores_ref = db.collection("proveedores")

    documentos = proveedores_ref.stream()

    ids = []

    for documento in documentos:
        try:
            ids.append(int(documento.id))
        except ValueError:
            pass

    nuevo_id = max(ids) + 1 if ids else 1

    proveedores_ref.document(str(nuevo_id)).set({
        "id_provedor": nuevo_id,
        "nombre_provedor": proveedor.nombre_provedor,
        "correo": proveedor.correo,
        "telefono": proveedor.numero_telefono
    })

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

    return proveedor


def eliminar_proveedor(id_provedor):
    """
    Elimina un proveedor de Firestore.
    """
    db.collection("proveedores") \
        .document(str(id_provedor)) \
        .delete()


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
        id_cliente,
        id_producto,
        cantidad,
        precio_unitario
):
    """
    Registra una venta individual en Firestore.
    """
    cantidad = int(cantidad)
    precio_unitario = float(precio_unitario)

    total = cantidad * precio_unitario

    venta = {
        "id_cliente": int(id_cliente),
        "productoID": str(id_producto),
        "cantidad": cantidad,
        "precioUnitario": precio_unitario,
        "total": total,
        "fecha": firestore.SERVER_TIMESTAMP
    }

    referencia = db.collection("ventas").document()

    referencia.set(venta)

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
        .where("id_cliente", "==", int(id_cliente))
        .stream()
    )

    for documento in documentos:
        venta = documento.to_dict()
        venta["document_id"] = documento.id
        historial.append(venta)

    return historial