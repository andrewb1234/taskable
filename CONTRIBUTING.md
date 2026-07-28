# Contributing to Mouvadah

Thank you for helping improve Mouvadah. Open an issue before a substantial
change so maintainers can confirm scope and licensing.

## Inbound license

Unless a file says otherwise, contributions outside `mcp/` are submitted
under AGPL-3.0-only and contributions inside `mcp/` are submitted under
Apache-2.0. By submitting a contribution, you represent that you have the
right to do so under that license. Do not include code, data, media, or other
material whose terms are incompatible with the destination license.

Disclose meaningful use of generated material in the pull request. A human
contributor must review the result, make the creative and technical choices,
and accept responsibility for the submission. Do not represent purely
machine-generated output as independently copyrightable human work.

## Developer Certificate of Origin

Every commit must include a `Signed-off-by` trailer confirming the
[Developer Certificate of Origin 1.1](https://developercertificate.org/):

```text
Signed-off-by: Your Name <your-email@example.com>
```

Create it with `git commit -s`. The sign-off certifies that you wrote the
contribution or otherwise have the right to submit it under the applicable
license.

## Commercial licensing boundary

Mouvadah does not currently ask contributors to sign a copyright assignment
or contributor license agreement. The project therefore must not relicense
outside contributions into a proprietary edition without the contributors’
permission. If the project later wants proprietary self-hosted licensing, it
will adopt and publish a reviewed contributor agreement before accepting
contributions intended for that edition.

## Pull requests

- Keep changes focused and add proportionate tests.
- Preserve security and tenant-boundary behavior.
- Update documentation when user-visible behavior changes.
- Confirm that required checks pass.
- Use a signed-off commit.
