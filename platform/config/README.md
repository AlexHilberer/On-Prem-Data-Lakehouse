# Runtime Configuration

Compose mounts tracked configuration read-only so a fresh deployment uses the
same reviewed settings as the current stack. Full vendor defaults are retained
where the application provides them, with the active lakehouse overrides left
uncommented.

| System | Tracked configuration | Container location |
| --- | --- | --- |
| Airflow 3.3.0 | `airflow/airflow.cfg` | `/opt/airflow/config/airflow.cfg` |
| Spark 3.5.8 | `spark/spark-defaults.conf`, `spark/spark-env.sh` | `/opt/spark/conf/` |
| Redis 7.2.15 | `redis/redis.conf` | `/usr/local/etc/redis/redis.conf` |
| PostgreSQL 17.10 | `postgres/postgresql.conf`, `postgres/pg_hba.conf`, `postgres/pg_ident.conf` | `/etc/postgresql/` |
| Polaris 1.6.0 | `polaris/application.properties` | `/deployments/config/application.properties` |
| Streamlit 1.59.2 | `control-panel/config.toml` | `/tmp/.streamlit/config.toml` |
| Trino 481 | `trino/` | `/etc/trino/` |
| Traefik 3.7.1 | `traefik/` | `/etc/traefik/` |
| Superset 6.1.0 | `superset/superset_config.py` | `/app/pythonpath/superset_config.py` |

Cube configuration and models live in `analytics/cube` and are mounted at
`/cube/conf`. OpenLDAP and Ranger configuration is packaged with their local
images, while Garage is rendered from its tracked template during
`./lakehouse.sh init`.

Secrets, passwords, generated certificates, and deployment connection strings
remain in the ignored `.env` and generated PKI files. Environment variables may
therefore override only settings that are secret or specific to container
wiring.

When upgrading a component, regenerate its full default snapshot from the new
pinned release, reapply the small lakehouse override set, and run the static and
integration suites. Vendor comments are intentionally kept because they make
the tracked snapshot usable as a configuration reference.
