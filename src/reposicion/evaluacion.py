"""Evaluacion con validacion temporal de origen rodante, igual para todos los modelos."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from reposicion.asof import cargar_asof
from reposicion.config import cargar_config, cuantil_critico, nombre_cuantil
from reposicion.features import construir_features
from reposicion.metricas import costo_negocio, metricas_puntuales, pinball
from reposicion.modelos import baseline, entrenar_cuantiles, predecir_cuantiles

LLAVE = ["date", "store_nbr", "family"]


def cuantiles_a_entrenar(costos, params) -> list[float]:
    return sorted({*params["cuantiles"], cuantil_critico(costos)})


def evaluar_fold(landing, historico, origen, reales, costos, params) -> list[dict]:
    h = params["horizonte_dias"]
    datos = cargar_asof(landing, historico, origen)  # solo lo disponible en el origen
    train, pred = construir_features(datos, origen, h, params["ventana_entrenamiento_dias"])
    real = reales[(reales["date"] >= origen) & (reales["date"] < origen + pd.Timedelta(days=h))]
    real = real[LLAVE + ["sales"]]

    filas = []
    base = pred[LLAVE].copy()
    base["pred"] = baseline(pred)
    base = base.merge(real, on=LLAVE, how="inner")
    fila = metricas_puntuales(base["sales"], base["pred"])
    fila.update(modelo="baseline", costo=costo_negocio(base["sales"], base["pred"], costos))
    filas.append(fila)

    qs = cuantiles_a_entrenar(costos, params)
    modelos = entrenar_cuantiles(train, qs, params["lightgbm"])
    q = predecir_cuantiles(modelos, pred).merge(real, on=LLAVE, how="inner")
    crit = nombre_cuantil(cuantil_critico(costos))
    fila = metricas_puntuales(q["sales"], q["q50"])
    fila["pinball"] = float(np.mean([pinball(q["sales"], q[nombre_cuantil(x)], x) for x in qs]))
    fila["cobertura_80"] = float(((q["sales"] >= q["q10"]) & (q["sales"] <= q["q90"])).mean())
    fila.update(modelo="lightgbm", costo=costo_negocio(q["sales"], np.ceil(q[crit]), costos))
    filas.append(fila)
    return filas


def evaluar(landing, historico, fecha_corte, costos, params) -> pd.DataFrame:
    corte = pd.Timestamp(fecha_corte)
    h = params["horizonte_dias"]
    reales = cargar_asof(landing, historico, corte)["sales"]  # ventas conocidas al corte
    filas = []
    for k in range(params["validacion"]["n_folds"], 0, -1):
        origen = corte - pd.Timedelta(days=h * k)
        for fila in evaluar_fold(landing, historico, origen, reales, costos, params):
            fila["origen"] = str(origen.date())
            filas.append(fila)
    return pd.DataFrame(filas)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--corte", required=True)
    p.add_argument("--landing", default="data/landing")
    p.add_argument("--historico", default="data/historico")
    p.add_argument("--config", default="config")
    p.add_argument("--salida", default="reports/comparacion_modelos.csv")
    a = p.parse_args()
    costos, params = cargar_config(a.config)
    res = evaluar(a.landing, a.historico, a.corte, costos, params)
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(a.salida, index=False)
    print(res.round(3).to_string(index=False))
    print()
    print(res.groupby("modelo")[["mae", "wape", "pinball", "cobertura_80", "costo"]].mean().round(3))


if __name__ == "__main__":
    main()
