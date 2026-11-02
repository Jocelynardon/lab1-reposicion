"""DAGs del producto. Solo orquestan: toda la logica vive en src/reposicion/."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow.sdk import dag, task
from airflow.timetables.trigger import CronTriggerTimetable

try:
    from airflow.sdk.exceptions import AirflowFailException
except ImportError:
    from airflow.exceptions import AirflowFailException

RAIZ = Path(os.environ.get("LAB_ROOT", "."))
LANDING = str(RAIZ / "data" / "landing")
HISTORICO = str(RAIZ / "data" / "historico")
CONFIG = str(RAIZ / "config")
MODELOS = str(RAIZ / "models")
PUBLICADO = str(RAIZ / "data" / "publicado")

BASE = dict(
    start_date=datetime(2017, 7, 3),
    end_date=datetime(2018, 12, 31),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    tags=["lab1"],
    default_args={"retries": 1, "retry_delay": timedelta(minutes=1)},
)
PARAMS = {"corte": ""}


def _corte(logical_date, params) -> str:
    """Fecha de corte = fecha logica de la ejecucion (o el parametro 'corte' si se indica)."""
    valor = (params or {}).get("corte")
    if valor:
        return str(valor)
    if logical_date is None:
        raise AirflowFailException("Ejecucion sin fecha logica: indique el parametro corte (AAAA-MM-DD)")
    return logical_date.date().isoformat()


def _detener_si_invalido(funcion, *args):
    """Datos invalidos: falla SIN reintentos para no contaminar el resultado."""
    from reposicion.validacion import DatosInvalidosError
    try:
        return funcion(*args)
    except DatosInvalidosError as e:
        raise AirflowFailException(f"Datos invalidos: {e}") from e


@dag(dag_id="preparar_origen", schedule=None,
     params={"corte_historico": "2017-06-30", "fin_bandeja": "2017-07-31"}, **BASE)
def preparar_origen():
    @task
    def generar_origen(params=None):
        from reposicion.bandeja import construir_bandeja, construir_historico
        requeridos = ["train.csv", "stores.csv", "holidays_events.csv", "oil.csv", "transactions.csv"]
        kaggle = RAIZ / "data" / "kaggle"
        faltan = [n for n in requeridos if not (kaggle / n).exists()]
        if faltan:
            raise AirflowFailException(f"Faltan archivos de Kaggle en data/kaggle: {faltan}")
        construir_historico(str(kaggle), HISTORICO, params["corte_historico"])
        construir_bandeja(str(kaggle), LANDING, params["corte_historico"], params["fin_bandeja"])
        return {"corte_historico": params["corte_historico"], "fin_bandeja": params["fin_bandeja"]}

    generar_origen()


preparar_origen()


@dag(dag_id="ingesta_validacion", schedule=CronTriggerTimetable("0 0 * * *", timezone="UTC"),
     params=PARAMS, **BASE)
def ingesta_validacion():
    @task
    def catalogar_bandeja(logical_date=None, params=None):
        from reposicion.operacion import catalogar
        return catalogar(LANDING, _corte(logical_date, params), str(RAIZ / "data" / "reportes" / "catalogo"))

    @task
    def validar_fuentes(logical_date=None, params=None):
        from reposicion.operacion import validar_y_reportar
        return _detener_si_invalido(validar_y_reportar, LANDING, HISTORICO,
                                    _corte(logical_date, params),
                                    str(RAIZ / "data" / "reportes" / "validacion"))

    catalogar_bandeja() >> validar_fuentes()


ingesta_validacion()


@dag(dag_id="preparacion_datos", schedule=CronTriggerTimetable("0 0 * * *", timezone="UTC"),
     params=PARAMS, **BASE)
def preparacion_datos():
    @task
    def construir_dataset(logical_date=None, params=None):
        from reposicion.config import cargar_config
        from reposicion.operacion import preparar_dataset
        _, par = cargar_config(CONFIG)
        return _detener_si_invalido(preparar_dataset, LANDING, HISTORICO,
                                    _corte(logical_date, params), par,
                                    str(RAIZ / "data" / "procesado"))

    construir_dataset()


preparacion_datos()


@dag(dag_id="pronostico_semanal", schedule=CronTriggerTimetable("0 6 * * 1", timezone="UTC"),
     params=PARAMS, **BASE)
def pronostico_semanal():
    @task
    def validar(logical_date=None, params=None):
        from reposicion.operacion import validar_y_reportar
        return _detener_si_invalido(validar_y_reportar, LANDING, HISTORICO,
                                    _corte(logical_date, params),
                                    str(RAIZ / "data" / "reportes" / "validacion"))

    @task
    def reentrenar_con_compuerta(logical_date=None, params=None):
        from reposicion.ciclo import promocionar
        from reposicion.config import cargar_config
        costos, par = cargar_config(CONFIG)
        r = _detener_si_invalido(promocionar, LANDING, HISTORICO,
                                 _corte(logical_date, params), costos, par, MODELOS)
        return {"decision": str(r.get("decision")), "motivo": str(r.get("motivo"))}

    @task
    def publicar_pronostico(logical_date=None, params=None):
        from reposicion.ciclo import publicar
        from reposicion.config import cargar_config
        costos, par = cargar_config(CONFIG)
        carpeta = _detener_si_invalido(publicar, LANDING, HISTORICO,
                                       _corte(logical_date, params), costos, par,
                                       PUBLICADO, MODELOS)
        return str(carpeta)

    validar() >> reentrenar_con_compuerta() >> publicar_pronostico()


pronostico_semanal()


@dag(dag_id="seguimiento_desempeno", schedule=CronTriggerTimetable("0 8 * * 1", timezone="UTC"),
     params=PARAMS, **BASE)
def seguimiento_desempeno():
    @task
    def comparar_con_ventas_reales(logical_date=None, params=None):
        from reposicion.config import cargar_config
        from reposicion.seguimiento import seguimiento
        corte = _corte(logical_date, params)
        costos, _ = cargar_config(CONFIG)
        res = seguimiento(LANDING, HISTORICO, PUBLICADO, corte, costos,
                          salida=str(RAIZ / "reports" / "seguimiento" / f"hasta={corte}.csv"))
        return {"cortes_evaluados": int(len(res))}

    comparar_con_ventas_reales()


seguimiento_desempeno()
