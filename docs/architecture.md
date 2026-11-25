# Architecture

## Constraints

The deployment follows these rules:

1. Spark performs all data processing.
2. Trino performs interactive queries but no transformation jobs.
3. Human identities originate in LDAP and are issued as OIDC tokens by authentik; machines use dedicated system identities.
4. Supported human data access passes through Ranger-enforced Trino.

## Deployment Topology

```mermaid
flowchart TB
  subgraph Access["Host Access"]
    Browser["Browser"]
    Operator["Local Operator"]
    DBeaver["DBeaver"]
  end

  subgraph Host["Single Docker Host"]
    subgraph Edge["Ingress"]
      Traefik["Traefik :443"]
    end

    subgraph Control["Control Plane"]
      LDAP["OpenLDAP"]
      Authentik["authentik OIDC"]
      Ranger["Ranger Admin"]
      UserSync["Ranger UserSync"]
      AirflowAPI["Airflow API"]
      Scheduler["Airflow Scheduler"]
      DagProcessor["Airflow DAG Processor"]
      Redis["Redis Task Broker"]
      ControlPanel["Streamlit Control Panel"]
    end

    subgraph Compute["Compute & Query"]
      SparkMaster["Spark Master"]
      SparkWorker["Spark Worker"]
      AirflowWorker["Airflow Celery Worker"]
      Trino["Trino"]
      Cube["Cube Core"]
      Superset["Superset"]
    end

    subgraph State["Persistent State"]
      PostgreSQL[("PostgreSQL")]
      Polaris["Polaris"]
      Garage[("Garage")]
    end
  end

  Browser -->|HTTPS hostnames| Traefik
  Operator -->|localhost :8501| ControlPanel
  Operator -->|localhost :8080| AirflowAPI
  Operator -->|localhost :8081| SparkMaster
  Operator -->|localhost :8088| Superset
  DBeaver -->|native TLS :8443| Trino
  Traefik --> AirflowAPI & Ranger & Cube & Superset & Authentik
  ControlPanel --> AirflowAPI
  LDAP --> Authentik & Ranger & Trino
  Authentik --> AirflowAPI & Superset & Trino & Polaris
  UserSync --> Ranger
  DagProcessor --> PostgreSQL
  Scheduler --> Redis --> AirflowWorker
  Scheduler --> PostgreSQL
  AirflowWorker --> PostgreSQL & SparkMaster
  SparkMaster --> SparkWorker
  SparkWorker --> PostgreSQL & Polaris & Garage
  Cube --> Trino
  Trino --> Ranger & Polaris & Garage
  AirflowAPI --> PostgreSQL
  Ranger --> PostgreSQL
  Polaris --> PostgreSQL
  Superset --> PostgreSQL
```

Each service has one replica. Airflow separates orchestration from queued task
work, and Spark separates coordination from execution.

## Exposure Model

Traefik provides the browser ingress tier for Airflow, Ranger, Cube, and
Superset. These services opt in through Docker labels, and Traefik connects to
their private container ports on the `lakehouse` network.

The control panel and Spark UI are operational tools bound only to loopback, so
they are not registered with Traefik. Trino exposes its own TLS listener on
loopback because JDBC speaks directly to the coordinator. Airflow, Ranger, and
Superset are available through both direct loopback ports and named HTTPS routes.

## Startup Flow

The root CLI starts core services, waits for health, applies Ranger and Polaris
configuration, then starts processing, query, and presentation services.

## Persistence

Docker volumes retain PostgreSQL, LDAP, Ranger, Garage, Airflow logs, and
Traefik-independent application state. Redis is a transient broker; PostgreSQL
remains authoritative for Airflow and Celery results. Configuration is
bind-mounted read-only from the repository, including the effective Airflow,
Spark, Redis, PostgreSQL, Polaris, and Streamlit settings. Generated secrets,
certificates, and deployment connection values remain outside those tracked
files and are ignored by version control.
