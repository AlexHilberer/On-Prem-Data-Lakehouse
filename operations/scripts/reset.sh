#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_dir}"

if [[ "${CONFIRM_RESET:-}" != "yes" ]]; then
  printf 'This deletes all lakehouse volumes. Re-run with CONFIRM_RESET=yes.\n' >&2
  exit 1
fi
docker compose down --volumes --remove-orphans
rm -f platform/config/garage/garage.generated.toml
printf 'Persistent platform data deleted; .env, PKI, truststores, and backups were retained.\n'
