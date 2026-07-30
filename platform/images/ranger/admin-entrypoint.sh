#!/usr/bin/env bash
set -euo pipefail

cd /opt/ranger/admin
if [[ -f /run/certs/ca.crt ]]; then
  keytool -importcert -noprompt -trustcacerts -alias lakehouse-local-ca \
    -file /run/certs/ca.crt -keystore "${JAVA_HOME}/lib/security/cacerts" \
    -storepass changeit 2>/dev/null || true
fi
if [[ ! -f .container-installed ]]; then
  render-ranger-config /opt/ranger/config/install.properties.template install.properties
  ./setup.sh
  touch .container-installed
fi

if [[ -x ews/ranger-admin-services.sh ]]; then
  ews/ranger-admin-services.sh start
elif [[ -x /etc/init.d/ranger-admin ]]; then
  /etc/init.d/ranger-admin start
else
  echo "Unable to locate Ranger Admin start script" >&2
  exit 1
fi

trap 'ews/ranger-admin-services.sh stop 2>/dev/null || true' TERM INT
tail -F ews/logs/catalina.out
