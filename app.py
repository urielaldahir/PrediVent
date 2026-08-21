from flask import Flask, render_template, request, url_for, session
from werkzeug.utils import redirect

from services.prediccion_service import prediccion_lineal, prediccion_bosque

from forms import *

from firestore_service import (
    # PRODUCTOS
    obtener_productos,
    obtener_producto,
    crear_producto,
    actualizar_producto,
    eliminar_producto,

    # CLIENTES
    obtener_usuario_por_correo,
    obtener_cliente_por_usuario,
    obtener_cliente,
    actualizar_cliente,
    actualizar_perfil_cliente,
    agregar_cliente,
    registrar_cliente,
    eliminar_cliente,
    obtener_clientes,
    obtener_historial_cliente,

    # EMPLEADOS
    obtener_empleados,
    obtener_empleado,
    actualizar_empleado,
    agregar_empleado,
    eliminar_empleado,
    obtener_empleado_por_correo,

    # PROVEEDORES
    agregar_proveedor,
    obtener_proveedores,
    obtener_proveedor,
    actualizar_proveedor,
    eliminar_proveedor,

    # CARRITO
    obtener_carrito,
    agregar_al_carrito,
    disminuir_del_carrito,
    vaciar_carrito,

    # VENTAS
    registrar_venta,
    actualizar_inventario,

    # HISTORIAL / PREDICCIÓN
    obtener_historial_ventas_producto
)

app = Flask(__name__)

app.config['SECRET_KEY'] = 'LlaveSecreta'

@app.route('/')  #Pagina principal
@app.route('/index')
@app.route('/index.html')


# ============================================================
# INICIO Y ACCESO
# ============================================================

def inicio():
    return render_template("index.html")


# ============================================================
# CLIENTES
# ============================================================

def agregarCliente():

    cliente = ClienteForm()

    if request.method == 'POST':

        if cliente.validate_on_submit():

            registrar_cliente(
                cliente.nombre.data,
                cliente.correo.data,
                cliente.numero_telefono.data,
                cliente.contraseña.data
            )

            return redirect(url_for('login'))

    return render_template(
        'RegistroCliente.html',
        forma=cliente
    )
def consultasClientes():

    clientes = obtener_clientes()

    return render_template(
        'consultas-cliente.html',
        cliente=clientes
    )
def editarCliente(id_cliente):

    cliente = obtener_cliente(id_cliente)

    if cliente is None:
        return "Cliente no encontrado", 404

    clienteForm = ClienteForm()

    if request.method == 'POST':

        if clienteForm.validate_on_submit():

            actualizar_cliente(
                id_cliente,
                clienteForm.nombre.data,
                clienteForm.numero_telefono.data,
                clienteForm.correo.data,
                clienteForm.contraseña.data
            )

            return redirect(url_for('consultasClientes'))

    else:

        clienteForm.nombre.data = cliente.get("nombre", "")
        clienteForm.numero_telefono.data = cliente.get("telefono", "")
        clienteForm.correo.data = cliente.get("correo", "")
        clienteForm.contraseña.data = cliente.get("contraseña", "")

    return render_template(
        "editar_cliente.html",
        forma=clienteForm
    )
def eliminarCliente(id_cliente):

    cliente = obtener_cliente(id_cliente)

    if cliente is None:
        return "Cliente no encontrado", 404

    eliminar_cliente(id_cliente)

    return redirect(url_for('consultasClientes'))
def login():

    if 'cliente' in session:
        return redirect(url_for('HomeClientes'))

    if request.method == 'POST':

        correo = request.form['email']
        contraseña = request.form['password']

        cliente = obtener_usuario_por_correo(correo)

        if cliente is not None and cliente.get('contraseña') == contraseña:

            usuario_id = cliente.get('document_id')

            cliente_data = obtener_cliente_por_usuario(usuario_id)

            if cliente_data is None:
                return "El usuario no tiene un perfil de cliente", 404

            session['cliente'] = cliente_data.get('id_cliente')

            return redirect(url_for('HomeClientes'))

        else:

            error = 'Correo o contraseña incorrectos'

            return render_template(
                'login.html',
                error=error
            )

    return render_template('login.html')
def HomeClientes():
    return render_template('PaginaUsuarios.html')
def logout():
    session.pop('cliente')
    return redirect(url_for('inicio'))
def editarPerfil(id_cliente):

    cliente = obtener_cliente(id_cliente)

    if cliente is None:
        return "Cliente no encontrado", 404

    clienteForm = ClienteForm2(
        data={
            "nombre": cliente.get("nombre", ""),
            "correo": cliente.get("correo", ""),
            "numero_telefono": cliente.get("telefono", ""),
            "contraseña": cliente.get("contraseña", "")
        }
    )

    if request.method == 'POST':

        if clienteForm.validate_on_submit():

            actualizado = actualizar_perfil_cliente(
                id_cliente,
                clienteForm.nombre.data,
                clienteForm.correo.data,
                clienteForm.numero_telefono.data,
                clienteForm.contraseña.data
            )

            if not actualizado:
                return "No se pudo actualizar el perfil", 400

            return redirect(url_for('perfil'))

    return render_template(
        "editar_perfil.html",
        forma=clienteForm
    )
def perfil():

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    cliente = obtener_cliente(id_cliente)

    if cliente is None:
        return "Cliente no encontrado", 404

    return render_template(
        'perfil.html',
        cliente=cliente
    )
def VerHistorial():

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    historial = obtener_historial_cliente(id_cliente)

    productos = []
    cantidades = {}

    for venta in historial:

        id_producto = venta.get("productoID")

        if id_producto is None:
            continue

        producto = obtener_producto(id_producto)

        if producto is not None:

            productos.append(producto)

            cantidades[int(id_producto)] = int(
                venta.get("cantidad", 1)
            )

    return render_template(
        "historial.html",
        producto=productos,
        cantidades=cantidades
    )


# ============================================================
# ADMINISTRACIÓN
# ============================================================

def AdminLogin():

    if 'empleado' in session:
        return redirect(url_for('HomeAdmin'))

    if request.method == 'POST':

        correo_empleado = request.form['email']
        contraseña = request.form['password']

        empleado = obtener_empleado_por_correo(correo_empleado)

        if empleado is not None and empleado.get('contraseña') == contraseña:

            session['empleado'] = empleado.get('id_empleado')

            if empleado.get('tipo_empleado') == 'admin':
                return redirect(url_for('HomeAdmin'))

        error = 'Correo o contraseña incorrectos'

        return render_template(
            'AdminLogin.html',
            error=error
        )

    return render_template('AdminLogin.html')
def HomeAdmin():
    return render_template('admin.html')
def logout2():
    session.pop('empleado', None)
    return redirect(url_for('login'))


# ============================================================
# EMPLEADOS
# ============================================================

def AgregarEmpleado():

    empleadoForm = EmpleadoFomr()

    if request.method == 'POST':

        if empleadoForm.validate_on_submit():

            class EmpleadoData:
                pass

            empleado = EmpleadoData()

            empleado.nombre_empleado = empleadoForm.nombre_empleado.data
            empleado.tipo_empleado = empleadoForm.tipo_empleado.data
            empleado.correo_empleado = empleadoForm.correo_empleado.data
            empleado.numero_telefono = empleadoForm.numero_telefono.data
            empleado.contraseña = empleadoForm.contraseña.data

            agregar_empleado(empleado)

            return redirect(url_for('HomeAdmin'))

    return render_template(
        'RegistroEmpleado.html',
        forma=empleadoForm
    )
def consultasEmpleados():
    empleados = obtener_empleados()
    return render_template('consultas-empleado.html', empleado=empleados)
def editarEmpleado(id_empleado):

    empleado = obtener_empleado(id_empleado)

    if empleado is None:
        return "Empleado no encontrado", 404

    empleadoForm = EmpleadoEditFomr()

    if request.method == 'POST':

        if empleadoForm.validate_on_submit():

            actualizar_empleado(
                id_empleado,
                empleadoForm.nombre_empleado.data,
                empleadoForm.tipo_empleado.data,
                empleadoForm.correo_empleado.data,
                empleadoForm.numero_telefono.data,
                empleadoForm.contraseña.data
            )

            return redirect(url_for('consultasEmpleados'))

    else:
        empleadoForm.nombre_empleado.data = empleado.get("nombre_empleado", "")
        empleadoForm.tipo_empleado.data = empleado.get("tipo_empleado", "")
        empleadoForm.correo_empleado.data = empleado.get("correo_empleado", "")
        empleadoForm.numero_telefono.data = empleado.get("telefono", "")
        empleadoForm.contraseña.data = empleado.get("contraseña", "")

    return render_template(
        "editar_empleado.html",
        forma=empleadoForm
    )
def eliminarEmpleado(id_empleado):

    empleado = obtener_empleado(id_empleado)

    if empleado is None:
        return "Empleado no encontrado", 404

    eliminar_empleado(id_empleado)

    return redirect(url_for('consultasEmpleados'))


# ============================================================
# PROVEEDORES
# ============================================================

def agregarProveedor():

    proveedor_form = ProvedorForm()

    # Obtener el siguiente ID desde Firestore
    proveedores = obtener_proveedores()

    if proveedores:
        ids = [
            int(p.get("id_provedor", 0))
            for p in proveedores
            if p.get("id_provedor") is not None
        ]

        max_id = max(ids) + 1 if ids else 1
    else:
        max_id = 1

    if request.method == 'POST':

        if proveedor_form.validate_on_submit():

            # Crear objeto temporal con los datos del formulario
            proveedor = type("Proveedor", (), {})()

            proveedor.nombre_provedor = proveedor_form.nombre_provedor.data
            proveedor.correo = proveedor_form.correo.data
            proveedor.numero_telefono = proveedor_form.numero_telefono.data

            # Guardar en Firestore
            agregar_proveedor(proveedor)

            return redirect(url_for('HomeAdmin'))

    return render_template(
        'RegistroProvedor.html',
        forma=proveedor_form,
        max_id=max_id
    )
def consultasProveedores():
    proveedor = obtener_proveedores()

    return render_template(
        'consultas-proveedor.html',
        proveedor=proveedor
    )
def editarProveedor(id_provedor):

    proveedor = obtener_proveedor(id_provedor)

    if proveedor is None:
        return "Proveedor no encontrado", 404

    proveedorForm = ProvedorForm()

    if request.method == 'POST':

        if proveedorForm.validate_on_submit():

            actualizar_proveedor(
                id_provedor,
                proveedorForm.nombre_provedor.data,
                proveedorForm.correo.data,
                proveedorForm.numero_telefono.data
            )

            return redirect(url_for('consultasProveedores'))

    else:
        proveedorForm.nombre_provedor.data = proveedor.get("nombre_provedor", "")
        proveedorForm.correo.data = proveedor.get("correo", "")
        proveedorForm.numero_telefono.data = proveedor.get("telefono", "")

    return render_template(
        "editar-provedor.html",
        forma=proveedorForm
    )
def eliminarProvedor(id_provedor):

    proveedor = obtener_proveedor(id_provedor)

    if proveedor is None:
        return "Proveedor no encontrado", 404

    eliminar_proveedor(id_provedor)

    return redirect(url_for('consultasProveedores'))


# ============================================================
# PRODUCTOS
# ============================================================

def agregarProducto():

    productoForm = ProductoForm()

    productos = obtener_productos()

    ids_existentes = {
        int(producto["id_producto"])
        for producto in productos
        if producto.get("id_producto") is not None
    }

    max_id = 1

    while max_id in ids_existentes:
        max_id += 1

    if request.method == 'POST':

        if productoForm.validate_on_submit():
            producto = crear_producto(
                id_provedor=productoForm.id_provedor.data,
                nombre_producto=productoForm.nombre_producto.data,
                cantidad=productoForm.cantidad.data,
                descripcion=productoForm.descripcion.data,
                precio=productoForm.precio.data,
                ruta_imagen=productoForm.RutaImagen.data
            )

            app.logger.info(
                f"Producto creado en Firestore: {producto}"
            )

            return redirect(url_for('HomeAdmin'))

    return render_template(
        'RegistroProducto.html',
        forma=productoForm,
        max_id=max_id
    )
def Catalogo():
    producto = obtener_productos()

    return render_template(
        'catalogo.html',
        producto=producto
    )
def consultasProducto():
    producto = obtener_productos()

    return render_template(
        'consultas-Producto.html',
        producto=producto
    )
def editarProducto(id_producto):

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    productoForm = ProductoForm(
        data={
            "id_provedor": producto.get("id_provedor"),
            "nombre_producto": producto.get("nombre_producto"),
            "cantidad": producto.get("cantidad"),
            "descripcion": producto.get("descripcion"),
            "precio": producto.get("precio"),
            "RutaImagen": producto.get("RutaImagen")
        }
    )

    if request.method == 'POST':

        if productoForm.validate_on_submit():

            actualizar_producto(
                id_producto=id_producto,
                id_provedor=productoForm.id_provedor.data,
                nombre_producto=productoForm.nombre_producto.data,
                cantidad=productoForm.cantidad.data,
                descripcion=productoForm.descripcion.data,
                precio=productoForm.precio.data,
                ruta_imagen=productoForm.RutaImagen.data
            )

            return redirect(
                url_for('consultasProducto')
            )

    return render_template(
        "editarProducto.html",
        forma=productoForm
    )
def eliminarProducto(id_producto):

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    eliminar_producto(id_producto)

    return redirect(
        url_for('consultasProducto')
    )
def prediccion_producto(id_producto):

    if 'empleado' not in session:
        return redirect(url_for('AdminLogin'))

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    historial = obtener_historial_ventas_producto(id_producto)

    res_lineal = prediccion_lineal(historial)
    res_bosque = prediccion_bosque(historial)

    return render_template(
        'prediccion.html',
        producto=producto["nombre_producto"],
        lineal=res_lineal,
        bosque=res_bosque,
        num_ventas=len(historial)
    )


# ============================================================
# CARRITO Y COMPRAS
# ============================================================

def CatalogoUsuarios():

    productos = obtener_productos()

    return render_template(
        'catalogo_usuario.html',
        producto=productos
    )
def agregar_carrito(id_producto):

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    agregar_al_carrito(id_cliente, id_producto)

    return redirect(url_for('miCarrito'))
def disminuir_carrito(id_producto):

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    disminuir_del_carrito(id_cliente, id_producto)

    return redirect(url_for('miCarrito'))
def vaciar_carrito_route():

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    vaciar_carrito(id_cliente)

    return redirect(url_for('miCarrito'))
def miCarrito():

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    carrito = obtener_carrito(id_cliente)

    productos_carrito = []
    total = 0

    for item in carrito:

        producto = obtener_producto(item["id_producto"])

        if producto is not None:

            cantidad = int(item.get("cantidad", 1))
            precio = float(producto.get("precio", 0))

            subtotal = cantidad * precio

            productos_carrito.append({
                "producto": producto,
                "cantidad": cantidad,
                "subtotal": subtotal
            })

            total += subtotal

    return render_template(
        "MiCarrito.html",
        carrito=productos_carrito,
        total=total
    )
def eliminar_carrito(id_producto):

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    disminuir_del_carrito(id_cliente, id_producto)

    return redirect(url_for('miCarrito'))
def Comprar():

    if 'cliente' not in session:
        return redirect(url_for('login'))

    id_cliente = session['cliente']

    carrito = obtener_carrito(id_cliente)

    if not carrito:
        return redirect(url_for('miCarrito'))

    # ==========================================
    # 1. VERIFICAR INVENTARIO
    # ==========================================

    for item in carrito:

        id_producto = item["id_producto"]
        cantidad = int(item.get("cantidad", 1))

        producto = obtener_producto(id_producto)

        if producto is None:
            return "Producto no encontrado", 404

        cantidad_disponible = int(
            producto.get(
                "cantidad",
                producto.get("cantida", 0)
            )
        )

        if cantidad > cantidad_disponible:
            return (
                f"No hay suficiente inventario de "
                f"{producto.get('nombre_producto', 'producto')}"
            ), 400

    # ==========================================
    # 2. REGISTRAR VENTAS Y DESCONTAR INVENTARIO
    # ==========================================

    for item in carrito:

        id_producto = item["id_producto"]
        cantidad = int(item.get("cantidad", 1))

        producto = obtener_producto(id_producto)

        precio = float(producto.get("precio", 0))

        # Registrar venta
        registrar_venta(
            id_cliente,
            id_producto,
            cantidad,
            precio
        )

        # Descontar inventario
        inventario_actualizado = actualizar_inventario(
            id_producto,
            cantidad
        )

        if not inventario_actualizado:
            return (
                f"No se pudo actualizar el inventario de "
                f"{producto.get('nombre_producto', 'producto')}"
            ), 400

    # ==========================================
    # 3. VACIAR CARRITO
    # ==========================================

    vaciar_carrito(id_cliente)

    # ==========================================
    # 4. REGRESAR AL INICIO
    # ==========================================

    return redirect(url_for('HomeClientes'))


# ============================================================
# CONSULTAS GENERALES
# ============================================================

def consultas():
    return render_template('consultas.html')


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True)