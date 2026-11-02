# DECISIONES

Decisiones técnicas y de producto del Laboratorio 1 (Motor de Reposición de Inventario).

## 1. Periodo y origen de datos
- **Decisión:** carga histórica hasta 2017-06-30; bandeja simulada con un archivo por fecha y fuente entre 2017-07-01 y 2017-07-31. Del 1 al 15 de agosto de 2017 quedan sin publicar para probar el flujo con datos nunca vistos.
- **Alternativa:** usar todo `train.csv` como histórico. Se descartó porque no habría periodo para operar el producto en el tiempo.
- La bandeja es un sistema externo: el flujo solo la lee. Solo `preparar_origen` la genera (de forma determinista) para simular la empresa.

## 2. Disponibilidad de la información en el tiempo
- **Decisión:** el nombre de cada archivo codifica la fecha del dato y la fecha de recepción (`sales_2017-07-10_recv-2017-07-11_v1.csv`). Un archivo es visible en una fecha de corte solo si `recepción <= corte`. Si hay varias versiones del mismo día, se usa la última ya recibida.
- **Rezagos simulados:** ventas +1 día, transacciones +2, petróleo +1 (solo días hábiles) y feriados 30 días antes del día.
- **Features sin fuga:** con ventas conocidas hasta T-1 y un horizonte de 7 días, todas las features de un día objetivo usan datos de al menos 7 días antes (lags de 7, 14, 21 y 28 días y medias móviles desplazadas 7 días). Hay una prueba que lo verifica: alterar una venta no cambia las features de los 7 días siguientes.
- **Alternativa:** reentrenar con ventas recursivas (predecir día a día). Se descartó por complejidad y por acumular error.

## 3. Validación de los datos
- **Inválido (detiene el flujo, sin reintentos):** columnas faltantes, fechas nulas, ventas negativas o no numéricas, claves duplicadas, nombres de archivo irreconocibles.
- **Esperado (no falla; deja aviso):** petróleo sin precio en fines de semana y feriados, y una fuente sin filas.
- Cada consumidor (ingesta, preparación, pronóstico) valida por su cuenta los datos as-of, de modo que ningún dato inválido contamina el resultado aunque otro DAG no haya corrido. Los reportes quedan en `data/reportes/`.

## 4. Correcciones de datos
- **Decisión:** una corrección llega como un archivo nuevo (`_v2`) 5 días después, y la versión 1 se considera defectuosa. Las correcciones solo son visibles desde su fecha de recepción, así que reprocesar el pasado con `backfill` reproduce lo que se habría sabido en cada fecha, y reprocesar con `--reprocess-behavior completed` después de recibir una corrección incorpora el dato corregido.
- El seguimiento se recalcula siempre desde cero contra las ventas conocidas al momento, por lo que incorpora las correcciones de forma automática.

## 5. Modelado
- **Baseline:** promedio del mismo día de la semana en las últimas 4 semanas.
- **Modelo de ML:** LightGBM con regresión por cuantiles (0.1, 0.25, 0.5, 0.75, 0.9). Se eligió por su buen desempeño en datos tabulares y por su bajo costo frente a modelos de deep learning, cuyo beneficio no justifica el costo adicional para este horizonte y estas series.
- **Validación:** origen rodante con 3 folds semanales, igual para todos los modelos; cada fold usa solo lo disponible en su fecha de corte.
- **Resultados (promedio de 3 folds):** MAE 60.4 vs 56.5, WAPE 13.0 % vs 12.1 %, costo de negocio 1.339 M vs 1.297 M (baseline vs LightGBM). La cobertura del intervalo 10-90 es de 0.82. La mejora es modesta y no uniforme: en uno de los tres folds LightGBM empeora levemente.

## 6. Pedido sugerido y costos
- Los costos viven en `config/costos.yaml` (versionado): quiebre 3.0 y merma 1.0 por unidad. Son supuestos, no datos de la empresa.
- El pedido es el pronóstico en el cuantil `quiebre / (quiebre + merma)` (0.75 con estos costos), interpolado entre los cuantiles entrenados y redondeado hacia arriba. Cambiar los costos cambia el pedido sin reentrenar ni modificar código.

## 7. Criterio para reemplazar el modelo vigente
- Cada semana se entrena un retador con datos hasta `corte - 7`. Retador y campeón se comparan en la semana `[corte-7, corte)`, que ninguno usó para entrenar, con el mismo código y los mismos costos.
- El retador reemplaza al campeón solo si mejora el costo de negocio en al menos 2 % y su cobertura 10-90 es de al menos 0.70. Los umbrales están en `config/params.yaml`.
- Resultado en la simulación: se promovió el primer modelo (sin campeón) y los tres retadores siguientes se descartaron por no alcanzar el 2 %. Cada decisión y su motivo quedan en `models/decisiones.csv`.

## 8. Idempotencia
- Cada tarea escribe en una ruta determinada por la fecha de corte, con escritura atómica; repetirla sobrescribe lo mismo. El registro de decisiones tiene una fila por corte, y si el retador ya es el campeón se conserva la decisión original.

## 9. Orquestación
- **Airflow 3.3.1 con LocalExecutor y Postgres** en Docker Compose: más liviano que Celery para un solo equipo.
- Cinco DAGs que solo orquestan: `preparar_origen` (manual), `ingesta_validacion` y `preparacion_datos` (diarios), `pronostico_semanal` y `seguimiento_desempeno` (lunes). La lógica vive en `src/reposicion/` con pruebas.
- Fecha lógica = fecha de corte. `catchup=False` y un `end_date` en 2018 evitan ejecuciones con fecha actual sin datos; los periodos pasados se procesan con backfill explícito. Concurrencia 1 por DAG porque el campeón es un estado compartido.
- La interfaz usa el modo de administrador abierto: es solo para desarrollo local.

## 10. Git y versionado de datos
- La rama `main` está protegida (PR obligatorio y pruebas en verde), con 0 aprobaciones requeridas porque el trabajo es individual. El repositorio es público para poder activar las reglas sin plan de pago y para que el equipo docente acceda.
- **DVC:** datos de entrada, históricos, bandeja, modelos y pronósticos publicados. **Remoto en disco local**: Google bloqueó la aplicación de DVC en una cuenta institucional, y configurar un cliente OAuth propio no valía el tiempo disponible. El equipo docente reconstruye desde los archivos de Kaggle, por lo que no depende de este remoto.

## 11. Limitaciones y trabajo futuro
- El modelo no usa todavía petróleo ni transacciones: se ingieren y validan, pero llegan con rezago y su aporte no se probó. Los feriados se usan solo a nivel nacional.
- Con lags mínimos de 7 días se pierde información reciente; un modelo recursivo o por horizonte podría mejorar el error.
- La promoción del día objetivo se aproxima con el promedio reciente porque no se conoce con anticipación.
- Los costos de negocio son supuestos y deberían calibrarse por familia de producto.

## 12. Uso de herramientas de IA
Se usó un asistente de IA para generar y depurar código. Todo el código y las decisiones fueron revisados y son responsabilidad de la autora.
