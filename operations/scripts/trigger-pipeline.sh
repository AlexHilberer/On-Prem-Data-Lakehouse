#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_dir}"
set -a
# shellcheck disable=SC1091
source .env
set +a

rows="${ROWS:-0}"
seed="${SEED:-42}"
run_id="manual-$(date -u +%Y%m%dT%H%M%SZ)"
payload="$(printf '{"dag_run_id":"%s","logical_date":null,"conf":{"rows":%s,"seed":%s}}' "$run_id" "$rows" "$seed")"
auth_payload="$(jq -nc \
  --arg username "${LDAP_ENGINEER_USERNAME}" \
  --arg password "${LDAP_ENGINEER_PASSWORD}" \
  '{username: $username, password: $password}')"
token="$(curl --fail --silent --show-error \
  --cacert platform/config/pki/ca.crt \
  --resolve airflow.lakehouse.local:443:127.0.0.1 \
  -H 'Content-Type: application/json' \
  -d "$auth_payload" \
  https://airflow.lakehouse.local/auth/token | jq -er .access_token)"

curl --fail --silent --show-error \
  --cacert platform/config/pki/ca.crt \
  --resolve airflow.lakehouse.local:443:127.0.0.1 \
  -X PATCH \
  -H "Authorization: Bearer ${token}" \
  -H 'Content-Type: application/json' \
  -d '{"is_paused":false}' \
  https://airflow.lakehouse.local/api/v2/dags/retail_lakehouse_pipeline >/dev/null

response="$(curl --fail --silent --show-error \
  --cacert platform/config/pki/ca.crt \
  --resolve airflow.lakehouse.local:443:127.0.0.1 \
  -H "Authorization: Bearer ${token}" \
  -H 'Content-Type: application/json' \
  -d "$payload" \
  https://airflow.lakehouse.local/api/v2/dags/retail_lakehouse_pipeline/dagRuns)"
printf '%s\n' "${response}"
if [[ "${rows}" == "0" ]]; then
  printf '\nTriggered %s with automatic demo volume and seed %s.\n' "$run_id" "$seed"
else
  printf '\nTriggered %s with %s rows and seed %s.\n' "$run_id" "$rows" "$seed"
fi

if [[ "${WAIT_FOR_PIPELINE:-0}" == "1" ]]; then
  for _ in $(seq 1 180); do
    state="$(curl --fail --silent --show-error \
      --cacert platform/config/pki/ca.crt \
      --resolve airflow.lakehouse.local:443:127.0.0.1 \
      -H "Authorization: Bearer ${token}" \
      "https://airflow.lakehouse.local/api/v2/dags/retail_lakehouse_pipeline/dagRuns/${run_id}" |
      jq -r '.state')"
    case "${state}" in
      success)
        printf 'Pipeline %s completed successfully.\n' "${run_id}"
        exit 0
        ;;
      failed)
        printf 'Pipeline %s failed.\n' "${run_id}" >&2
        exit 1
        ;;
    esac
    sleep 5
  done
  printf 'Timed out waiting for pipeline %s.\n' "${run_id}" >&2
  exit 1
fi
