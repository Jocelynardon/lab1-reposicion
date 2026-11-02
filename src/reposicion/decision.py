"""Pedido sugerido y criterio de promocion de modelos (funciones puras)."""
from __future__ import annotations

import numpy as np

from reposicion.config import nombre_cuantil


def pedido_desde_cuantiles(pred, qs, q_crit):
    """Interpola el pronostico en el cuantil critico y redondea hacia arriba."""
    qs = sorted(qs)
    arr = pred[[nombre_cuantil(q) for q in qs]].to_numpy()
    qc = min(max(q_crit, qs[0]), qs[-1])
    j = min(int(np.searchsorted(qs, qc, side="right")) - 1, len(qs) - 2)
    w = (qc - qs[j]) / (qs[j + 1] - qs[j])
    return np.ceil(arr[:, j] * (1 - w) + arr[:, j + 1] * w)


def decidir_promocion(costo_campeon, costo_retador, cobertura_retador, reglas):
    """Criterio explicito: el retador reemplaza al campeon solo si cumple las reglas."""
    if costo_campeon is None:
        return True, "sin campeon vigente"
    mejora = (costo_campeon - costo_retador) / costo_campeon
    if mejora < reglas["mejora_costo_min"]:
        return False, f"mejora de costo {mejora:.1%} menor al minimo {reglas['mejora_costo_min']:.1%}"
    if cobertura_retador < reglas["cobertura_min"]:
        return False, f"cobertura {cobertura_retador:.2f} menor a {reglas['cobertura_min']:.2f}"
    return True, f"mejora de costo {mejora:.1%}"
