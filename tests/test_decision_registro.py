import pandas as pd

from reposicion.decision import decidir_promocion, pedido_desde_cuantiles
from reposicion.registro import campeon, fijar_campeon, registrar_decision

QS = [0.1, 0.25, 0.5, 0.75, 0.9]
REGLAS = {"mejora_costo_min": 0.02, "cobertura_min": 0.70}


def _q():
    return pd.DataFrame({"q10": [10.0], "q25": [20.0], "q50": [40.0],
                         "q75": [60.0], "q90": [100.0]})


def test_pedido_en_cuantil_exacto():
    assert pedido_desde_cuantiles(_q(), QS, 0.75)[0] == 60


def test_pedido_interpolado_entre_cuantiles():
    assert pedido_desde_cuantiles(_q(), QS, 0.625)[0] == 50


def test_pedido_sube_si_el_quiebre_es_mas_caro():
    assert pedido_desde_cuantiles(_q(), QS, 0.9)[0] > pedido_desde_cuantiles(_q(), QS, 0.5)[0]


def test_primer_modelo_se_promueve():
    assert decidir_promocion(None, 100.0, 0.8, REGLAS)[0]


def test_mejora_insuficiente_se_descarta():
    assert not decidir_promocion(100.0, 99.0, 0.8, REGLAS)[0]


def test_mejora_suficiente_se_promueve():
    assert decidir_promocion(100.0, 95.0, 0.8, REGLAS)[0]


def test_cobertura_baja_se_descarta():
    assert not decidir_promocion(100.0, 90.0, 0.5, REGLAS)[0]


def test_registro_idempotente(tmp_path):
    fila = {"corte": "2017-07-31", "decision": "promovido"}
    registrar_decision(fila, tmp_path)
    registrar_decision(fila, tmp_path)
    assert len(pd.read_csv(tmp_path / "decisiones.csv")) == 1


def test_campeon(tmp_path):
    assert campeon(tmp_path) is None
    fijar_campeon("v_1", tmp_path)
    assert campeon(tmp_path) == "v_1"
