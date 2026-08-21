import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor


def preparar_datos(historial_producto):
    X = []
    y = []

    for h in historial_producto:
        X.append([h.cantidad])
        y.append(h.cantidad)

    return X, y


def prediccion_lineal(historial_producto):
    if len(historial_producto) < 2:
        return None

    X, y = preparar_datos(historial_producto)

    modelo = LinearRegression()
    modelo.fit(X, y)

    proximo = np.array([[len(historial_producto)]])

    return round(float(modelo.predict(proximo)[0]), 2)


def prediccion_bosque(historial_producto):
    if len(historial_producto) < 3:
        return None

    X, y = preparar_datos(historial_producto)

    modelo = RandomForestRegressor(
        n_estimators=100,
        random_state=42
    )

    modelo.fit(X, y)

    proximo = np.array([[len(historial_producto)]])

    return round(float(modelo.predict(proximo)[0]), 2)