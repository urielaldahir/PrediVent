from app import db


class Cliente(db.Model):
    id_cliente = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    numero_telefono = db.Column(db.String(10), unique=True, nullable=False)
    contraseña = db.Column(db.String(30), nullable=False)

class Provedor(db.Model):
    id_provedor = db.Column(db.Integer, primary_key=True)
    nombre_provedor = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    numero_telefono = db.Column(db.String(10), unique=True, nullable=False)


class Empleado(db.Model):
    id_empleado = db.Column(db.Integer, primary_key=True)
    nombre_empleado = db.Column(db.String(70))
    tipo_empleado = db.Column(db.String(30))
    correo_empleado = db.Column(db.String(100), unique=True, nullable=False)
    numero_telefono = db.Column(db.String(10), unique=True, nullable=False)
    contraseña = db.Column(db.String(30), nullable=False)

class Producto(db.Model):
    id_producto = db.Column(db.Integer, primary_key=True)
    id_provedor = db.Column(db.Integer, db.ForeignKey(Provedor.id_provedor))
    nombre_producto = db.Column(db.String(100), nullable=False)
    cantidad =  db.Column(db.Integer, nullable=False)
    descripcion = db.Column(db.String(50), nullable=False)
    precio = db.Column(db.Integer)
    RutaImagen = db.Column(db.String(100))

class Carrito(db.Model):
    id_carrito = db.Column(db.Integer, primary_key=True)
    id_producto = db.Column(db.Integer, db.ForeignKey(Producto.id_producto))
    cantidad = db.Column(db.Integer)

class Historial(db.Model):
    id_historal = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey(Cliente.id_cliente))
    id_producto = db.Column(db.Integer, db.ForeignKey(Producto.id_producto))
    cantidad = db.Column(db.Integer)








