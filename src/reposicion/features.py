"""Features 'as-of': cada feature de un dia objetivo usa datos de al menos 7 dias antes.

Con ventas disponibles hasta T-1 y un horizonte de 7 dias (T..T+6), el lag minimo
permitido es 7: asi todas las features existen en la fecha de corte.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = [
    "store_nbr", "family_cod", "cluster", "dow", "dom", "month", "feriado",
    "lag_7", "lag_14", "lag_21", "lag_28", "media_7", "media_28", "promo_7",
]
TIPOS_FERIADO = {"Holiday", "Additional", "Bridge", "Transfer", "Event"}


def _feriados(holidays: pd.DataFrame) -> set:
    if holidays.empty:
        return set()
    h = holidays[
        (holidays["locale"] == "National")
        & holidays["type"].isin(TIPOS_FERIADO)
        & (~holidays["transferred"].astype(bool))
    ]
    return set(h["date"].dt.normalize())


def construir_features(datos, fecha_corte, horizonte: int, ventana: int):
    """Devuelve (train, pred). train: dias conocidos; pred: dias T..T+horizonte-1."""
    corte = pd.Timestamp(fecha_corte)
    inicio = corte - pd.Timedelta(days=ventana + 40)
    v = datos["sales"]
    v = v[(v["date"] >= inicio) & (v["date"] < corte)]
    fechas = pd.date_range(inicio, corte + pd.Timedelta(days=horizonte - 1))

    llaves = ["store_nbr", "family"]
    ventas = v.pivot_table(index="date", columns=llaves, values="sales", aggfunc="last")
    ventas = ventas.reindex(fechas)
    promo = v.pivot_table(index="date", columns=llaves, values="onpromotion", aggfunc="last")
    promo = promo.reindex(index=fechas, columns=ventas.columns)

    mats = {
        "target": ventas,
        "lag_7": ventas.shift(7),
        "lag_14": ventas.shift(14),
        "lag_21": ventas.shift(21),
        "lag_28": ventas.shift(28),
        "media_7": ventas.rolling(7, min_periods=4).mean().shift(7),
        "media_28": ventas.rolling(28, min_periods=14).mean().shift(7),
        "promo_7": promo.rolling(7, min_periods=4).mean().shift(7),
    }
    cols = ventas.columns
    nf, nc = ventas.shape
    largo = pd.DataFrame({
        "date": np.repeat(fechas.to_numpy(), nc),
        "store_nbr": np.tile(cols.get_level_values(0).to_numpy(), nf),
        "family": np.tile(cols.get_level_values(1).to_numpy(), nf),
    })
    for nombre, m in mats.items():
        largo[nombre] = m.to_numpy(dtype="float32").ravel()

    largo["dow"] = largo["date"].dt.day_of_week
    largo["dom"] = largo["date"].dt.day
    largo["month"] = largo["date"].dt.month
    largo["feriado"] = largo["date"].isin(_feriados(datos["holidays"])).astype("int8")
    largo["family_cod"] = pd.Categorical(largo["family"]).codes
    cluster = datos["stores"].set_index("store_nbr")["cluster"]
    largo["cluster"] = largo["store_nbr"].map(cluster)

    desde = corte - pd.Timedelta(days=ventana)
    train = largo[(largo["date"] >= desde) & (largo["date"] < corte) & largo["target"].notna()]
    pred = largo[largo["date"] >= corte]
    return train.reset_index(drop=True), pred.reset_index(drop=True)
