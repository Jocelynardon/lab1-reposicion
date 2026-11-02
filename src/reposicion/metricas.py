"""Metricas tecnicas y de negocio."""
from __future__ import annotations

import numpy as np


def metricas_puntuales(real, pred) -> dict:
    real, pred = np.asarray(real, dtype=float), np.asarray(pred, dtype=float)
    err = np.abs(real - pred)
    return {"mae": float(err.mean()), "wape": float(err.sum() / max(real.sum(), 1e-9))}


def pinball(real, pred, q: float) -> float:
    d = np.asarray(real, dtype=float) - np.asarray(pred, dtype=float)
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def costo_negocio(real, pedido, costos) -> float:
    """Costo total: quiebre por unidad faltante + merma por unidad sobrante."""
    real, pedido = np.asarray(real, dtype=float), np.asarray(pedido, dtype=float)
    faltante = np.maximum(real - pedido, 0.0)
    sobrante = np.maximum(pedido - real, 0.0)
    return float((costos["quiebre"] * faltante + costos["merma"] * sobrante).sum())
