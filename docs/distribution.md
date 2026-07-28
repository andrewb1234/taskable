# Mouvadah distribution

Mouvadah Community is a self-hosted human-agent control and memory plane. The
current release stage is alpha: source installation is supported for early
users, while packaged releases and managed Cloud service follow after their
release gates pass.

## Editions and licenses

| Offering | Description | License or terms |
| --- | --- | --- |
| Mouvadah Community | Complete self-hosted API and web application | AGPL-3.0-only |
| Mouvadah MCP | Connector for local and hosted agent harnesses | Apache-2.0 |
| Mouvadah Cloud | Operated hosting, upgrades, backups, integrations, and support | Service terms when available |

The repository’s root [`LICENSE`](../LICENSE) applies to the API, web
application, deployment materials, and other files unless a file says
otherwise. The contents of [`mcp/`](../mcp/) use the separate
[`mcp/LICENSE`](../mcp/LICENSE). The software licenses grant copyright
permissions, not rights to Mouvadah branding; see
[`TRADEMARKS.md`](../TRADEMARKS.md).

## Install from source

The supported alpha path requires Python 3.12 or newer and Node.js 20 or
newer:

```bash
git clone https://github.com/andrewb1234/taskable.git
cd taskable
python3 bootstrap.py
```

The bootstrap creates an isolated environment, applies migrations, provisions
a local owner and API key, and prints commands for starting the API, web
application, and MCP bridge. See the repository [`README`](../README.md) for
the full local and Docker workflows.

## Packaged releases

A future version tag will build checksummed GitHub Release assets and versioned
API/web images. The release will contain:

- the `mouvadah-mcp` wheel and source archive;
- a local installer and Docker Compose manifest;
- API and web container images;
- license, trademark, and third-party notices; and
- SHA-256 checksums.

PyPI distribution of `mouvadah-mcp` and a Homebrew tap may follow after a
versioned release passes clean-install, upgrade, and rollback checks. `npx` is
not a primary channel because the connector is Python and the application is a
multi-container service.

## Retraction

Published open-source copies cannot be recalled. A release or container tag
can be removed from its original channel, and a Python release can be yanked,
but existing downloads and valid license grants remain. Security or packaging
problems are corrected with a documented advisory and a new version rather
than silently replacing an immutable release.
