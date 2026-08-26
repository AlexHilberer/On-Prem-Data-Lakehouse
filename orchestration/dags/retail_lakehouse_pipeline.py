from datetime import datetime, timezone
import os
import uuid

from airflow.decorators import dag, task
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

from pipeline.generator import generate_batch


@dag(
    dag_id="retail_lakehouse_pipeline",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    tags=["lakehouse", "retail", "spark"],
    params={"rows": 0, "seed": 42},
)
def retail_lakehouse_pipeline():
    @task
    def generate(**context) -> dict:
        batch_id = str(uuid.uuid4())
        return generate_batch(
            database_url=os.environ["AIRFLOW_CONN_RETAIL_SOURCE"],
            rows=int(context["params"]["rows"]),
            seed=int(context["params"]["seed"]),
            batch_id=batch_id,
        )

    batch = generate()
    transform = SparkSubmitOperator(
        task_id="spark_transform",
        application="/opt/airflow/pipeline/spark_retail.py",
        conn_id="spark_default",
        application_args=[
            "--batch-id",
            "{{ ti.xcom_pull(task_ids='generate')['batch_id'] }}",
        ],
        conf={
            # Spark executors connect back to the client-mode driver in this worker.
            "spark.driver.host": "airflow-worker",
            "spark.driver.bindAddress": "0.0.0.0",
        },
        verbose=True,
    )
    batch >> transform


retail_lakehouse_pipeline()
