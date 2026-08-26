#!/usr/bin/env bash
set -euo pipefail

if (( $# > 0 )); then
  services=("$@")
else
  services=(
    postgres redis openldap ranger-admin ranger-usersync garage polaris
    spark-master spark-worker airflow-api airflow-scheduler airflow-worker
    airflow-dag-processor control-panel trino cube superset traefik
  )
fi

deadline=$((SECONDS + 900))
while (( SECONDS < deadline )); do
  unhealthy=()
  for service in "${services[@]}"; do
    container_id="$(docker compose ps -q "${service}")"
    if [[ -z "${container_id}" ]]; then
      unhealthy+=("${service}:missing")
      continue
    fi
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
    if [[ "${status}" != "healthy" && "${status}" != "running" ]]; then
      unhealthy+=("${service}:${status}")
    fi
  done
  if (( ${#unhealthy[@]} == 0 )); then
    printf 'Platform is ready.\n'
    printf 'Trust %s and add the lakehouse.local names from the README.\n' "platform/config/pki/ca.crt"
    exit 0
  fi
  printf 'Waiting for: %s\n' "${unhealthy[*]}"
  sleep 10
done

docker compose ps
printf 'Timed out waiting for platform readiness.\n' >&2
exit 1
