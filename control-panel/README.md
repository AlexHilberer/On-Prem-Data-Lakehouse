# Control Panel

The Streamlit control panel provides a focused operational UI for the
`retail_lakehouse_pipeline` DAG.

## Access

Open `http://127.0.0.1:8501`. The panel has no user-facing login and is intended
only as a local convenience interface.

The port is bound to `127.0.0.1` and is intentionally not routed through
Traefik. This keeps the operational POC immediately available on the Docker
host without adding another public hostname. Airflow itself remains reachable
through both `http://127.0.0.1:8080` and its Traefik HTTPS route.

The panel silently obtains an Airflow API token with
`LDAP_ENGINEER_USERNAME` and `LDAP_ENGINEER_PASSWORD` from `.env`. Airflow still
validates that internal identity through LDAP and authorizes it with the
engineer role.

## Features

- Trigger automatic two-year/monthly demo periods or override the order volume.
- Supply a deterministic seed for reproducible business behavior.
- Inspect the latest 20 DAG runs and their parameters.
- Inspect task states and timing for a selected run.
- Refresh manually or poll active runs every 5, 10, or 30 seconds.
- Jump directly to the local Airflow and Spark UIs.

## Data Flow

```mermaid
sequenceDiagram
  actor User
  participant Panel as Streamlit
  participant Airflow
  participant LDAP
  participant Spark

  User->>Panel: Open local operator UI
  Panel->>Airflow: POST /auth/token with configured engineer
  Airflow->>LDAP: Validate internal identity and groups
  Airflow-->>Panel: JWT
  User->>Panel: Trigger rows and seed
  Panel->>Airflow: POST DAG run with JWT
  Airflow->>Spark: Submit transformation
  Panel->>Airflow: Poll runs and task instances
  Airflow-->>Panel: State and timing
```

The application calls only the supported Airflow REST API and never reads the
Airflow metadata database. The internal password is supplied through the
container environment and is never entered or displayed in the UI.
