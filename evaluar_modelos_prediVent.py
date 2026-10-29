"""Evalúa los seis modelos de PrediVent con progreso y tiempos en consola.

Este script solo lee historiales y genera un CSV local; no modifica Firestore,
inventario ni ventas.
"""
import csv
import time
from pathlib import Path

from firestore_service import (
    obtener_productos,
    obtener_historial_ventas_producto,
)
from services.prediccion_service import generar_prediccion

NOMBRES_MODELOS = {
    "lineal": "Regresión lineal",
    "arbol": "Árbol de decisión",
    "bosque": "Bosque aleatorio",
    "extra_trees": "Extra Trees",
    "gradient_boosting": "Gradient Boosting",
    "svr": "SVR",
}
ETAPAS_POR_PRODUCTO = 13  # consulta + 6 evaluaciones + 6 pronósticos


def formato_tiempo(segundos):
    if segundos is None or segundos < 0 or segundos == float("inf"):
        return "calculando..."
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas} h {minutos:02d} min"
    if minutos:
        return f"{minutos} min {segundos:02d} s"
    return f"{segundos} s"


def mostrar_progreso(indice, total, etapa_local, inicio, detalle):
    fraccion = ((indice - 1) + min(etapa_local, ETAPAS_POR_PRODUCTO) / ETAPAS_POR_PRODUCTO) / max(total, 1)
    porcentaje = min(100.0, fraccion * 100)
    transcurrido = time.monotonic() - inicio
    restante = (transcurrido / fraccion - transcurrido) if fraccion > 0 else None
    barra_ancho = 24
    llenos = int(barra_ancho * porcentaje / 100)
    barra = "#" * llenos + "-" * (barra_ancho - llenos)
    print(
        f"\r[{barra}] {porcentaje:6.2f}% | Producto {indice}/{total} | "
        f"{detalle} | Transcurrido: {formato_tiempo(transcurrido)} | "
        f"Restante aprox.: {formato_tiempo(restante)}",
        end="\n" if etapa_local >= ETAPAS_POR_PRODUCTO else "\r",
        flush=True,
    )


print("\n======================================================")
print("       EVALUACIÓN GLOBAL DEL MÓDULO PREDIVENT")
print("======================================================\n")
print("Obteniendo lista de productos de Firestore...", flush=True)
productos = obtener_productos()
productos = [p for p in productos if p.get("id_producto") is not None]
resultados = []
total_productos = len(productos)
inicio_global = time.monotonic()

print(f"Productos encontrados: {total_productos}")
print("La consola se actualizará durante la consulta y el procesamiento de cada modelo.\n", flush=True)

for indice, producto in enumerate(productos, start=1):
    id_producto = producto.get("id_producto")
    nombre_producto = producto.get("nombre_producto", "Sin nombre")
    etapa_local = 0
    print(f"\n[{indice}/{total_productos}] Consultando historial de producto {id_producto} ({nombre_producto})...", flush=True)
    try:
        historial = obtener_historial_ventas_producto(id_producto)
        etapa_local = 1
        mostrar_progreso(indice, total_productos, etapa_local, inicio_global, f"Historial recibido: {len(historial)} registros")

        def callback_progreso(etapa, modelo):
            es_inicio = etapa.startswith("iniciando_")
            if not es_inicio:
                nonlocal_stage["etapa"] += 1
            if "evaluacion" in etapa:
                verbo = "Evaluando"
            else:
                verbo = "Pronosticando 7 días con"
            estado = "iniciando" if es_inicio else "terminado"
            mostrar_progreso(
                indice,
                total_productos,
                nonlocal_stage["etapa"],
                inicio_global,
                f"Producto {id_producto} | {verbo} {NOMBRES_MODELOS.get(modelo, modelo)} ({estado})",
            )

        nonlocal_stage = {"etapa": etapa_local}
        resultado = generar_prediccion(historial, progress_callback=callback_progreso)

        if resultado.get("estado") != "ok":
            print(
                f"\n[OMITIDO] Producto {id_producto}: "
                f"{resultado.get('mensaje', 'sin datos evaluables')}",
                flush=True,
            )
            mostrar_progreso(indice, total_productos, ETAPAS_POR_PRODUCTO, inicio_global, f"Producto {id_producto} omitido")
            continue

        metricas = resultado.get("metricas") or {}
        fila = {
            "id_producto": id_producto,
            "nombre": nombre_producto,
            "ventas": resultado.get("num_ventas", 0),
            "dias": resultado.get("dias_historicos", 0),
            "modelo_seleccionado": resultado.get("modelo_seleccionado", "desconocido"),
        }
        for modelo in NOMBRES_MODELOS:
            datos = metricas.get(modelo) or {}
            fila[f"mae_{modelo}"] = datos.get("mae")
            fila[f"rmse_{modelo}"] = datos.get("rmse")
            fila[f"r2_{modelo}"] = datos.get("r2")
            fila[f"smape_{modelo}"] = datos.get("smape")
            fila[f"wape_{modelo}"] = datos.get("wape")
            fila[f"pronostico_7_dias_{modelo}"] = (
                resultado.get("pronosticos_7_dias", {}).get(modelo)
            )
        resultados.append(fila)
        mostrar_progreso(indice, total_productos, ETAPAS_POR_PRODUCTO, inicio_global, f"Producto {id_producto} terminado")

    except Exception as error:
        print(f"\n[ERROR] Producto {id_producto}: {type(error).__name__}: {error}", flush=True)
        mostrar_progreso(indice, total_productos, ETAPAS_POR_PRODUCTO, inicio_global, f"Producto {id_producto} con error")

print("\n\n======================================================")
print("RESULTADO GLOBAL")
print("======================================================")
print(f"Productos con predicción evaluable: {len(resultados)} de {total_productos}")

if not resultados:
    print("No se encontraron productos con datos suficientes para evaluar.")
    raise SystemExit(0)

conteo = {modelo: 0 for modelo in NOMBRES_MODELOS}
for fila in resultados:
    modelo = fila["modelo_seleccionado"]
    conteo[modelo] = conteo.get(modelo, 0) + 1

print("\nMODELO SELECCIONADO POR PRODUCTO (menor RMSE; desempate por MAE):")
for modelo, cantidad in sorted(conteo.items(), key=lambda par: par[1], reverse=True):
    print(f"{NOMBRES_MODELOS.get(modelo, modelo)} ({modelo}): {cantidad} productos")

print("\nDETALLE POR PRODUCTO")
print("------------------------------------------------------")
for fila in resultados:
    print(
        f"\nProducto {fila['id_producto']} | {str(fila['nombre'])[:35]} | "
        f"Historial: {fila['ventas']} registros / {fila['dias']} días"
    )
    print(f"  Modelo seleccionado: {NOMBRES_MODELOS.get(fila['modelo_seleccionado'], fila['modelo_seleccionado'])}")
    for modelo, nombre in NOMBRES_MODELOS.items():
        print(
            f"  {nombre}: MAE={fila[f'mae_{modelo}']}, "
            f"RMSE={fila[f'rmse_{modelo}']}, R²={fila[f'r2_{modelo}']}, "
            f"sMAPE={fila[f'smape_{modelo}']}, WAPE={fila[f'wape_{modelo}']}, "
            f"Pronóstico 7 días={fila[f'pronostico_7_dias_{modelo}']}"
        )

ruta_csv = Path(__file__).resolve().parent / "reporte_evaluacion_modelos.csv"
with ruta_csv.open("w", newline="", encoding="utf-8-sig") as archivo:
    columnas = list(resultados[0].keys())
    escritor = csv.DictWriter(archivo, fieldnames=columnas)
    escritor.writeheader()
    escritor.writerows(resultados)

print("\n======================================================")
print(f"Reporte CSV generado: {ruta_csv}")
print(f"Tiempo total: {formato_tiempo(time.monotonic() - inicio_global)}")
print("La evaluación solo lee los historiales; no modifica Firestore, ventas ni inventario.")
print("======================================================\n")
