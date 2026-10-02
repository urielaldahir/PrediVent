from firestore_service import (
    obtener_productos,
    obtener_historial_ventas_producto
)

from services.prediccion_service import generar_prediccion


print("\n======================================================")
print("        EVALUACIÓN GLOBAL DEL MÓDULO PREDIVENT")
print("======================================================\n")


productos = obtener_productos()

resultados = []


for producto in productos:

    id_producto = producto.get("id_producto")

    if id_producto is None:
        continue

    try:

        historial = obtener_historial_ventas_producto(
            id_producto
        )

        resultado = generar_prediccion(
            historial
        )

        if resultado.get("estado") != "ok":
            continue

        metricas = resultado.get(
            "metricas"
        ) or {}

        lineal = metricas.get(
            "lineal"
        ) or {}

        bosque = metricas.get(
            "bosque"
        ) or {}

        resultados.append({

            "id_producto":
                id_producto,

            "nombre":
                producto.get(
                    "nombre_producto",
                    "Sin nombre"
                ),

            "ventas":
                resultado.get(
                    "num_ventas",
                    0
                ),

            "dias":
                resultado.get(
                    "dias_historicos",
                    0
                ),

            "modelo":
                resultado.get(
                    "modelo_seleccionado",
                    "desconocido"
                ),

            "mae_lineal":
                lineal.get("mae"),

            "mae_bosque":
                bosque.get("mae"),

            "rmse_lineal":
                lineal.get("rmse"),

            "rmse_bosque":
                bosque.get("rmse"),

            "r2_lineal":
                lineal.get("r2"),

            "r2_bosque":
                bosque.get("r2"),

            "pred_lineal":
                resultado.get(
                    "prediccion_lineal_7_dias"
                ),

            "pred_bosque":
                resultado.get(
                    "prediccion_bosque_7_dias"
                )
        })

    except Exception as e:

        print(
            f"[ERROR] Producto {id_producto}: {e}"
        )


print("\n======================================================")
print("                    RESULTADO")
print("======================================================\n")


print(
    f"Productos con predicción evaluable: "
    f"{len(resultados)}"
)


if not resultados:

    print(
        "\nNo se encontraron productos con "
        "datos suficientes para evaluar."
    )

    raise SystemExit


# ======================================================
# CONTAR MODELOS SELECCIONADOS
# ======================================================

conteo = {}


for resultado in resultados:

    modelo = resultado["modelo"]

    conteo[modelo] = (
        conteo.get(modelo, 0) + 1
    )


print("\nMODELO SELECCIONADO POR PRODUCTO:")
print("--------------------------------------")


for modelo, cantidad in sorted(
    conteo.items(),
    key=lambda x: x[1],
    reverse=True
):

    print(
        f"{modelo}: {cantidad} productos"
    )


# ======================================================
# DETALLE DE CADA PRODUCTO
# ======================================================

print("\nDETALLE:")
print("--------------------------------------")


for resultado in resultados:

    print(
        f"Producto {resultado['id_producto']} | "
        f"{resultado['nombre'][:35]}"
    )

    print(
        f"  Historial: "
        f"{resultado['ventas']} ventas / "
        f"{resultado['dias']} días"
    )

    print(
        f"  Seleccionado: "
        f"{resultado['modelo']}"
    )

    print(
        f"  MAE -> "
        f"Lineal: {resultado['mae_lineal']} | "
        f"Bosque: {resultado['mae_bosque']}"
    )

    print(
        f"  RMSE -> "
        f"Lineal: {resultado['rmse_lineal']} | "
        f"Bosque: {resultado['rmse_bosque']}"
    )

    print(
        f"  R² -> "
        f"Lineal: {resultado['r2_lineal']} | "
        f"Bosque: {resultado['r2_bosque']}"
    )

    print(
        f"  Pronóstico 7 días -> "
        f"Lineal: {resultado['pred_lineal']} | "
        f"Bosque: {resultado['pred_bosque']}"
    )

    print()


# ======================================================
# FINAL
# ======================================================

print("======================================================")
print("IMPORTANTE")
print("======================================================")

print(
    "Esta prueba NO modifica Firestore."
)

print(
    "Esta prueba NO modifica el inventario."
)

print(
    "Esta prueba NO agrega ni elimina ventas."
)

print(
    "Solo evalúa el comportamiento actual "
    "del módulo de predicción."
)

print("======================================================\n")