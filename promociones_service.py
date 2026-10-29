from datetime import datetime
from firebase_config import firestore_db

COLECCION = "promociones"
MAX_DESCUENTO_PORCENTAJE = 50


def listar_promociones():
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
                "Pendiente de aprobación"
            )
        except (TypeError, ValueError):
            p["estado_calculado"] = "Fechas inválidas"
        resultado.append(p)
    return sorted(resultado, key=lambda x: x.get("fecha_inicio", ""))


def crear_promocion(datos, creado_por="admin", aprobada=False):
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
        "nombre": nombre,
        "descripcion": (datos.get("descripcion") or "").strip(),
        "tipo": tipo,
        "fecha_inicio": inicio.isoformat(timespec="minutes"),
        "fecha_fin": fin.isoformat(timespec="minutes"),
        "porcentaje": 0,
        "cantidad_minima": 1,
        "ids_productos": [],
        "aprobada": bool(aprobada),
        "activa": False,
        "combinable": datos.get("combinable") == "on",
        "creado_por": creado_por,
        "creado_en": datetime.now().isoformat(timespec="seconds"),
        "limite_descuento": MAX_DESCUENTO_PORCENTAJE,
    }
    if tipo in {"porcentaje", "bienvenida", "paquete"}:
        try:
            porcentaje = float(datos.get("porcentaje") or 0)
        except (TypeError, ValueError):
            raise ValueError("El porcentaje debe ser numérico.")
        if not 0 < porcentaje <= MAX_DESCUENTO_PORCENTAJE:
            raise ValueError(f"El descuento debe estar entre 1 y {MAX_DESCUENTO_PORCENTAJE}%.")
        p["porcentaje"] = porcentaje
    if tipo == "cantidad":
        try:
            p["cantidad_minima"] = int(datos.get("cantidad_minima") or 0)
            p["porcentaje"] = float(datos.get("porcentaje") or 0)
        except (TypeError, ValueError):
            raise ValueError("Cantidad mínima y porcentaje deben ser números.")
        if p["cantidad_minima"] < 2:
            raise ValueError("La cantidad mínima debe ser al menos 2.")
        if not 0 < p["porcentaje"] <= MAX_DESCUENTO_PORCENTAJE:
            raise ValueError(f"El descuento debe estar entre 1 y {MAX_DESCUENTO_PORCENTAJE}%.")
    raw_ids = datos.get("ids_productos", "")
    p["ids_productos"] = [x.strip() for x in raw_ids.split(",") if x.strip()]
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
        ref.update({"aprobada": True})
    elif accion == "activar":
        p = snap.to_dict() or {}
        if not p.get("aprobada"):
            raise ValueError("Primero debes aprobar la propuesta.")
        ref.update({"activa": True})
    elif accion == "desactivar":
        ref.update({"activa": False})
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


def generar_propuestas():
    """Genera sugerencias basadas en ventas e inventario; no publica ni cambia precios."""
    productos = {str(d.id): (d.to_dict() or {}) for d in firestore_db.collection("productos").stream()}
    ventas_por_producto = {}
    for doc in firestore_db.collection("ventas").stream():
        v = doc.to_dict() or {}
        pid = v.get("id_producto")
        if pid is not None:
            ventas_por_producto[str(pid)] = ventas_por_producto.get(str(pid), 0) + int(v.get("cantidad", 1) or 1)
    ordenados = sorted(productos.items(), key=lambda par: ventas_por_producto.get(par[0], 0), reverse=True)
    propuestas = []
    disponibles = [(pid, p) for pid, p in productos.items() if int(p.get("cantidad", p.get("cantida", 0)) or 0) > 0]
    if len(disponibles) >= 2:
        mas_vendido = ordenados[0] if ordenados else disponibles[0]
        lentos = sorted(disponibles, key=lambda par: ventas_por_producto.get(par[0], 0))
        lento = next((x for x in lentos if x[0] != mas_vendido[0]), None)
        if lento:
            propuestas.append({
                "nombre": "Paquete sugerido: " + str(mas_vendido[1].get("nombre_producto", "Producto popular")) + " + " + str(lento[1].get("nombre_producto", "Producto con baja rotación")),
                "tipo": "paquete",
                "ids_productos": [mas_vendido[0], lento[0]],
                "descripcion": "Combina un producto con más ventas con otro de menor rotación. Revisa compatibilidad y margen antes de aprobar.",
                "motivo": f"Ventas registradas: {ventas_por_producto.get(mas_vendido[0], 0)} frente a {ventas_por_producto.get(lento[0], 0)}.",
                "porcentaje": 5
            })
    for pid, p in sorted(disponibles, key=lambda par: ventas_por_producto.get(par[0], 0))[:3]:
        propuestas.append({
            "nombre": "Impulsar " + str(p.get("nombre_producto", "producto")),
            "tipo": "porcentaje",
            "ids_productos": [pid],
            "descripcion": "Propuesta para probar una promoción temporal en un producto con pocas ventas registradas.",
            "motivo": f"Ventas registradas: {ventas_por_producto.get(pid, 0)}; inventario: {p.get('cantidad', p.get('cantida', 0))}.",
            "porcentaje": 5
        })
    return propuestas
