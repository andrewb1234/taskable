# Third-party notices

Audit date: 2026-07-27.

Mouvadah depends on third-party software. Each dependency remains under its
own license; neither AGPL-3.0-only nor Apache-2.0 replaces those terms. Exact
versions are resolved by `web/package-lock.json` and the Python environment or
release image. Distributed package metadata retains the dependency license
files where supplied upstream.

This inventory covers direct application dependencies and noteworthy build
dependencies. A release operator must regenerate a full software bill of
materials and license report from the final images and archives before a
public release.

## API runtime

| Dependency | License reported by installed distribution |
| --- | --- |
| FastAPI | MIT |
| Starlette | BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| SQLModel | MIT |
| Alembic | MIT |
| Pydantic | MIT |
| pydantic-settings | MIT |
| python-dotenv | BSD-3-Clause |
| HTTPX | BSD-3-Clause |
| sse-starlette | BSD-3-Clause |
| PyJWT | MIT |
| psycopg2-binary | LGPL with linking exceptions |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| prometheus-client | Apache-2.0 AND BSD-2-Clause |
| sentry-sdk | MIT |
| OpenTelemetry API, SDK, and OTLP HTTP exporter | Apache-2.0 |

## MCP runtime

| Dependency | License reported by installed distribution |
| --- | --- |
| MCP Python SDK | MIT |
| HTTPX | BSD-3-Clause |
| python-dotenv | BSD-3-Clause |

## Web runtime

The direct React, React DOM, Radix UI, `clsx`, and `tailwind-merge`
dependencies report MIT licenses. `lucide-react` reports ISC and
`class-variance-authority` reports Apache-2.0.

The lockfile also contains build/test tooling under Apache-2.0, MPL-2.0,
CC-BY-4.0, MIT, ISC, BSD, and 0BSD terms. In particular, Lightning CSS and its
platform binaries report MPL-2.0, and `caniuse-lite` reports CC-BY-4.0. Those
tools/data are not intentionally copied into the production web image, but
their terms must be reevaluated if the build or image contents change.

## Compatibility review

The audited direct dependencies do not present an identified incompatibility
with the repository’s AGPL-3.0-only core or Apache-2.0 MCP bridge.
`psycopg2-binary` relies on its published LGPL exceptions. This is an
engineering inventory, not a substitute for counsel’s review of a final
distribution.
