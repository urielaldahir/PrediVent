from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, validators, PasswordField, EmailField, RadioField, IntegerField, DateField
from wtforms.validators import DataRequired, EqualTo, InputRequired


class ClienteForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()] )
    correo = EmailField('Correo', validators=[DataRequired()], render_kw={"placeholder": "correo@ejemplo.com"})
    numero_telefono = StringField('Telefono', validators=[DataRequired(), validators.Length(min=10, max=10)])
    contraseña = PasswordField('Contraseña',validators=[InputRequired(), validators.Length(min=8)])
    enviar = SubmitField('Enviar')

class ClienteForm2(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()] )
    correo = EmailField('Correo', validators=[DataRequired()], render_kw={"placeholder": "correo@ejemplo.com"})
    numero_telefono = StringField('Telefono', validators=[DataRequired(), validators.Length(min=10, max=10)])
    contraseña = StringField('Contraseña',validators=[InputRequired(), validators.Length(min=8)])
    enviar = SubmitField('Enviar')

class EmpleadoFomr(FlaskForm):
    nombre_empleado = StringField('Nombre', validators=[DataRequired()] )
    tipo_empleado = StringField('Cargo',  validators=[DataRequired()], render_kw={"placeholder": "admin" })
    correo_empleado = EmailField('Correo', validators=[DataRequired()], render_kw={"placeholder": "correo@ejemplo.com"})
    numero_telefono = StringField('Telefono', validators=[DataRequired(), validators.Length(min=10, max=10)])
    contraseña = PasswordField('Contraseña',validators=[InputRequired(), validators.Length(min=8)])
    enviar = SubmitField('Enviar')


class EmpleadoEditFomr(FlaskForm):
    nombre_empleado = StringField('Nombre', validators=[DataRequired()] )
    tipo_empleado = StringField('Cargo',  validators=[DataRequired()], render_kw={"placeholder": "admin" })
    correo_empleado = EmailField('Correo', validators=[DataRequired()], render_kw={"placeholder": "correo@ejemplo.com"})
    numero_telefono = StringField('Telefono', validators=[DataRequired(), validators.Length(min=10, max=10)])
    contraseña = StringField('Contraseña',validators=[InputRequired(), validators.Length(min=8)])
    enviar = SubmitField('Enviar')

class ProductoForm(FlaskForm):
    id_provedor = IntegerField('Id Proveedor', validators=[DataRequired()])
    nombre_producto = StringField('Nombre del producto', validators=[DataRequired()])
    cantidad = IntegerField('Cantidad', validators=[DataRequired()])
    descripcion = StringField('Descripcion', validators=[DataRequired()])
    precio = IntegerField('Precio del producto', validators=[DataRequired()])
    RutaImagen = StringField('Ruta de la imagen', validators=[DataRequired()])
    enviar = SubmitField('Enviar')


class ProvedorForm(FlaskForm):
    nombre_provedor = StringField('Nombre de proveedor', validators=[DataRequired()] )
    correo = EmailField('Correo', validators=[DataRequired()], render_kw={"placeholder": "correo@ejemplo.com"})
    numero_telefono = StringField('Telefono', validators=[DataRequired(), validators.Length(min=8, max=10)])
    enviar = SubmitField('Enviar')

