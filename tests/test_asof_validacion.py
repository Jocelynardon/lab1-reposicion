import pandas as pd

from reposicion.asof import archivos_disponibles, listar_bandeja
from reposicion.validacion import validar_fuente


def _archivo(landing, dato, recv, version, ventas):
    d = landing / "sales"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"id": [1], "date": [dato], "store_nbr": [1], "family": ["A"],
                  "sales": [ventas], "onpromotion": [0]}).to_csv(
        d / f"sales_{dato}_recv-{recv}_v{version}.csv", index=False)


def test_correccion_solo_visible_desde_su_recepcion(tmp_path):
    _archivo(tmp_path, "2017-07-01", "2017-07-02", 1, 100.0)
    _archivo(tmp_path, "2017-07-01", "2017-07-06", 2, 10.0)
    cat = listar_bandeja(tmp_path)
    antes = archivos_disponibles(cat, "2017-07-05")
    despues = archivos_disponibles(cat, "2017-07-06")
    assert list(antes["version"]) == [1]
    assert list(despues["version"]) == [2]


def test_nada_visible_antes_de_recibirse(tmp_path):
    _archivo(tmp_path, "2017-07-01", "2017-07-02", 1, 100.0)
    cat = listar_bandeja(tmp_path)
    assert archivos_disponibles(cat, "2017-07-01").empty


def test_ventas_negativas_es_error():
    df = pd.DataFrame({"id": [1], "date": pd.to_datetime(["2017-07-01"]),
                       "store_nbr": [1], "family": ["A"], "sales": [-1.0],
                       "onpromotion": [0]})
    errores, _ = validar_fuente("sales", df)
    assert errores


def test_oil_sin_precio_es_aviso_no_error():
    df = pd.DataFrame({"date": pd.to_datetime(["2017-07-01"]),
                       "dcoilwtico": [float("nan")]})
    errores, avisos = validar_fuente("oil", df)
    assert not errores
    assert avisos
