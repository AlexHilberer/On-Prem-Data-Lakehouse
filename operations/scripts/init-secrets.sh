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
  elif [[ -z "$(env_value "${key}")" ]]; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  fi
}

write_env_group() {
  local key
  for key in "$@"; do
    if grep -q "^${key}=" .env; then
      printf '%s=%s\n' "${key}" "$(env_value "${key}")"
    fi
  done
}

organize_env() {
  local temporary_file
  temporary_file="$(mktemp)"
  {
    printf '# Compose runtime\n'
    write_env_group COMPOSE_PROJECT_NAME LAKEHOUSE_DOMAIN AIRFLOW_UID LAKEHOUSE_TIMEZONE

    printf '\n# Database credentials\n'
    write_env_group POSTGRES_ADMIN_PASSWORD AIRFLOW_DB_PASSWORD RANGER_DB_PASSWORD \
      POLARIS_DB_PASSWORD SUPERSET_DB_PASSWORD SOURCE_DB_PASSWORD

    printf '\n# LDAP identities\n'
    write_env_group LDAP_ADMIN_PASSWORD LDAP_CONFIG_PASSWORD LDAP_ANALYST_USERNAME \
      LDAP_ANALYST_PASSWORD LDAP_ENGINEER_USERNAME LDAP_ENGINEER_PASSWORD CUBE_LDAP_PASSWORD

    printf '\n# Ranger and Polaris\n'
    write_env_group RANGER_ADMIN_PASSWORD POLARIS_ROOT_PASSWORD POLARIS_SPARK_CLIENT_ID \
      POLARIS_SPARK_CLIENT_SECRET POLARIS_TRINO_CLIENT_ID POLARIS_TRINO_CLIENT_SECRET

    printf '\n# Garage object storage\n'
    write_env_group GARAGE_ACCESS_KEY GARAGE_SECRET_KEY GARAGE_RPC_SECRET GARAGE_ADMIN_TOKEN \
      GARAGE_METRICS_TOKEN

    printf '\n# Application secrets\n'
    write_env_group CUBE_API_SECRET CUBE_SQL_PASSWORD AIRFLOW_SECRET_KEY SUPERSET_SECRET_KEY \
      TRINO_SHARED_SECRET

    while IFS= read -r line; do
      case "${line%%=*}" in
        '# Compose runtime'|'# Database credentials'|'# LDAP identities'|'# Ranger and Polaris'|'# Garage object storage'|'# Application secrets')
          ;;
        COMPOSE_PROJECT_NAME|LAKEHOUSE_DOMAIN|AIRFLOW_UID|LAKEHOUSE_TIMEZONE|POSTGRES_ADMIN_PASSWORD|AIRFLOW_DB_PASSWORD|RANGER_DB_PASSWORD|POLARIS_DB_PASSWORD|SUPERSET_DB_PASSWORD|SOURCE_DB_PASSWORD|LDAP_ADMIN_PASSWORD|LDAP_CONFIG_PASSWORD|LDAP_ANALYST_USERNAME|LDAP_ANALYST_PASSWORD|LDAP_ENGINEER_USERNAME|LDAP_ENGINEER_PASSWORD|CUBE_LDAP_PASSWORD|RANGER_ADMIN_PASSWORD|POLARIS_ROOT_PASSWORD|POLARIS_SPARK_CLIENT_ID|POLARIS_SPARK_CLIENT_SECRET|POLARIS_TRINO_CLIENT_ID|POLARIS_TRINO_CLIENT_SECRET|GARAGE_ACCESS_KEY|GARAGE_SECRET_KEY|GARAGE_RPC_SECRET|GARAGE_ADMIN_TOKEN|GARAGE_METRICS_TOKEN|CUBE_API_SECRET|CUBE_SQL_PASSWORD|AIRFLOW_SECRET_KEY|SUPERSET_SECRET_KEY|TRINO_SHARED_SECRET)
          ;;
        '')
          ;;
        *)
          printf '%s\n' "${line}"
          ;;
      esac
    done < .env
  } > "${temporary_file}"
  mv "${temporary_file}" .env
  chmod 600 .env
}

ensure_env_value COMPOSE_PROJECT_NAME onprem-lakehouse
ensure_env_value LAKEHOUSE_DOMAIN lakehouse.local
ensure_env_value AIRFLOW_UID 50000
ensure_env_value LAKEHOUSE_TIMEZONE Europe/Berlin
ensure_env_value LDAP_ANALYST_USERNAME alice.analyst
ensure_env_value LDAP_ENGINEER_USERNAME bob.engineer
# Preserve passwords created by the earlier persona-specific variable names.
ensure_env_value LDAP_ANALYST_PASSWORD "$(env_value ALICE_PASSWORD || true)"
ensure_env_value LDAP_ENGINEER_PASSWORD "$(env_value BOB_PASSWORD || true)"
sed -i '/^ALICE_PASSWORD=/d; /^BOB_PASSWORD=/d' .env

ensure_env_value POSTGRES_ADMIN_PASSWORD "$(random_hex)"
ensure_env_value AIRFLOW_DB_PASSWORD "$(random_hex)"
ensure_env_value RANGER_DB_PASSWORD "$(random_hex)"
ensure_env_value POLARIS_DB_PASSWORD "$(random_hex)"
ensure_env_value SUPERSET_DB_PASSWORD "$(random_hex)"
ensure_env_value SOURCE_DB_PASSWORD "$(random_hex)"
ensure_env_value LDAP_ADMIN_PASSWORD "$(random_hex)"
ensure_env_value LDAP_CONFIG_PASSWORD "$(random_hex)"
ensure_env_value LDAP_ANALYST_PASSWORD "$(random_hex 12)"
ensure_env_value LDAP_ENGINEER_PASSWORD "$(random_hex 12)"
ensure_env_value CUBE_LDAP_PASSWORD "$(random_hex)"
ensure_env_value RANGER_ADMIN_PASSWORD "$(random_ranger_password)"
ensure_env_value POLARIS_ROOT_PASSWORD "$(random_hex)"
ensure_env_value POLARIS_SPARK_CLIENT_ID root
ensure_env_value POLARIS_SPARK_CLIENT_SECRET '${POLARIS_ROOT_PASSWORD}'
ensure_env_value POLARIS_TRINO_CLIENT_ID root
ensure_env_value POLARIS_TRINO_CLIENT_SECRET '${POLARIS_ROOT_PASSWORD}'
ensure_env_value GARAGE_ACCESS_KEY "GK$(random_hex 16)"
ensure_env_value GARAGE_SECRET_KEY "$(random_hex 32)"
ensure_env_value GARAGE_RPC_SECRET "$(random_hex 32)"
ensure_env_value GARAGE_ADMIN_TOKEN "$(random_hex 32)"
ensure_env_value GARAGE_METRICS_TOKEN "$(random_hex 32)"
ensure_env_value CUBE_API_SECRET "$(random_hex 32)"
ensure_env_value CUBE_SQL_PASSWORD "$(random_hex)"
ensure_env_value AIRFLOW_SECRET_KEY "$(random_hex 32)"
ensure_env_value SUPERSET_SECRET_KEY "$(random_hex 32)"
ensure_env_value TRINO_SHARED_SECRET "$(random_hex 64)"

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

sed -i '/^[A-Z_][A-Z0-9_]*_IMAGE=/d' .env

current_ranger_password="$(sed -n 's/^RANGER_ADMIN_PASSWORD=//p' .env | tail -n 1)"
if [[ ! "${current_ranger_password}" =~ [A-Z] ]] \
  || [[ ! "${current_ranger_password}" =~ [a-z] ]] \
  || [[ ! "${current_ranger_password}" =~ [0-9] ]]; then
  sed -i "s/^RANGER_ADMIN_PASSWORD=.*/RANGER_ADMIN_PASSWORD=$(random_ranger_password)/" .env
fi

organize_env

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
