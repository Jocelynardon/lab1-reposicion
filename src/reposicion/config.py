"""Carga de configuracion versionada (costos y parametros)."""
from __future__ import annotations

from pathlib import Path

import yaml


def cargar_config(carpeta="config"):
    base = Path(carpeta)
    costos = yaml.safe_load((base / "costos.yaml").read_text(encoding="utf-8-sig"))["costos"]
    params = yaml.safe_load((base / "params.yaml").read_text(encoding="utf-8-sig"))
    return costos, params


def cuantil_critico(costos) -> float:
    """Cuantil optimo: costo_quiebre / (costo_quiebre + costo_merma)."""
    return round(costos["quiebre"] / (costos["quiebre"] + costos["merma"]), 2)


def nombre_cuantil(q: float) -> str:
    return f"q{int(round(q * 100)):02d}"
