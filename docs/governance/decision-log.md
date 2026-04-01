# POLYMAX — Decision Log

**Area:** docs/governance · **Authority:** Operator
**Format:** newest first · Each entry: date · version · decision · rationale

---

## 2026-04-01 — v0.5.26 — Documentation content verification pass (Status A)

**Decision:** Stale test counts in `regression_tiers.md` (~553/~554) corrected to
actual post-v0.5.23 counts (~594/~595). Atlas "Last updated" header corrected from
v0.5.22 to v0.5.23. No new contracts, no production code changes.

**Rationale:** Doc content must be verifiable against the actual test suite.
Stale counts degrade trust in tier documentation.

---

## 2026-04-01 — v0.5.25 — README surface cleanup (Status B)

**Decision:** README milestone chronology corrected (was reversed v0.5.22→v0.5.23→v0.5.24).
Project structure tree updated to reflect actual directories. Testing Docs section added
with table linking to all six `docs/testing/` files. Tier commands added.

**Rationale:** README was the only surface listing docs/testing files; the new
Testing Docs section makes them discoverable without expanding README scope.

---

## 2026-04-01 — v0.5.24 — Frontend/backend interface alignment (Status B)

**Decision:** `Market` interface in `frontend/src/lib/api.ts` was missing `end_date`
field. `SyncResult` interface was missing `registry_total_count`. Both added.
`SyncAction.tsx` now surfaces "Registry total" row. Launcher reads host/port from
`config/default.toml` instead of hardcoding defaults.

**Rationale:** Frontend interface drift causes silent display failures.
`config/default.toml` is the declared single source of truth for host/port;
launcher must honour it.

---

## 2026-04-01 — v0.5.23 — Regression tier contract lock (Status B)

**Decision:** Regression tier definitions (Smoke / Standard / Full) documented in
`docs/testing/regression_tiers.md` with executable pytest commands and
change-type decision table. 41 new tier contract tests added.

**Rationale:** Tier logic was understood but not executable-documented; contributors
could not determine which tests to run for a given change type.

---

## 2026-04-01 — v0.5.22 — Contract atlas lock (Status A)

**Decision:** `docs/testing/discovery_sync_contract_atlas.md` created as single-page
canonical index of all 13 locked/deferred contracts. 43 new atlas contract tests added.

**Rationale:** Contract surfaces were individually locked but had no cross-referencing
index. The atlas is the navigation entry point for new contributors.

---

## 2026-04-01 — v0.5.21 — Snapshot refresh trigger policy lock

**Decision:** Refresh policy documented in `docs/testing/gamma_snapshot_refresh_policy.md`.
Required triggers (live test FAILED, missing key, `[BREAKING DRIFT]` alert, planned
upgrade) separated from negative triggers (SKIPPED, PASSED, connection error,
value-only change). Optional proactive cadence defined.

**Rationale:** Without a policy, refresh decisions were ad hoc and undocumented.

---

## 2026-04-01 — v0.5.20 — Drift response ownership lock

**Decision:** `docs/testing/gamma_drift_response_roles.md` created. Operator decides;
Claude implements under approval; no unilateral fixture commits. Decision matrix
and live-test action table locked.

**Rationale:** Ownership of upstream API drift response was undefined. This created
ambiguity about who may commit fixture changes.

---

## 2026-04-01 — v0.5.19 — Upstream drift triage workflow lock

**Decision:** `docs/testing/gamma_contract_workflow.md` created with step-by-step
triage procedure. `tools/refresh_gamma_snapshot.py` CLI helper committed.
REQUIRED_FIELDS / OPTIONAL_FIELDS separation established.

**Rationale:** No documented process existed for responding to Gamma API shape drift.

---

## 2026-04-01 — v0.5.17 — Canonical text field normalization (Status B — production fix)

**Decision:** Whitespace-only `slug` caused a silent downstream mapping failure.
Fix: `_normalize()` strips and None-ifies whitespace-only `slug`; strips whitespace
from `question`. Locked in `FetchedMarket` docstring.

**Rationale:** Silent failure (no error, no candidate, no log entry) was worse
than a validation error. Normalization contract now covers this boundary case.

---

## 2026-04-01 — v0.5.16 — Fetcher normalization contract lock

**Decision:** `_normalize()` field policy table documented in docstring and locked by
integration tests. Boundary cases: `id` absent → skip; `question` absent → `""`;
`slug` falsy → `None`; `enableOrderBook` absent → `None`; `tokens` non-list → `None`.

**Rationale:** Normalization behaviour was tested but not formally documented,
making it unsafe to change individual field handling in isolation.

---

## 2026-04-01 — v0.5.15 — Pipeline edge-state contracts lock

**Decision:** Five canonical pipeline edge states locked cross-layer: `empty`,
`all-rejected`, `all-mapping-failed`, `all-duplicate`, `all-new-valid`.
Cross-layer invariants (candidate alignment, partition identity, taxonomy completeness)
verified for each state.

**Rationale:** Edge states had been tested individually but not documented as a
closed set with cross-layer invariants.

---

## 2026-04-01 — v0.5.14 — Mapping failure semantics lock (3-gate model)

**Decision:** Three mutually exclusive pipeline gates formally locked:
Gate 1 = discovery rejection (counts candidates);
Gate 2 = mapping failure (counts candidates, not Market objects);
Gate 3 = registry duplicate (counts Market objects).
Pipeline invariant: `(fetched − skipped_mapping) × 2 = mapped`.

**Rationale:** Gate semantics were implicit. Without the invariant, partial failures
were undetectable from the SyncResult fields alone.

---

## 2026-04-01 — v0.5.13 — Mapper multiplicity contract lock

**Decision:** `MarketMapper.map()` always produces exactly 2 `Market` objects per
candidate (`MARKETS_PER_CANDIDATE = 2`): one `-up` and one `-down`. Declared as
a fixed structural property via named constant in `market_sync.py`.

**Rationale:** The ×2 multiplier was implicit in the implementation. Making it a
named constant prevents accidental drift and makes the invariant testable.

---

## 2026-04-01 — v0.5.7 — Registry add-only / lifecycle deliberately deferred

**Decision:** `InMemoryMarketRegistry` is add-only. Existing entries are never
updated or removed on re-sync. Lifecycle management (stale entry cleanup,
expiry, archival) is explicitly deferred — not a bug, not a gap.

**Rationale:** Premature lifecycle logic adds complexity before the deployment
model (scheduler, persistence layer) is decided. Deferral documented in
`_LIFECYCLE_NOTE` docstring in `market_sync.py`.

**Open risk:** Stale entries accumulate indefinitely; cleanup needed before
production deployment.

---

## 2026-04-01 — v0.5.5b — Duration source semantics: source_timestamp = event start

**Decision:** `source_timestamp` is `startDate` from Gamma — the event start time,
not the fetch time. A misleading domain comment was corrected. Duration is
`end_date − source_timestamp` (total event span), not remaining time.

**Rationale:** The original comment implied fetch time. Near-expiry markets with
valid total duration must be accepted; using remaining time would incorrectly reject them.

---

## 2026-04-01 — v0.5.4 — Fetcher is pure normalisation (no filtering)

**Decision:** `PolymarketFetchService` applies no candidate filtering.
`DiscoveryService` is the sole candidate-selection authority.
Fetcher responsibility limited to: HTTP fetch + raw → `FetchedMarket` normalisation.

**Rationale:** Separation of concerns. Filtering logic in the fetcher is invisible
to the discovery layer and cannot be overridden or inspected.

---

## 2026-04-01 — Foundation — Backend as single source of truth

**Decision:** All authoritative data lives in the backend. Frontend is display-only
and never computes or stores authoritative state.

**Rationale:** Foundational architecture decision. Prevents state divergence between
layers and simplifies debugging.

---

## 2026-04-01 — Foundation — Local-first, launcher-entry architecture

**Decision:** POLYMAX runs locally via `python launcher/main.py`. No cloud deployment,
no external auth, no SaaS dependencies in the core loop.

**Rationale:** Project goal is a local trading panel. Cloud complexity is out of
scope at this stage.
