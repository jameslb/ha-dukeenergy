# Read-only preflight and download-free rollback — 2026-10-22

**Nothing deployed, moved, reloaded or restarted.** This supersedes the earlier
suggestion that an integration reload could activate edited Python source.

## Verified installed state

- Authenticated HA API RUNNING, Core 2026.10.2. Both voice controllers are
  stopped/manual/watchdog-off; candidate remains phase5-ddce9562d743.
- Installed Duke directory is 0.4.0 and its Python source matches the retained
  reviewed baseline. All 11 static integration files were recovered privately;
  config entries, credentials, ledger and recorder were not copied or edited.
- aiodukeenergy 1.1.0: exact Git repository and commit
  ebb68991eb6b92950d9f4e9bd9978f71f173d32e, actual import origin and all six tracked
  source-file hashes match `client_lock.json`. A separate isolated import check
  passed with network, subprocess and file writes prohibited. No API client
  method was called and no bytecode files were written.
- Installed HA source confirms retryable setup before Core startup listens for
  `EVENT_HOMEASSISTANT_STARTED`. Actual lifecycle behavior remains a future
  deployment observation, not an outcome of these offline tests.

## Two activation hazards identified

`ConfigEntries.async_reload()` unloads and sets up an entry; its loader returns
cached component modules. It does not reload the changed Python source. A future
activation therefore needs a separately approved **Core-process self-restart**.
No VM/host restart, Supervisor restart, import-cache surgery or hot patch is part
of this plan. The current no-restart instruction remains in effect.

A legacy directory `/config/custom_components/duke_energy.backup-20260924-111236`
also declares domain `duke_energy`, version 0.3.0. The installed loader indexes
custom integrations by manifest domain, so a duplicate can shadow the intended
version depending on enumeration order. Nothing was moved during preflight.
Before any future activation, relocate only this verified legacy directory
outside `custom_components`, retain it, and require exactly one Duke declaration.
Do not stage candidate or rollback directories inside `custom_components`.

## Exact local bundles

`scripts/build_offline_bundles.py` builds two local bundles from a fresh installed
snapshot, enforcing `deployment/installed-0.4.0.lock.json`. A drifted snapshot
fails before output is created. Existing output/search-path destinations are
rejected. The script never connects to HA, installs or deploys anything.

Each bundle contains 13 integration files. Nine existing source/translation files
are byte-identical to the fresh installed snapshot. The candidate changes only
`__init__.py` and `manifest.json`, adding `client_dependency.py` and
`client_lock.json`. No library/site-packages files are copied or changed.

The rollback is **behavioral, not a byte-exact original-manifest restore**:

- restore original first-refresh-before-sensors startup behavior (including
  before Core readiness), without the candidate's boot deferral;
- retain the same exact-fork verifier and an empty `requirements` list;
- retain the existing authentication/statistics/coordinator/sensor code and data;
- use manifest version 0.4.0, with no URL installer requirement or fallback.

Candidate and rollback differ only in `__init__.py` and `manifest.json`. The
original unmodified reference snapshot is retained separately for evidence; its
URL requirement must **not** be restored as the operational offline rollback.
Both operational bundles avoid Duke package downloads by construction. This is
not a blanket guarantee about unrelated integrations during any Core restart.
A read-only custom-requirement scan found Duke URL requirements in the main and
legacy directories; other entry-configured custom requirements passed their
installed checks. YAML-only/unconfigured integrations and future drift are not
covered by that assertion. Do not activate if the fresh no-download check cannot
account for the full startup configuration; do not use package-skip overrides.

## Proposed deployment steps — approval required, not executed

1. Recheck Core readiness, no active backup/update/reload, controllers off,
   capture inactive, client provenance/hashes/imports and live integration hashes.
   Abort on drift; do not repair/download a dependency automatically.
2. Back up the current integration files into a new, access-restricted operation
   directory **outside** the integration search path, e.g.
   `/share/phase5-duke-startup-20261022-<operation-id>/`. Keep config-entry settings,
   credentials, cost ledger and recorder database in place; never restore these
   data files from a stale snapshot.
3. Stage the hash-verified candidate and operational rollback there. Verify paths
   resolve within that operation directory and no destination already exists.
   Relocate the single verified legacy backup there without deleting it. Recheck
   that `custom_components` has exactly one `duke_energy` manifest.
4. Apply only four runtime files under `/config/custom_components/duke_energy`:
   verifier and lock first, integration init next, manifest last. Use temporary
   files and per-file rename within the destination directory, check hashes and
   abort on concurrent edits. Preserve permissions. Do not copy the whole config,
   client library, caches or data; do not call an integration reload.
5. **Only with separate Core-restart approval**, request HA's native
   restart service (domain `homeassistant`, action `restart`) after its normal config checks. Do not
   use VM power controls, Docker kill, forced stop or repeated restart commands.
   File deployment alone does not activate the new module. If graceful restart
   stalls, stop and report; do not escalate automatically.
6. Verify a new Core process, API RUNNING, the 0.4.1 manifest and loaded-code
   evidence, the startup not-ready → started-event → real-refresh sequence,
   truthful sensor availability and absence of a Duke package-manager attempt.
   Compare existing statistics/ledger continuity without manual refreshes,
   deleting history or rebuilding statistics. Do not replay voice tests. A Core
   restart can briefly affect other HA integrations and normal startup routines.

## Operational rollback steps — separately authorized if needed

1. Confirm the same exact client is still installed and rollback payload hashes
   match. If library/source/data drifted, stop rather than overwrite it.
2. Restore only rollback `__init__.py`, then rollback `manifest.json`. Keep the
   identical verifier/lock, existing ledger, recorder, credentials and other nine
   files. Verify empty requirements and exactly one Duke manifest. Keep the
   legacy backup outside the search path; do not restore its URL requirement.
3. If Core is responsive, request one separately authorized native Core
   self-restart and verify original refresh ordering and data continuity. If it
   is unresponsive, restore files through the existing authenticated recovery
   path, report the state and obtain direction; do not force-stop or restart the
   VM/host. Never claim file restoration alone reverted cached running code.

## Local validation and remaining gate

The fresh installed-source candidate passed 21 offline checks; rollback passed
20, including original boot ordering plus the same provenance/statistics checks.
The reproducible builder produced byte-identical payloads to those tested.
Focused cached Ruff lint/format passes. The HA/client boundaries use doubles;
there was no live refresh, statistics write, reload or timing test.

**Next:** review these concrete steps and the Core-only activation/rollback scope.
No restart is authorized by this preflight. The Duke candidate is still not
installed. Matter's internal failure and every Phase 5 physical/recognition/
echo/provider gate remain open.
