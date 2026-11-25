#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"
requested_project_name="${COMPOSE_PROJECT_NAME:-}"
set -a
# shellcheck disable=SC1091
source .env
set +a
if [[ -n "${requested_project_name}" ]]; then
  export COMPOSE_PROJECT_NAME="${requested_project_name}"
fi

if ! docker info >/dev/null 2>&1; then
  printf 'Docker daemon is unavailable; integration tests skipped.\n'
  exit 0
fi

required=(
  postgres redis openldap ranger-admin garage polaris spark-master spark-worker
  airflow-api airflow-scheduler airflow-worker airflow-dag-processor
  control-panel trino cube superset traefik authentik-server authentik-worker jupyterhub
)
for service in "${required[@]}"; do
  test -n "$(docker compose ps -q "${service}")" || {
    printf 'Service %s is not running. Run ./lakehouse.sh up first.\n' "${service}" >&2
    exit 1
  }
done

docker compose exec -T -e LDAPTLS_CACERT=/run/certs/ca.crt openldap ldapwhoami \
  -x -H ldaps://openldap:636 \
  -D "uid=${LDAP_ANALYST_USERNAME},ou=people,dc=lakehouse,dc=local" \
  -w "${LDAP_ANALYST_PASSWORD}" >/dev/null
docker compose exec -T -e LDAPTLS_CACERT=/run/certs/ca.crt openldap ldapwhoami \
  -x -H ldaps://openldap:636 \
  -D "uid=${LDAP_ENGINEER_USERNAME},ou=people,dc=lakehouse,dc=local" \
  -w "${LDAP_ENGINEER_PASSWORD}" >/dev/null
docker compose exec -T -e LDAPTLS_CACERT=/run/certs/ca.crt openldap ldapsearch \
  -LLL -x -H ldaps://openldap:636 \
  -D "cn=admin,dc=lakehouse,dc=local" \
  -w "${LDAP_ADMIN_PASSWORD}" \
  -b "uid=${LDAP_ANALYST_USERNAME},ou=people,dc=lakehouse,dc=local" memberOf |
  grep -q 'memberOf: cn=lakehouse_analysts,ou=groups,dc=lakehouse,dc=local'

curl --fail --silent --show-error --cacert platform/config/pki/ca.crt \
  --resolve airflow.lakehouse.local:443:127.0.0.1 \
  https://airflow.lakehouse.local/api/v2/monitor/health >/dev/null
curl --fail --silent --show-error --cacert platform/config/pki/ca.crt \
  --resolve superset.lakehouse.local:443:127.0.0.1 \
  https://superset.lakehouse.local/health >/dev/null
curl --fail --silent --show-error --cacert platform/config/pki/ca.crt \
  --resolve ranger.lakehouse.local:443:127.0.0.1 \
  https://ranger.lakehouse.local/login.jsp >/dev/null
curl --fail --silent --show-error http://127.0.0.1:6080/login.jsp >/dev/null
curl --fail --silent --show-error --cacert platform/config/pki/ca.crt \
  --resolve cube.lakehouse.local:443:127.0.0.1 \
  https://cube.lakehouse.local/readyz >/dev/null
curl --fail --silent --show-error --cacert platform/config/pki/ca.crt \
  --resolve authentik.lakehouse.local:443:127.0.0.1 \
  https://authentik.lakehouse.local/application/o/lakehouse/.well-known/openid-configuration |
  grep -q '"issuer"'
curl --fail --silent --show-error http://127.0.0.1:8000/hub/health >/dev/null

# Airflow UI logins go through authentik, and machines use the local service user.
curl --silent --show-error --output /dev/null --dump-header - --cacert platform/config/pki/ca.crt \
  --resolve airflow.lakehouse.local:443:127.0.0.1 \
  https://airflow.lakehouse.local/auth/login/authentik |
  grep -i '^location:' | grep -q 'redirect_uri=https%3A%2F%2Fairflow.lakehouse.local'
test "$(curl --silent --output /dev/null --write-out '%{http_code}' --cacert platform/config/pki/ca.crt \
  --resolve airflow.lakehouse.local:443:127.0.0.1 -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg p "${AIRFLOW_SERVICE_PASSWORD}" '{username: "svc_control", password: $p}')" \
  https://airflow.lakehouse.local/auth/token)" = 201

# Polaris accepts only authentik tokens: the root credential is refused, machine identities work.
polaris_status() {
  docker compose exec -T airflow-api curl --silent --output /dev/null --write-out '%{http_code}' "$@"
}
test "$(jq -rn --arg secret "${POLARIS_ROOT_PASSWORD}" \
  '"grant_type=client_credentials&client_id=root&scope=PRINCIPAL_ROLE:ALL&client_secret=\($secret | @uri)"' |
  docker compose exec -T airflow-api curl --silent --output /dev/null --write-out '%{http_code}' \
    -X POST --data @- http://polaris:8181/api/catalog/v1/oauth/tokens)" = 501
for machine_secret in "${OIDC_POLARIS_ADMIN_CLIENT_SECRET}" "${OIDC_PIPELINE_CLIENT_SECRET}" "${OIDC_TRINO_CLIENT_SECRET}"; do
  machine_token="$(jq -rn --arg secret "${machine_secret}" \
    '"grant_type=client_credentials&client_id=lakehouse&scope=openid%20profile&client_secret=\($secret | @uri)"' |
    curl --fail --silent --show-error --cacert platform/config/pki/ca.crt \
      --resolve authentik.lakehouse.local:443:127.0.0.1 --data @- \
      https://authentik.lakehouse.local/application/o/token/ | jq -er .access_token)"
  test "$(polaris_status -H "Authorization: Bearer ${machine_token}" \
    http://polaris:8181/api/catalog/v1/lakehouse/namespaces)" = 200
done
test "$(polaris_status -H 'Authorization: Bearer not.a.token' \
  http://polaris:8181/api/catalog/v1/lakehouse/namespaces)" = 401

curl --fail --silent --show-error http://127.0.0.1:8080/ |
  grep -q '<title>Airflow'
spark_ui="$(curl --fail --silent --show-error http://127.0.0.1:8081/)"
grep -q 'Spark Master' <<<"${spark_ui}"
grep -q '/proxy/worker-' <<<"${spark_ui}"
curl --fail --silent --show-error \
  http://127.0.0.1:8501/_stcore/health |
  grep -q 'ok'

if [[ "${RUN_PIPELINE_TEST:-0}" == "1" ]]; then
  WAIT_FOR_PIPELINE=1 ROWS=50 SEED=7 \
    ./operations/scripts/trigger-pipeline.sh >/dev/null
fi

trino_response="$(curl --fail --silent --show-error \
  --cacert platform/config/pki/ca.crt \
  --user "${LDAP_ANALYST_USERNAME}:${LDAP_ANALYST_PASSWORD}" \
  -H "X-Trino-User: ${LDAP_ANALYST_USERNAME}" \
  -H 'X-Trino-Catalog: lakehouse' \
  -H 'X-Trino-Schema: gold' \
  --data 'SELECT (SELECT count(*) FROM sales_performance) AS sales_rows, (SELECT count(*) FROM product_performance) AS product_rows, (SELECT count(*) FROM customer_360) AS customer_rows, (SELECT count(*) FROM system.jdbc.tables) AS metadata_rows' \
  https://127.0.0.1:8443/v1/statement)"
for _ in $(seq 1 30); do
  jq -e '.error' <<<"${trino_response}" >/dev/null && {
    jq .error <<<"${trino_response}" >&2
    exit 1
  }
  if jq -e '.data' <<<"${trino_response}" >/dev/null; then
    break
  fi
  next_uri="$(jq -r '.nextUri // empty' <<<"${trino_response}")"
  test -n "${next_uri}"
  next_uri="${next_uri/https:\/\/trino:8443/https:\/\/127.0.0.1:8443}"
  trino_response="$(curl --fail --silent --show-error \
    --cacert platform/config/pki/ca.crt \
    --user "${LDAP_ANALYST_USERNAME}:${LDAP_ANALYST_PASSWORD}" \
    -H "X-Trino-User: ${LDAP_ANALYST_USERNAME}" \
    "${next_uri}")"
  sleep 1
done
jq -e '.data[0][0] > 0 and .data[0][1] > 0 and .data[0][2] > 0 and .data[0][3] > 0' <<<"${trino_response}" >/dev/null

redirect_status="$(curl --silent --show-error --output /dev/null \
  --write-out '%{http_code}' \
  --resolve airflow.lakehouse.local:80:127.0.0.1 \
  http://airflow.lakehouse.local)"
[[ "${redirect_status}" == "301" || "${redirect_status}" == "308" ]]

printf 'Integration smoke tests passed.\n'
