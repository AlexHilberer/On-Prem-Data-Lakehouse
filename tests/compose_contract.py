import configparser
import json
from pathlib import Path
import re
import subprocess
import tomllib


configuration = json.loads(
    subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
)
services = configuration["services"]
compose_source = Path("compose.yaml").read_text()
env_example = Path(".env.example").read_text()

assert not re.search(r"\$\{[A-Z_][A-Z0-9_]*_IMAGE(?::-[^}]*)?\}", compose_source)
assert not re.search(r"^[A-Z_][A-Z0-9_]*_IMAGE=", env_example, re.MULTILINE)


def mounted_config(service_name, target):
    mount = next(
        item for item in services[service_name]["volumes"] if item["target"] == target
    )
    assert mount["read_only"] is True
    return mount

for service_name, service in services.items():
    assert service["container_name"] == f"lakehouse-{service_name}"

for removed_service in (
    "airflow-init",
    "caddy",
    "platform-bootstrap",
    "polaris-bootstrap",
    "superset-init",
):
    assert removed_service not in services, f"removed service present: {removed_service}"

required_airflow = {
    "airflow-api",
    "airflow-scheduler",
    "airflow-worker",
    "airflow-dag-processor",
}
assert required_airflow <= services.keys(), "Airflow 3 process topology is incomplete"

assert services["traefik"]["image"] == "traefik:v3.7.1"
assert services["control-panel"]["image"] == "onprem-lakehouse/control-panel:1.0.0"
assert services["redis"]["image"] == "redis:7.2.15-bookworm"
assert not services["redis"].get("ports"), "Redis must remain internal"

airflow_environment = services["airflow-scheduler"]["environment"]
assert airflow_environment["AIRFLOW_CONFIG"] == "/opt/airflow/config/airflow.cfg"
assert airflow_environment["AIRFLOW__CELERY__RESULT_BACKEND"].startswith(
    "db+postgresql+psycopg2://airflow:"
)

airflow_config = configparser.ConfigParser()
airflow_config.read("platform/config/airflow/airflow.cfg")
assert airflow_config["core"]["executor"] == "CeleryExecutor"
assert airflow_config["core"].getint("parallelism") == 2
assert airflow_config["celery"]["broker_url"] == "redis://redis:6379/0"
assert airflow_config["celery"].getint("worker_concurrency") == 2
assert airflow_config["celery_broker_transport_options"].getint(
    "visibility_timeout"
) == 86400

airflow_config_mount = mounted_config(
    "airflow-scheduler", "/opt/airflow/config/airflow.cfg"
)
assert airflow_config_mount["source"].endswith(
    "/platform/config/airflow/airflow.cfg"
)
assert services["airflow-worker"]["command"] == ["celery", "worker"]
assert {"airflow-api", "redis", "spark-master"} <= services["airflow-worker"][
    "depends_on"
].keys()

redis_config = Path("platform/config/redis/redis.conf").read_text()
assert "bind * -::*" in redis_config
assert "protected-mode no" in redis_config
assert "appendonly no" in redis_config
assert services["redis"]["command"] == [
    "redis-server",
    "/usr/local/etc/redis/redis.conf",
]
assert mounted_config("redis", "/usr/local/etc/redis/redis.conf")[
    "source"
].endswith("/platform/config/redis/redis.conf")

postgres_config = Path("platform/config/postgres/postgresql.conf").read_text()
assert "hba_file = '/etc/postgresql/pg_hba.conf'" in postgres_config
assert "ident_file = '/etc/postgresql/pg_ident.conf'" in postgres_config
assert "host all all all scram-sha-256" in Path(
    "platform/config/postgres/pg_hba.conf"
).read_text()
assert services["postgres"]["command"] == [
    "postgres",
    "-c",
    "config_file=/etc/postgresql/postgresql.conf",
]
for filename in ("postgresql.conf", "pg_hba.conf", "pg_ident.conf"):
    assert mounted_config("postgres", f"/etc/postgresql/{filename}")[
        "source"
    ].endswith(f"/platform/config/postgres/{filename}")

spark_defaults = Path("platform/config/spark/spark-defaults.conf").read_text()
assert "spark.master                                      spark://spark-master:7077" in spark_defaults
assert "spark.sql.catalog.lakehouse.type                  rest" in spark_defaults
for service_name in (*required_airflow, "spark-master", "spark-worker"):
    mounted_config(service_name, "/opt/spark/conf/spark-defaults.conf")
    mounted_config(service_name, "/opt/spark/conf/spark-env.sh")

polaris_properties = Path(
    "platform/config/polaris/application.properties"
).read_text()
assert "polaris.persistence.type=relational-jdbc" in polaris_properties
assert services["polaris"]["environment"]["QUARKUS_CONFIG_LOCATIONS"] == (
    "/deployments/config/application.properties,"
    "/deployments/config/auth-external.properties"
)
assert "polaris.authentication.type=external" in Path(
    "platform/config/polaris/auth-external.properties"
).read_text()
assert "polaris.authentication.type=mixed" in Path(
    "platform/config/polaris/auth-mixed.properties"
).read_text()
assert "polaris.authentication.type" not in polaris_properties
assert "POLARIS_PERSISTENCE_TYPE" not in services["polaris"]["environment"]
for name in ("application", "auth-external", "auth-mixed"):
    mounted_config("polaris", f"/deployments/config/{name}.properties")

with Path("platform/config/control-panel/config.toml").open("rb") as handle:
    streamlit_config = tomllib.load(handle)
assert streamlit_config["server"]["address"] == "0.0.0.0"
assert streamlit_config["server"]["port"] == 8501
assert streamlit_config["server"]["headless"] is True
assert streamlit_config["browser"]["gatherUsageStats"] is False
assert services["control-panel"]["command"] == ["streamlit", "run", "app.py"]
mounted_config("control-panel", "/tmp/.streamlit/config.toml")

assert len(Path("platform/config/airflow/airflow.cfg").read_text().splitlines()) > 4000
assert len(redis_config.splitlines()) > 2000
assert len(postgres_config.splitlines()) > 800
assert len(Path("platform/config/control-panel/config.toml").read_text().splitlines()) > 2500

routed_services = {
    name
    for name, service in services.items()
    if service.get("labels", {}).get("traefik.enable") == "true"
}
assert routed_services == {
    "airflow-api",
    "authentik-server",
    "cube",
    "jupyterhub",
    "ranger-admin",
    "superset",
}

socket_mount = next(
    mount
    for mount in services["traefik"]["volumes"]
    if mount["target"] == "/var/run/docker.sock"
)
assert socket_mount["read_only"] is True

published_ports = {
    (port["target"], port["published"]) for port in services["traefik"]["ports"]
}
assert published_ports == {(80, "80"), (443, "443")}


def localhost_ports(service_name):
    return {
        (port["target"], port["published"], port["host_ip"])
        for port in services[service_name].get("ports", [])
    }


assert localhost_ports("airflow-api") == {(8080, "8080", "127.0.0.1")}
assert localhost_ports("ranger-admin") == {(6080, "6080", "127.0.0.1")}
assert localhost_ports("spark-master") == {(8080, "8081", "127.0.0.1")}
assert localhost_ports("control-panel") == {(8501, "8501", "127.0.0.1")}
assert localhost_ports("trino") == {(8443, "8443", "127.0.0.1")}
assert localhost_ports("superset") == {(8088, "8088", "127.0.0.1")}
assert localhost_ports("jupyterhub") == {(8000, "8000", "127.0.0.1")}
for target in (
    "/srv/jupyterhub/jupyterhub_config.py",
    "/srv/jupyterhub/token_broker.py",
    "/etc/ipython/ipython_kernel_config.py",
    "/opt/lakehouse-notebook",
):
    mounted_config("jupyterhub", target)
assert services["jupyterhub"]["hostname"] == "jupyterhub"
assert services["jupyterhub"]["environment"]["GARAGE_ACCESS_KEY"]
assert "spark-master" in services["jupyterhub"]["depends_on"]
assert services["trino"]["hostname"] == "trino"
assert services["openldap"]["environment"]["LDAP_ANALYST_USERNAME"]
assert services["openldap"]["environment"]["LDAP_ENGINEER_USERNAME"]
import re

required_by_panel = set(re.findall(r'os\.environ\["([A-Z_]+)"\]', Path("control-panel/app.py").read_text()))
assert required_by_panel <= set(services["control-panel"]["environment"]), required_by_panel
assert services["control-panel"]["environment"]["AIRFLOW_SERVICE_USERNAME"] == "svc_control"
assert services["control-panel"]["environment"]["AIRFLOW_SERVICE_PASSWORD"]

garage_config = next(
    mount
    for mount in services["garage"]["volumes"]
    if mount["target"] == "/etc/garage.toml"
)
assert garage_config["source"].endswith(
    "/platform/config/garage/garage.generated.toml"
)

assert "spark.ui.reverseProxy=true" in services["spark-master"]["environment"][
    "SPARK_MASTER_OPTS"
]
assert "spark.ui.reverseProxy=true" in services["spark-worker"]["environment"][
    "SPARK_WORKER_OPTS"
]

# Spark runs in client mode, so executors must reach the driver inside the task worker.
dag_source = Path("orchestration/dags/retail_lakehouse_pipeline.py").read_text()
assert '"spark.driver.host": "airflow-worker"' in dag_source
