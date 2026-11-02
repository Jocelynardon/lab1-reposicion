import pandas as pd

from reposicion.bandeja import construir_bandeja


def _kaggle(tmp_path):
    k = tmp_path / "kaggle"
    k.mkdir()
    fechas = pd.date_range("2017-06-29", "2017-07-05")
    n = len(fechas)
    pd.DataFrame({
        "id": range(n * 2),
        "date": fechas.repeat(2),
        "store_nbr": [1, 1] * n,
        "family": ["A", "B"] * n,
        "sales": [10.0] * (n * 2),
        "onpromotion": [0] * (n * 2),
    }).to_csv(k / "train.csv", index=False)
    pd.DataFrame({"date": fechas, "store_nbr": 1, "transactions": 100}).to_csv(
        k / "transactions.csv", index=False)
    pd.DataFrame({"date": fechas, "dcoilwtico": 50.0}).to_csv(k / "oil.csv", index=False)
    pd.DataFrame({"date": ["2017-07-02"], "type": ["Holiday"], "locale": ["National"],
                  "locale_name": ["Ecuador"], "description": ["x"],
                  "transferred": [False]}).to_csv(k / "holidays_events.csv", index=False)
    return k


def test_bandeja_un_archivo_por_fecha_y_correccion(tmp_path):
    k = _kaggle(tmp_path)
    landing = tmp_path / "landing"
    construir_bandeja(k, landing, "2017-06-30", "2017-07-03", n_correcciones=1)

    ventas = sorted(p.name for p in (landing / "sales").iterdir())
    assert len([n for n in ventas if n.endswith("_v1.csv")]) == 3
    assert len([n for n in ventas if n.endswith("_v2.csv")]) == 1
    assert "sales_2017-07-01_recv-2017-07-02_v1.csv" in ventas
    assert not any("2017-06-30" in n for n in ventas)
    feriado = [p.name for p in (landing / "holidays").iterdir()]
    assert feriado == ["holidays_2017-07-02_recv-2017-06-02_v1.csv"]


def test_bandeja_es_determinista(tmp_path):
    k = _kaggle(tmp_path)
    construir_bandeja(k, tmp_path / "a", "2017-06-30", "2017-07-03")
    construir_bandeja(k, tmp_path / "b", "2017-06-30", "2017-07-03")
    na = sorted(p.name for p in (tmp_path / "a" / "sales").iterdir())
    nb = sorted(p.name for p in (tmp_path / "b" / "sales").iterdir())
    assert na == nb
