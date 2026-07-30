# Orchestration

Apache Airflow owns pipeline control flow while Spark owns data processing.
The DAG never performs analytical transformations inside Airflow tasks.

## Airflow Processes

Airflow 3 runs its minimum supported process set:

| Process | Responsibility | Public |
| --- | --- | --- |
| API server | UI, REST API, task execution API | Traefik HTTPS and localhost `8080` |
| Scheduler | Creates task instances and runs LocalExecutor | No |
| DAG processor | Parses and serializes DAG code | No |

These are separate responsibilities, not redundant replicas.

## Retail DAG

```mermaid
flowchart LR
  Trigger["Manual trigger<br/>automatic volume or rows + seed"] --> Generate["generate<br/>Python task"]
  Generate --> Batch["Batch ID in XCom"]
  Batch --> SparkSubmit["spark_transform<br/>SparkSubmitOperator"]
  SparkSubmit --> Spark["Spark master + worker"]
  Spark --> Iceberg["Bronze · Silver · Gold"]
```

The DAG is unscheduled by design and can be triggered from the UI or with:

```bash
./lakehouse.sh pipeline
ROWS=5000 SEED=42 ./lakehouse.sh pipeline
```

It can also be triggered from the
[control panel](../control-panel/README.md) at `http://127.0.0.1:8501`.
Both the CLI and control panel call Airflow API v2 rather than writing directly
to the metadata database.

The first automatic run creates two years of history; later runs advance the
simulation by 30 days. Retries remain idempotent because every generated
dataset and Iceberg write is scoped by a batch identifier.
