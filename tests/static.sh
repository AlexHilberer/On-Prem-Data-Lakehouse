#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

docker compose config --quiet

test -x lakehouse.sh
test ! -e Makefile
test ! -d docker
test ! -d pipeline
test ! -d scripts
test ! -d platform/config/caddy

python3 tests/compose_contract.py
python3 tests/markdown_links.py

if rg -n 'service_completed_successfully|restart:\s*["'\'']?no' compose.yaml; then
  printf 'One-shot Compose lifecycle configuration found.\n' >&2
  exit 1
fi

if rg -n 'image:\s+\S+:latest\b' compose.yaml platform/images; then
  printf 'Unpinned latest image found.\n' >&2
  exit 1
fi

python3 -m compileall -q orchestration data-pipeline analytics control-panel platform/config
python3 -m unittest -q tests/control_panel_test.py

for policy in platform/config/ranger/policies/*.json; do
  python3 -m json.tool "${policy}" >/dev/null
done

test -s platform/config/pki/ca.crt
test -s platform/config/pki/trino.pem
test -s platform/config/garage/garage.generated.toml
test -s platform/config/trino/dbeaver-trino-truststore.p12
test ! -e .runtime
if rg -n --hidden '\\.runtime' . \
  --glob '!.git/**' --glob '!README.md' --glob '!docs/**' \
  --glob '!tests/static.sh'; then
  printf 'Obsolete .runtime reference found.\n' >&2
  exit 1
fi
git check-ignore -q \
  .env \
  platform/config/pki/ca.key \
  platform/config/garage/garage.generated.toml \
  platform/config/trino/dbeaver-trino-truststore.p12 \
  operations/backups 2>/dev/null || true

printf 'Static validation passed.\n'
