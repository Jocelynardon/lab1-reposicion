"""Registro de modelos: versiones en disco, puntero al campeon y bitacora de decisiones."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd


def guardar_modelo(modelos, meta, base="models"):
    d = Path(base) / meta["version"]
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelos, d / "modelos.joblib")
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def cargar_modelo(version, base="models"):
    d = Path(base) / version
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    return joblib.load(d / "modelos.joblib"), meta


def campeon(base="models"):
    p = Path(base) / "champion.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["version"]


def fijar_campeon(version, base="models"):
    Path(base).mkdir(parents=True, exist_ok=True)
    (Path(base) / "champion.json").write_text(
        json.dumps({"version": version}), encoding="utf-8")


def registrar_decision(fila, base="models"):
    """Una fila por fecha de corte: repetir el corte reemplaza su fila (idempotente)."""
    Path(base).mkdir(parents=True, exist_ok=True)
    p = Path(base) / "decisiones.csv"
    previas = pd.read_csv(p) if p.exists() else pd.DataFrame()
    if not previas.empty:
        previas = previas[previas["corte"] != fila["corte"]]
    marcos = [m for m in (previas, pd.DataFrame([fila])) if not m.empty]
    pd.concat(marcos, ignore_index=True).to_csv(p, index=False)


def decision_previa(corte, base="models"):
    """Decision ya registrada para una fecha de corte (o None)."""
    p = Path(base) / "decisiones.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    fila = df[df["corte"] == corte]
    if fila.empty:
        return None
    return {k: (None if pd.isna(v) else v) for k, v in fila.iloc[0].to_dict().items()}
