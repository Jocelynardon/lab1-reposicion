"""Construye la carga historica y la bandeja (sistema de origen simulado).

La bandeja es un sistema externo: este modulo solo la GENERA a partir de los
CSV de Kaggle. El flujo del producto la lee, pero nunca la modifica.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

FUENTES = {
    "train.csv": "sales",
    "transactions.csv": "transactions",
    "oil.csv": "oil",
    "holidays_events.csv": "holidays",
}
# Dias entre la fecha del dato y su recepcion (negativo = llega por anticipado).
LAG_RECEPCION = {"sales": 1, "transactions": 2, "oil": 1, "holidays": -30}
DIAS_CORRECCION = 5


def _leer(kaggle_dir, nombre: str) -> pd.DataFrame:
    return pd.read_csv(Path(kaggle_dir) / nombre, parse_dates=["date"])


def construir_historico(kaggle_dir, salida_dir, corte) -> None:
    """Carga historica inicial: todo lo anterior o igual a la fecha de corte."""
    corte = pd.Timestamp(corte)
    salida = Path(salida_dir)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, fuente in FUENTES.items():
        df = _leer(kaggle_dir, nombre)
        df[df["date"] <= corte].to_parquet(salida / f"{fuente}.parquet", index=False)
    pd.read_csv(Path(kaggle_dir) / "stores.csv").to_parquet(
        salida / "stores.parquet", index=False
    )


def _escribir(destino: Path, fuente, dia, recepcion, version, df) -> None:
    nombre = f"{fuente}_{dia:%Y-%m-%d}_recv-{recepcion:%Y-%m-%d}_v{version}.csv"
    df.to_csv(destino / nombre, index=False)


def _con_errores(g: pd.DataFrame, rng) -> pd.DataFrame:
    """Version 1 defectuosa: infla las ventas de ~5% de las filas."""
    g = g.copy()
    k = max(1, int(len(g) * 0.05))
    idx = rng.choice(g.index.to_numpy(), size=k, replace=False)
    g.loc[idx, "sales"] = (g.loc[idx, "sales"] * rng.uniform(2, 5, size=k) + 1).round(3)
    return g


def construir_bandeja(kaggle_dir, landing_dir, corte, fin, n_correcciones=3, semilla=42):
    """Un archivo por fecha y fuente para el periodo (corte, fin]. Determinista."""
    corte, fin = pd.Timestamp(corte), pd.Timestamp(fin)
    rng = np.random.default_rng(semilla)
    dias = pd.date_range(corte + pd.Timedelta(days=1), fin)
    idx = rng.choice(len(dias), size=min(n_correcciones, len(dias)), replace=False)
    dias_corregidos = {dias[i] for i in idx}

    for nombre, fuente in FUENTES.items():
        df = _leer(kaggle_dir, nombre)
        df = df[(df["date"] > corte) & (df["date"] <= fin)]
        destino = Path(landing_dir) / fuente
        destino.mkdir(parents=True, exist_ok=True)
        for dia, g in df.groupby("date"):
            recepcion = dia + pd.Timedelta(days=LAG_RECEPCION[fuente])
            if fuente == "sales" and dia in dias_corregidos:
                _escribir(destino, fuente, dia, recepcion, 1, _con_errores(g, rng))
                correccion = dia + pd.Timedelta(days=DIAS_CORRECCION)
                _escribir(destino, fuente, dia, correccion, 2, g)
            else:
                _escribir(destino, fuente, dia, recepcion, 1, g)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kaggle", default="data/kaggle")
    p.add_argument("--historico", default="data/historico")
    p.add_argument("--landing", default="data/landing")
    p.add_argument("--corte", required=True)
    p.add_argument("--fin", required=True)
    a = p.parse_args()
    construir_historico(a.kaggle, a.historico, a.corte)
    construir_bandeja(a.kaggle, a.landing, a.corte, a.fin)


if __name__ == "__main__":
    main()
