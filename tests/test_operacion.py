import pandas as pd
import pytest

from reposicion.operacion import catalogar, validar_y_reportar
from reposicion.registro import decision_previa, registrar_decision
from reposicion.validacion import DatosInvalidosError


def _venta(landing, dato, recv, version, ventas):
    d = landing / "sales"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"id": [1], "date": [dato], "store_nbr": [1], "family": ["A"],
                  "sales": [ventas], "onpromotion": [0]}).to_csv(
        d / f"sales_{dato}_recv-{recv}_v{version}.csv", index=False)


def test_catalogar_cuenta_correcciones(tmp_path):
    landing = tmp_path / "landing"
    _venta(landing, "2017-07-01", "2017-07-02", 1, 10.0)
    _venta(landing, "2017-07-01", "2017-07-06", 2, 9.0)
    antes = catalogar(landing, "2017-07-05", tmp_path / "cat")
    despues = catalogar(landing, "2017-07-06", tmp_path / "cat")
    assert antes["versiones_corregidas"] == 0
    assert despues["versiones_corregidas"] == 1


def test_dato_invalido_detiene_y_deja_reporte(tmp_path):
    landing, hist = tmp_path / "landing", tmp_path / "hist"
    hist.mkdir()
    pd.DataFrame({"store_nbr": [1], "cluster": [1]}).to_parquet(hist / "stores.parquet")
    _venta(landing, "2017-07-01", "2017-07-02", 1, -5.0)
    with pytest.raises(DatosInvalidosError):
        validar_y_reportar(landing, hist, "2017-07-03", tmp_path / "rep")
    assert (tmp_path / "rep" / "corte=2017-07-03.json").exists()


def test_decision_previa(tmp_path):
    assert decision_previa("2017-07-10", tmp_path) is None
    registrar_decision({"corte": "2017-07-10", "decision": "promovido"}, tmp_path)
    assert decision_previa("2017-07-10", tmp_path)["decision"] == "promovido"
