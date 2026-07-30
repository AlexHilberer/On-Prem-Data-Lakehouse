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

token="$(curl -fsS -X POST http://polaris:8181/api/catalog/v1/oauth/tokens \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode client_id=root \
  --data-urlencode "client_secret=${POLARIS_ROOT_PASSWORD}" \
  --data-urlencode scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)"

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

echo "Platform bootstrap completed"
