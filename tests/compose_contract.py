import json
import subprocess


configuration = json.loads(
    subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
)
services = configuration["services"]

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

required_airflow = {"airflow-api", "airflow-scheduler", "airflow-dag-processor"}
assert required_airflow <= services.keys(), "Airflow 3 process topology is incomplete"

assert services["traefik"]["image"] == "traefik:v3.7.1"
assert services["control-panel"]["image"] == "onprem-lakehouse/control-panel:1.0.0"

routed_services = {
    name
    for name, service in services.items()
    if service.get("labels", {}).get("traefik.enable") == "true"
}
assert routed_services == {"airflow-api", "cube", "ranger-admin", "superset"}

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
assert localhost_ports("spark-master") == {(8080, "8081", "127.0.0.1")}
assert localhost_ports("control-panel") == {(8501, "8501", "127.0.0.1")}
assert localhost_ports("trino") == {(8443, "8443", "127.0.0.1")}
assert localhost_ports("superset") == {(8088, "8088", "127.0.0.1")}
assert services["trino"]["hostname"] == "trino"
assert services["openldap"]["environment"]["LDAP_ANALYST_USERNAME"]
assert services["openldap"]["environment"]["LDAP_ENGINEER_USERNAME"]
assert services["control-panel"]["environment"]["LDAP_ENGINEER_USERNAME"]
assert services["control-panel"]["environment"]["LDAP_ENGINEER_PASSWORD"]

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
