#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_dir}"
requested_project_name="${COMPOSE_PROJECT_NAME:-}"
set -a
# shellcheck disable=SC1091
source .env
set +a
if [[ -n "${requested_project_name}" ]]; then
  export COMPOSE_PROJECT_NAME="${requested_project_name}"
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="operations/backups/${timestamp}"
mkdir -p "${destination}"

docker compose exec -T postgres pg_dumpall \
  --username platform_admin > "${destination}/postgres.sql"
docker compose exec -T openldap \
  slapcat -f /etc/openldap/slapd.conf > "${destination}/ldap.ldif"
docker run --rm \
  -v "${COMPOSE_PROJECT_NAME}_garage_meta:/source:ro" \
  -v "$(pwd)/${destination}:/backup" \
  alpine:3.22 tar -czf /backup/garage-meta.tar.gz -C /source .
docker run --rm \
  -v "${COMPOSE_PROJECT_NAME}_garage_data:/source:ro" \
  -v "$(pwd)/${destination}:/backup" \
  alpine:3.22 tar -czf /backup/garage-data.tar.gz -C /source .
printf 'Backup written to %s\n' "${destination}"
