# AGENTS.md

## Project overview

This repository is a single-host, Docker Compose data lakehouse demonstration.
It combines PostgreSQL, OpenLDAP, authentik, JupyterHub, Apache Ranger, Garage, Apache Polaris, Spark,
Airflow, Trino, Cube, Superset, Traefik, and a Streamlit control panel.

Read the root `README.md` first. Before changing a domain, also read its local
README and the relevant material under `docs/`:

- `platform/` contains images and runtime configuration.
- `orchestration/` contains the Airflow DAG.
- `data-pipeline/` contains the deterministic generator and Spark transforms.
- `analytics/` contains Cube models and Superset bootstrap logic.
- `control-panel/` contains the local Streamlit operations UI.
- `operations/` contains internal lifecycle helpers.
- `tests/` contains static contracts and live-stack smoke tests.

## Architectural invariants

Preserve these boundaries unless the requested change explicitly revises the
architecture and its documentation:

- Spark owns every analytical transformation and quality gate. Do not move
  transformations into Airflow, Trino, Cube, or Superset.
- Trino is query-only. Polaris owns Iceberg catalog metadata, and Garage owns
  table objects.
- Airflow owns orchestration and consists of API server, scheduler, and DAG
  processor services. DAGs are manually triggered and use Airflow API v2.
- Human identity lives in LDAP and is exposed through authentik OIDC. Machines use
  system identities (`svc_pipeline`, `svc_trino`, `svc_polaris_admin`, `svc_control`).
  Polaris runs in `external` mode and never accepts the shared root credential;
  Trino authorization is enforced by Ranger and Spark access by Polaris.
  Cube accesses curated gold data through the least-privilege `svc_cube`
  identity; it does not impersonate users.
- Keep the control panel bound to loopback unless authentication and the
  security model are deliberately redesigned. It uses the configured engineer
  identity internally and must never display its password.
- Named browser routes use Traefik HTTPS. Trino keeps native TLS for JDBC.
  Operational ports documented as local-only must stay on `127.0.0.1`.
- Pipeline retries must remain idempotent through batch identifiers. Automatic
  runs must continue to advance non-overlapping time periods, while explicit
  seeds remain reproducible.
- Keep container image versions pinned; do not introduce `latest` tags.

The executable Compose contract in `tests/compose_contract.py` is authoritative
for service names, container names, routing, port bindings, mounts, and required
Airflow processes. Update tests and documentation together when intentionally
changing one of those contracts.

## Working conventions

- Use `./lakehouse.sh` as the public lifecycle interface. Keep focused
  implementation scripts under `operations/scripts/`; do not add a parallel
  Makefile or another public command tree.
- Shell scripts use Bash, `set -euo pipefail`, quoted expansions, and paths
  resolved relative to the repository. Keep scripts non-interactive unless an
  operation is intentionally destructive.
- Python follows the existing straightforward typed style. Prefer standard
  library `unittest` for focused unit coverage and keep imports compatible with
  the container paths used by Compose.
- Add brief comments only when they explain non-obvious intent, constraints, or
  cross-service behavior. Do not narrate straightforward code or expand a
  comment beyond one sentence when one sentence is sufficient.
- Preserve comments in full vendor configuration snapshots; their upstream
  reference text is intentionally exempt from the short-comment convention.
- Keep bootstrap and reconciliation logic idempotent. Service restarts and
  repeated `./lakehouse.sh bootstrap` runs must not create duplicate policies,
  catalogs, datasets, charts, or dashboards.
- Configuration is spread across `compose.yaml`, `.env.example`, image
  Dockerfiles, mounted files under `platform/config/`, and initialization
  scripts. Trace all consumers before renaming an environment variable,
  service, hostname, port, database object, table, or Cube model.
- If a change affects topology, exposure, identity, policy, persistence,
  startup, data flow, or operator commands, update the relevant domain README
  and `docs/` page in the same change.
- Preserve existing user changes. Keep edits focused, and do not reformat or
  regenerate unrelated files.

## Secrets and generated state

Never print, copy into patches, or commit values from `.env`. Use
`.env.example` for non-secret defaults and variable names only.

The following are local/generated artifacts and are not source files:

- `.env`
- private material under `platform/config/pki/`
- `platform/config/garage/garage.generated.toml`
- `platform/config/trino/dbeaver-trino-truststore.p12`
- `operations/backups/`

`./lakehouse.sh init` generates secrets, certificates, the Garage configuration,
and the DBeaver truststore. Avoid running it for changes that do not need those
artifacts because it may reconcile the local `.env` file.

Do not run `CONFIRM_RESET=yes ./lakehouse.sh reset`, remove Compose volumes, or
delete backups unless the user explicitly requests loss of persistent data.
`./lakehouse.sh down` is non-destructive to volumes but still interrupts the
running environment, so use it only when the task requires it.

## Validation

Run the narrowest relevant checks first, then broaden according to the change:

```bash
# Python syntax and focused control-panel unit tests
python3 -m compileall -q orchestration data-pipeline analytics control-panel platform/config
python3 -m unittest -q tests/control_panel_test.py

# Documentation links
python3 tests/markdown_links.py

# Compose rendering and repository contracts (requires Docker Compose)
docker compose config --quiet
python3 tests/compose_contract.py

# Complete static suite; generated local artifacts must already exist
./tests/static.sh

# Live integration smoke tests; requires the healthy full stack
./tests/integration.sh

# Optional end-to-end pipeline check on a healthy stack
RUN_PIPELINE_TEST=1 ./tests/integration.sh
```

Use `./lakehouse.sh test` only when Docker is available and full repository
validation is warranted; it initializes local artifacts, then runs static and
integration checks. Integration tests normally require `./lakehouse.sh up` to
have completed. If the stack is not running or a required tool is unavailable,
report the skipped validation clearly rather than claiming it passed.

When behavior changes, add or adjust a focused test. For Compose changes,
extend `tests/compose_contract.py`; for control-panel API behavior, extend
`tests/control_panel_test.py`; for operational behavior, exercise the relevant
public `lakehouse.sh` command where practical.

## Change checklist

Before handing off a change:

1. Confirm the architectural and security boundaries above still hold.
2. Check that no secrets, private keys, generated files, backups, or runtime
   logs entered the diff.
3. Update configuration consumers, tests, and documentation together.
4. Run and report the relevant validation, including any checks that could not
   run because the Docker stack or host dependencies were unavailable.
