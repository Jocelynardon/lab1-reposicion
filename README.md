# Motor de Reposición de Inventario

Laboratorio 1 · Maestría en Data Science · Reproducibilidad y orquestación de un producto de ML.

Cada semana el producto entrega, por tienda y familia de producto (datos de Corporación Favorita):

1. un **pronóstico de ventas** a 7 días con incertidumbre (cuantiles 0.1, 0.25, 0.5, 0.75 y 0.9),
2. un **pedido sugerido** derivado del pronóstico y de los costos de negocio (`config/costos.yaml`),
3. el **seguimiento del desempeño** contra las ventas reales a medida que se conocen.

Las decisiones técnicas y de producto están en [DECISIONES.md](DECISIONES.md).

## Cómo funciona

```
data/kaggle ──► preparar_origen ──► data/historico + data/landing (bandeja: el flujo solo la lee)
                                         │
                 ingesta_validacion (diario)       valida lo disponible al corte
                 preparacion_datos  (diario)       dataset procesado as-of
                 pronostico_semanal (lunes)        validar → reentrenar con compuerta → publicar
                 seguimiento_desempeno (lunes)     publicado vs ventas reales
```

Principio: **toda predicción usa solo lo que estaba disponible en su fecha de corte**. Los archivos de la bandeja codifican la fecha del dato y la de recepción (`sales_2017-07-10_recv-2017-07-11_v1.csv`), y una corrección (`_v2`) solo es visible desde su recepción.

## Requisitos

- Docker con Compose v2 (se recomiendan 8 GB de memoria para Docker).
- Git. Python 3.11 o superior solo si desea correr las pruebas o DVC fuera de Docker.

## Puesta en marcha desde cero

1. **Clonar** el repositorio y entrar a la carpeta.
2. **Colocar los datos de Kaggle** (competencia *Store Sales - Time Series Forecasting*) en `data/kaggle/`. Se necesitan exactamente estos 5 archivos: `train.csv`, `stores.csv`, `holidays_events.csv`, `oil.csv` y `transactions.csv`.

   ```bash
   mkdir -p data/kaggle        # Windows: mkdir data\kaggle
   cp /ruta/descargas/{train,stores,holidays_events,oil,transactions}.csv data/kaggle/
   ```

3. **Crear la carpeta de logs.** Linux o macOS: `mkdir -p airflow/logs && echo "AIRFLOW_UID=$(id -u)" > .env`. Windows: `mkdir airflow\logs`.
4. **Construir y levantar Airflow 3.3.1:**

   ```bash
   docker compose build
   docker compose up airflow-init
   docker compose up -d
   ```

   La interfaz queda en http://localhost:8080 (modo de administrador abierto, solo para desarrollo local; no pide usuario). Antes del paso siguiente espere 30 a 60 segundos hasta que `docker compose exec airflow-scheduler airflow dags list` muestre los 5 DAGs; si se ejecuta el paso 5 antes, falla con `DagNotFound`.
5. **Generar el sistema de origen** (carga histórica hasta 2017-06-30 y bandeja de julio de 2017). Ejecute el DAG `preparar_origen` desde la interfaz o con:

   ```bash
   docker compose exec airflow-scheduler airflow dags trigger preparar_origen
   ```

   Espere a que termine en verde. Para otro periodo se puede pasar `--conf '{"corte_historico": "2017-06-30", "fin_bandeja": "2017-08-15"}'` (los datos de Kaggle llegan hasta el 15 de agosto de 2017).
6. **Ejecutar el flujo sobre el periodo** con backfill. El DAG semanal corre los lunes a las 06:00 UTC, por eso el `--to-date` lleva un día de más:

   ```bash
   docker compose exec airflow-scheduler airflow backfill create --dag-id pronostico_semanal --from-date 2017-07-10 --to-date 2017-08-01 --reprocess-behavior completed --max-active-runs 1
   docker compose exec airflow-scheduler airflow backfill create --dag-id seguimiento_desempeno --from-date 2017-07-31 --to-date 2017-08-02 --reprocess-behavior completed
   docker compose exec airflow-scheduler airflow backfill create --dag-id ingesta_validacion --from-date 2017-07-28 --to-date 2017-08-01 --reprocess-behavior completed
   docker compose exec airflow-scheduler airflow backfill create --dag-id preparacion_datos --from-date 2017-07-30 --to-date 2017-08-01 --reprocess-behavior completed
   ```

   El primer lunes entrena y promueve el primer modelo; los siguientes aplican la compuerta de promoción. Las corridas del semanal son secuenciales porque el campeón es un estado compartido. Para **reprocesar** datos corregidos, repita el backfill con `--reprocess-behavior completed`.
7. **Resultados:**
   - `data/publicado/corte=AAAA-MM-DD/`: pronóstico por cuantiles, pedido sugerido y `meta.json` (modelo, costos y commit usados).
   - `models/decisiones.csv`: decisión de la compuerta en cada corte, con su motivo.
   - `reports/seguimiento/hasta=AAAA-MM-DD.csv`: desempeño de lo publicado.
   - `data/reportes/`: catálogo de la bandeja y reportes de validación por corte.

Para apagar: `docker compose down` (con `--volumes` se borra también la base de metadatos).

## Estructura

| Ruta | Contenido |
|---|---|
| `src/reposicion/` | toda la lógica: bandeja, lectura as-of, validación, features, modelos, métricas, ciclo y seguimiento |
| `dags/` | DAGs de Airflow (solo orquestan) |
| `config/` | `costos.yaml` (costo de quiebre y de merma) y `params.yaml` |
| `tests/` | pruebas con `pytest` sobre datos sintéticos |
| `*.dvc`, `.dvc/` | punteros y configuración de DVC |
| `reports/` | comparación de modelos y seguimiento |
| `docs/evidencia/` | capturas y salidas que documentan el funcionamiento |

## Configuración

- `config/costos.yaml`: costo de quedarse sin producto (quiebre) y de merma. El pedido sugerido es el pronóstico en el cuantil `quiebre / (quiebre + merma)`. **Cambiar estos valores cambia el pedido sin tocar el código ni reentrenar.**
- `config/params.yaml`: horizonte, ventana de entrenamiento, cuantiles, hiperparámetros y umbrales de la compuerta de promoción.

## Pruebas

```bash
pip install -r requirements.txt
pytest -q
```

Se ejecutan en cada Pull Request con GitHub Actions. La rama `main` está protegida.

## Versionado de datos con DVC

Los datos, la bandeja, los resultados procesados, los modelos y los pronósticos publicados se versionan con DVC y **no están en Git**; Git guarda solo los punteros (`*.dvc`). El remoto configurado es una carpeta local (`E:\Galileo\2604\dvc-remote`), porque Google bloqueó la aplicación de DVC en una cuenta institucional. En este proyecto hay que **indicar siempre los archivos `.dvc`**, porque los comandos sin argumentos no detectan los punteros de `data/`:

```bash
dvc add data/kaggle data/historico data/landing data/procesado data/publicado data/reportes models
dvc push data/historico.dvc data/landing.dvc data/publicado.dvc data/procesado.dvc data/reportes.dvc models.dvc
dvc pull data/publicado.dvc
```

El equipo docente reconstruye el producto desde los archivos de Kaggle, así que no depende de ese remoto.

## Resultados

Validación temporal de origen rodante (3 folds semanales, horizonte de 7 días, costos 3.0 y 1.0), promedio de los folds:

| Modelo | MAE | WAPE | Pinball | Cobertura 10-90 | Costo de negocio |
|---|---|---|---|---|---|
| Baseline (mismo día de la semana, 4 semanas) | 60.4 | 13.0 % | n/a | n/a | 1 338 520 |
| LightGBM por cuantiles | 56.5 | 12.1 % | 21.0 | 0.82 | 1 297 479 |

LightGBM mejora al baseline en promedio y en 2 de los 3 folds. El detalle por fold está en `reports/comparacion_modelos.csv`.

**Compuerta de promoción.** El retador reemplaza al campeón si mejora el costo de negocio en al menos 2 % y su cobertura es de al menos 0.70, evaluados en la semana que ninguno de los dos vio para entrenar:

| Corte | Decisión | Motivo |
|---|---|---|
| 2017-07-10 | promovido | sin campeón vigente |
| 2017-07-17 | descartado | mejora de costo 0.7 % (menor al 2 % exigido) |
| 2017-07-24 | descartado | mejora de costo -0.4 % (menor al 2 % exigido) |
| 2017-07-31 | descartado | mejora de costo 0.3 % (menor al 2 % exigido) |

Ejecutar el flujo por línea de comandos y luego con Airflow produjo decisiones y costos idénticos.

## Evidencia de funcionamiento

- Ejecuciones en la interfaz de Airflow: `docs/evidencia/01_airflow_dags_verdes.png` y `docs/evidencia/02_grafo_pronostico_semanal.png`.
- Datos inválidos: `docs/evidencia/03_datos_invalidos_rojo.png` (la validación detiene el flujo sin reintentos y deja un reporte con `estado: invalido`) y `docs/evidencia/04_recuperacion_verde.png` (al restaurar la bandeja, las mismas corridas pasan a verde).
- Correcciones: la versión corregida de un día (`_v2`) solo es visible desde su fecha de recepción; el catálogo en `data/reportes/catalogo/` lo muestra (0 versiones corregidas el día previo y 1 el día de recepción).
- Decisiones de la compuerta: `docs/evidencia/05_decisiones.png`.
- Comparación de modelos: `reports/comparacion_modelos.csv`. Seguimiento del desempeño: `reports/seguimiento/`.

### Reproducción de un pronóstico pasado con DVC

Se reprodujo el pronóstico del corte 2017-07-24 en un directorio limpio, con la versión de código del tag `publicado-2017-07-31` y los datos descargados con DVC:

```bash
git worktree add ../repro-2017-07-24 publicado-2017-07-31
cd ../repro-2017-07-24
dvc pull data/historico.dvc data/landing.dvc
dvc pull data/publicado.dvc
PYTHONPATH=src python -m reposicion.reproducir --corte 2017-07-24
```

Resultado obtenido:

```json
{
  "corte": "2017-07-24",
  "version_modelo": "v_2017-07-03",
  "git_commit_original": "c1a841a3cb5178ca71226e3603dd9c1568761534",
  "filas": 12474,
  "max_dif_abs": 0.0,
  "identico": true
}
```

El módulo `reproducir` regenera el pronóstico con la versión de modelo y los costos registrados en el `meta.json` publicado, y lo compara con el original: la diferencia máxima es 0. El `git_commit_original` es el de la rama de trabajo, previo al *squash merge*; el código equivalente es el del tag. Captura: `docs/evidencia/06_reproduccion_dvc.png`.

## Situaciones reales que el flujo maneja

| Situación | Comportamiento |
|---|---|
| Los datos llegan por partes | cada archivo lleva su fecha de recepción; el flujo solo ve lo recibido al corte |
| Un dato se corrige después de publicado | la versión corregida (`_v2`) entra desde su recepción y el reprocesamiento la incorpora |
| Datos inválidos (columnas faltantes, ventas negativas, duplicados) | la tarea falla **sin reintentos** y deja un reporte; no se publica nada |
| Petróleo sin precio en fines de semana y feriados | se registra un aviso; no falla |
| Repetir una tarea o un backfill | es idempotente: mismas rutas por fecha de corte y escritura atómica |

## Limitaciones

Ver la sección 11 de [DECISIONES.md](DECISIONES.md).
