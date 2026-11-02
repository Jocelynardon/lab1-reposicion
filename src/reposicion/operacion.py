"""Operaciones del flujo invocadas por los DAGs: catalogo, validacion con reporte y datasets."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from reposicion.asof import archivos_disponibles, cargar_asof, listar_bandeja
from reposicion.features import construir_features
from reposicion.validacion import DatosInvalidosError, exigir_validos


def _escribir_json(ruta: Path, contenido: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(contenido, indent=2, default=str), encoding="utf-8")
    tmp.replace(ruta)  # escritura atomica: repetir la tarea deja el mismo resultado


def catalogar(landing, corte, salida) -> dict:
    """Archivos de la bandeja visibles en la fecha de corte (la ultima version de cada dia)."""
    corte = pd.Timestamp(corte)
    cat = archivos_disponibles(listar_bandeja(landing), corte)
    carpeta = Path(salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    cat.assign(ruta=cat["ruta"].astype(str)).to_csv(
        carpeta / f"corte={corte:%Y-%m-%d}.csv", index=False)
    return {"corte": str(corte.date()), "archivos": int(len(cat)),
            "versiones_corregidas": int((cat["version"] > 1).sum())}


def validar_y_reportar(landing, historico, corte, salida) -> dict:
    """Valida las fuentes as-of. Deja un reporte y, si hay datos invalidos, detiene el flujo."""
    corte = pd.Timestamp(corte)
    datos = cargar_asof(landing, historico, corte)
    ventas = datos["sales"]
    ultima = ventas["date"].max() if not ventas.empty else None
    reporte = {"corte": str(corte.date()),
               "ultima_venta": None if ultima is None else str(ultima.date()),
               "filas": {k: int(len(v)) for k, v in datos.items()}}
    ruta = Path(salida) / f"corte={corte:%Y-%m-%d}.json"
    try:
        avisos = exigir_validos(datos)
    except DatosInvalidosError as e:
        reporte.update(estado="invalido", error=str(e))
        _escribir_json(ruta, reporte)
        raise
    if ultima is not None and ultima < corte - pd.Timedelta(days=1):
        avisos.append(f"sales: la ultima venta ({ultima.date()}) es anterior a lo esperado")
    reporte.update(estado="valido", avisos=avisos)
    _escribir_json(ruta, reporte)
    return {"estado": "valido", "avisos": len(avisos)}


def preparar_dataset(landing, historico, corte, params, salida) -> dict:
    """Dataset procesado para el modelo, construido solo con informacion disponible al corte."""
    corte = pd.Timestamp(corte)
    datos = cargar_asof(landing, historico, corte)
    exigir_validos(datos)
    train, pred = construir_features(
        datos, corte, params["horizonte_dias"], params["ventana_entrenamiento_dias"])
    carpeta = Path(salida) / f"corte={corte:%Y-%m-%d}"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, df in (("train", train), ("pred", pred)):
        tmp = carpeta / f"{nombre}.tmp"
        df.to_parquet(tmp, index=False)
        tmp.replace(carpeta / f"{nombre}.parquet")
    return {"corte": str(corte.date()), "filas_train": int(len(train)),
            "filas_pred": int(len(pred))}
