#!/usr/bin/env bash
set -euo pipefail

superset db upgrade
superset init
cd /app
python /app/bootstrap/bootstrap.py
