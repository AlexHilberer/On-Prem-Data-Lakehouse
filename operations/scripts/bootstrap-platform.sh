#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

retry() {
  attempts=0
  until "$@"; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      return 1
    fi
    sleep 5
  done
}

retry curl -fsS http://ranger-admin:6080/login.jsp -o /dev/null
retry curl -fsS -u "admin:${RANGER_ADMIN_PASSWORD}" \
  http://ranger-admin:6080/service/public/v2/api/servicedef/name/trino \
  -o /dev/null

service_payload='{
  "name": "trino_lakehouse",
  "type": "trino",
  "isEnabled": true,
  "configs": {
    "username": "admin",
    "password": "'"${RANGER_ADMIN_PASSWORD}"'",
    "jdbc.driverClassName": "io.trino.jdbc.TrinoDriver",
    "jdbc.url": "jdbc:trino://trino:8443"
  }
}'

# Ranger exposes no declarative startup path, so its service and policies are upserted.
ensure_ranger_service() {
  existing_service="$(curl -fsS -u "admin:${RANGER_ADMIN_PASSWORD}" \
    http://ranger-admin:6080/service/public/v2/api/service/name/trino_lakehouse \
    2>/dev/null || true)"
  if printf '%s' "${existing_service:-null}" \
    | jq -e 'type == "object" and (.id != null)' >/dev/null 2>&1; then
    return 0
  fi
  curl -fsS -u "admin:${RANGER_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' \
    -d "$service_payload" \
    http://ranger-admin:6080/service/public/v2/api/service >/dev/null
}
retry ensure_ranger_service

upsert_ranger_policy() {
  existing="$(curl -fsS -u "admin:${RANGER_ADMIN_PASSWORD}" \
    --get \
    --data-urlencode "serviceName=trino_lakehouse" \
    --data-urlencode "policyName=${name}" \
    http://ranger-admin:6080/service/public/v2/api/policy || true)"
  policy_id="$(printf '%s' "$existing" | jq -r '.[0].id // empty' 2>/dev/null || true)"
  if [ -n "$policy_id" ]; then
    curl -fsS -u "admin:${RANGER_ADMIN_PASSWORD}" \
      -X PUT -H 'Content-Type: application/json' -d @"$policy" \
      "http://ranger-admin:6080/service/public/v2/api/policy/${policy_id}" >/dev/null
  else
    curl -fsS -u "admin:${RANGER_ADMIN_PASSWORD}" \
      -H 'Content-Type: application/json' -d @"$policy" \
      http://ranger-admin:6080/service/public/v2/api/policy >/dev/null
  fi
}

for policy_template in "${script_dir}"/policies/*.json; do
  policy="$(mktemp)"
  sed \
    -e "s|__LDAP_ANALYST_USERNAME__|${LDAP_ANALYST_USERNAME}|g" \
    -e "s|__LDAP_ENGINEER_USERNAME__|${LDAP_ENGINEER_USERNAME}|g" \
    "${policy_template}" > "${policy}"
  name="$(jq -r .name "${policy}")"
  retry upsert_ranger_policy
  rm -f "${policy}"
done

# Airflow's token endpoint accepts only local users under OIDC, so machines use this one.
if airflow users list 2>/dev/null | grep -qw svc_control; then
  airflow users reset-password --username svc_control --password "${AIRFLOW_SERVICE_PASSWORD}" >/dev/null
else
  airflow users create --username svc_control --firstname Control --lastname Service \
    --email svc_control@lakehouse.local --role Op --password "${AIRFLOW_SERVICE_PASSWORD}" >/dev/null
fi

# Polaris treats an existing catalog as a successful bootstrap outcome.
polaris_status() {
  curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $1" \
    http://polaris:8181/api/management/v1/principal-roles || true
}

# The secret goes through stdin so it never appears in the process list.
fetch_token() {
  jq -rn --arg secret "$2" --arg id "$3" --arg scope "$4" \
    '"grant_type=client_credentials&client_id=\($id)&scope=\($scope | @uri)&client_secret=\($secret | @uri)"' |
    curl -sS "${@:5}" --data @- "$1" | jq -r '.access_token // empty' || true
}

token=""
for _ in $(seq 1 90); do
  token="$(fetch_token https://authentik.lakehouse.local/application/o/token/ \
    "${OIDC_POLARIS_ADMIN_CLIENT_SECRET}" lakehouse 'openid profile' \
    --cacert /opt/airflow/certs/ca.crt -X POST)"
  [[ -n "${token}" ]] && break
  sleep 2
done
if [[ -z "${token}" ]]; then
  echo "authentik did not issue a Polaris admin token" >&2
  exit 1
fi

admin_status="$(polaris_status "${token}")"
if [[ "${admin_status}" == 401 || "${admin_status}" == 403 ]]; then
  # Workaround: the machine principals do not exist yet, so the root credential is used once. See CLAUDE.md#pitfalls
  token="$(fetch_token http://polaris:8181/api/catalog/v1/oauth/tokens \
    "${POLARIS_ROOT_PASSWORD}" root 'PRINCIPAL_ROLE:ALL' -X POST)"
  if [[ -z "${token}" || "$(polaris_status "${token}")" != 200 ]]; then
    echo "Polaris admin access failed; start Polaris with POLARIS_AUTHENTICATION_TYPE=mixed" >&2
    exit 75
  fi
elif [[ "${admin_status}" != 200 ]]; then
  echo "Polaris returned HTTP ${admin_status} for the admin identity" >&2
  exit 1
fi

catalog_payload='{
  "catalog": {
    "name": "lakehouse",
    "type": "INTERNAL",
    "properties": {"default-base-location": "s3://lakehouse/warehouse"},
    "storageConfigInfo": {
      "storageType": "S3",
      "allowedLocations": ["s3://lakehouse/"],
      "endpoint": "http://garage:3900",
      "endpointInternal": "http://garage:3900",
      "region": "garage",
      "stsUnavailable": true,
      "pathStyleAccess": true
    }
  }
}'
curl -fsS -X POST http://polaris:8181/api/management/v1/catalogs \
  -H "Authorization: Bearer ${token}" \
  -H 'Content-Type: application/json' \
  -d "$catalog_payload" >/dev/null 2>&1 || true

polaris_api() {
  local method="$1" path="$2" body="${3:-}" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X "${method}" \
    "http://polaris:8181/api/management/v1${path}" \
    -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
    ${body:+-d "${body}"})"
  # 409 means the object already exists, which keeps reruns idempotent.
  if [[ ! "${code}" =~ ^(2..|409)$ ]]; then
    echo "Polaris ${method} ${path} failed: HTTP ${code}" >&2
    return 1
  fi
}

# Principal roles match authentik groups (lakehouse_<role>); conflicts mean already present.
for role in analysts engineers pipeline trino; do
  polaris_api POST /principal-roles "{\"principalRole\":{\"name\":\"${role}\"}}"
done
polaris_api POST /catalogs/lakehouse/catalog-roles '{"catalogRole":{"name":"reader"}}'
polaris_api POST /catalogs/lakehouse/catalog-roles '{"catalogRole":{"name":"writer"}}'
# Analysts read only the gold namespace, mirroring the Ranger analyst policy.
for privilege in CATALOG_READ_PROPERTIES NAMESPACE_LIST; do
  polaris_api PUT /catalogs/lakehouse/catalog-roles/reader/grants \
    "{\"grant\":{\"type\":\"catalog\",\"privilege\":\"${privilege}\"}}"
done
for privilege in NAMESPACE_READ_PROPERTIES TABLE_LIST TABLE_READ_PROPERTIES TABLE_READ_DATA; do
  polaris_api PUT /catalogs/lakehouse/catalog-roles/reader/grants \
    "{\"grant\":{\"type\":\"namespace\",\"namespace\":[\"gold\"],\"privilege\":\"${privilege}\"}}"
  # Revoking a missing grant fails harmlessly, so older stacks narrow without erroring.
  curl -sS -o /dev/null -X POST http://polaris:8181/api/management/v1/catalogs/lakehouse/catalog-roles/reader/grants \
    -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
    -d "{\"grant\":{\"type\":\"catalog\",\"privilege\":\"${privilege}\"}}" || true
done
polaris_api PUT /catalogs/lakehouse/catalog-roles/writer/grants \
  '{"grant":{"type":"catalog","privilege":"CATALOG_MANAGE_CONTENT"}}'
polaris_api PUT /principal-roles/analysts/catalog-roles/lakehouse '{"catalogRole":{"name":"reader"}}'
polaris_api PUT /principal-roles/engineers/catalog-roles/lakehouse '{"catalogRole":{"name":"writer"}}'

# The Trino engine only queries; the pipeline writes.
polaris_api POST /catalogs/lakehouse/catalog-roles '{"catalogRole":{"name":"engine_reader"}}'
for privilege in CATALOG_READ_PROPERTIES NAMESPACE_LIST NAMESPACE_READ_PROPERTIES \
  TABLE_LIST TABLE_READ_PROPERTIES TABLE_READ_DATA VIEW_LIST VIEW_READ_PROPERTIES; do
  polaris_api PUT /catalogs/lakehouse/catalog-roles/engine_reader/grants \
    "{\"grant\":{\"type\":\"catalog\",\"privilege\":\"${privilege}\"}}"
done
polaris_api PUT /principal-roles/pipeline/catalog-roles/lakehouse '{"catalogRole":{"name":"writer"}}'
polaris_api PUT /principal-roles/trino/catalog-roles/lakehouse '{"catalogRole":{"name":"engine_reader"}}'

# Principals are keyed by the preferred_username claim from authentik.
for pair in "${LDAP_ANALYST_USERNAME}:analysts" "${LDAP_ENGINEER_USERNAME}:engineers" \
  svc_pipeline:pipeline svc_trino:trino svc_polaris_admin:service_admin; do
  polaris_api POST /principals "{\"principal\":{\"name\":\"${pair%%:*}\"}}"
  polaris_api PUT "/principals/${pair%%:*}/principal-roles" "{\"principalRole\":{\"name\":\"${pair##*:}\"}}"
done

echo "Platform bootstrap completed"
