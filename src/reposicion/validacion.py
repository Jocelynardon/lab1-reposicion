"""Validacion de fuentes: lo invalido detiene el flujo, lo esperado solo avisa."""
from __future__ import annotations

import pandas as pd

ESQUEMAS = {
    "sales": {"id", "date", "store_nbr", "family", "sales", "onpromotion"},
    "transactions": {"date", "store_nbr", "transactions"},
    "oil": {"date", "dcoilwtico"},
    "holidays": {"date", "type", "locale", "locale_name", "description", "transferred"},
}


class DatosInvalidosError(ValueError):
    """Datos que no deben entrar al flujo."""


def validar_fuente(fuente: str, df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos). Errores = invalido; avisos = situacion esperada."""
    errores: list[str] = []
    avisos: list[str] = []
    if df.empty:
        return errores, [f"{fuente}: sin filas"]
    faltan = ESQUEMAS[fuente] - set(df.columns)
    if faltan:
        return [f"{fuente}: faltan columnas {sorted(faltan)}"], avisos
    if df["date"].isna().any():
        errores.append(f"{fuente}: fechas nulas")

    if fuente == "sales":
        ventas = pd.to_numeric(df["sales"], errors="coerce")
        if ventas.isna().any():
            errores.append("sales: ventas nulas o no numericas")
        if (ventas < 0).any():
            errores.append("sales: ventas negativas")
        if (pd.to_numeric(df["onpromotion"], errors="coerce") < 0).any():
            errores.append("sales: onpromotion negativo")
        if df.duplicated(["date", "store_nbr", "family"]).any():
            errores.append("sales: filas duplicadas por fecha, tienda y familia")
        if df["store_nbr"].isna().any():
            errores.append("sales: tienda nula")
    elif fuente == "transactions":
        tx = pd.to_numeric(df["transactions"], errors="coerce")
        if tx.isna().any() or (tx < 0).any():
            errores.append("transactions: valores nulos o negativos")
        if df.duplicated(["date", "store_nbr"]).any():
            errores.append("transactions: duplicados por fecha y tienda")
    elif fuente == "oil":
        precio = pd.to_numeric(df["dcoilwtico"], errors="coerce")
        if (precio < 0).any():
            errores.append("oil: precio negativo")
        if precio.isna().any():
            avisos.append("oil: dias sin precio (fines de semana o feriados)")
        if df.duplicated(["date"]).any():
            errores.append("oil: fechas duplicadas")
    return errores, avisos


def exigir_validos(datos: dict[str, pd.DataFrame]) -> list[str]:
    """Valida todas las fuentes. Lanza DatosInvalidosError si hay errores."""
    errores: list[str] = []
    avisos: list[str] = []
    for fuente in ESQUEMAS:
        e, a = validar_fuente(fuente, datos[fuente])
        errores += e
        avisos += a
    if errores:
        raise DatosInvalidosError("; ".join(errores))
    return avisos
