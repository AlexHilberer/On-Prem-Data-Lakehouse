# Documentation

| Guide | Contents |
| --- | --- |
| [Architecture](architecture.md) | Components, deployment topology, data and query flows |
| [Security](security.md) | Identity, authorization, transport, secrets, and boundaries |
| [Operations](operations.md) | Setup, lifecycle, endpoints, backup, reset, and troubleshooting |
| [Decisions](decisions.md) | Important design choices and tradeoffs |
| [Images](images.md) | Version pins, provenance, and build strategy |
| [Control panel](../control-panel/README.md) | Local pipeline trigger and run monitoring |

Domain-specific implementation notes are available in the
[platform](../platform/README.md), [orchestration](../orchestration/README.md),
[data pipeline](../data-pipeline/README.md),
[analytics](../analytics/README.md),
[control panel](../control-panel/README.md), and
[operations](../operations/README.md) READMEs.

Start with the root [project overview](../README.md). Use the
[architecture guide](architecture.md#exposure-model) to understand why some
interfaces use Traefik labels while operational and JDBC endpoints bind
directly to localhost.
