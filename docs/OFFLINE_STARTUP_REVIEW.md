# Offline Duke startup correction — review only

Prepared against the retained installed 0.4.0 Python source and pinned client,
not the older local checkout. Commit 818c9ec records that baseline separately.
This branch is not deployed and does not propose another HA outage.

## Proposed change

- `manifest.json`: candidate 0.4.1 has no package-manager requirements. It uses
  the preinstalled managed client; it never downloads or substitutes a public
  package with the same version number.
- `client_lock.json` and `client_dependency.py`: require aiodukeenergy 1.1.0 from
  the existing jameslb fork, commit ebb68991eb6b92950d9f4e9bd9978f71f173d32e.
  Verify its recorded Git provenance, actual import location and SHA-256 of all
  six tracked client files. Mismatch/missing files cause retryable entry setup
  failure, without installation or Duke API access. File verification runs in
  HA's executor rather than blocking the event loop.
- `__init__.py`: while Core is not running, report retryable `ConfigEntryNotReady`
  before token validation, cost loading or first refresh. Once running, the
  ordinary entry retry executes the existing setup sequence unchanged: token
  validity, cost load, first refresh, then sensor registration.

The fork, OAuth implementation, configuration-flow behavior, poll scheduling,
coordinator, sensor definitions, statistics algorithms and cost ledger format
are unchanged from the retained baseline. Existing sensors can remain
unavailable until that real refresh succeeds; no values or completion are
fabricated. There are no new background tasks, timeout increases, HA patches,
package-skip settings or model changes. Config-flow module imports are unchanged;
the verifier protects entry setup, not HA's global module loader.

## Offline validation

Two baseline regressions failed before this correction: boot setup immediately
performed authentication/statistics work, and its manifest still invoked the Git
requirement installer. Both pass afterward.

21 standalone unittest checks pass, covering deferred setup/retry, preserved
refresh-before-sensors ordering, retryable timeout versus invalid credentials,
exact cached-fork files, altered/missing source, wrong provenance/version/import
location, and real ledger deduplication plus pending-statistics persistence and
acknowledgement. Framework/client calls use explicit doubles; no Duke/HA service
is contacted. The cached pinned client checkout supplies fixture bytes; Windows
CRLF is normalized only in fixtures, never by the production verifier.

Run with an existing Python 3.13+ runtime (no dependency installation):

```powershell
$env:DUKE_PINNED_SOURCE = 'C:/src/aiodukeenergy/src/aiodukeenergy'
C:/src/aiodukeenergy/.venv/Scripts/python.exe tests/offline_startup.py -v
```

The standalone filename avoids injecting its doubles into normal pytest
collection. Focused Ruff lint and formatting pass using cached Ruff 0.15.5.
Statistics/authentication files are also compared with the retained baseline;
none changed. No restart, download, voice test or deployment occurred.

These tests do not run HA 2026.10's actual retry scheduler, recorder database or
Duke service. No startup-time reduction or live acceptance is claimed.

## Deployment conditions and rollback — not executed

Before any future approved deployment, perform a read-only verification of the
actual installed client with this guard. The retained provenance matches the
commit, but its full live file hashes/import location have not been checked by
this candidate. Abort on mismatch; do not install, repair, relax verification,
or fall back automatically. Verify transitive imports using the already-installed
runtime, and retain the current integration files, settings and ledger unchanged.

Deploying requires separate approval for the exact bundle and any integration
reload. Do not restart HA/its VM or repeat the locking maintenance for this
candidate. If approved later, observe the actual HA retry event and truthful
sensor availability without voice requests. Preserve the existing ledger and
recorder; do not delete history, change unique IDs or trigger manual statistics
rebuilds.

The unchanged client and baseline 818c9ec remain available for rollback. Restoring
its original URL requirement can invoke the package manager on reload; therefore
an original-bundle rollback reload must not be run unattended under a no-download
scope. Resolve that reload scope before deployment rather than after a failure.
Matter's earlier internal startup failure remains unresolved; this correction
does not claim to fix it or complete any Phase 5 physical gate.
