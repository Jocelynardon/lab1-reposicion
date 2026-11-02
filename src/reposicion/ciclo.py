"""Ciclo del producto: reentrenar con compuerta y publicar pronostico y pedido."""
from __future__ import annotations

import argparse
import os
import json
import subprocess
from pathlib import Path

import pandas as pd

from reposicion.asof import cargar_asof
from reposicion.config import cargar_config, cuantil_critico
from reposicion.decision import decidir_promocion, pedido_desde_cuantiles
from reposicion.evaluacion import LLAVE, cuantiles_a_entrenar
from reposicion.features import construir_features
from reposicion.metricas import costo_negocio, metricas_puntuales
from reposicion.modelos import entrenar_cuantiles, predecir_cuantiles
from reposicion.registro import (campeon, cargar_modelo, fijar_campeon,
                                 guardar_modelo, registrar_decision, decision_previa)
from reposicion.validacion import exigir_validos


def _git_commit() -> str:
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, timeout=10)
        return r.stdout.strip() or "desconocido"
    except Exception:
        return "desconocido"


def entrenar_version(landing, historico, origen, costos, params, base="models"):
    origen = pd.Timestamp(origen)
    datos = cargar_asof(landing, historico, origen)
    exigir_validos(datos)
    train, _ = construir_features(datos, origen, params["horizonte_dias"],
                                  params["ventana_entrenamiento_dias"])
    qs = cuantiles_a_entrenar(costos, params)
    modelos = entrenar_cuantiles(train, qs, params["lightgbm"])
    version = f"v_{origen:%Y-%m-%d}"
    meta = {"version": version,
            "entrenado_hasta": str((origen - pd.Timedelta(days=1)).date()),
            "cuantiles": qs, "filas_entrenamiento": int(len(train)),
            "git_commit": _git_commit()}
    guardar_modelo(modelos, meta, base)
    return version


def _puntuar(modelos, pred, reales, costos):
    q = predecir_cuantiles(modelos, pred).merge(reales, on=LLAVE, how="inner")
    pedido = pedido_desde_cuantiles(q, sorted(modelos), cuantil_critico(costos))
    return {
        "costo": costo_negocio(q["sales"], pedido, costos),
        "wape": metricas_puntuales(q["sales"], q["q50"])["wape"],
        "cobertura_80": float(((q["sales"] >= q["q10"]) & (q["sales"] <= q["q90"])).mean()),
    }


def promocionar(landing, historico, corte, costos, params, base="models"):
    """Entrena el retador y aplica la compuerta en la semana que ninguno vio."""
    corte = pd.Timestamp(corte)
    h = params["horizonte_dias"]
    origen = corte - pd.Timedelta(days=h)
    retador = entrenar_version(landing, historico, origen, costos, params, base)
    actual = campeon(base)
    fila = {"corte": str(corte.date()), "campeon": actual, "retador": retador}
    if actual == retador:
        previa = decision_previa(str(corte.date()), base)
        if previa is not None:
            return previa
        fila.update(decision="sin cambios", motivo="el retador ya es el campeon")
    else:
        datos = cargar_asof(landing, historico, origen)
        _, pred = construir_features(datos, origen, h, params["ventana_entrenamiento_dias"])
        reales = cargar_asof(landing, historico, corte)["sales"]
        reales = reales[(reales["date"] >= origen) & (reales["date"] < corte)]
        reales = reales[LLAVE + ["sales"]]
        sr = _puntuar(cargar_modelo(retador, base)[0], pred, reales, costos)
        sc = _puntuar(cargar_modelo(actual, base)[0], pred, reales, costos) if actual else None
        ok, motivo = decidir_promocion(sc["costo"] if sc else None, sr["costo"],
                                       sr["cobertura_80"], params["promocion"])
        if ok:
            fijar_campeon(retador, base)
        fila.update(costo_campeon=sc["costo"] if sc else None,
                    costo_retador=sr["costo"], cobertura_retador=sr["cobertura_80"],
                    decision="promovido" if ok else "descartado", motivo=motivo)
    registrar_decision(fila, base)
    return fila


def publicar(landing, historico, corte, costos, params, salida="data/publicado", base="models"):
    """Pronostico por cuantiles y pedido sugerido con la informacion disponible al corte."""
    corte = pd.Timestamp(corte)
    version = campeon(base)
    if version is None:
        raise RuntimeError("No hay modelo campeon: ejecute 'promocionar' primero")
    datos = cargar_asof(landing, historico, corte)
    avisos = exigir_validos(datos)
    modelos, meta_modelo = cargar_modelo(version, base)
    _, pred = construir_features(datos, corte, params["horizonte_dias"],
                                 params["ventana_entrenamiento_dias"])
    q = predecir_cuantiles(modelos, pred)
    qc = cuantil_critico(costos)
    q["pedido"] = pedido_desde_cuantiles(q, sorted(modelos), qc)
    q["corte"] = corte

    carpeta = Path(salida) / f"corte={corte:%Y-%m-%d}"
    carpeta.mkdir(parents=True, exist_ok=True)
    tmp = carpeta / "pronostico.tmp"
    q.to_parquet(tmp, index=False)
    tmp.replace(carpeta / "pronostico.parquet")  # escritura atomica
    info = {"corte": str(corte.date()), "version_modelo": version,
            "modelo_entrenado_hasta": meta_modelo["entrenado_hasta"],
            "cuantil_critico": qc, "costos": costos,
            "ventas_hasta": str(datos["sales"]["date"].max().date()),
            "filas": int(len(q)), "avisos": avisos, "git_commit": _git_commit()}
    (carpeta / "meta.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return carpeta


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["promocionar", "publicar"])
    p.add_argument("--corte", required=True)
    p.add_argument("--landing", default="data/landing")
    p.add_argument("--historico", default="data/historico")
    p.add_argument("--config", default="config")
    a = p.parse_args()
    costos, params = cargar_config(a.config)
    if a.cmd == "promocionar":
        print(promocionar(a.landing, a.historico, a.corte, costos, params))
    else:
        print(publicar(a.landing, a.historico, a.corte, costos, params))


if __name__ == "__main__":
    main()
