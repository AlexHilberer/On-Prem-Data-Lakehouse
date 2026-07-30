#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${repo_dir}"

usage() {
  cat <<'EOF'
Usage: ./lakehouse.sh <command> [arguments]

Commands:
  up          Initialize, build, bootstrap, and start the platform
  down        Stop the platform without deleting persistent data
  reset       Delete containers and persistent data (requires CONFIRM_RESET=yes)
  build       Build all locally maintained images
  bootstrap   Re-apply Ranger policies and Polaris catalog configuration
  pipeline    Trigger the retail Airflow DAG (supports ROWS and SEED)
  test        Run static and integration smoke tests
  ps          Show service status
  logs        Follow service logs; optional service names are accepted
  backup      Back up PostgreSQL, LDAP, and Garage data
  init        Generate local secrets and certificates
  help        Show this help
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

require_docker() {
  require_command docker
  if ! docker compose version >/dev/null 2>&1; then
    printf 'Docker Compose v2 is required.\n' >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    printf 'Docker daemon is unavailable.\n' >&2
    exit 1
  fi
}

initialize() {
  require_command openssl
  require_command keytool
  ./operations/scripts/init-secrets.sh
}

bootstrap() {
  docker compose exec -T airflow-api \
    /opt/airflow/bootstrap/bootstrap-platform.sh
}

start_platform() {
  require_docker
  initialize

  printf 'Starting core platform services...\n'
  docker compose up -d --remove-orphans \
    postgres openldap garage ranger-admin ranger-usersync polaris airflow-api
  ./operations/scripts/wait-for-platform.sh \
    postgres openldap garage ranger-admin ranger-usersync polaris airflow-api

  printf 'Applying platform configuration...\n'
  bootstrap

  printf 'Starting processing, query, semantic, and UI services...\n'
  docker compose up -d --remove-orphans
  ./operations/scripts/wait-for-platform.sh

  cat <<'EOF'
Lakehouse is ready:
  Control:  http://127.0.0.1:8501
  Airflow:  http://127.0.0.1:8080
  Spark:    http://127.0.0.1:8081
  Trino:    https://127.0.0.1:8443
  Ranger:   https://ranger.lakehouse.local
  Superset: https://superset.lakehouse.local
  Cube:     https://cube.lakehouse.local

LDAP credentials: .env
EOF
}

command="${1:-help}"
if (( $# > 0 )); then
  shift
fi

case "${command}" in
  up)
    start_platform
    ;;
  down)
    require_docker
    docker compose down --remove-orphans "$@"
    ;;
  reset)
    require_docker
    ./operations/scripts/reset.sh "$@"
    ;;
  build)
    require_docker
    initialize
    docker compose build "$@"
    ;;
  bootstrap)
    require_docker
    bootstrap
    ;;
  pipeline)
    require_docker
    require_command curl
    require_command jq
    ./operations/scripts/trigger-pipeline.sh "$@"
    ;;
  test)
    require_docker
    initialize
    ./tests/static.sh
    ./tests/integration.sh
    ;;
  ps)
    require_docker
    docker compose ps "$@"
    ;;
  logs)
    require_docker
    docker compose logs -f --tail=200 "$@"
    ;;
  backup)
    require_docker
    ./operations/scripts/backup.sh "$@"
    ;;
  init)
    initialize
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    printf 'Unknown command: %s\n\n' "${command}" >&2
    usage >&2
    exit 2
    ;;
esac
