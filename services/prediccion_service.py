from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


MIN_DIAS_ENTRENAMIENTO = 14
MIN_REGISTROS_MODELO = 7
DIAS_PREDICCION = 7


FEATURES = [
    "indice_tiempo",
    "dia_semana",
    "dia_mes",
    "mes",
    "lag_1",
    "lag_7",
    "media_7",
]


def _convertir_fecha(fecha: Any):
    if fecha is None:
        return None

    if isinstance(fecha, datetime):
        if fecha.tzinfo is not None:
            return fecha.astimezone(timezone.utc).replace(tzinfo=None)
        return fecha

    if hasattr(fecha, "to_datetime"):
        try:
            return _convertir_fecha(fecha.to_datetime())
        except Exception:
            pass

    try:
        fecha_convertida = pd.to_datetime(fecha, errors="coerce", utc=True)
        if pd.isna(fecha_convertida):
            return None
        return fecha_convertida.to_pydatetime().replace(tzinfo=None)
    except Exception:
        return None


def _normalizar_historial(historial):
    filas = []

    for venta in historial or []:
        fecha = _convertir_fecha(getattr(venta, "fecha", None))

        if fecha is None:
            continue

        try:
            cantidad = float(getattr(venta, "cantidad", 0) or 0)
        except (TypeError, ValueError):
            cantidad = 0.0

        if cantidad < 0:
            continue

        filas.append({
            "fecha": fecha,
            "cantidad": cantidad,
        })

    if not filas:
        return pd.DataFrame(columns=["fecha", "cantidad"])

    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["cantidad"] = pd.to_numeric(
        df["cantidad"],
        errors="coerce"
    ).fillna(0.0)

    df = df.dropna(subset=["fecha"])
    df = df.sort_values("fecha")

    return df


def _crear_serie_diaria(df):
    if df.empty:
        return pd.DataFrame(columns=["fecha", "cantidad"])

    diario = (
        df.assign(fecha=df["fecha"].dt.normalize())
        .groupby("fecha", as_index=False)["cantidad"]
        .sum()
        .sort_values("fecha")
    )

    fecha_inicio = diario["fecha"].min()
    fecha_fin = diario["fecha"].max()

    rango = pd.date_range(
        fecha_inicio,
        fecha_fin,
        freq="D"
    )

    diario = (
        diario.set_index("fecha")
        .reindex(rango, fill_value=0.0)
        .rename_axis("fecha")
        .reset_index()
    )

    diario["cantidad"] = diario["cantidad"].astype(float)

    return diario


def _crear_features_entrenamiento(serie):
    df = serie.copy()

    df["indice_tiempo"] = np.arange(
        len(df),
        dtype=float
    )

    df["dia_semana"] = df["fecha"].dt.dayofweek
    df["dia_mes"] = df["fecha"].dt.day
    df["mes"] = df["fecha"].dt.month

    df["lag_1"] = df["cantidad"].shift(1)
    df["lag_7"] = df["cantidad"].shift(7)

    df["media_7"] = (
        df["cantidad"]
        .shift(1)
        .rolling(7)
        .mean()
    )

    return df.dropna().reset_index(drop=True)


def _dividir_entrenamiento_prueba(df):
    n = len(df)

    if n < MIN_REGISTROS_MODELO:
        return None, None

    n_test = max(
        2,
        int(round(n * 0.20))
    )

    if n - n_test < 2:
        n_test = 2

    corte = n - n_test

    entrenamiento = df.iloc[:corte].copy()
    prueba = df.iloc[corte:].copy()

    return entrenamiento, prueba


def _calcular_metricas(real, predicho):
    real = np.asarray(real, dtype=float)
    predicho = np.asarray(predicho, dtype=float)

    mae = float(
        mean_absolute_error(
            real,
            predicho
        )
    )

    rmse = float(
        np.sqrt(
            mean_squared_error(
                real,
                predicho
            )
        )
    )

    if (
        len(real) >= 2
        and np.unique(real).size > 1
    ):
        r2 = float(
            r2_score(
                real,
                predicho
            )
        )
    else:
        r2 = None

    denominador = (
        np.abs(real)
        + np.abs(predicho)
    )

    mask = denominador > 0

    if np.any(mask):
        smape = float(
            np.mean(
                2.0
                * np.abs(
                    real[mask]
                    - predicho[mask]
                )
                / denominador[mask]
            )
            * 100.0
        )
    else:
        smape = 0.0

    total_real = float(
        np.sum(np.abs(real))
    )

    if total_real > 0:
        wape = float(
            np.sum(
                np.abs(
                    real - predicho
                )
            )
            / total_real
            * 100.0
        )
    else:
        wape = None

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "smape": smape,
        "wape": wape,
    }


def _crear_modelos():
    return {
        "lineal": LinearRegression(),

        "bosque": RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
    }



def _entrenar_modelos(
    entrenamiento,
    prueba
):
    X_train = entrenamiento[FEATURES]
    y_train = entrenamiento["cantidad"]

    X_test = prueba[FEATURES]

    modelos = _crear_modelos()
    predicciones = {}

    for nombre, modelo in modelos.items():

        modelo.fit(
            X_train,
            y_train
        )

        predicciones[nombre] = np.maximum(
            0.0,
            np.asarray(
                modelo.predict(X_test),
                dtype=float
            )
        )

    return modelos, predicciones


def _evaluar_modelos(
    prueba,
    predicciones
):
    real = prueba["cantidad"].to_numpy(
        dtype=float
    )

    return {
        nombre: _calcular_metricas(
            real,
            predicho
        )
        for nombre, predicho
        in predicciones.items()
    }


def _seleccionar_modelo(metricas):
    """
    Selecciona únicamente entre los dos modelos
    de Machine Learning.
    """

    candidatos = []

    for nombre in (
        "lineal",
        "bosque"
    ):

        datos = metricas.get(nombre)

        if not datos:
            continue

        rmse = datos.get("rmse")
        mae = datos.get("mae")

        if rmse is None:
            continue

        if mae is None:
            mae = float("inf")

        candidatos.append(
            (
                nombre,
                float(rmse),
                float(mae)
            )
        )

    if not candidatos:
        return "lineal"

    candidatos.sort(
        key=lambda elemento: (
            elemento[1],
            elemento[2]
        )
    )

    return candidatos[0][0]


def _crear_feature_futuro(
    fecha,
    indice_tiempo,
    historial_cantidades
):
    valores = list(
        historial_cantidades
    )

    lag_1 = (
        float(valores[-1])
        if len(valores) >= 1
        else 0.0
    )

    if len(valores) >= 7:
        lag_7 = float(
            valores[-7]
        )
    else:
        lag_7 = float(
            np.mean(
                valores or [0.0]
            )
        )

    ultimos_7 = valores[-7:]

    media_7 = (
        float(
            np.mean(ultimos_7)
        )
        if ultimos_7
        else 0.0
    )

    return pd.DataFrame([
        {
            "indice_tiempo": float(
                indice_tiempo
            ),
            "dia_semana": int(
                fecha.dayofweek
            ),
            "dia_mes": int(
                fecha.day
            ),
            "mes": int(
                fecha.month
            ),
            "lag_1": lag_1,
            "lag_7": lag_7,
            "media_7": media_7,
        }
    ])


def _predecir_futuro(
    modelo,
    serie,
    dias=DIAS_PREDICCION
):
    fechas = list(
        pd.to_datetime(
            serie["fecha"]
        )
    )

    valores = [
        float(x)
        for x in serie["cantidad"].tolist()
    ]

    if not fechas:
        return []

    ultima_fecha = fechas[-1]
    indice_inicial = len(valores)

    resultados = []

    for paso in range(
        1,
        dias + 1
    ):

        fecha_futura = (
            ultima_fecha
            + pd.Timedelta(
                days=paso
            )
        )

        X_futuro = _crear_feature_futuro(
            fecha_futura,
            indice_inicial + paso - 1,
            valores
        )

        prediccion = float(
            modelo.predict(
                X_futuro[FEATURES]
            )[0]
        )

        prediccion = max(
            0.0,
            prediccion
        )

        resultados.append({
            "fecha": fecha_futura.strftime(
                "%Y-%m-%d"
            ),
            "cantidad": round(
                prediccion,
                2
            ),
        })

        # Predicción recursiva:
        # la predicción pasa a formar parte
        # de los siguientes lags.
        valores.append(
            prediccion
        )

    return resultados


def _sumar_prediccion(
    predicciones
):
    return round(
        float(
            sum(
                item["cantidad"]
                for item in predicciones
            )
        ),
        2
    )


def _resultado_vacio(
    estado,
    mensaje,
    num_ventas,
    dias_historicos,
    promedio_diario,
    serie_historica
):
    return {
        "estado": estado,
        "mensaje": mensaje,
        "num_ventas": int(
            num_ventas
        ),
        "dias_historicos": int(
            dias_historicos
        ),
        "promedio_diario": round(
            float(
                promedio_diario
            ),
            2
        ),
        "prediccion_lineal_7_dias": 0,
        "prediccion_bosque_7_dias": 0,
        "prediccion_seleccionada_7_dias": 0,
        "modelo_seleccionado": None,
        "predicciones_lineal": [],
        "predicciones_bosque": [],
        "predicciones_seleccionadas": [],
        "serie_historica": serie_historica,
        "metricas": {},
    }


def generar_prediccion(
    historial
):
    df = _normalizar_historial(
        historial
    )

    if df.empty:
        return _resultado_vacio(
            "sin_datos",
            "No existen ventas con fecha válida para este producto.",
            0,
            0,
            0,
            []
        )

    serie = _crear_serie_diaria(
        df
    )

    serie_historica = [
        {
            "fecha": row["fecha"].strftime(
                "%Y-%m-%d"
            ),
            "cantidad": round(
                float(row["cantidad"]),
                2
            ),
        }
        for _, row in serie.iterrows()
    ]

    if len(serie) < MIN_DIAS_ENTRENAMIENTO:
        return _resultado_vacio(
            "datos_insuficientes",
            (
                f"Se requieren al menos "
                f"{MIN_DIAS_ENTRENAMIENTO} días "
                "de historial para entrenar el modelo."
            ),
            len(df),
            len(serie),
            serie["cantidad"].mean(),
            serie_historica
        )

    features = _crear_features_entrenamiento(
        serie
    )

    entrenamiento, prueba = (
        _dividir_entrenamiento_prueba(
            features
        )
    )

    if (
        entrenamiento is None
        or prueba is None
        or len(entrenamiento) < 2
    ):
        return _resultado_vacio(
            "datos_insuficientes",
            "No existen suficientes registros para evaluar los modelos.",
            len(df),
            len(serie),
            serie["cantidad"].mean(),
            serie_historica
        )

    modelos, predicciones_test = (
        _entrenar_modelos(
            entrenamiento,
            prueba
        )
    )

    metricas = _evaluar_modelos(
        prueba,
        predicciones_test
    )

    modelo_seleccionado = (
        _seleccionar_modelo(
            metricas
        )
    )

    modelo_final = modelos[
        modelo_seleccionado
    ]

    # Reentrenar el modelo ML seleccionado
    # usando todo el historial disponible.
    modelo_final.fit(
        features[FEATURES],
        features["cantidad"]
    )
    modelo_lineal = modelos["lineal"]
    modelo_bosque = modelos["bosque"]

    modelo_lineal.fit(
        features[FEATURES],
        features["cantidad"]
    )

    modelo_bosque.fit(
        features[FEATURES],
        features["cantidad"]
    )

    predicciones_lineal = (
        _predecir_futuro(
            modelo_lineal,
            serie,
            DIAS_PREDICCION
        )
    )

    predicciones_bosque = (
        _predecir_futuro(
            modelo_bosque,
            serie,
            DIAS_PREDICCION
        )
    )

    if modelo_seleccionado == "bosque":
        predicciones_seleccionadas = (
            predicciones_bosque
        )
    else:
        predicciones_seleccionadas = (
            predicciones_lineal
        )

    return {
        "estado": "ok",
        "mensaje": "Predicción generada correctamente.",
        "num_ventas": int(
            len(df)
        ),
        "dias_historicos": int(
            len(serie)
        ),
        "promedio_diario": round(
            float(
                serie["cantidad"].mean()
            ),
            2
        ),
        "prediccion_lineal_7_dias":
            _sumar_prediccion(
                predicciones_lineal
            ),
        "prediccion_bosque_7_dias":
            _sumar_prediccion(
                predicciones_bosque
            ),
        "modelo_seleccionado":
            modelo_seleccionado,
        "prediccion_seleccionada_7_dias":
            _sumar_prediccion(
                predicciones_seleccionadas
            ),
        "predicciones_lineal":
            predicciones_lineal,
        "predicciones_bosque":
            predicciones_bosque,
        "predicciones_seleccionadas":
            predicciones_seleccionadas,
        "serie_historica":
            serie_historica,
        "metricas":
            metricas,
    }


# Compatibilidad con código anterior.
def prediccion_lineal(
    historial
):
    resultado = generar_prediccion(
        historial
    )

    return resultado.get(
        "prediccion_lineal_7_dias",
        0
    )


def prediccion_bosque(
    historial
):
    resultado = generar_prediccion(
        historial
    )

    return resultado.get(
        "prediccion_bosque_7_dias",
        0
    )
