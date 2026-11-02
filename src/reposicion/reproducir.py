"""Reproduce un pronostico ya publicado y lo compara con el original."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd

from reposicion.ciclo import publicar
from reposicion.config import cargar_config
from reposicion.evaluacion import LLAVE


def reproducir(corte, landing="data/landing", historico="data/historico",
               config="config", publicado="data/publicado", base="models") -> dict:
    """Regenera el pronostico con la version de modelo y los costos registrados al publicar."""
    _, params = cargar_config(config)
    original_dir = Path(publicado) / f"corte={corte}"
    meta = json.loads((original_dir / "meta.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        carpeta = publicar(landing, historico, corte, meta["costos"], params,
                           salida=tmp, base=base, version=meta["version_modelo"])
        nuevo = pd.read_parquet(carpeta / "pronostico.parquet")
    original = pd.read_parquet(original_dir / "pronostico.parquet")
    nuevo = nuevo.sort_values(LLAVE).reset_index(drop=True)
    original = original.sort_values(LLAVE).reset_index(drop=True)
    cols = [c for c in original.columns if c.startswith("q") or c == "pedido"]
    misma_llave = nuevo[LLAVE].equals(original[LLAVE])
    dif = float((nuevo[cols].astype(float) - original[cols].astype(float)).abs().to_numpy().max())
    return {"corte": corte, "version_modelo": meta["version_modelo"],
            "git_commit_original": meta.get("git_commit"), "filas": int(len(original)),
            "max_dif_abs": dif, "identico": bool(misma_llave and dif <= 1e-6)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--corte", required=True)
    a = p.parse_args()
    print(json.dumps(reproducir(a.corte), indent=2))


if __name__ == "__main__":
    main()
