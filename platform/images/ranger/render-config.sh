#!/usr/bin/env bash
set -euo pipefail

template="$1"
destination="$2"
rendered="$(mktemp)"
trap 'rm -f "${rendered}"' EXIT
envsubst < "${template}" > "${rendered}"

if [[ ! -f "${destination}" ]]; then
  cp "${rendered}" "${destination}"
  exit 0
fi

python3 - "${rendered}" "${destination}" <<'PY'
from pathlib import Path
import sys

overlay_path = Path(sys.argv[1])
destination_path = Path(sys.argv[2])

overrides = {}
for line in overlay_path.read_text().splitlines():
    stripped = line.strip()
    if stripped and not stripped.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        overrides[key.strip()] = value

output = []
replaced = set()
for line in destination_path.read_text().splitlines():
    stripped = line.strip()
    if stripped and not stripped.startswith("#") and "=" in line:
        key = line.split("=", 1)[0].strip()
        if key in overrides:
            if key not in replaced:
                output.append(f"{key}={overrides[key]}")
                replaced.add(key)
            continue
    output.append(line)

for key, value in overrides.items():
    if key not in replaced:
        output.append(f"{key}={value}")

destination_path.write_text("\n".join(output) + "\n")
PY
