#!/usr/bin/env bash
set -euo pipefail

output="$(
  cd /opt/polaris-admin
  java -XX:MaxRAMPercentage=80.0 \
    -jar /opt/polaris-admin/polaris-admin-tool.jar \
    bootstrap \
    -r "${POLARIS_REALM:-POLARIS}" \
    -c "${POLARIS_REALM:-POLARIS},root,${POLARIS_ROOT_PASSWORD}" 2>&1
)" || status=$?
status="${status:-0}"
printf '%s\n' "${output}"

# Reusing an initialized relational realm is the normal restart path.
if (( status != 0 )) && [[ "${output}" != *"already been bootstrapped"* ]]; then
  exit "${status}"
fi

exec /opt/jboss/container/java/run/run-java.sh
