import math

from flask import Flask, render_template, request, url_for, session
from werkzeug.utils import redirect
from firebase_admin import auth
from datetime import datetime

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
    obtener_cliente_por_firebase_uid,
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
    obtener_historial_ventas,
    obtener_historial_ventas_producto
)


app = Flask(__name__)

app.config['SECRET_KEY'] = 'LlaveSecreta'

from functools import wraps
# ============================================================
# INICIO Y ACCESO
# ============================================================

@app.route('/')
@app.route('/index')
@app.route('/index.html')
def inicio():
    return render_template("index.html")

def requiere_admin(func):
    @wraps(func)
    def funcion_protegida(*args, **kwargs):

        # No hay sesión iniciada
        if 'empleado' not in session:
            return redirect(url_for('AdminLogin'))

        # La sesión existe, pero no es administrador
        if session.get('tipo_empleado') != 'admin':
            return redirect(url_for('HomeEmpleado'))

        return func(*args, **kwargs)

    return funcion_protegida


def requiere_empleado(func):
    @wraps(func)
    def funcion_protegida(*args, **kwargs):

        # No hay sesión iniciada
        if 'empleado' not in session:
            return redirect(url_for('AdminLogin'))

        # Solo empleados o administradores
        if session.get('tipo_empleado') not in ['empleado', 'admin']:
            return redirect(url_for('inicio'))

        return func(*args, **kwargs)

    return funcion_protegida
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
                session['verificacion_tipo'] = 'cliente'

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
    tipo = session.get('verificacion_tipo')

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

            auth.update_user(uid, email_verified=True)   # <-- añadir

            datos = resultado

            # ==========================
            # CLIENTE
            # ==========================
            if tipo == 'cliente':

                registrar_cliente(
                    datos['nombre'],
                    datos['correo'],
                    datos['numero_telefono'],
                    firebase_uid=uid
                )

                destino = 'login'

            # ==========================
            # EMPLEADO
            # ==========================
            elif tipo == 'empleado':

                empleado_data = session.get(
                    'empleado_pendiente'
                )

                if not empleado_data:
                    return redirect(
                        url_for('AgregarEmpleado')
                    )

                class EmpleadoData:
                    pass

                empleado = EmpleadoData()

                empleado.nombre_empleado = (
                    empleado_data['nombre_empleado']
                )

                empleado.tipo_empleado = (
                    empleado_data['tipo_empleado']
                )

                empleado.correo_empleado = (
                    empleado_data['correo_empleado']
                )

                empleado.numero_telefono = (
                    empleado_data['numero_telefono']
                )

                # Se guarda el empleado en Firestore.
                # agregar_empleado() NO guarda contraseña.
                agregar_empleado(empleado)

                destino = 'AdminLogin'

            else:
                return "Tipo de verificación no válido", 400

            # Limpiar datos temporales
            session.pop('verificacion_uid', None)
            session.pop('verificacion_correo', None)
            session.pop('verificacion_tipo', None)
            session.pop('empleado_pendiente', None)

            return redirect(
                url_for(destino)
            )

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
@requiere_admin
def consultasClientes():

    clientes = obtener_clientes()

    return render_template(
        'consultas-cliente.html',
        cliente=clientes
    )


@app.route('/editar/cliente/<id_cliente>', methods=['GET', 'POST'])
@requiere_admin
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
@requiere_admin
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

                # Los clientes nuevos guardan el UID de Firebase en su perfil,
                # por lo que podemos resolver el cliente con una sola lectura.
                cliente_data = obtener_cliente_por_firebase_uid(uid)

                # Compatibilidad con clientes antiguos que todavía no tienen
                # firebase_uid guardado.
                if cliente_data is None:
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

    if 'cliente' not in session:
        return redirect(url_for('login'))

    return render_template('PaginaUsuarios.html')


@app.route('/logout')
def logout():

    session.pop('cliente', None)

    return redirect(url_for('inicio'))


@app.route('/editar/perfil/<id_cliente>', methods=['GET', 'POST'])
def editarPerfil(id_cliente):

    if 'cliente' not in session:
        return redirect(url_for('login'))

    if str(session.get('cliente')) != str(id_cliente):
        return "No tienes permiso para editar este perfil", 403

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

    # ========================================================
    # OBTENER FILTRO
    # ========================================================

    filtro = request.args.get(
        'filtro',
        'todos'
    )

    # ========================================================
    # OBTENER HISTORIAL
    # ========================================================

    historial = obtener_historial_cliente(
        id_cliente
    )

    historial_completo = []

    # Fecha actual
    ahora = datetime.now()

    for venta in historial:

        id_producto = venta.get("productoID")

        if id_producto is None:
            continue

        # ====================================================
        # FECHA DE LA VENTA
        # ====================================================

        fecha = venta.get("fecha")

        # ====================================================
        # FILTRO: ESTE MES
        # ====================================================

        if filtro == "mes":

            if fecha is None:
                continue

            if (
                fecha.year != ahora.year
                or fecha.month != ahora.month
            ):
                continue

        # ====================================================
        # FILTRO: ESTE AÑO
        # ====================================================

        elif filtro == "ano":

            if fecha is None:
                continue

            if fecha.year != ahora.year:
                continue

        # ====================================================
        # OBTENER PRODUCTO
        # ====================================================

        producto = obtener_producto(
            id_producto
        )

        if producto is None:
            continue

        # ====================================================
        # FORMATEAR FECHA
        # ====================================================

        fecha_formateada = ""

        if fecha is not None:

            fecha_formateada = fecha.strftime(
                "%d/%m/%Y %H:%M"
            )

        # ====================================================
        # AGREGAR VENTA
        # ====================================================

        historial_completo.append({

            "id_producto": id_producto,

            "nombre": producto.get(
                "nombre_producto",
                "Producto"
            ),

            "descripcion": producto.get(
                "descripcion",
                ""
            ),

            "cantidad": int(
                venta.get(
                    "cantidad",
                    0
                )
            ),

            "precio": float(
                venta.get(
                    "precioUnitario",
                    0
                )
            ),

            "total": float(
                venta.get(
                    "total",
                    0
                )
            ),

            "fecha": fecha,

            "fecha_formateada": fecha_formateada

        })

    # ========================================================
    # ORDENAR
    # MÁS RECIENTE PRIMERO
    # ========================================================

    historial_completo.sort(
        key=lambda venta:
            venta["fecha"] or datetime.min,
        reverse=True
    )

    # ========================================================
    # MOSTRAR HISTORIAL
    # ========================================================

    return render_template(
        "historial.html",
        historial=historial_completo,
        filtro=filtro
    )

# ============================================================
# ADMINISTRACIÓN
# ============================================================

@app.route('/admin-login', methods=['GET', 'POST'])
def AdminLogin():

    # --------------------------------------------------------
    # SI YA HAY UNA SESIÓN ACTIVA
    # --------------------------------------------------------

    if 'empleado' in session:

        if session.get('tipo_empleado') == 'admin':
            return redirect(url_for('HomeAdmin'))

        elif session.get('tipo_empleado') == 'empleado':
            return redirect(url_for('HomeEmpleado'))

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    if request.method == 'POST':

        correo_empleado = request.form.get(
            'email',
            ''
        ).strip().lower()

        contraseña = request.form.get(
            'password',
            ''
        )

        try:

            # ------------------------------------------------
            # AUTENTICAR CON FIREBASE
            # ------------------------------------------------

            autenticado, respuesta = iniciar_sesion_firebase(
                correo_empleado,
                contraseña
            )

            if not autenticado:

                return render_template(
                    'AdminLogin.html',
                    error='Correo o contraseña incorrectos'
                )

            # ------------------------------------------------
            # OBTENER UID
            # ------------------------------------------------

            uid = respuesta.get('localId')

            if not uid:

                return render_template(
                    'AdminLogin.html',
                    error='No se pudo validar la cuenta'
                )

            # ------------------------------------------------
            # OBTENER USUARIO DE FIREBASE
            # ------------------------------------------------

            usuario_firebase = auth.get_user(uid)

            if usuario_firebase.email.lower() != correo_empleado:

                return render_template(
                    'AdminLogin.html',
                    error='Correo o contraseña incorrectos'
                )

            # ------------------------------------------------
            # VERIFICAR CORREO
            # ------------------------------------------------

            if not usuario_firebase.email_verified:

                return render_template(
                    'AdminLogin.html',
                    error='Tu correo todavía no está verificado.'
                )

            # ------------------------------------------------
            # BUSCAR EMPLEADO EN FIRESTORE
            # ------------------------------------------------

            empleado = obtener_empleado_por_correo(
                correo_empleado
            )

            if empleado is None:

                return render_template(
                    'AdminLogin.html',
                    error='El empleado no está registrado en el sistema'
                )

            # ------------------------------------------------
            # OBTENER TIPO DE EMPLEADO
            # ------------------------------------------------

            tipo_empleado = empleado.get(
                'tipo_empleado',
                ''
            )

            tipo_empleado = tipo_empleado.strip().lower()

            # ------------------------------------------------
            # GUARDAR DATOS EN SESIÓN
            # ------------------------------------------------

            session['empleado'] = empleado.get(
                'id_empleado'
            )

            session['firebase_uid'] = uid

            session['nombre_empleado'] = empleado.get(
                'nombre_empleado',
                'Empleado'
            )

            session['tipo_empleado'] = tipo_empleado

            session['correo_empleado'] = empleado.get(
                'correo_empleado'
            )

            # ------------------------------------------------
            # MOSTRAR INFORMACIÓN EN CONSOLA
            # ------------------------------------------------

            print('========================================')
            print('LOGIN CORRECTO')
            print('Correo:', correo_empleado)
            print('UID:', uid)
            print(
                'ID empleado:',
                empleado.get('id_empleado')
            )
            print(
                'Nombre:',
                empleado.get('nombre_empleado')
            )
            print('Tipo:', tipo_empleado)
            print('========================================')

            # ------------------------------------------------
            # REDIRECCIÓN SEGÚN EL TIPO
            # ------------------------------------------------

            if tipo_empleado == 'admin':

                return redirect(
                    url_for('HomeAdmin')
                )

            elif tipo_empleado == 'empleado':

                return redirect(
                    url_for('HomeEmpleado')
                )

            else:

                session.clear()

                return render_template(
                    'AdminLogin.html',
                    error='El tipo de usuario no está configurado correctamente'
                )

        except Exception as e:

            print('========================================')
            print('ERROR EN LOGIN')
            print(type(e).__name__)
            print(e)
            print('========================================')

            return render_template(
                'AdminLogin.html',
                error='Ocurrió un error al iniciar sesión'
            )

    return render_template(
        'AdminLogin.html'
    )


# ============================================================
# PANEL DEL ADMINISTRADOR
# ============================================================

@app.route('/admin')
def HomeAdmin():

    # No hay sesión
    if 'empleado' not in session:

        return redirect(
            url_for('AdminLogin')
        )

    # Si no es administrador,
    # no puede entrar aquí.
    if session.get('tipo_empleado') != 'admin':

        return redirect(
            url_for('HomeEmpleado')
        )

    nombre_empleado = session.get(
        'nombre_empleado',
        'Administrador'
    )

    return render_template(
        'admin.html',
        nombre_empleado=nombre_empleado
    )


# ============================================================
# PANEL DEL EMPLEADO
# ============================================================

@app.route('/empleado')
def HomeEmpleado():

    # No hay sesión
    if 'empleado' not in session:

        return redirect(
            url_for('AdminLogin')
        )

    # Si es administrador,
    # no puede entrar al panel de empleado.
    if session.get('tipo_empleado') == 'admin':

        return redirect(
            url_for('HomeAdmin')
        )

    nombre_empleado = session.get(
        'nombre_empleado',
        'Empleado'
    )

    return render_template(
        'HomeEmpleado.html',
        nombre_empleado=nombre_empleado
    )

# ============================================================
# CERRAR SESIÓN
# ============================================================

@app.route('/logout-admin')
def logout2():

    session.clear()

    return redirect(
        url_for('inicio')
    )

# ============================================================
# EMPLEADOS
# ============================================================
#
@app.route('/agregar/empleado', methods=['GET', 'POST'])
@requiere_admin
def AgregarEmpleado():

    empleadoForm = EmpleadoFomr()

    if request.method == 'POST':
        print("SE RECIBIO POST")

        if empleadoForm.validate_on_submit():
            print("FORMULARIO VALIDO")

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
                empleadoForm.correo_empleado.data.strip().lower()
            )

            empleado.numero_telefono = (
                empleadoForm.numero_telefono.data
            )

            empleado.contraseña = (
                empleadoForm.contraseña.data
            )

            try:

                print("PASO 1: Intentando crear usuario en Firebase...")

                # Crear usuario en Firebase Authentication
                usuario_firebase = crear_usuario_firebase(
                    empleado.correo_empleado,
                    empleado.contraseña
                )

                print("PASO 2: Usuario creado en Firebase")
                print("UID:", usuario_firebase.uid)

                # Datos que se conservarán durante la verificación
                datos_registro = {
                    'nombre': empleado.nombre_empleado,
                    'numero_telefono': empleado.numero_telefono,
                    'correo': empleado.correo_empleado,
                    'tipo_empleado': empleado.tipo_empleado
                }

                print("PASO 3: Datos de registro preparados")

                # Generar y enviar código de verificación
                generar_y_guardar_codigo(
                    firestore_db,
                    empleado.correo_empleado,
                    usuario_firebase.uid,
                    datos_registro
                )

                print("PASO 4: Código de verificación generado y enviado")

                # Guardar datos de verificación en sesión
                session['verificacion_uid'] = usuario_firebase.uid
                session['verificacion_correo'] = empleado.correo_empleado
                session['verificacion_tipo'] = 'empleado'

                session['empleado_pendiente'] = {
                    'nombre_empleado': empleado.nombre_empleado,
                    'tipo_empleado': empleado.tipo_empleado,
                    'correo_empleado': empleado.correo_empleado,
                    'numero_telefono': empleado.numero_telefono
                }

                print("PASO 5: Datos guardados en sesión")
                print("PASO 6: Redirigiendo a verificación...")

                # Ir a la pantalla donde se introduce el código
                return redirect(
                    url_for('verificarCorreo')
                )

            except auth.EmailAlreadyExistsError:

                print("ERROR: El correo ya existe en Firebase.")

                return render_template(
                    'RegistroEmpleado.html',
                    forma=empleadoForm,
                    error='Ese correo ya tiene una cuenta en Firebase.'
                )

            except Exception as e:

                print("ERROR AL CREAR EMPLEADO:")
                print(type(e).__name__)
                print(e)

                return render_template(
                    'RegistroEmpleado.html',
                    forma=empleadoForm,
                    error='No se pudo enviar el código de verificación. Revisa la configuración del correo.'
                )

    return render_template(
        'RegistroEmpleado.html',
        forma=empleadoForm
    )

@app.route('/consultas/empleados')
@requiere_admin
def consultasEmpleados():

    empleados = obtener_empleados()

    return render_template(
        'consultas-empleado.html',
        empleado=empleados
    )


@app.route('/editar/empleado/<id_empleado>', methods=['GET', 'POST'])
@requiere_admin
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
@requiere_admin
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
@requiere_admin
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
@requiere_admin
def consultasProveedores():

    proveedor = obtener_proveedores()

    return render_template(
        'consultas-proveedor.html',
        proveedor=proveedor
    )


@app.route('/editar/provedor/<id_provedor>', methods=['GET', 'POST'])
@requiere_admin
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
@requiere_admin
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
@requiere_admin
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
@requiere_admin
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
@requiere_admin
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
# VENTA REALIZADA POR EMPLEADO
# ============================================================

# ============================================================
# VENTA REALIZADA POR EMPLEADO
# ============================================================

@app.route('/empleado/registrar-venta', methods=['GET', 'POST'])
@requiere_empleado
def registrarVentaEmpleado():

    productos = obtener_productos()
    clientes = obtener_clientes()

    if request.method == 'POST':

        # ====================================================
        # OBTENER DATOS DEL FORMULARIO
        # ====================================================

        id_cliente = request.form.get('id_cliente')
        id_producto = request.form.get('id_producto')
        cantidad = request.form.get('cantidad')

        # ====================================================
        # VALIDAR CLIENTE
        # ====================================================

        if not id_cliente:

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error='Debes seleccionar un cliente.'
            )

        cliente = next(
            (
                c for c in clientes
                if str(c.get('id_cliente')) == str(id_cliente)
            ),
            None
        )

        if cliente is None:

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error='El cliente seleccionado no existe.'
            )

        # ====================================================
        # VALIDAR PRODUCTO
        # ====================================================

        if not id_producto:

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error='Debes seleccionar un producto.'
            )

        # ====================================================
        # VALIDAR CANTIDAD
        # ====================================================

        try:

            cantidad = int(cantidad)

            if cantidad <= 0:
                raise ValueError

        except (TypeError, ValueError):

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error='La cantidad debe ser un número mayor que 0.'
            )

        # ====================================================
        # BUSCAR PRODUCTO
        # ====================================================

        producto = next(
            (
                p for p in productos
                if str(p.get('id_producto')) == str(id_producto)
            ),
            None
        )

        if producto is None:

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error='El producto no existe.'
            )

        # ====================================================
        # VERIFICAR INVENTARIO
        # ====================================================

        inventario = int(
            producto.get(
                'cantidad',
                producto.get('cantida', 0)
            )
        )

        if cantidad > inventario:

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error=(
                    f"No hay suficiente inventario. "
                    f"Disponibles: {inventario}"
                )
            )

        # ====================================================
        # OBTENER PRECIO
        # ====================================================

        precio = float(
            producto.get(
                'precio',
                0
            )
        )

        # ====================================================
        # OBTENER EMPLEADO ACTUAL
        # ====================================================

        id_empleado = session.get('empleado')

        if id_empleado is None:

            return redirect(
                url_for('AdminLogin')
            )

        # El nombre del empleado ya se guarda en la sesión durante el login.
        # Así evitamos una lectura adicional de Firestore en cada venta.

        # ====================================================
        # REGISTRAR VENTA
        # ====================================================

        registrar_venta(
            id_cliente=id_cliente,
            id_producto=id_producto,
            cantidad=cantidad,
            precio_unitario=precio,
            id_empleado=id_empleado,
            producto_nombre=producto.get('nombre_producto'),
            cliente_nombre=cliente.get('nombre'),
            empleado_nombre=session.get('nombre_empleado', 'Empleado')
        )

        # ====================================================
        # DESCONTAR INVENTARIO
        # ====================================================

        inventario_actualizado = actualizar_inventario(
            id_producto,
            cantidad
        )

        if not inventario_actualizado:

            return render_template(
                'registrar_venta.html',
                productos=productos,
                clientes=clientes,
                error='No se pudo actualizar el inventario.'
            )

        # ====================================================
        # CALCULAR TOTAL
        # ====================================================

        total = cantidad * precio

        # ====================================================
        # MOSTRAR RESULTADO
        # ====================================================

        # Actualizamos la copia local para no volver a leer los 99
        # productos de Firestore solo para refrescar el formulario.
        producto['cantidad'] = inventario - cantidad

        return render_template(
            'registrar_venta.html',
            productos=productos,
            clientes=clientes,
            mensaje=(
                f"Venta registrada correctamente. "
                f"Cliente: {cliente.get('nombre', 'Cliente')} | "
                f"Total: ${total:.2f}"
            )
        )

    # ========================================================
    # MOSTRAR FORMULARIO
    # ========================================================

    return render_template(
        'registrar_venta.html',
        productos=productos,
        clientes=clientes
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

@app.route('/producto/<id_producto>')
def detalle_producto(id_producto):

    producto = obtener_producto(id_producto)

    if producto is None:
        return "Producto no encontrado", 404

    return render_template(
        'detalle_producto.html',
        producto=producto
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

    # Guardamos los productos ya leídos para reutilizarlos
    # en el registro de la venta. Antes se volvían a leer
    # desde Firestore en el segundo ciclo.
    productos_carrito = {}

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

        productos_carrito[str(id_producto)] = producto

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

        producto = productos_carrito.get(
            str(id_producto)
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
            precio,
            producto_nombre=producto.get('nombre_producto')
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
# COMPRAR AHORA
# ============================================================

@app.route('/comprar-ahora/<id_producto>', methods=['POST'])
def comprar_ahora(id_producto):

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    cantidad = request.form.get(
        'cantidad',
        1
    )

    try:

        cantidad = int(cantidad)

    except (TypeError, ValueError):

        cantidad = 1

    if cantidad <= 0:

        cantidad = 1

    producto = obtener_producto(
        id_producto
    )

    if producto is None:

        return "Producto no encontrado", 404

    stock = int(
        producto.get(
            'cantidad',
            producto.get(
                'cantida',
                0
            )
        )
    )

    if stock <= 0:

        return "Producto agotado", 400

    if cantidad > stock:

        return (
            f"Solo hay {stock} unidades disponibles."
        ), 400

    total = (
        float(producto.get('precio', 0))
        * cantidad
    )

    return render_template(
        'confirmar_compra.html',
        producto=producto,
        cantidad=cantidad,
        total=total,
        stock=stock
    )


@app.route('/confirmar-compra/<id_producto>', methods=['POST'])
def confirmar_compra(id_producto):

    if 'cliente' not in session:

        return redirect(
            url_for('login')
        )

    id_cliente = session['cliente']

    cantidad = request.form.get(
        'cantidad',
        1
    )

    try:

        cantidad = int(cantidad)

    except (TypeError, ValueError):

        return "Cantidad inválida", 400

    if cantidad <= 0:

        return "Cantidad inválida", 400


    # ========================================================
    # OBTENER PRODUCTO ACTUAL
    # ========================================================

    producto = obtener_producto(
        id_producto
    )

    if producto is None:

        return "Producto no encontrado", 404


    # ========================================================
    # VERIFICAR INVENTARIO ACTUAL
    # ========================================================

    stock = int(
        producto.get(
            'cantidad',
            producto.get(
                'cantida',
                0
            )
        )
    )

    if cantidad > stock:

        return (
            f"No hay suficiente inventario. "
            f"Solo quedan {stock} unidades."
        ), 400


    precio = float(
        producto.get(
            'precio',
            0
        )
    )


    # ========================================================
    # REGISTRAR VENTA
    # ========================================================

    registrar_venta(
        id_cliente,
        id_producto,
        cantidad,
        precio,
        producto_nombre=producto.get(
            'nombre_producto'
        )
    )


    # ========================================================
    # DESCONTAR INVENTARIO
    # ========================================================

    inventario_actualizado = actualizar_inventario(
        id_producto,
        cantidad
    )

    if not inventario_actualizado:

        return (
            "No se pudo actualizar el inventario."
        ), 400


    # ========================================================
    # COMPRA EXITOSA
    # ========================================================

    return render_template(
        'compra_exitosa.html',
        producto=producto,
        cantidad=cantidad,
        total=precio * cantidad
    )

# ============================================================
# CONSULTAS GENERALES
# ============================================================

@app.route('/consultas')
@requiere_admin
def consultas():

    return render_template(
        'consultas.html'
    )

# ============================================================
# HISTORIAL GENERAL DE VENTAS
# ============================================================

@app.route('/consultas/ventas')
@requiere_admin
def historialVentasAdmin():

    filtro = request.args.get(
        'filtro',
        'todas'
    )

    # ========================================================
    # VALIDAR FILTRO
    # ========================================================

    if filtro not in [
        'todas',
        'mensual',
        'anual'
    ]:

        filtro = 'todas'

    # ========================================================
    # OBTENER VENTAS
    # ========================================================

    try:

        ventas = obtener_historial_ventas(
            filtro
        )

    except Exception as error:

        print(
            "ERROR AL OBTENER HISTORIAL DE VENTAS:"
        )

        print(error)

        return render_template(
            'historial_ventas_admin.html',
            ventas=[],
            filtro=filtro,
            ventas_totales=0,
            productos_vendidos=0,
            registros_venta=0,
            promedio_venta=0,
            error_firestore=True
        )

    # ========================================================
    # IDS QUE REALMENTE NECESITAMOS
    # ========================================================

    ids_productos = set()
    ids_clientes = set()
    ids_empleados = set()

    for venta in ventas:

        id_producto = venta.get(
            'productoID'
        )

        if (
            id_producto is not None
            and not venta.get('producto_nombre')
        ):

            ids_productos.add(
                str(id_producto)
            )

        id_cliente = venta.get(
            'id_cliente'
        )

        if (
            id_cliente is not None
            and not venta.get('cliente_nombre')
        ):

            ids_clientes.add(
                str(id_cliente)
            )

        id_empleado = venta.get(
            'id_empleado'
        )

        if (
            id_empleado is not None
            and not venta.get('empleado_nombre')
        ):

            ids_empleados.add(
                str(id_empleado)
            )

    # ========================================================
    # DICCIONARIOS
    # ========================================================

    productos_dict = {}
    clientes_dict = {}
    empleados_dict = {}

    # ========================================================
    # PRODUCTOS NECESARIOS
    # ========================================================

    for id_producto in ids_productos:

        try:

            producto = obtener_producto(
                id_producto
            )

            if producto:

                productos_dict[
                    str(id_producto)
                ] = producto

        except Exception as error:

            print(
                f"Error obteniendo producto {id_producto}:"
            )

            print(error)

    # ========================================================
    # CLIENTES NECESARIOS
    # ========================================================

    for id_cliente in ids_clientes:

        try:

            cliente = obtener_cliente(
                id_cliente
            )

            if cliente:

                clientes_dict[
                    str(id_cliente)
                ] = cliente

        except Exception as error:

            print(
                f"Error obteniendo cliente {id_cliente}:"
            )

            print(error)

    # ========================================================
    # EMPLEADOS NECESARIOS
    # ========================================================

    for id_empleado in ids_empleados:

        try:

            empleado = obtener_empleado(
                id_empleado
            )

            if empleado:

                empleados_dict[
                    str(id_empleado)
                ] = empleado

        except Exception as error:

            print(
                f"Error obteniendo empleado {id_empleado}:"
            )

            print(error)

    # ========================================================
    # PREPARAR HISTORIAL
    # ========================================================

    historial = []

    for venta in ventas:

        # ----------------------------------------------------
        # PRODUCTO
        # ----------------------------------------------------

        id_producto = venta.get(
            'productoID'
        )

        nombre_producto = venta.get(
            'producto_nombre'
        )

        if not nombre_producto:

            producto = productos_dict.get(
                str(id_producto)
            )

            if producto:

                nombre_producto = producto.get(
                    'nombre_producto',
                    'Producto'
                )

            else:

                nombre_producto = (
                    'Producto no encontrado'
                )

        # ----------------------------------------------------
        # CLIENTE
        # ----------------------------------------------------

        id_cliente = venta.get(
            'id_cliente'
        )

        cliente_nombre = venta.get(
            'cliente_nombre'
        ) or 'Venta directa'

        if (
            id_cliente is not None
            and not venta.get('cliente_nombre')
        ):

            cliente = clientes_dict.get(
                str(id_cliente)
            )

            if cliente:

                cliente_nombre = cliente.get(
                    'nombre',
                    f'Cliente {id_cliente}'
                )

        # ----------------------------------------------------
        # EMPLEADO
        # ----------------------------------------------------

        id_empleado = venta.get(
            'id_empleado'
        )

        empleado_nombre = venta.get(
            'empleado_nombre'
        ) or 'Cliente'

        if (
            id_empleado is not None
            and not venta.get('empleado_nombre')
        ):

            empleado = empleados_dict.get(
                str(id_empleado)
            )

            if empleado:

                empleado_nombre = empleado.get(
                    'nombre_empleado',
                    f'Empleado {id_empleado}'
                )

        # ----------------------------------------------------
        # FECHA
        # ----------------------------------------------------

        fecha = venta.get(
            'fecha'
        )

        fecha_formateada = 'Sin fecha'

        if fecha:

            try:

                fecha_formateada = fecha.strftime(
                    '%d/%m/%Y %H:%M'
                )

            except AttributeError:

                fecha_formateada = str(
                    fecha
                )

        # ----------------------------------------------------
        # CANTIDAD
        # ----------------------------------------------------

        try:

            cantidad = int(
                venta.get(
                    'cantidad',
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            cantidad = 0

        # ----------------------------------------------------
        # PRECIO
        # ----------------------------------------------------

        try:

            precio = float(
                venta.get(
                    'precioUnitario',
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            precio = 0.0

        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        try:

            total = float(
                venta.get(
                    'total',
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            total = 0.0

        # ----------------------------------------------------
        # AGREGAR
        # ----------------------------------------------------

        historial.append({

            'fecha': fecha_formateada,

            'cliente': cliente_nombre,

            'empleado': empleado_nombre,

            'producto': nombre_producto,

            'cantidad': cantidad,

            'precio': precio,

            'total': total

        })

    # ========================================================
    # RESUMEN
    # ========================================================

    ventas_totales = sum(
        venta['total']
        for venta in historial
    )

    productos_vendidos = sum(
        venta['cantidad']
        for venta in historial
    )

    registros_venta = len(
        historial
    )

    if registros_venta > 0:

        promedio_venta = (
            ventas_totales /
            registros_venta
        )

    else:

        promedio_venta = 0

    # ========================================================
    # MOSTRAR
    # ========================================================

    return render_template(
        'historial_ventas_admin.html',

        ventas=historial,

        filtro=filtro,

        ventas_totales=ventas_totales,

        productos_vendidos=productos_vendidos,

        registros_venta=registros_venta,

        promedio_venta=promedio_venta,

        error_firestore=False
    )

# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )