#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_dir}"
mkdir -p platform/config/pki platform/config/garage platform/config/trino

random_hex() {
  openssl rand -hex "${1:-24}"
}

random_ranger_password() {
  printf 'Rr1%s' "$(random_hex 20)"
}

if [[ ! -f .env ]]; then
  cp .env.example .env
  cat >> .env <<EOF
POSTGRES_ADMIN_PASSWORD=$(random_hex)
AIRFLOW_DB_PASSWORD=$(random_hex)
RANGER_DB_PASSWORD=$(random_hex)
POLARIS_DB_PASSWORD=$(random_hex)
SUPERSET_DB_PASSWORD=$(random_hex)
SOURCE_DB_PASSWORD=$(random_hex)
LDAP_ADMIN_PASSWORD=$(random_hex)
LDAP_CONFIG_PASSWORD=$(random_hex)
LDAP_ANALYST_PASSWORD=$(random_hex 12)
LDAP_ENGINEER_PASSWORD=$(random_hex 12)
CUBE_LDAP_PASSWORD=$(random_hex)
RANGER_ADMIN_PASSWORD=$(random_ranger_password)
POLARIS_ROOT_PASSWORD=$(random_hex)
POLARIS_SPARK_CLIENT_ID=root
POLARIS_SPARK_CLIENT_SECRET=\${POLARIS_ROOT_PASSWORD}
POLARIS_TRINO_CLIENT_ID=root
POLARIS_TRINO_CLIENT_SECRET=\${POLARIS_ROOT_PASSWORD}
GARAGE_ACCESS_KEY=GK$(random_hex 16)
GARAGE_SECRET_KEY=$(random_hex 32)
CUBE_API_SECRET=$(random_hex 32)
CUBE_SQL_PASSWORD=$(random_hex)
AIRFLOW_SECRET_KEY=$(random_hex 32)
SUPERSET_SECRET_KEY=$(random_hex 32)
EOF
  chmod 600 .env
fi

env_value() {
  sed -n "s/^${1}=//p" .env | tail -n 1
}

ensure_env_value() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" .env; then
    printf '%s=%s\n' "${key}" "${value}" >> .env
  fi
}

ensure_env_value LDAP_ANALYST_USERNAME alice.analyst
ensure_env_value LDAP_ENGINEER_USERNAME bob.engineer
# Preserve passwords created by the earlier persona-specific variable names.
ensure_env_value LDAP_ANALYST_PASSWORD "$(env_value ALICE_PASSWORD || true)"
ensure_env_value LDAP_ENGINEER_PASSWORD "$(env_value BOB_PASSWORD || true)"

if [[ -z "$(env_value LDAP_ANALYST_PASSWORD)" ]]; then
  sed -i "s/^LDAP_ANALYST_PASSWORD=.*/LDAP_ANALYST_PASSWORD=$(random_hex 12)/" .env
fi
if [[ -z "$(env_value LDAP_ENGINEER_PASSWORD)" ]]; then
  sed -i "s/^LDAP_ENGINEER_PASSWORD=.*/LDAP_ENGINEER_PASSWORD=$(random_hex 12)/" .env
fi
sed -i '/^ALICE_PASSWORD=/d; /^BOB_PASSWORD=/d' .env

analyst_username="$(env_value LDAP_ANALYST_USERNAME)"
engineer_username="$(env_value LDAP_ENGINEER_USERNAME)"
for username in "${analyst_username}" "${engineer_username}"; do
  if [[ ! "${username}" =~ ^[A-Za-z0-9._-]+$ ]]; then
    printf 'LDAP username contains unsupported characters: %s\n' "${username}" >&2
    exit 1
  fi
done
if [[ "${analyst_username}" == "${engineer_username}" ]]; then
  printf 'LDAP analyst and engineer usernames must be different.\n' >&2
  exit 1
fi

ensure_env_value GARAGE_RPC_SECRET "$(random_hex 32)"
ensure_env_value GARAGE_ADMIN_TOKEN "$(random_hex 32)"
ensure_env_value GARAGE_METRICS_TOKEN "$(random_hex 32)"

if ! grep -q '^TRINO_SHARED_SECRET=' .env; then
  printf 'TRINO_SHARED_SECRET=%s\n' "$(random_hex 64)" >> .env
fi

if ! grep -q '^TRAEFIK_IMAGE=' .env; then
  printf 'TRAEFIK_IMAGE=traefik:v3.7.1\n' >> .env
fi
if ! grep -q '^CONTROL_PANEL_IMAGE=' .env; then
  printf 'CONTROL_PANEL_IMAGE=onprem-lakehouse/control-panel:1.0.0\n' >> .env
fi
sed -i '/^CADDY_IMAGE=/d' .env

current_ranger_password="$(sed -n 's/^RANGER_ADMIN_PASSWORD=//p' .env | tail -n 1)"
if [[ ! "${current_ranger_password}" =~ [A-Z] ]] \
  || [[ ! "${current_ranger_password}" =~ [a-z] ]] \
  || [[ ! "${current_ranger_password}" =~ [0-9] ]]; then
  sed -i "s/^RANGER_ADMIN_PASSWORD=.*/RANGER_ADMIN_PASSWORD=$(random_ranger_password)/" .env
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

# Existing keys are retained so previously trusted certificates remain valid.
if [[ ! -f platform/config/pki/ca.key ]]; then
  openssl req -x509 -newkey rsa:4096 -nodes -days 1825 \
    -keyout platform/config/pki/ca.key -out platform/config/pki/ca.crt \
    -subj "/CN=On-Prem Lakehouse Local CA"
fi

issue_certificate() {
  local name="$1"
  local common_name="$2"
  local sans="$3"
  local work_dir
  if [[ -f "platform/config/pki/${name}.crt" ]]; then
    return
  fi
  work_dir="$(mktemp -d)"
  openssl req -newkey rsa:2048 -nodes \
    -keyout "platform/config/pki/${name}.key" \
    -out "${work_dir}/${name}.csr" \
    -subj "/CN=${common_name}"
  cat > "${work_dir}/${name}.ext" <<EOF
subjectAltName=${sans}
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF
  openssl x509 -req -days 825 \
    -in "${work_dir}/${name}.csr" \
    -CA platform/config/pki/ca.crt -CAkey platform/config/pki/ca.key -CAcreateserial \
    -out "platform/config/pki/${name}.crt" \
    -extfile "${work_dir}/${name}.ext"
  rm -rf "${work_dir}"
}

issue_certificate ldap openldap "DNS:openldap,DNS:ldap.lakehouse.local"
issue_certificate trino trino "DNS:trino,DNS:trino.lakehouse.local,IP:127.0.0.1"
issue_certificate gateway lakehouse.local \
  "DNS:airflow.lakehouse.local,DNS:ranger.lakehouse.local,DNS:superset.lakehouse.local,DNS:cube.lakehouse.local"
cat platform/config/pki/trino.key platform/config/pki/trino.crt > platform/config/pki/trino.pem
chmod 600 platform/config/pki/*.key platform/config/pki/trino.pem

if [[ ! -f platform/config/pki/polaris-token.key ]]; then
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 \
    -out platform/config/pki/polaris-token.key 2>/dev/null
  openssl pkey -in platform/config/pki/polaris-token.key -pubout \
    -out platform/config/pki/polaris-token.pub
  chmod 600 platform/config/pki/polaris-token.key
fi

sed \
  -e "s|__GARAGE_RPC_SECRET__|${GARAGE_RPC_SECRET}|" \
  -e "s|__GARAGE_ADMIN_TOKEN__|${GARAGE_ADMIN_TOKEN}|" \
  -e "s|__GARAGE_METRICS_TOKEN__|${GARAGE_METRICS_TOKEN}|" \
  platform/config/garage/garage.toml.template \
  > platform/config/garage/garage.generated.toml
chmod 600 platform/config/garage/garage.generated.toml

if [[ -f platform/config/trino/dbeaver-trino-truststore.p12 ]]; then
  keytool -delete \
    -alias lakehouse-ca \
    -keystore platform/config/trino/dbeaver-trino-truststore.p12 \
    -storetype PKCS12 \
    -storepass changeit >/dev/null 2>&1 || true
fi
keytool -importcert -noprompt \
  -alias lakehouse-ca \
  -file platform/config/pki/ca.crt \
  -keystore platform/config/trino/dbeaver-trino-truststore.p12 \
  -storetype PKCS12 \
  -storepass changeit >/dev/null
chmod 600 platform/config/trino/dbeaver-trino-truststore.p12

printf 'Initialized secrets, service configuration, and certificates from .env.\n'
printf 'LDAP analyst: %s (LDAP_ANALYST_PASSWORD)\n' "${LDAP_ANALYST_USERNAME}"
printf 'LDAP engineer: %s (LDAP_ENGINEER_PASSWORD)\n' "${LDAP_ENGINEER_USERNAME}"
