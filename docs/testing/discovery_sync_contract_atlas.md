# POLYMAX — Discovery/Sync Contract Atlas

**Introduced:** v0.5.22 · **Last updated:** v0.5.22 (2026-04-01)

Single-page canonical index of every locked contract in the fetch → discovery
→ sync → API chain.  This document does not duplicate content — it links to
authoritative sources and provides the minimal summary needed to orient a new
contributor or reviewer.

For the full test scenario matrix, see:
`docs/testing/discovery_regression_matrix.md`

---

## How to read this atlas

Each entry has five fields:

| Field | Meaning |
|-------|---------|
| **Canonical rule** | The locked invariant, one sentence |
| **Source of truth** | Where the rule is authoritatively defined (code / docstring / doc) |
| **Protected by** | Test file(s) that enforce the rule |
| **Status** | `LOCKED` (invariant; change requires test update) · `DEFERRED` (decision intentionally postponed) |
| **Open risks** | Known gaps or future concerns; not re-openings of closed decisions |

---

## 1. Fetcher Normalization Contract

**Canonical rule:** `PolymarketFetchService._normalize()` is a pure normalisation
pass — it applies no candidate filtering.  Every raw field follows the policy
table in its docstring (id absent → skip; question absent → ""; slug whitespace →
None; enableOrderBook absent → None; tokens non-list → None; dates absent →
None).

**Source of truth:**
`backend/app/services/market_fetcher.py` — `_normalize()` docstring field policy table

**Protected by:**
`backend/tests/services/test_market_fetcher.py` ·
`backend/tests/integration/test_fetcher_normalization_contract.py` ·
`backend/tests/integration/test_discovery_flow.py`

**Status:** LOCKED (v0.5.4, v0.5.16)

**Open risks:** None — normalization policy fully documented and tested.

---

## 2. Canonical Text Field Normalization Contract

**Canonical rule:** `slug` is an identifier-like field — whitespace-only →
`None`; `None`/absent → `None`; non-blank → stripped string.  `question` is a
display-text field — whitespace-only → `""`; absent → `""`.  Neither can be a
whitespace-only string downstream.

**Source of truth:**
`backend/app/services/market_fetcher.py` — `FetchedMarket` docstring
(slug/question canonical contracts)

**Protected by:**
`backend/tests/integration/test_canonical_text_field_normalization.py` ·
`backend/tests/integration/test_fetcher_normalization_contract.py`

**Status:** LOCKED (v0.5.17 — production fix; whitespace-only slug caused silent
mapping failure)

**Open risks:** None — fix prevents whitespace slug from reaching the mapper.

---

## 3. Discovery Selection Contract

**Canonical rule:** `DiscoveryService` is the **sole candidate-selection
authority**.  The fetcher never filters.  Five rejection rules applied in order:
`INACTIVE` → `NO_ORDER_BOOK` → `EMPTY_TOKENS` → `MISSING_DATES` →
`DURATION_OUT_OF_RANGE`.  First failing rule wins.

**Source of truth:**
`backend/app/services/market_discovery.py` — `DiscoveryService.evaluate()` docstring

**Protected by:**
`backend/tests/services/test_market_discovery.py` ·
`backend/tests/integration/test_discovery_flow.py`

**Status:** LOCKED (v0.5.5)

**Open risks:** None — 5-rule set closed; any new rule requires a new milestone.

---

## 4. Duration Semantics Contract

**Canonical rule:** Duration = `end_date − source_timestamp` (total event span,
not remaining time).  `source_timestamp` is `startDate` from Gamma — the event
start time, not the fetch time.  Valid window: [240 s, 360 s] inclusive.
Near-expiry markets with valid total duration are accepted.

**Source of truth:**
`backend/app/services/market_discovery.py` — `DURATION_OUT_OF_RANGE` rule ·
`backend/app/services/market_fetcher.py` — `source_timestamp` docstring

**Protected by:**
`backend/tests/services/test_market_discovery.py` — `TestDurationRejection` ·
`backend/tests/integration/test_discovery_flow.py` — `TestDurationSemantics`

**Status:** LOCKED (v0.5.5a, v0.5.5b)

**Open risks:** None — semantics locked including near-expiry edge case.

---

## 5. Rejection Taxonomy Contract

**Canonical rule:** `DiscoveryResult.string_breakdown` is the single
canonical `RejectionReason` enum → string serialisation point.  Always
returns all 5 taxonomy keys, even for zero-count reasons.  Enum is the
authority; serialised string is derived.

**Source of truth:**
`backend/app/services/market_discovery.py` — `DiscoveryResult.string_breakdown` docstring

**Protected by:**
`backend/tests/integration/test_rejection_taxonomy_contract.py`

**Status:** LOCKED (v0.5.10)

**Open risks:** None.

---

## 6. Mapper Multiplicity Contract

**Canonical rule:** `MarketMapper.map()` always produces exactly **2 domain
`Market` objects** per candidate (`MARKETS_PER_CANDIDATE = 2`): one `-up` and
one `-down`.  This is a fixed structural property, not configurable.

**Source of truth:**
`backend/app/services/market_sync.py` — `MarketMapper` docstring,
`MARKETS_PER_CANDIDATE` constant

**Protected by:**
`backend/tests/integration/test_mapper_multiplicity_contract.py`

**Status:** LOCKED (v0.5.13)

**Open risks:** None.

---

## 7. Mapping Failure Semantics Contract

**Canonical rule:** Three mutually exclusive pipeline gates:
Gate 1 = `rejected_count` (discovery; counts candidates);
Gate 2 = `skipped_mapping` (mapper failure; counts candidates, not Market objects);
Gate 3 = `skipped_duplicate` (registry; counts Market objects).
Pipeline invariant: `(fetched − skipped_mapping) × 2 = mapped`.

**Source of truth:**
`backend/app/services/market_sync.py` — `SyncResult` docstring, "Three pipeline
failure gates" section

**Protected by:**
`backend/tests/integration/test_mapping_failure_semantics.py`

**Status:** LOCKED (v0.5.14)

**Open risks:** None.

---

## 8. Sync Summary Semantics Contract

**Canonical rule:** `SyncResult` fields describe the **processing window only**
(current sync call), not lifetime totals.  `fetched` = candidates passed from
discovery (not raw API count).  `registry_total` = full registry size including
entries from prior syncs.

**Source of truth:**
`backend/app/services/market_sync.py` — `SyncResult` docstring

**Protected by:**
`backend/tests/integration/test_sync_summary_semantics.py`

**Status:** LOCKED (v0.5.8)

**Open risks:** None.

---

## 9. Discover/Sync Contract Alignment

**Canonical rule:** `discover.candidate_count == sync.fetched_count` always.
`discover.fetched_count` intentionally differs from `sync.fetched_count` (discover
counts raw API records; sync counts candidates from discovery).  All 5 taxonomy
keys present in both endpoints, always.

**Source of truth:**
`backend/app/api/routers/markets.py` — `DiscoveryResponse` docstring (intentional
difference documented)

**Protected by:**
`backend/tests/integration/test_discover_sync_contract_alignment.py`

**Status:** LOCKED (v0.5.11)

**Open risks:** None.

---

## 10. Registry Add-Only / Lifecycle Semantics

**Canonical rule:** `InMemoryMarketRegistry` is **add-only** — existing entries
are never updated or removed on re-sync.  Stale entry cleanup and lifecycle
management are **deliberately deferred** (not yet implemented).  This is a
conscious architectural decision, not a gap.

**Source of truth:**
`backend/app/services/market_sync.py` — `MarketSyncService` lifecycle docstring
(`_LIFECYCLE_NOTE`)

**Protected by:**
`backend/tests/integration/test_registry_lifecycle.py`

**Status:** LOCKED (contract); DEFERRED (lifecycle implementation — explicit
decision, not a bug)

**Open risks:** Stale entries accumulate indefinitely; cleanup strategy needed
before production deployment.

---

## 11. Pipeline Edge-State Contracts

**Canonical rule:** Five canonical pipeline edge states are deterministic and
cross-layer consistent: `empty`, `all-rejected`, `all-mapping-failed`,
`all-duplicate`, `all-new-valid`.  Cross-layer invariants hold for every edge
state: candidate alignment, partition identity, taxonomy completeness.

**Source of truth:**
`backend/app/services/market_sync.py` — `SyncResult` docstring,
"Pipeline edge-state reference table"

**Protected by:**
`backend/tests/integration/test_pipeline_edge_state_contract.py`

**Status:** LOCKED (v0.5.15)

**Open risks:** None.

---

## 12. Live Gamma Contract Snapshot

**Canonical rule:** `backend/tests/fixtures/gamma_snapshot.json` (10 records) is
the committed, frozen representation of the expected Gamma API response shape.
Pipeline normalization, discovery, and sync produce deterministic results on this
fixture.  Real API shape is verified via `@pytest.mark.live` (skipped by default).

**Source of truth:**
`backend/tests/fixtures/gamma_snapshot.json` ·
`backend/tests/integration/test_live_gamma_contract_snapshot.py`

**Protected by:**
`backend/tests/integration/test_live_gamma_contract_snapshot.py` (22 tests + 1 live-skipped)

**Status:** LOCKED (v0.5.18)

**Open risks:** If Gamma API shape changes, fixture must be manually refreshed.
See drift triage workflow below (§13).

---

## 13. Drift Triage / Ownership / Refresh Trigger Policy

**Canonical rule:** Three interlocking contracts govern upstream drift response:
(a) **Workflow** — how to classify expected vs breaking drift and how to refresh
the fixture step-by-step;
(b) **Ownership** — Operator decides; Claude implements under approval; no
unilateral fixture commits;
(c) **Trigger policy** — required triggers (live test FAILED/missing-key,
`[BREAKING DRIFT]` alert, planned API upgrade) vs negative triggers (SKIPPED,
PASSED, connection error, value-only change) vs optional proactive cadence.

**Source of truth:**
`docs/testing/gamma_contract_workflow.md` ·
`docs/testing/gamma_drift_response_roles.md` ·
`docs/testing/gamma_snapshot_refresh_policy.md` ·
`tools/refresh_gamma_snapshot.py` (REQUIRED_FIELDS / OPTIONAL_FIELDS)

**Protected by:**
`backend/tests/integration/test_upstream_drift_triage_workflow.py` ·
`backend/tests/integration/test_drift_response_ownership.py` ·
`backend/tests/integration/test_snapshot_refresh_trigger_policy.py`

**Status:** LOCKED (v0.5.19, v0.5.20, v0.5.21)

**Open risks:**
- Gamma API upgrade announcements are external signals outside automated testing.
- If the team grows, ownership roles must be redistributed.

---

## Summary table

| # | Contract surface | Status | Introduced | Test file |
|---|-----------------|--------|------------|-----------|
| 1 | Fetcher normalization | LOCKED | v0.5.4 / v0.5.16 | `test_fetcher_normalization_contract.py` |
| 2 | Canonical text field normalization | LOCKED | v0.5.17 | `test_canonical_text_field_normalization.py` |
| 3 | Discovery selection (5-rule) | LOCKED | v0.5.5 | `test_discovery_flow.py` |
| 4 | Duration semantics | LOCKED | v0.5.5a/b | `test_market_discovery.py` |
| 5 | Rejection taxonomy | LOCKED | v0.5.10 | `test_rejection_taxonomy_contract.py` |
| 6 | Mapper multiplicity (×2) | LOCKED | v0.5.13 | `test_mapper_multiplicity_contract.py` |
| 7 | Mapping failure semantics (3 gates) | LOCKED | v0.5.14 | `test_mapping_failure_semantics.py` |
| 8 | Sync summary semantics | LOCKED | v0.5.8 | `test_sync_summary_semantics.py` |
| 9 | Discover/sync alignment | LOCKED | v0.5.11 | `test_discover_sync_contract_alignment.py` |
| 10 | Registry add-only / lifecycle DEFERRED | LOCKED+DEFERRED | v0.5.7 | `test_registry_lifecycle.py` |
| 11 | Pipeline edge-state contracts | LOCKED | v0.5.15 | `test_pipeline_edge_state_contract.py` |
| 12 | Live Gamma contract snapshot | LOCKED | v0.5.18 | `test_live_gamma_contract_snapshot.py` |
| 13 | Drift triage / ownership / trigger policy | LOCKED | v0.5.19–21 | `test_upstream_drift_triage_workflow.py` · `test_drift_response_ownership.py` · `test_snapshot_refresh_trigger_policy.py` |

---

## Known deferred decisions

| Decision | Status | Rationale |
|----------|--------|-----------|
| Registry lifecycle / stale entry cleanup | DEFERRED | Deliberate; see §10 |
| Persistence (database storage) | DEFERRED | In-memory registry only at this stage |
| Concurrency / parallel sync | DEFERRED | Applicable when scheduler is added |
| Strategy / risk / entry timing | OUT OF SCOPE | Not a discovery-layer concern |
| Full live CI integration | DEFERRED | Manual refresh workflow is the current standard |

---

## Quick navigation

| I want to know… | Go to |
|-----------------|-------|
| Full scenario matrix (all 360+ test scenarios) | `docs/testing/discovery_regression_matrix.md` |
| How to refresh the Gamma fixture | `docs/testing/gamma_contract_workflow.md` |
| Who decides on drift response | `docs/testing/gamma_drift_response_roles.md` |
| When to refresh (trigger policy) | `docs/testing/gamma_snapshot_refresh_policy.md` |
| Field normalization policy detail | `backend/app/services/market_fetcher.py` — `_normalize()` docstring |
| Pipeline gate semantics detail | `backend/app/services/market_sync.py` — `SyncResult` docstring |
