# Container Image Inventory

All runtime versions are pinned in `.env.example`; `latest` tags are rejected by
the static tests. Registry tags and source-release URLs were last reviewed on
2026-08-26.

| Component | Source | Strategy |
| --- | --- | --- |
| OpenLDAP 2.6.13 | [OpenLDAP source release](https://www.openldap.org/software/download/OpenLDAP/openldap-release/openldap-2.6.13.tgz) | Multi-stage source build because upstream does not publish an official runtime image |
| Ranger 2.8.0 | [Apache source release](https://downloads.apache.org/ranger/2.8.0/apache-ranger-2.8.0.tar.gz) | Multi-stage Maven build for Admin and UserSync; verifies the Apache SHA-512 checksum |
| Spark 3.5.8 | [`apache/spark:3.5.8-java17-python3`](https://hub.docker.com/_/spark) | Extended with Iceberg, AWS, PostgreSQL JDBC, and pipeline dependencies |
| Airflow 3.3.0 | [`apache/airflow:3.3.0-python3.10`](https://hub.docker.com/r/apache/airflow/tags) | Extended with the Spark client, provider, and pipeline dependencies |
| Trino 481 | [`trinodb/trino:481`](https://hub.docker.com/r/trinodb/trino/tags) | Official image with the native Ranger access-control plugin |
| Garage 2.3.0 | [`dxflrs/garage:v2.3.0`](https://hub.docker.com/r/dxflrs/garage/tags) | Image published by Association Deuxfleurs |
| Polaris 1.6.0 | [`apache/polaris:1.6.0`](https://hub.docker.com/r/apache/polaris/tags) and [`apache/polaris-admin-tool:1.6.0`](https://hub.docker.com/r/apache/polaris-admin-tool/tags) | Local image combines official server and admin artifacts for relational bootstrap |
| PostgreSQL 17.10 | [`postgres:17.10-bookworm`](https://hub.docker.com/_/postgres) | Docker Official Image |
| Redis 7.2.15 | [`redis:7.2.15-bookworm`](https://hub.docker.com/_/redis) | Internal Celery task broker with no published port |
| Cube Core 1.7.11 | [`cubejs/cube:v1.7.11`](https://hub.docker.com/r/cubejs/cube/tags) | Project image with Trino and PostgreSQL-compatible SQL support |
| Superset 6.1.0 | [`apache/superset:6.1.0`](https://hub.docker.com/r/apache/superset/tags) | Extended with LDAP and PostgreSQL drivers |
| Traefik 3.7.1 | [`traefik:v3.7.1`](https://hub.docker.com/_/traefik) | Official image providing local HTTPS ingress through Docker labels |
| Control panel 1.0.0 | [`python:3.12.13-slim-bookworm`](https://hub.docker.com/_/python) with Streamlit 1.59.2 | Minimal local operator UI for Airflow pipeline operations |

Before upgrading, verify the new upstream tag, review release notes, update the
pin, rebuild with `./lakehouse.sh build --pull`, run static and integration
tests, then execute the pipeline against fresh and restored data.

Image provenance is independent of exposure. Traefik routing is enabled through
Compose labels only for Airflow, Ranger, Superset, and Cube; direct localhost
services remain ordinary Docker services on the shared internal network.

Pinned vendor configuration snapshots are documented in the
[runtime configuration inventory](../platform/config/README.md). Regenerate
those snapshots together with an image upgrade so defaults and runtime
behavior cannot drift independently.
