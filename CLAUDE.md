# CLAUDE.md

Project context and rules for AI agents. This file is the single source of truth for the current state of the repo. Keep it current and concise.

Priority: explicit user instruction > this file > agent defaults.

---

## Project

- **Name:** On-Premises Data Lakehouse
- **Purpose:** Single-host Docker Compose lakehouse with LDAP identity, Ranger authorization, Spark processing, Iceberg tables and governed analytics.
- **Stack:** PostgreSQL 17, Garage (S3), Apache Polaris (Iceberg REST catalog), OpenLDAP, authentik (OIDC), JupyterHub, Apache Ranger, Airflow 3 (Celery, Redis), Spark 3.5, Trino, Cube Core, Superset, Traefik, Streamlit control panel. Python 3 and Bash. 21 single-replica services named `lakehouse-*`.
- **Entry point(s):** `./lakehouse.sh` (the only public lifecycle interface; no Makefile), `compose.yaml`, DAG `orchestration/dags/retail_lakehouse_pipeline.py`, `data-pipeline/generator.py`, `data-pipeline/spark_retail.py`, `control-panel/app.py`.
- **Also read:** `AGENTS.md` (invariants), `README.md`, domain READMEs and `docs/`.
- **Host needs:** Linux amd64, Docker Compose v2, 16 GiB RAM, ~30 GiB disk, openssl, keytool, curl, jq, Python 3, `/etc/hosts` entries `127.0.0.1 airflow|ranger|superset|cube|authentik|jupyter.lakehouse.local`.

## Commands

- **Install:** `./lakehouse.sh init` (`.env`, local PKI, Garage config, DBeaver truststore); `python -m pip install -r control-panel/requirements.txt` for static tests (CI also needs ripgrep).
- **Dev:** `./lakehouse.sh up|down|ps|logs [svc]|bootstrap|backup`; `ROWS=5000 SEED=100 ./lakehouse.sh pipeline`; `CONFIRM_RESET=yes ./lakehouse.sh reset` is destructive.
- **Test:** `./tests/static.sh` (CI runs this); `python3 -m unittest -q tests/control_panel_test.py`; `python3 tests/compose_contract.py`; `python3 tests/markdown_links.py`; `./tests/integration.sh` (needs a healthy stack; `RUN_PIPELINE_TEST=1` for end to end); `./lakehouse.sh test` runs all.
- **Lint / format:** None configured. `static.sh` runs compileall, `docker compose config --quiet` and `json.tool` on Ranger policies.
- **Build:** `./lakehouse.sh build [service]`. The first build is slow (Ranger and OpenLDAP build from source).
- **CI:** `.github/workflows/validate.yml`, push to main only: `init` then `static.sh`. No integration job.

---

## Rules

Bias: caution over speed. For trivial tasks, use judgment.

### 1. Think before coding

- State your assumptions. If you are unsure, ask.
- If a request has several interpretations, list them. Don't pick one silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what is confusing, and ask before writing code.

### 2. Simplicity

- Write the minimum code that solves the problem.
- No features, options, or configurability beyond what was asked.
- No abstractions for single-use code.
- No error handling for impossible cases.
- If it could be half the size, rewrite it. Test: would a senior engineer call this overcomplicated?
- Match the existing style, even if you would do it differently.

### 3. Verification

- Turn every task into a check you can run:
  - "Fix the bug" -> write a test that reproduces it, then make it pass.
  - "Add validation" -> write tests for invalid input, then make them pass.
  - "Refactor X" -> tests pass before and after.
- For multi-step tasks, state a short plan first:
  `1. <step> -> verify: <check>`
- Loop until every check passes. Only then commit.

### 4. Comments

- One short sentence max. No exceptions.
- Only where the code is not self-explanatory. Explain *why*, never *what*.
- No commented-out code, no TODOs, no history notes. Those go in [Pitfalls](#pitfalls) or [Open Tasks](#open-tasks).
- Workarounds are the only place a comment is mandatory (see rule 8).

### 5. File length

- Soft limit: **~600 lines**. Exceeding it means refactor.
- One responsibility per file. Split by responsibility, not by line count.
- A file must be readable top to bottom without jumping around.

### 6. Memory (this file)

- Update this file whenever you change structure, commands, dependencies, or conventions.
- Add anything new you discover about the repo.
- Delete outdated information. This file describes the current state, not history.
- Keep entries short. If a section grows too large, condense it.

### 7. Pitfalls

- Document known issues, failed attempts, and workarounds in [Pitfalls](#pitfalls), not in code.
- Exception: at a workaround site, add one line:
  `// Workaround: <reason>. See CLAUDE.md#pitfalls`

### 8. Git

**Pushing**
- **Never push.** No `git push` in any form, no exceptions, even if a task seems to require it. Only the user pushes.

**When to commit**
- Commit only if a git repo exists (`git rev-parse --is-inside-work-tree`). Never run `git init`.
- Commit after each completed, working change: one logical change per commit, with tests passing.
- Stage specific files. No `git add -A` or `git add .` without checking `git status` first.
- Never commit secrets or build artifacts.
- Never commit a `.env` file. Variants such as `.env.example` may be committed. Staging `.env` is fine when needed, but unstage it with `git restore --staged <file>` before committing. Make sure `.gitignore` lists `.env`.

**Commit messages**
- One line, imperative mood, max 72 characters. Example: `Split auth service into token and session modules`
- Add a body only if the change can't be understood without one. The body is max 2 short lines.
- Never mention AI, Claude, agents, or any assisting tool. No `Co-Authored-By`, no `Generated with`, no `Claude-Session` trailers, no emoji signatures.

**Fixing mistakes**
- If a commit message mentions an AI tool anyway, undo it immediately:
  `git reset --soft HEAD~1`, then recommit with a clean message.
- Check with `git log -1 --format=%B` after every commit.
- If the `commit-msg` hook rejects a commit, rewrite the message. Never bypass the hook.
- Only rewrite your own unpushed commits. Never force anything, never use `--no-verify`, never rewrite history the user already has.

**Subagents**
- Subagents never commit. The main agent reviews their changes and commits.

---

## Subagents

- `comment-cleaner`: run it on changed files after edits. Its changes go in their own commit. Merge its report into Open Tasks and Pitfalls.
- `file-refactorer`: run it when a file exceeds the line limit. One file per spawn. Merge its report into Architecture and Pitfalls.
- `code-reviewer`: run it on your changes before every commit. Fix its "Must fix" findings first.
- `security-auditor`: run it when a change touches auth, input handling, file paths, subprocesses or network code.
- `debugger`: use it when a failure's cause isn't obvious after one look. Merge its Pitfalls notes.
- `test-writer`: use it when new or changed behavior lacks tests.
- `explorer`: use it for broad searches, so file dumps stay out of your context.
- Subagents never edit this file. You merge their reports.

---

## Architecture

| Path | Purpose |
|------|---------|
| `lakehouse.sh`, `compose.yaml`, `.env.example` | Lifecycle CLI, service topology, env template (`.env` is ignored) |
| `platform/images/` | Dockerfiles and entrypoints (airflow, control-panel, openldap, polaris, ranger, spark, superset) |
| `platform/config/` | Tracked configs mounted read-only; Ranger policies/templates; `pki/` holds generated keys |
| `orchestration/dags/retail_lakehouse_pipeline.py` | Manual DAG: `generate` >> `spark_transform` (params `rows=0`, `seed=42`) |
| `data-pipeline/generator.py` | Deterministic Faker generator into Postgres `source` schema, idempotent per batch ID |
| `data-pipeline/spark_retail.py` | PySpark: JDBC source to Iceberg bronze/silver/gold via Polaris and Garage, with quality gates |
| `analytics/cube/` | Cube `checkSqlAuth` (only `CUBEJS_SQL_USER`) and models over `gold.*` |
| `analytics/superset/` | `init.sh` and idempotent `bootstrap.py` (datasets, charts, dashboards on Cube SQL API) |
| `control-panel/` | Streamlit UI (`app.py`) and `AirflowClient` over Airflow v2 API; loopback only |
| `operations/scripts/` | Helpers called by `lakehouse.sh`; `operations/backups/` is generated |
| `tests/` | `static.sh`, `integration.sh`, `compose_contract.py` (authoritative Compose contract), `control_panel_test.py`, `markdown_links.py` |
| `platform/config/jupyterhub/` | Hub config, `token_broker.py` (refreshes OIDC tokens), `lakehouse_notebook` kernel package (`spark_builder`, `get_token`, `%sql`) |
| `platform/config/authentik/` | Blueprints for the LDAP source, the `lakehouse` OIDC provider and the machine service accounts |
| `platform/config/polaris/` | `application.properties` (OIDC mapping) plus `auth-external.properties` / `auth-mixed.properties` (selected through `QUARKUS_CONFIG_LOCATIONS`) |
| `LICENSE`, `NOTICE` | Apache License 2.0 and the list of projects the stack builds on |
| `docs/` | `architecture.md`, `security.md`, `operations.md`, `images/` (README screenshots) |

### Invariants

- Spark owns all transformations and quality gates; Trino is query-only; Polaris owns catalog metadata, Garage owns table objects.
- Humans live in LDAP and log in through authentik OIDC. Machines use system identities: `svc_pipeline` (Spark), `svc_trino`, `svc_polaris_admin` (authentik service accounts, client secret `base64(user:app-password)`), `svc_control` (local Airflow user for the control panel and trigger script) and `svc_cube` (LDAP, Cube to Trino).
- Polaris runs in `external` mode and never accepts the shared root credential; Ranger authorizes Trino; Polaris authorizes Spark per identity; Cube reads gold as `svc_cube` and does not propagate user identity.
- Accepted non-OIDC exceptions: Ranger Admin and usersync (LDAP), Cube to Trino, Spark UI, control panel UI, Garage.
- Control panel stays on 127.0.0.1 and never shows the engineer password. Local-only ports stay on 127.0.0.1; Redis is internal only.
- Pin image versions, never `:latest`. Bootstrap and reconciliation stay idempotent. Pipeline retries are idempotent via batch IDs.
- No secrets in the repo. Never reset, remove volumes or delete backups unless the user asks.
- Topology, exposure, identity, policy, persistence, startup, data flow or command changes also update the domain README and `docs/`.
- Renaming an env var, service, host or port: trace compose.yaml, `.env.example`, Dockerfiles, `platform/config` and init scripts.
- Dependencies (all pinned): `requests`, `streamlit` (control panel); `faker`, `psycopg2-binary` (generator); `Authlib` (Superset image, required by Flask-AppBuilder OAuth login); `oauthenticator`, `pyspark`, `trino`, `pyiceberg`, `pandas` (JupyterHub image). Spark, Airflow, Superset and Cube come from images.

## Conventions

- **Language specifics:** Follow the path-scoped rules for each language (Python, JS/TS, Bash, Java, C#). Where they are silent, follow the language's standard style guide and the patterns already in the file.
- **Naming:** Use descriptive names over abbreviations, and the casing convention of the language. Booleans read as questions (`is_ready`, `hasAccess`). Functions are verbs, and types are nouns. Match the existing names in the codebase before introducing new patterns.
- **Error handling:** Validate input at system boundaries (CLI args, files, network, external APIs), and trust internal code. Fail fast with specific error types and messages that name the bad value. Keep the cause when wrapping errors. Never swallow errors silently (no empty catch blocks). Catch only what you can handle, and let the rest propagate.
- **Testing:** Use the test framework the project already uses. Every behavior change comes with a test. Tests are fast, deterministic, offline and independent of each other. Test behavior through public interfaces, not implementation details. Mock only at external boundaries (network, time, filesystem, subprocess).
- **Dependencies:** Prefer the standard library, then existing dependencies. Add a new one only if it saves substantial code, is actively maintained, and has a compatible license. Declare it in the project's manifest (`pyproject.toml`, `package.json`, `pom.xml`/`build.gradle`, `.csproj`) with a version constraint, use the lock file of the existing package manager, and keep dev-only tools out of the runtime dependencies. Record every new dependency and why it was added in this file.

---

## Pitfalls

### Known issues

- Control panel has no user login and uses a shared engineer account; access relies on the loopback binding. Location: `control-panel/app.py`
- `jdbc_query` splits user and password from the DB URL on `@` and `:`; breaks if the password contains `@`. Location: `data-pipeline/spark_retail.py`
- `overwrite_batch` interpolates `batch_id` into SQL (UUID, low risk). Location: `data-pipeline/spark_retail.py`
- `replace_legacy_table` drops tables lacking required columns with PURGE. Location: `data-pipeline/spark_retail.py`
- Superset metrics `COUNT(DISTINCT "orderCount")` and `COUNT(DISTINCT "customerCount")` look wrong (unverified). Location: `analytics/superset/bootstrap.py`
- Cube SQL user's `securityContext` role is hard-coded to `superset`. Location: `analytics/cube/cube.js`
- Trino cert covers 127.0.0.1 only; DBeaver must use 127.0.0.1. Truststore password is `changeit`.
- Docker Desktop VM can exit during a pipeline with under 16 GiB.
- Polaris and Garage have no Ranger plugin, so they stay internal. Direct Airflow and control-panel ports are HTTP over loopback.
- `tests/integration.sh` exits 0 when Docker is unavailable. `static.sh` needs init artifacts and its final `git check-ignore ... || true` cannot fail.
- `static.sh` forbids Makefile, `docker/`, `pipeline/`, `scripts/`, `.runtime`, caddy, one-shot services, `service_completed_successfully` and `restart: no`.
- Reset keeps `.env`, PKI, truststore and backups.
- Superset and Airflow have no LDAP login; authentik is the only way into their UIs.
- Polaris machine principals must exist before `external` mode accepts a service token; a fresh stack needs the one-time mixed window that `./lakehouse.sh bootstrap` runs automatically.
- Polaris cannot take its authentication type from an environment variable (map-keyed config); use the `auth-*.properties` files.
- Airflow behind Traefik needs `AIRFLOW__FAB__ENABLE_PROXY_FIX`, otherwise OIDC redirect URIs use `http`.
- authentik refresh tokens are single use and service-account tokens expire after 8 hours; the Spark pipeline fetches a fresh token per run.
- Notebook kernels hold the shared Garage keys, and Spark sessions see Ranger-masked columns unmasked (masks apply only in Trino).
- The hub token broker is the only token refresher (authentik refresh tokens are single use, so hub-side refresh stays disabled); users must not be hub admins, or a kernel could read other users' refresh tokens.
- Docker Desktop can serve a stale copy of a single-file bind mount after an in-place edit; recreate the container.

### Attempted and rejected

- None recorded.

### Workarounds

- **Problem:** Spark executors must reach the client-mode driver on the Airflow worker.
  **Workaround:** `spark.driver.host=airflow-worker`, `bindAddress=0.0.0.0`.
  **Location:** `orchestration/dags/retail_lakehouse_pipeline.py`
  **Remove when:** Spark runs in cluster mode.
- **Problem:** Garage S3 compatibility.
  **Workaround:** `chunked-encoding-enabled=false`, `checksum-enabled=false` (uncommented in code).
  **Location:** `data-pipeline/spark_retail.py`
  **Remove when:** Garage supports chunked encoding and checksums.
- **Problem:** The Ranger build fails because the Kylin plugin needs `RoaringBitmap:0.7.36-os-kylin-r1`, which repo.spring.io now answers with 401.
  **Workaround:** The Dockerfile strips the Kylin modules, dependencies and assembly descriptors from the 2.8.0 poms before `mvn -Pall`.
  **Location:** `platform/images/ranger/Dockerfile`
  **Remove when:** Ranger drops or republishes the Kylin dependency, or the pinned version moves past it.
- **Problem:** Machine principals do not exist in Polaris on a fresh stack, and `external` mode cannot create them.
  **Workaround:** `lakehouse.sh bootstrap` recreates Polaris once with `POLARIS_AUTHENTICATION_TYPE=mixed`, creates the principals with the root credential, and flips back to `external`.
  **Location:** `lakehouse.sh`, `operations/scripts/bootstrap-platform.sh`
  **Remove when:** Polaris can provision an external admin principal at bootstrap.
- **Problem:** authentik's Python 3.13 rejects a CA certificate without `keyUsage`, which broke LDAP over TLS.
  **Workaround:** `init-secrets.sh` re-signs an existing CA with the same key plus `CA:TRUE` and `keyCertSign` (old file kept as `ca.crt.bak`), and creates new CAs that way.
  **Location:** `operations/scripts/init-secrets.sh`
  **Remove when:** All stacks were created with a CA that already has `keyUsage`.

---

## Open Tasks

- [ ] Add the CLAUDE.md workaround comments at the two workaround sites (reason: rule 7)
- [ ] Verify the Superset distinct-count metrics (reason: suspected wrong)
- [ ] Add a linter/formatter (reason: none configured)
