"""Modelos: baseline simple y LightGBM por cuantiles."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np

from reposicion.config import nombre_cuantil
from reposicion.features import FEATURES


def baseline(df):
    """Piso de comparacion: promedio del mismo dia de la semana en las ultimas 4 semanas."""
    return df[["lag_7", "lag_14", "lag_21", "lag_28"]].mean(axis=1).fillna(0.0).to_numpy()


def entrenar_cuantiles(train, cuantiles, params):
    X, y = train[FEATURES], train["target"]
    return {
        q: lgb.LGBMRegressor(objective="quantile", alpha=q, **params).fit(X, y)
        for q in sorted(cuantiles)
    }


def predecir_cuantiles(modelos, df):
    salida = df[["date", "store_nbr", "family"]].copy()
    cols = []
    for q in sorted(modelos):
        col = nombre_cuantil(q)
        salida[col] = np.maximum(modelos[q].predict(df[FEATURES]), 0.0)
        cols.append(col)
    salida[cols] = np.sort(salida[cols].to_numpy(), axis=1)  # evita cruce de cuantiles
    return salida
