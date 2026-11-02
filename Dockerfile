FROM apache/airflow:3.3.1
RUN pip install --no-cache-dir pandas pyarrow pyyaml lightgbm scikit-learn joblib
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
USER airflow
