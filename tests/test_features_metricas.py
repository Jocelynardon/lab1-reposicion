import pandas as pd

from reposicion.config import cuantil_critico
from reposicion.features import FEATURES, construir_features
from reposicion.metricas import costo_negocio

CORTE = pd.Timestamp("2017-03-01")


def _datos():
    fechas = pd.date_range("2017-01-01", "2017-02-28")
    ventas = pd.DataFrame({
        "id": range(len(fechas)), "date": fechas, "store_nbr": 1, "family": "A",
        "sales": [float(i % 7) + 1 for i in range(len(fechas))], "onpromotion": 0,
    })
    return {
        "sales": ventas,
        "holidays": pd.DataFrame(columns=["date", "type", "locale", "locale_name",
                                          "description", "transferred"]),
        "stores": pd.DataFrame({"store_nbr": [1], "cluster": [3]}),
    }


def test_features_no_usan_informacion_posterior():
    d0 = pd.Timestamp("2017-02-10")
    a, _ = construir_features(_datos(), CORTE, 7, 30)
    d2 = _datos()
    d2["sales"].loc[d2["sales"]["date"] == d0, "sales"] = 9999.0
    b, _ = construir_features(d2, CORTE, 7, 30)
    fa, fb = a.set_index("date"), b.set_index("date")
    ventana = pd.date_range(d0, d0 + pd.Timedelta(days=6))
    pd.testing.assert_frame_equal(fa.loc[ventana, FEATURES], fb.loc[ventana, FEATURES])
    d7 = d0 + pd.Timedelta(days=7)  # este dia SI usa d0 como lag_7
    assert fa.loc[d7, "lag_7"] != fb.loc[d7, "lag_7"]


def test_pred_cubre_el_horizonte():
    _, pred = construir_features(_datos(), CORTE, 7, 30)
    assert len(pred) == 7
    assert pred["date"].min() == CORTE


def test_cuantil_critico_y_costo():
    costos = {"quiebre": 3.0, "merma": 1.0}
    assert cuantil_critico(costos) == 0.75
    assert costo_negocio([10], [8], costos) == 6.0   # faltan 2 -> 2 * 3
    assert costo_negocio([10], [12], costos) == 2.0  # sobran 2 -> 2 * 1
