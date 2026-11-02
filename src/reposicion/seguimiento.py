"""Seguimiento del desempeno: pronosticos publicados vs ventas reales conocidas hoy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from reposicion.asof import cargar_asof
from reposicion.config import cargar_config
from reposicion.evaluacion import LLAVE
from reposicion.metricas import costo_negocio, metricas_puntuales


def seguimiento(landing, historico, publicado, fecha, costos, salida="reports/seguimiento.csv"):
    """Recalcula todo desde cero: las correcciones recibidas se incorporan solas."""
    reales = cargar_asof(landing, historico, fecha)["sales"][LLAVE + ["sales"]]
    filas = []
    for carpeta in sorted(Path(publicado).glob("corte=*")):
        pron = pd.read_parquet(carpeta / "pronostico.parquet")
        meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
        m = pron.merge(reales, on=LLAVE, how="inner")
        if m.empty:
            continue
        fila = metricas_puntuales(m["sales"], m["q50"])
        fila.update(
            corte=meta["corte"], version_modelo=meta["version_modelo"],
            dias_evaluados=int(m["date"].nunique()),
            cobertura_80=float(((m["sales"] >= m["q10"]) & (m["sales"] <= m["q90"])).mean()),
            costo_pedido=costo_negocio(m["sales"], m["pedido"], costos),
            conocido_al=str(pd.Timestamp(fecha).date()),
        )
        filas.append(fila)
    cols = ["corte", "version_modelo", "dias_evaluados", "mae", "wape",
            "cobertura_80", "costo_pedido", "conocido_al"]
    res = pd.DataFrame(filas, columns=cols)
    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(salida, index=False)
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fecha", required=True, help="ventas conocidas hasta esta fecha")
    p.add_argument("--landing", default="data/landing")
    p.add_argument("--historico", default="data/historico")
    p.add_argument("--publicado", default="data/publicado")
    p.add_argument("--config", default="config")
    a = p.parse_args()
    costos, _ = cargar_config(a.config)
    print(seguimiento(a.landing, a.historico, a.publicado, a.fecha, costos).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
