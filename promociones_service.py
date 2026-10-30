from datetime import datetime
from flask import g, has_request_context
from firebase_config import firestore_db
import time
import threading

COLECCION = "promociones"
MAX_DESCUENTO_PORCENTAJE = 50

# Caché breve en memoria para evitar volver a descargar productos y ventas
# cada vez que se generan propuestas. Solo afecta las sugerencias, no los precios
# ni la validación de inventario de una compra.
_CACHE_PROPUESTAS = {}
_CACHE_PROPUESTAS_LOCK = threading.Lock()
_CACHE_PROPUESTAS_TTL = 180  # segundos


def _cache_peticion():
    """Devuelve el caché asociado a la petición Flask actual."""
    if not has_request_context():
        return None
    if not hasattr(g, "_predi_promociones_cache"):
        g._predi_promociones_cache = {}
    return g._predi_promociones_cache


def listar_promociones():
    cache = _cache_peticion()
    if cache is not None and "promociones" in cache:
        return [dict(p) for p in cache["promociones"]]

    ahora = datetime.now()
    resultado = []
    for doc in firestore_db.collection(COLECCION).stream():
        p = doc.to_dict() or {}
        p["id"] = doc.id
        try:
            inicio = datetime.fromisoformat(p.get("fecha_inicio", ""))
            fin = datetime.fromisoformat(p.get("fecha_fin", ""))
            aprobado = bool(p.get("aprobada", False))
            p["estado_calculado"] = (
                "Programada" if ahora < inicio else
                "Finalizada" if ahora > fin else
                "Activa" if aprobado and p.get("activa", False) else
                "Desactivada" if aprobado and p.get("desactivada", False) else
                "Aprobada, pendiente de activar" if aprobado and not p.get("activa", False) else
                "Pendiente de aprobación"
            )
        except (TypeError, ValueError):
            p["estado_calculado"] = "Fechas inválidas"
        resultado.append(p)
    resultado = sorted(resultado, key=lambda x: x.get("fecha_inicio", ""))
    if cache is not None:
        cache["promociones"] = [dict(p) for p in resultado]
    return resultado


def crear_promocion(datos, creado_por="admin", aprobada=False):
    p = crear_datos_promocion(datos, creado_por=creado_por, aprobada=aprobada)
    ref = firestore_db.collection(COLECCION).document()
    ref.set(p)
    p["id"] = ref.id
    return p


def cambiar_estado_promocion(id_promocion, accion):
    ref = firestore_db.collection(COLECCION).document(id_promocion)
    snap = ref.get()
    if not snap.exists:
        raise ValueError("No se encontró la promoción.")
    if accion == "aprobar":
        ref.update({"aprobada": True, "desactivada": False})
    elif accion == "activar":
        p = snap.to_dict() or {}
        if not p.get("aprobada"):
            raise ValueError("Primero debes aprobar la propuesta.")
        ref.update({"activa": True, "desactivada": False})
    elif accion == "desactivar":
        ref.update({"activa": False, "desactivada": True})
    elif accion == "eliminar":
        ref.delete()
    else:
        raise ValueError("Acción no válida.")


def promociones_vigentes():
    ahora = datetime.now()
    activas = []
    for p in listar_promociones():
        if p.get("estado_calculado") == "Activa":
            try:
                ini = datetime.fromisoformat(p["fecha_inicio"])
                fin = datetime.fromisoformat(p["fecha_fin"])
                if ini <= ahora <= fin:
                    activas.append(p)
            except (TypeError, ValueError):
                pass
    return activas


def generar_propuestas(tipo_solicitado="todos"):
    """Sugiere promociones según ventas e inventario. No publica ni cambia precios.
    tipo_solicitado: paquete (3+), individual (1), dos (exactamente 2), todos.
    """
    # Reutiliza el resultado durante 3 minutos. La generación de propuestas
    # es orientativa; el precio y el inventario de las compras se validan aparte.
    ahora_cache = time.monotonic()
    with _CACHE_PROPUESTAS_LOCK:
        entrada = _CACHE_PROPUESTAS.get("datos")
        datos_cacheados = entrada[1] if entrada and ahora_cache - entrada[0] < _CACHE_PROPUESTAS_TTL else None

    if datos_cacheados is None:
        productos = {}
        for doc in firestore_db.collection("productos").stream():
            producto = doc.to_dict() or {}
            pid = producto.get("id_producto", doc.id)
            productos[str(pid)] = producto

        ventas_por_producto = {}
        for doc in firestore_db.collection("ventas").stream():
            v = doc.to_dict() or {}
            pid = v.get("id_producto", v.get("productoID"))
            if pid is not None:
                try:
                    cantidad_vendida = int(v.get("cantidad", 1) or 1)
                except (TypeError, ValueError):
                    cantidad_vendida = 1
                ventas_por_producto[str(pid)] = ventas_por_producto.get(str(pid), 0) + cantidad_vendida

        datos_cacheados = (productos, ventas_por_producto)
        with _CACHE_PROPUESTAS_LOCK:
            _CACHE_PROPUESTAS["datos"] = (time.monotonic(), datos_cacheados)
    else:
        productos, ventas_por_producto = datos_cacheados

    disponibles = [
        (pid, p) for pid, p in productos.items()
        if int(p.get("cantidad", p.get("cantida", 0)) or 0) > 0
    ]
    lentos = sorted(disponibles, key=lambda par: ventas_por_producto.get(par[0], 0))
    populares = sorted(disponibles, key=lambda par: ventas_por_producto.get(par[0], 0), reverse=True)
    propuestas = []

    def producto_nombre(par):
        return str(par[1].get("nombre_producto", "Producto"))

    if tipo_solicitado in {"todos", "individual"}:
        for pid, prod in lentos[:5]:
            propuestas.append({
                "nombre": "Impulsar " + producto_nombre((pid, prod)),
                "tipo": "porcentaje", "alcance": "seleccionados",
                "ids_productos": [pid],
                "descripcion": "Descuento temporal para impulsar un producto con baja rotación.",
                "motivo": f"Ventas registradas: {ventas_por_producto.get(pid, 0)}; inventario: {prod.get('cantidad', prod.get('cantida', 0))}.",
                "porcentaje": 5
            })

    if tipo_solicitado in {"todos", "dos"} and len(disponibles) >= 2:
        popular = populares[0]
        lento = next((x for x in lentos if x[0] != popular[0]), None)
        if lento:
            propuestas.append({
                "nombre": "Dúo sugerido: " + producto_nombre(popular) + " + " + producto_nombre(lento),
                "tipo": "paquete", "alcance": "paquete",
                "ids_productos": [popular[0], lento[0]],
                "descripcion": "Combinación de exactamente dos productos para una oferta conjunta.",
                "motivo": f"Ventas registradas: {ventas_por_producto.get(popular[0], 0)} y {ventas_por_producto.get(lento[0], 0)}.",
                "porcentaje": 5
            })

    if tipo_solicitado in {"todos", "paquete"} and len(disponibles) >= 3:
        seleccion = populares[:1] + [x for x in lentos if x[0] != populares[0][0]][:2]
        if len(seleccion) >= 3:
            propuestas.append({
                "nombre": "Paquete sugerido: " + " + ".join(producto_nombre(x) for x in seleccion),
                "tipo": "paquete", "alcance": "paquete",
                "ids_productos": [x[0] for x in seleccion],
                "descripcion": "Paquete de tres productos combinando un artículo popular con artículos de menor rotación. Verifica compatibilidad.",
                "motivo": "Combinación basada en ventas registradas e inventario disponible.",
                "porcentaje": 5
            })
    return propuestas


def actualizar_promocion_borrador(id_promocion, datos):
    """Actualiza únicamente promociones que siguen siendo borradores."""
    ref = firestore_db.collection(COLECCION).document(id_promocion)
    snap = ref.get()
    if not snap.exists:
        raise ValueError("No se encontró la promoción.")
    actual = snap.to_dict() or {}
    if actual.get("activa"):
        raise ValueError("Desactiva la promoción antes de editarla.")
    # Cualquier modificación requiere una nueva aprobación administrativa.
    nueva = crear_datos_promocion(datos, creado_por=actual.get("creado_por", "admin"), aprobada=False)
    nueva.pop("creado_en", None)
    nueva["activa"] = False
    nueva["aprobada"] = False
    nueva["desactivada"] = False
    ref.update(nueva)
    return True


def crear_datos_promocion(datos, creado_por="admin", aprobada=False):
    """Valida y normaliza datos de promoción sin guardarlos; reutilizable al editar."""
    tipo = (datos.get("tipo") or "").strip()
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("Escribe el nombre de la promoción.")
    if tipo not in {"porcentaje", "cantidad", "paquete", "bienvenida"}:
        raise ValueError("Tipo de promoción no válido.")
    try:
        inicio = datetime.fromisoformat(datos.get("fecha_inicio", ""))
        fin = datetime.fromisoformat(datos.get("fecha_fin", ""))
    except (TypeError, ValueError):
        raise ValueError("Indica fechas de inicio y fin válidas.")
    if fin <= inicio:
        raise ValueError("La fecha final debe ser posterior a la inicial.")
    p = {
        "nombre": nombre, "descripcion": (datos.get("descripcion") or "").strip(),
        "tipo": tipo, "fecha_inicio": inicio.isoformat(timespec="minutes"),
        "fecha_fin": fin.isoformat(timespec="minutes"), "porcentaje": 0,
        "cantidad_minima": 1, "ids_productos": [], "aprobada": bool(aprobada),
        "activa": False, "desactivada": False, "combinable": datos.get("combinable") == "on",
        "creado_por": creado_por, "creado_en": datetime.now().isoformat(timespec="seconds"),
        "limite_descuento": MAX_DESCUENTO_PORCENTAJE,
        "alcance": (datos.get("alcance") or ("todos" if tipo == "bienvenida" else "seleccionados")).strip()
    }
    if tipo in {"porcentaje", "cantidad", "paquete", "bienvenida"}:
        try: p["porcentaje"] = float(datos.get("porcentaje") or 0)
        except (TypeError, ValueError): raise ValueError("El porcentaje debe ser numérico.")
        if not 0 < p["porcentaje"] <= MAX_DESCUENTO_PORCENTAJE:
            raise ValueError(f"El descuento debe estar entre 1 y {MAX_DESCUENTO_PORCENTAJE}%.")
    if tipo == "cantidad":
        try: p["cantidad_minima"] = int(datos.get("cantidad_minima") or 0)
        except (TypeError, ValueError): raise ValueError("La cantidad mínima debe ser numérica.")
        if p["cantidad_minima"] < 2: raise ValueError("La cantidad mínima debe ser al menos 2.")
    if hasattr(datos, "getlist"):
        ids = datos.getlist("ids_productos")
        raw = datos.get("ids_productos", "")
    else:
        ids, raw = [], datos.get("ids_productos", "")
    if raw:
        if isinstance(raw, (list, tuple, set)):
            ids.extend(raw)
        else:
            ids.extend(str(raw).split(","))
    p["ids_productos"] = list(dict.fromkeys(str(x).strip() for x in ids if str(x).strip()))
    if tipo == "bienvenida": p["alcance"] = "todos"
    if p["alcance"] not in {"todos", "seleccionados", "paquete"}:
        raise ValueError("Selecciona un alcance válido.")
    if p["alcance"] == "todos": p["ids_productos"] = []
    elif not p["ids_productos"]: raise ValueError("Selecciona al menos un producto o aplica a todos.")
    if tipo == "paquete" or p["alcance"] == "paquete":
        p["tipo"] = "paquete"; p["alcance"] = "paquete"
        if len(p["ids_productos"]) < 2: raise ValueError("Un paquete debe incluir al menos dos productos.")
    return p


def _cliente_es_nuevo(id_cliente):
    """Considera nuevo al cliente que aún no tiene ventas registradas."""
    if not id_cliente:
        return False
    # Consulta únicamente ventas de este cliente; no descarga todo el historial.
    ventas = firestore_db.collection("ventas")
    consulta = ventas.where("id_cliente", "==", str(id_cliente)).limit(1)
    if next(consulta.stream(), None) is not None:
        return False

    # Compatibilidad por si los registros antiguos guardaron el ID como número.
    try:
        id_numerico = int(id_cliente)
    except (TypeError, ValueError):
        return True

    consulta_numerica = ventas.where("id_cliente", "==", id_numerico).limit(1)
    return next(consulta_numerica.stream(), None) is None


def promocion_aplicable_a_producto(promocion, producto, id_cliente=None, cantidad=1):
    """Valida alcance, vigencia y elegibilidad de una promoción individual."""
    tipo = promocion.get("tipo")
    if tipo == "paquete":
        return False
    ids = [str(x) for x in (promocion.get("ids_productos") or [])]
    alcance = promocion.get("alcance")
    if alcance == "todos" or (not ids and tipo == "bienvenida"):
        coincide = True
    elif ids:
        pid = str(producto.get("id_producto", ""))
        coincide = pid in ids
    else:
        # Compatibilidad con promociones antiguas sin campo alcance.
        coincide = False
    if not coincide:
        return False
    if tipo == "cantidad" and int(cantidad or 1) < int(promocion.get("cantidad_minima", 2) or 2):
        return False
    if tipo == "bienvenida":
        if not id_cliente or not _cliente_es_nuevo(id_cliente):
            return False
        uso_id = f'{promocion.get("id")}_{id_cliente}'
        if firestore_db.collection("usos_promociones").document(uso_id).get().exists:
            return False
    return True


def promociones_para_producto(producto, id_cliente=None, cantidad=1):
    return [
        p for p in promociones_vigentes()
        if promocion_aplicable_a_producto(p, producto, id_cliente=id_cliente, cantidad=cantidad)
    ]


def calcular_precio_promocional(producto, id_cliente=None, cantidad=1):
    """Devuelve precio unitario y promoción elegible; nunca usa precios del navegador."""
    try:
        precio = max(0.0, float(producto.get("precio", 0) or 0))
    except (TypeError, ValueError):
        precio = 0.0
    promos = promociones_para_producto(producto, id_cliente=id_cliente, cantidad=cantidad)
    if not promos:
        return precio, None, 0.0
    promo = max(promos, key=lambda p: float(p.get("porcentaje", 0) or 0))
    porcentaje = min(MAX_DESCUENTO_PORCENTAJE, max(0.0, float(promo.get("porcentaje", 0) or 0)))
    final = round(max(0.0, precio * (1 - porcentaje / 100)), 2)
    return final, promo, round(precio - final, 2)
