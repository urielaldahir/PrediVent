import math

from flask import Flask, render_template, request, url_for, session
from werkzeug.utils import redirect
from firebase_admin import auth

from firebase_config import firestore_db
from auth_service import (
    crear_usuario_firebase,
    generar_y_guardar_codigo,
    verificar_codigo,
    iniciar_sesion_firebase,
    enviar_correo_recuperacion,
)

from services.prediccion_service import generar_prediccion

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


# ============================================================
# INICIO Y ACCESO
# ============================================================

@app.route('/')
@app.route('/index')
@app.route('/index.html')
def inicio():
    return render_template("index.html")


# ============================================================
# CLIENTES
# ============================================================

@app.route('/registro-cliente', methods=['GET', 'POST'])
def agregarCliente():

    cliente = ClienteForm()

    if request.method == 'POST':

        if cliente.validate_on_submit():

            correo = cliente.correo.data.strip().lower()
            contraseña = cliente.contraseña.data

            # Evita duplicados en el sistema actual.
            usuario_existente = obtener_usuario_por_correo(correo)

            if usuario_existente is not None:
                return render_template(
                    'RegistroCliente.html',
                    forma=cliente,
                    error='Ese correo ya está registrado.'
                )

            try:
                # La contraseña queda gestionada por Firebase Authentication.
                usuario_firebase = crear_usuario_firebase(
                    correo,
                    contraseña
                )

                datos_registro = {
                    'nombre': cliente.nombre.data,
                    'numero_telefono': cliente.numero_telefono.data,
                    'correo': correo
                }

                # Guardamos únicamente un hash del código en Firestore.
                generar_y_guardar_codigo(
                    firestore_db,
                    correo,
                    usuario_firebase.uid,
                    datos_registro
                )

                session['verificacion_uid'] = usuario_firebase.uid
                session['verificacion_correo'] = correo

                return redirect(url_for('verificarCorreo'))

            except auth.EmailAlreadyExistsError:
                return render_template(
                    'RegistroCliente.html',
                    forma=cliente,
                    error='Ese correo ya tiene una cuenta en Firebase.'
                )

            except Exception as e:
                print('Error durante el registro:', e)
                return render_template(
                    'RegistroCliente.html',
                    forma=cliente,
                    error='No se pudo enviar el código de verificación. Revisa la configuración del correo.'
                )

    return render_template(
        'RegistroCliente.html',
        forma=cliente
    )


@app.route('/verificar-correo', methods=['GET', 'POST'])
def verificarCorreo():

    uid = session.get('verificacion_uid')
    correo = session.get('verificacion_correo')

    if not uid or not correo:
        return redirect(url_for('agregarCliente'))

    if request.method == 'POST':

        codigo = request.form.get('codigo', '').strip()

        if not codigo.isdigit() or len(codigo) != 6:
            return render_template(
                'verificar_correo.html',
                correo=correo,
                error='Introduce un código de 6 dígitos.'
            )

        correcto, resultado = verificar_codigo(
            firestore_db,
            uid,
            codigo
        )

        if correcto:
            datos = resultado

            # Solo después de comprobar el código creamos el perfil en Firestore.
            registrar_cliente(
                datos['nombre'],
                datos['correo'],
                datos['numero_telefono'],
                firebase_uid=uid
            )

            session.pop('verificacion_uid', None)
            session.pop('verificacion_correo', None)

            return redirect(url_for('login', verificado='1'))

        return render_template(
            'verificar_correo.html',
            correo=correo,
            error=resultado
        )

    return render_template(
        'verificar_correo.html',
        correo=correo
    )


@app.route('/consultas/clientes')
def consultasClientes():

    clientes = obtener_clientes()

    return render_template(
        'consultas-cliente.html',
        cliente=clientes
    )


@app.route('/editar/cliente/<id_cliente>', methods=['GET', 'POST'])
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


@app.route('/eliminar/cliente/<id_cliente>')
def eliminarCliente(id_cliente):

    cliente = obtener_cliente(id_cliente)

    if cliente is None:
        return "Cliente no encontrado", 404

    eliminar_cliente(id_cliente)

    return redirect(url_for('consultasClientes'))


@app.route('/login', methods=['GET', 'POST'])
def login():

    if 'cliente' in session:
        return redirect(url_for('HomeClientes'))

    if request.method == 'POST':

        correo = request.form.get('email', '').strip().lower()
        contraseña = request.form.get('password', '')

        try:
            autenticado, respuesta = iniciar_sesion_firebase(
                correo,
                contraseña
            )

            if autenticado:

                uid = respuesta.get('localId')

                # Consultamos Firebase Authentication para obtener
                # el estado real de verificación del correo.
                usuario_firebase = auth.get_user(uid)

                if not usuario_firebase.email_verified:
                    return render_template(
                        'login.html',
                        error='Tu correo todavía no está verificado. Completa la verificación antes de iniciar sesión.'
                    )

                usuario = obtener_usuario_por_correo(correo)

                if usuario is None:
                    return render_template(
                        'login.html',
                        error='La cuenta existe en Firebase, pero todavía no tiene perfil en PrediVent.'
                    )

                cliente_data = obtener_cliente_por_usuario(
                    usuario.get('document_id')
                )

                if cliente_data is None:
                    return "El usuario no tiene un perfil de cliente", 404

                session['cliente'] = cliente_data.get('id_cliente')
                session['firebase_uid'] = uid

                return redirect(url_for('HomeClientes'))

            # Mensajes amigables para errores habituales de Firebase.
            if respuesta == 'EMAIL_NOT_FOUND':
                error = 'Correo o contraseña incorrectos'
            elif respuesta == 'INVALID_PASSWORD':
                error = 'Correo o contraseña incorrectos'
            elif respuesta == 'USER_DISABLED':
                error = 'Esta cuenta está deshabilitada.'
            else:
                error = 'Correo o contraseña incorrectos'

            return render_template('login.html', error=error)

        except Exception as e:
            print('Error durante el inicio de sesión:', e)
            return render_template(
                'login.html',
                error='No se pudo conectar con el servicio de autenticación.'
            )

    return render_template('login.html')

@app.route('/recuperar-contrasena', methods=['GET', 'POST'])
def recuperar_contrasena():

    if request.method == 'POST':

        correo = request.form.get('email', '').strip().lower()

        if not correo:
            return render_template(
                'recuperar_contrasena.html',
                error='Ingresa tu correo electrónico.'
            )

        try:
            enviar_correo_recuperacion(correo)

            return render_template(
                'recuperar_contrasena.html',
                mensaje='Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.'
            )

        except Exception as e:
            print('Error al recuperar contraseña:', e)

            return render_template(
                'recuperar_contrasena.html',
                error='No se pudo enviar el correo de recuperación.'
            )

    return render_template('recuperar_contrasena.html')


@app.route('/home-clientes')
def HomeClientes():
    return render_template('PaginaUsuarios.html')


@app.route('/logout')
def logout():

    session.pop('cliente', None)

    return redirect(url_for('inicio'))


@app.route('/editar/perfil/<id_cliente>', methods=['GET', 'POST'])
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


@app.route('/perfil')
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


@app.route('/historial')
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

@app.route('/admin-login', methods=['GET', 'POST'])
def AdminLogin():

    if 'empleado' in session:
        return redirect(url_for('HomeAdmin'))

    if request.method == 'POST':

        correo_empleado = request.form['email'].strip().lower()
        contraseña = request.form['password']

        # Solo permitimos el correo administrativo de PrediVent
        if correo_empleado != 'predivent.sistema@gmail.com':
            return render_template(
                'AdminLogin.html',
                error='Correo o contraseña incorrectos'
            )

        try:
            # Autenticación mediante Firebase Authentication
            autenticado, respuesta = iniciar_sesion_firebase(
                correo_empleado,
                contraseña
            )


            if autenticado:

                uid = respuesta.get('localId')

                usuario_firebase = auth.get_user(uid)

                print("EMAIL:", usuario_firebase.email)
                print("VERIFICADO:", usuario_firebase.email_verified)

                if usuario_firebase.email == 'predivent.sistema@gmail.com':
                    auth.update_user(
                        uid,
                        email_verified=True
                    )

                    auth.revoke_refresh_tokens(uid)

                    usuario_firebase = auth.get_user(uid)

                    print("ADMIN MARCADO COMO VERIFICADO")
                    print("VERIFICADO AHORA:", usuario_firebase.email_verified)

                usuario_firebase = auth.get_user(uid)

                if not usuario_firebase.email_verified:
                    return render_template(
                        'AdminLogin.html',
                        error='El correo del administrador no está verificado.'
                    )

                empleado = obtener_empleado_por_correo(
                    correo_empleado
                )

                if empleado is not None:
                    session['empleado'] = empleado.get(
                        'id_empleado'
                    )

                    session['firebase_uid'] = uid

                    return redirect(
                        url_for('HomeAdmin')
                    )

        except Exception as e:
            print('Error en login de administrador:', e)

        return render_template(
            'AdminLogin.html',
            error='Correo o contraseña incorrectos'
        )

    return render_template('AdminLogin.html')
@app.route('/admin')
def HomeAdmin():
    return render_template('admin.html')


@app.route('/logout-admin')
def logout2():

    session.pop('empleado', None)

    return redirect(url_for('login'))


# ============================================================
# EMPLEADOS
# ============================================================
#
@app.route('/agregar/empleado', methods=['GET', 'POST'])
def AgregarEmpleado():

    empleadoForm = EmpleadoFomr()

    if request.method == 'POST':

        if empleadoForm.validate_on_submit():

            class EmpleadoData:
                pass

            empleado = EmpleadoData()

            empleado.nombre_empleado = (
                empleadoForm.nombre_empleado.data
            )

            empleado.tipo_empleado = (
                empleadoForm.tipo_empleado.data
            )

            empleado.correo_empleado = (
                empleadoForm.correo_empleado.data
            )

            empleado.numero_telefono = (
                empleadoForm.numero_telefono.data
            )

            empleado.contraseña = (
                empleadoForm.contraseña.data
            )

            try:

                # Crear usuario en Firebase Authentication
                crear_usuario_firebase(
                    empleado.correo_empleado,
                    empleado.contraseña
                )

                # Guardar empleado en Firestore
                # La contraseña NO se guarda en Firestore
                agregar_empleado(empleado)

                return redirect(
                    url_for('HomeAdmin')
                )

            except Exception as e:

                print("ERROR AL CREAR EMPLEADO:", e)

                return render_template(
                    'RegistroEmpleado.html',
                    forma=empleadoForm,
                    error='No fue posible crear el empleado. Verifica que el correo no esté registrado.'
                )

    return render_template(
        'RegistroEmpleado.html',
        forma=empleadoForm
    )

@app.route('/consultas/empleados')
def consultasEmpleados():

    empleados = obtener_empleados()

    return render_template(
        'consultas-empleado.html',
        empleado=empleados
    )


@app.route('/editar/empleado/<id_empleado>', methods=['GET', 'POST'])
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

            return redirect(
                url_for('consultasEmpleados')
            )

    else:

        empleadoForm.nombre_empleado.data = (
            empleado.get("nombre_empleado", "")
        )

        empleadoForm.tipo_empleado.data = (
            empleado.get("tipo_empleado", "")
        )

        empleadoForm.correo_empleado.data = (
            empleado.get("correo_empleado", "")
        )

        empleadoForm.numero_telefono.data = (
            empleado.get("telefono", "")
        )

        empleadoForm.contraseña.data = (
            empleado.get("contraseña", "")
        )

    return render_template(
        "editar_empleado.html",
        forma=empleadoForm
    )


@app.route('/eliminar/empleado/<id_empleado>')
def eliminarEmpleado(id_empleado):

    empleado = obtener_empleado(id_empleado)

    if empleado is None:
        return "Empleado no encontrado", 404

    eliminar_empleado(id_empleado)

    return redirect(
        url_for('consultasEmpleados')
    )


# ============================================================
# PROVEEDORES
# ============================================================

@app.route('/agregar/proveedor', methods=['GET', 'POST'])
def agregarProveedor():

    proveedor_form = ProvedorForm()

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

            proveedor = type(
                "Proveedor",
                (),
                {}
            )()

            proveedor.nombre_provedor = (
                proveedor_form.nombre_provedor.data
            )

            proveedor.correo = (
                proveedor_form.correo.data
            )

            proveedor.numero_telefono = (
                proveedor_form.numero_telefono.data
            )

            agregar_proveedor(proveedor)

            return redirect(
                url_for('HomeAdmin')
            )

    return render_template(
        'RegistroProvedor.html',
        forma=proveedor_form,
        max_id=max_id
    )


@app.route('/consultas/proveedores')
def consultasProveedores():

    proveedor = obtener_proveedores()

    return render_template(
        'consultas-proveedor.html',
        proveedor=proveedor
    )


@app.route('/editar/provedor/<id_provedor>', methods=['GET', 'POST'])
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

            return redirect(
                url_for('consultasProveedores')
            )

    else:

        proveedorForm.nombre_provedor.data = (
            proveedor.get(
                "nombre_provedor",
                ""
            )
        )

        proveedorForm.correo.data = (
            proveedor.get(
                "correo",
                ""
            )
        )

        proveedorForm.numero_telefono.data = (
            proveedor.get(
                "telefono",
                ""
            )
        )

    return render_template(
        "editar-provedor.html",
        forma=proveedorForm
    )


@app.route('/eliminar/provedor/<id_provedor>')
def eliminarProvedor(id_provedor):

    proveedor = obtener_proveedor(id_provedor)

    if proveedor is None:
        return "Proveedor no encontrado", 404

    eliminar_proveedor(id_provedor)

    return redirect(
        url_for('consultasProveedores')
    )


# ============================================================
# PRODUCTOS
# ============================================================

@app.route('/agregar/producto', methods=['GET', 'POST'])
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

            return redirect(
                url_for('HomeAdmin')
            )

    return render_template(
        'RegistroProducto.html',
        forma=productoForm,
        max_id=max_id
    )


@app.route('/catalogo')
def Catalogo():

    producto = obtener_productos()

    return render_template(
        'catalogo.html',
        producto=producto
    )


@app.route('/consultas/productos')
def consultasProducto():

    producto = obtener_productos()

    return render_template(
        'consultas-Producto.html',
        producto=producto
    )


@app.route('/editar/producto/<id_producto>', methods=['GET', 'POST'])
def editarProducto(id_producto):

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    productoForm = ProductoForm(
        data={
            "id_provedor": producto.get(
                "id_provedor"
            ),

            "nombre_producto": producto.get(
                "nombre_producto"
            ),

            "cantidad": producto.get(
                "cantidad"
            ),

            "descripcion": producto.get(
                "descripcion"
            ),

            "precio": producto.get(
                "precio"
            ),

            "RutaImagen": producto.get(
                "RutaImagen"
            )
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


@app.route('/eliminar/producto/<id_producto>')
def eliminarProducto(id_producto):

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    eliminar_producto(id_producto)

    return redirect(
        url_for('consultasProducto')
    )


# ============================================================
# PREDICCIÓN DE DEMANDA
# ============================================================

@app.route('/predecir/producto/<id_producto>')
def prediccion_producto(id_producto):

    # --------------------------------------------------------
    # VERIFICAR SESIÓN DE ADMINISTRADOR
    # --------------------------------------------------------

    if 'empleado' not in session:

        return redirect(
            url_for('AdminLogin')
        )

    # --------------------------------------------------------
    # OBTENER PRODUCTO
    # --------------------------------------------------------

    producto = obtener_producto(
        id_producto
    )

    if producto is None:

        return "Producto no encontrado", 404

    # --------------------------------------------------------
    # OBTENER HISTORIAL DE VENTAS
    # --------------------------------------------------------

    historial = obtener_historial_ventas_producto(
        id_producto
    )

    # --------------------------------------------------------
    # GENERAR PREDICCIÓN
    # --------------------------------------------------------

    resultado = generar_prediccion(
        historial
    )

    # --------------------------------------------------------
    # OBTENER INVENTARIO ACTUAL
    # --------------------------------------------------------

    inventario_actual = producto.get(
        "cantidad",
        producto.get("cantida", 0)
    )

    try:

        inventario_actual = float(
            inventario_actual
        )

    except (
        TypeError,
        ValueError
    ):

        inventario_actual = 0.0

    # --------------------------------------------------------
    # VARIABLES DE INVENTARIO
    # --------------------------------------------------------

    demanda_7_dias = None

    diferencia_inventario = None

    reposicion_sugerida = None

    estado_inventario = "sin_datos"

    # --------------------------------------------------------
    # ANALIZAR INVENTARIO
    # --------------------------------------------------------

    if resultado.get("estado") == "ok":

        demanda_7_dias = resultado.get(
            "prediccion_seleccionada_7_dias",
            0
        )

        try:

            demanda_7_dias = float(
                demanda_7_dias
            )

        except (
            TypeError,
            ValueError
        ):

            demanda_7_dias = 0.0

        # ----------------------------------------------------
        # DIFERENCIA ENTRE INVENTARIO Y DEMANDA
        # ----------------------------------------------------

        diferencia_inventario = (
            inventario_actual
            - demanda_7_dias
        )

        # ----------------------------------------------------
        # ESTADO DEL INVENTARIO
        # ----------------------------------------------------

        if inventario_actual < demanda_7_dias:

            estado_inventario = "riesgo"

        elif inventario_actual <= (
            demanda_7_dias * 1.25
        ):

            estado_inventario = "precaucion"

        else:

            estado_inventario = "suficiente"

        # ----------------------------------------------------
        # REPOSICIÓN SUGERIDA
        # ----------------------------------------------------
        #
        # Si la demanda estimada supera el inventario,
        # se calcula cuántas unidades faltarían para
        # cubrir los próximos 7 días.
        #
        # Se redondea hacia arriba porque las unidades
        # de inventario son enteras.
        #
        # Ejemplo:
        #
        # Inventario = 10
        # Demanda = 16.5
        #
        # Faltante = 6.5
        # Reposición = 7
        #
        # ----------------------------------------------------

        if demanda_7_dias > inventario_actual:

            reposicion_sugerida = int(
                math.ceil(
                    demanda_7_dias
                    - inventario_actual
                )
            )

        else:

            reposicion_sugerida = 0

    # --------------------------------------------------------
    # RENDERIZAR DASHBOARD
    # --------------------------------------------------------

    return render_template(

        'prediccion.html',

        producto=producto.get(
            "nombre_producto",
            "Producto"
        ),

        resultado=resultado,

        inventario_actual=round(
            inventario_actual,
            2
        ),

        demanda_7_dias=(
            round(
                demanda_7_dias,
                2
            )
            if demanda_7_dias is not None
            else None
        ),

        diferencia_inventario=(
            round(
                diferencia_inventario,
                2
            )
            if diferencia_inventario is not None
            else None
        ),

        reposicion_sugerida=(
            reposicion_sugerida
        ),

        estado_inventario=(
            estado_inventario
        )
    )


# ============================================================
# CARRITO Y COMPRAS
# ============================================================

@app.route('/catalogo-usuario')
def CatalogoUsuarios():

    productos = obtener_productos()

    return render_template(
        'catalogo_usuario.html',
        producto=productos
    )


@app.route('/carrito/agregar/<id_producto>')
def agregar_carrito(id_producto):

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    producto = obtener_producto(
        id_producto
    )

    if producto is None:

        return "Producto no encontrado", 404

    agregar_al_carrito(
        id_cliente,
        id_producto
    )

    return redirect(
        url_for('miCarrito')
    )


@app.route('/carrito/disminuir/<id_producto>')
def disminuir_carrito(id_producto):

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    disminuir_del_carrito(
        id_cliente,
        id_producto
    )

    return redirect(
        url_for('miCarrito')
    )


@app.route('/carrito/vaciar')
def vaciar_carrito_route():

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    vaciar_carrito(
        id_cliente
    )

    return redirect(
        url_for('miCarrito')
    )


@app.route('/carrito')
def miCarrito():

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    carrito = obtener_carrito(
        id_cliente
    )

    productos_carrito = []

    total = 0

    for item in carrito:

        producto = obtener_producto(
            item["id_producto"]
        )

        if producto is not None:

            cantidad = int(
                item.get(
                    "cantidad",
                    1
                )
            )

            precio = float(
                producto.get(
                    "precio",
                    0
                )
            )

            subtotal = (
                cantidad * precio
            )

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


@app.route('/carrito/eliminar/<id_producto>')
def eliminar_carrito(id_producto):

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    disminuir_del_carrito(
        id_cliente,
        id_producto
    )

    return redirect(
        url_for('miCarrito')
    )


@app.route('/comprar')
def Comprar():

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    carrito = obtener_carrito(
        id_cliente
    )

    if not carrito:

        return redirect(
            url_for('miCarrito')
        )

    # ========================================================
    # 1. VERIFICAR INVENTARIO
    # ========================================================

    for item in carrito:

        id_producto = item["id_producto"]

        cantidad = int(
            item.get(
                "cantidad",
                1
            )
        )

        producto = obtener_producto(
            id_producto
        )

        if producto is None:

            return "Producto no encontrado", 404

        cantidad_disponible = int(
            producto.get(
                "cantidad",
                producto.get(
                    "cantida",
                    0
                )
            )
        )

        if cantidad > cantidad_disponible:

            return (
                f"No hay suficiente inventario de "
                f"{producto.get('nombre_producto', 'producto')}"
            ), 400

    # ========================================================
    # 2. REGISTRAR VENTAS Y DESCONTAR INVENTARIO
    # ========================================================

    for item in carrito:

        id_producto = item["id_producto"]

        cantidad = int(
            item.get(
                "cantidad",
                1
            )
        )

        producto = obtener_producto(
            id_producto
        )

        precio = float(
            producto.get(
                "precio",
                0
            )
        )

        # ----------------------------------------------------
        # REGISTRAR VENTA
        # ----------------------------------------------------

        registrar_venta(
            id_cliente,
            id_producto,
            cantidad,
            precio
        )

        # ----------------------------------------------------
        # DESCONTAR INVENTARIO
        # ----------------------------------------------------

        inventario_actualizado = actualizar_inventario(
            id_producto,
            cantidad
        )

        if not inventario_actualizado:

            return (
                f"No se pudo actualizar el inventario de "
                f"{producto.get('nombre_producto', 'producto')}"
            ), 400

    # ========================================================
    # 3. VACIAR CARRITO
    # ========================================================

    vaciar_carrito(
        id_cliente
    )

    # ========================================================
    # 4. REGRESAR AL INICIO
    # ========================================================

    return redirect(
        url_for('HomeClientes')
    )


# ============================================================
# CONSULTAS GENERALES
# ============================================================

@app.route('/consultas')
def consultas():

    return render_template(
        'consultas.html'
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )