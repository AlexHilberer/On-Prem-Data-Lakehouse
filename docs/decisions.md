# Architecture Decisions

| Decision | Rationale | Tradeoff |
| --- | --- | --- |
| Spark-only processing | Keeps transformation ownership explicit and testable | Small jobs still pay Spark startup cost |
| Trino as query-only engine | Separates interactive query concerns from pipeline compute | Requires Spark for every materialized transformation |
| LDAP as human identity source | Demonstrates centralized on-premises identity | Application metadata still caches user records |
| Ranger enforcement through Trino | Uses a supported policy plugin and one governed query path | Polaris and Garage are protected by network and service credentials instead |
| No impersonation | Avoids cross-user delegation complexity | Cube queries appear downstream as `svc_cube` |
| Celery Airflow worker | Keeps task execution out of the scheduler and makes the execution boundary visible | Requires a Redis broker and another container |
| Four Airflow processes | Airflow 3 uses separate API, scheduler, DAG processor, and task worker responsibilities | More containers than development `standalone` mode |
| Ranger source build | No suitable official runtime image is available | First build is slow and resource intensive |
| Polaris wrapper image | Relational persistence requires the official admin tool bootstrap | Local image combines two official artifacts |
| Selective Traefik ingress | Centralizes TLS for named browser apps while labels make participation explicit | Operational tools use separate loopback ports |
| Single shell lifecycle | Offers one discoverable operational interface | Internal helpers remain implementation details |
| Explicit container names | Makes this single-host example easier to inspect | Prevents Compose replica scaling without editing the file |
| Localhost operator UIs | Makes Airflow, Spark, Streamlit, and JDBC immediately usable from the host | Remote workstations require tunneling or changed bindings |
| Local control panel without login | Keeps the loopback-only operator workflow frictionless while using the configured engineer identity internally | Must remain bound to localhost because every local user receives engineer-level pipeline controls |
| Spark master UI proxy | Exposes worker and application monitoring through one port | The master becomes the UI access path |
| Native Trino TLS | Gives JDBC clients a direct authenticated coordinator endpoint | Clients must trust the generated local CA |
| Single replicas | Matches the POC resource and simplicity target | No high availability or failover |

These decisions optimize for an understandable, demonstrable on-premises
platform rather than production-scale availability.
