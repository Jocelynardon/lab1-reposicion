"""Lectura 'as-of' de la bandeja: solo lo que habia llegado en la fecha de corte."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from reposicion.bandeja import LAG_RECEPCION

PATRON = re.compile(
    r"^(?P<fuente>[a-z]+)_(?P<dato>\d{4}-\d{2}-\d{2})"
    r"_recv-(?P<recv>\d{4}-\d{2}-\d{2})_v(?P<version>\d+)\.csv$"
)
COLUMNAS = ["fuente", "fecha_dato", "fecha_recepcion", "version", "ruta"]
LLAVES = {
    "sales": ["date", "store_nbr", "family"],
    "transactions": ["date", "store_nbr"],
    "oil": ["date"],
}


def listar_bandeja(landing_dir) -> pd.DataFrame:
    """Catalogo de archivos de la bandeja (solo lectura)."""
    filas = []
    for ruta in sorted(Path(landing_dir).rglob("*.csv")):
        m = PATRON.match(ruta.name)
        if m is None:
            raise ValueError(f"Nombre no reconocido en la bandeja: {ruta.name}")
        filas.append({
            "fuente": m["fuente"],
            "fecha_dato": pd.Timestamp(m["dato"]),
            "fecha_recepcion": pd.Timestamp(m["recv"]),
            "version": int(m["version"]),
            "ruta": ruta,
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


def archivos_disponibles(catalogo: pd.DataFrame, fecha_corte) -> pd.DataFrame:
    """Archivos ya recibidos en la fecha de corte; la ultima version de cada dia."""
    corte = pd.Timestamp(fecha_corte)
    visibles = catalogo[catalogo["fecha_recepcion"] <= corte]
    return (
        visibles.sort_values("version")
        .groupby(["fuente", "fecha_dato"])
        .tail(1)
        .sort_values(["fuente", "fecha_dato"])
        .reset_index(drop=True)
    )


def cargar_asof(landing_dir, historico_dir, fecha_corte) -> dict[str, pd.DataFrame]:
    """Devuelve un DataFrame por fuente con la informacion disponible al corte."""
    corte = pd.Timestamp(fecha_corte)
    catalogo = archivos_disponibles(listar_bandeja(landing_dir), corte)
    salida: dict[str, pd.DataFrame] = {}
    for fuente, lag in LAG_RECEPCION.items():
        partes = []
        hist = Path(historico_dir) / f"{fuente}.parquet"
        if hist.exists():
            h = pd.read_parquet(hist)
            partes.append(h[h["date"] + pd.Timedelta(days=lag) <= corte])
        for ruta in catalogo.loc[catalogo["fuente"] == fuente, "ruta"]:
            partes.append(pd.read_csv(ruta, parse_dates=["date"]))
        df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
        if not df.empty:
            if fuente == "holidays":
                df = df.drop_duplicates()
            else:
                df = df.drop_duplicates(subset=LLAVES[fuente], keep="last")
            df = df.sort_values("date").reset_index(drop=True)
        salida[fuente] = df
    salida["stores"] = pd.read_parquet(Path(historico_dir) / "stores.parquet")
    return salida
