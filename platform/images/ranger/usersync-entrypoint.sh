#!/usr/bin/env bash
set -euo pipefail

cd /opt/ranger/usersync
if [[ -f /run/certs/ca.crt ]]; then
  keytool -importcert -noprompt -trustcacerts -alias lakehouse-local-ca \
    -file /run/certs/ca.crt -keystore "${JAVA_HOME}/lib/security/cacerts" \
    -storepass changeit 2>/dev/null || true
fi
if [[ ! -f .container-installed ]]; then
  render-ranger-config /opt/ranger/config/install.properties.template install.properties
  ./setup.sh
  test -x /etc/init.d/ranger-usersync
  test -d /opt/ranger/usersync/conf
  touch .container-installed
fi

rm -f /var/run/ranger/usersync.pid

if [[ -x /etc/init.d/ranger-usersync ]]; then
  /etc/init.d/ranger-usersync start
  trap '/etc/init.d/ranger-usersync stop 2>/dev/null || true' TERM INT
  tail -F logs/usersync-*-ranger.log
elif [[ -x ranger-usersync-services.sh ]]; then
  ./ranger-usersync-services.sh start
  trap './ranger-usersync-services.sh stop 2>/dev/null || true' TERM INT
  tail -F logs/usersync.log
else
  echo "Unable to locate Ranger UserSync start script" >&2
  exit 1
fi
