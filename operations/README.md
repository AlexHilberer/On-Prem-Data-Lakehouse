# Operations

`lakehouse.sh` is the only public lifecycle interface. Focused helpers remain
under `operations/scripts/` and are called by the root CLI.

## Command Reference

| Command | Purpose |
| --- | --- |
| `./lakehouse.sh up` | Initialize, bootstrap, and start the platform |
| `./lakehouse.sh down` | Stop containers without deleting volumes |
| `./lakehouse.sh build` | Build locally maintained images |
| `./lakehouse.sh bootstrap` | Reapply Ranger policies and Polaris catalog configuration |
| `./lakehouse.sh pipeline` | Trigger the retail DAG |
| `./lakehouse.sh test` | Run static and integration smoke tests |
| `./lakehouse.sh backup` | Back up PostgreSQL, LDAP, and Garage |
| `CONFIRM_RESET=yes ./lakehouse.sh reset` | Delete persistent platform data |

See the [operations guide](../docs/operations.md) for endpoints, host setup,
troubleshooting, backups, and reset behavior.
