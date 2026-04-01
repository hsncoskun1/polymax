# POLYMAX — Discovery / Fetch / Sync Regression Matrix

**Living document — update with every version that changes behaviour in the
fetch → discovery → sync → API chain.**

Last updated: v0.5.16 (2026-04-01) · Total automated tests: **381**

---

## 1. Purpose and Scope

### What this document verifies

Every scenario in the fetch → discovery → sync → API production path that
must remain stable across future releases. It is the companion to the
automated test suite — each scenario maps to one or more pytest tests.

### Layers covered

| Layer | Key component | Responsibility |
|-------|--------------|----------------|
| **Fetch** | `PolymarketFetchService` | HTTP → `FetchedMarket` normalisation only; no candidate filtering |
| **Discovery** | `DiscoveryService` | Sole candidate-selection authority; applies all 5 rejection rules |
| **Sync** | `MarketSyncService` | Orchestration — uses discovery output to write to registry |
| **API** | `POST /discover`, `POST /sync` | HTTP interface; surfaces discovery/sync results |

### Explicitly out of scope

- Strategy / risk / entry timing (when is it too late to enter a market?)
- Force sell / settlement / position management
- Trading execution / order routing
- Runtime remaining-time gating
- Frontend rendering / UI components
- Database persistence (in-memory registry only at this stage)

---

## 2. Version Changelog

| Version | Key Behaviour Change | New Test Behaviour | Regression to Protect | Retired Behaviour |
|---------|---------------------|-------------------|----------------------|-------------------|
| v0.1.1 | Backend shell, `/health` endpoint | Health endpoint returns 200 + JSON body | — | — |
| v0.2.1 | Domain `Market` model, `InMemoryMarketRegistry` | CRUD operations, duplicate/not-found exceptions, status transitions | — | — |
| v0.2.2 | Markets REST API (5 CRUD endpoints) | HTTP 200/201/404/409/422 per operation | — | — |
| v0.3.1 | `PolymarketClient` shell (httpx, read-only) | Timeout/HTTP errors raise typed exceptions | — | — |
| v0.3.2 | `PolymarketFetchService` + `FetchedMarket` DTO | Normalisation: id, question, slug, active, closed, dates | — | — |
| v0.3.3 | `MarketMapper` + `MarketSyncService` (single-shot) | fetch → map → registry write; UP+DOWN per market | — | — |
| v0.3.4 | `POST /sync` endpoint | Sync response shape (fetched/mapped/written/skipped counts) | — | — |
| v0.3.7 | `enableOrderBook` + `tokens` gates added to `_is_5m_candidate` | AMM-only and no-token markets filtered | fetch still returns all | — |
| v0.3.8 | Duration gate `[240, 360]s` added to `_is_5m_candidate` | Markets outside 5m window filtered | fetch still returns all | — |
| v0.3.9 | `extract_symbol()` for question/slug → coin ticker | BTC/ETH/SOL/etc. extracted; unknown → fallback | Symbol not a rejection criterion | — |
| v0.4.1 | `DiscoveryService` shell (3 rules: INACTIVE, MISSING_DATES, DURATION_OUT_OF_RANGE) | Rejection breakdown tracking, DiscoveryResult | — | — |
| v0.4.2 | `POST /discover` endpoint | fetch → evaluate, no registry write | — | — |
| v0.5.1 | `end_date` field on domain `Market` + mapper | `end_date` propagated from FetchedMarket → domain Market | — | — |
| v0.5.2 | `MarketSyncService` routes through `DiscoveryService` | Sync uses discovery candidates; no dual candidate path | `fetch_candidates()` still existed but bypassed | — |
| v0.5.3 | `enable_order_book` + `tokens` fields on `FetchedMarket`; `NO_ORDER_BOOK` + `EMPTY_TOKENS` rules in `DiscoveryService` | 5-rule discovery; order-book and token gates at FetchedMarket level | All prior rules still apply | `_is_5m_candidate` was duplicate (removed next version) |
| v0.5.4 | `fetch_candidates()` and `_is_5m_candidate()` removed | `fetch_markets()` is the only public fetcher method | Fetcher must not filter | ✅ `fetch_candidates()` retired; ✅ `_is_5m_candidate()` retired |
| v0.5.5 | Integration test suite — 4 contracts locked (C1–C4) | End-to-end chain from raw dict to API response | All prior unit-level contracts | — |
| v0.5.5a | Duration semantics locked — total duration not remaining time | Near-expiry valid markets always pass discovery | Duration uses `end_date − source_timestamp` | — |
| v0.5.5b | Duration source semantics locked — `source_timestamp` confirmed as event start time (`startDate`) | Semantic chain `startDate → source_timestamp → duration` is test-locked | Domain model comment corrected from "freshness from upstream" to "event start time" | — |
| v0.5.6 | Sync / Registry Behavior Lock — 5 registry contracts (C1–C5) + Scenario G (previously-valid market handling) + API summary integrity | Registry key format, add-only semantics, no-update-on-resync, C4 per-reason guards, mixed-payload determinism, registry stays after invalid transition, POST /sync response matches registry state | All prior sync + discovery contracts still hold | — |
| v0.5.7 | Registry Lifecycle Semantics Lock — add-only/retained model documented as deliberate deferred decision; 11 new tests; market_sync.py lifecycle docstring added | Lifecycle decision: C (deferred); 4 rejection-reason lifecycle tests (A), closed/inactive explicit tests (B/C), sync summary gap documented (D), mixed lifecycle payload determinism (E) | All prior contracts still hold; stale entry behavior now explicit | — |
| v0.5.8 | Sync Summary Semantics Lock — SyncResult.registry_total added; SyncResponse.registry_total_count added; SyncResult docstring clarified (fetched=candidates not raw fetch); 12 new tests | Summary semantics: processing window only; fetched≠raw API count; registry_total exposes full registry size including stale | All prior contracts still hold | — |
| v0.5.9 | Rejection Observability Lock — SyncResult.rejected_count + rejection_breakdown added; SyncResponse exposes both fields; 14 new tests | rejected_count surfaces non-candidates; breakdown is always 5-key complete; fetched + rejected_count = total input; API passes fields through; observability read-only w.r.t. registry behavior | All prior contracts still hold | — |
| v0.5.10 | Rejection Taxonomy Contract Lock — DiscoveryResult.string_breakdown property added as single canonical enum→string serialization point; 15 new taxonomy contract tests | Canonical source: RejectionReason enum; single serialization point (string_breakdown property); zero-count policy documented; drift detection locked; docs/runtime alignment verified | All prior contracts still hold | Duplicate r.value conversions in market_sync.py and discover endpoint retired |
| v0.5.11 | Discover/Sync Contract Alignment Lock — DiscoveryResponse docstring expanded with intentional differences; 10 new alignment tests | candidate alignment: discover.candidate_count==sync.fetched_count; shared taxonomy/zero-count; intentional fetched_count difference documented; operator consistency under mixed payload; no behavioral changes | All prior contracts still hold | — |
| v0.5.12 | Cross-Layer Field Semantics Lock — SyncResult docstring extended with API field name mapping table; 9 new cross-layer field semantics tests | discover/sync field sets locked; SyncResult→SyncResponse _count suffix convention documented; raw/candidate/rejected partition naming consistent; registry_total semantically distinct from processing-window fields; docs/runtime alignment verified | All prior contracts still hold | — |
| v0.5.13 | Mapper Multiplicity Contract Lock — MarketMapper docstring expanded with explicit multiplicity contract; MARKETS_PER_CANDIDATE=2 constant added; SyncResult.mapped docstring clarified; 14 new multiplicity tests | exact-two canonical contract; mapped counts Market objects not candidates; written+skipped_duplicate=mapped partition; -up/-down identity stable; docs/runtime/summary alignment | All prior contracts still hold | — |
| v0.5.14 | Mapping Failure Semantics Lock — SyncResult docstring extended with three-pipeline-gate section (Gate 1: discovery rejection, Gate 2: mapping failure, Gate 3: registry duplicate); pipeline invariant documented; 12 new mapping failure semantics tests | Gate 2 (skipped_mapping) is distinct from Gate 1 (rejected_count) and Gate 3 (skipped_duplicate); skipped_mapping counts candidates not Market objects; mapping failure does not write to registry; pipeline invariant: (fetched−skipped_mapping)×2=mapped; docs/runtime/API alignment | All prior contracts still hold | — |
| v0.5.15 | Pipeline Edge-State Contract Lock — SyncResult docstring extended with edge-state reference table (5 canonical states: empty/all-rejected/all-map-failed/all-duplicate/all-new-valid); Status A: no production changes needed; 16 new edge-state contract tests (A–F) | empty cross-layer invariant locked; all-rejected cross-layer partition locked; all-map-failed service/invariant locked; all-duplicate partition/registry locked; all-new-valid candidate-alignment locked; cross-layer invariants (candidate_count==fetched_count; discover.fetched==sync.fetched+sync.rejected) tested for all edge states | All prior contracts still hold | — |
| v0.5.16 | Fetcher Input Normalization Contract Lock — _normalize() docstring extended with field normalization policy table; Status A: normalization already consistent; 34 new boundary-case normalization tests (A–F) | question None/absent/''→''; slug falsy→None; market_id blank→skip; datetime absent/invalid→None; active/closed absent→False; enable_order_book absent→None (conservative, not False); tokens non-list→None (conservative, not []); event_id extracted from first events dict; normalization never filters candidates | All prior contracts still hold | — |

---

## 3. Test Matrix

Each row is an independently testable scenario.

**Priority key:**
- `P0` — Release-blocking: failure means the system is fundamentally broken
- `P1` — Important: failure is a significant regression
- `P2` — Helpful: edge-case or defensive coverage

---

### 3.1 Fetch Normalisation Scenarios

| ID | Pri | Introduced | Scenario | Expected Result | Automated Test |
|----|-----|------------|----------|-----------------|----------------|
| FETCH-001 | P0 | v0.5.4 | `fetch_markets()` returns all records including inactive, AMM-only, no-tokens, missing-date, wrong-duration markets | All records returned; no silent filtering | `TestFetchMarkets::test_no_candidate_filtering_applied` · `TestFetcherIsNormaliserNotSelector::test_fetch_returns_all_markets_including_invalid_ones` |
| FETCH-002 | P0 | v0.5.5 | Field values that DiscoveryService checks are preserved intact | `active=False`, `enable_order_book=False`, `tokens=[]` survive normalisation | `TestFetcherIsNormaliserNotSelector::test_fetch_preserves_field_values_discovery_needs_to_evaluate` |
| FETCH-003 | P1 | v0.3.2 | Records with missing or empty `id` are skipped with a warning | Skipped, all others returned | `TestFetchMarkets::test_skips_record_with_missing_id` |
| FETCH-004 | P2 | v0.3.2 | `limit` parameter forwarded to `client.get_markets()` | Called with correct limit | `TestFetchMarkets::test_passes_limit_to_client` |
| FETCH-005 | P1 | v0.3.2 | Client errors (`PolymarketTimeoutError`) propagate to caller | Exception re-raised | `TestFetchMarkets::test_propagates_client_error` |
| FETCH-006 | P1 | v0.3.2 | ISO-8601 `startDate` / `endDate` parsed to timezone-aware datetime | Correct datetime values; `None` on absent/invalid | `TestNormalization::test_parses_source_timestamp` · `test_end_date_none_when_absent` · `test_source_timestamp_none_on_unparseable_date` |
| FETCH-007 | P1 | v0.3.2 | Optional fields (`slug`, `question`, `event_id`) normalise correctly | `slug=None` when absent; `question=""` when absent; `event_id` from first event | `TestNormalization::test_slug_none_when_absent` · `test_event_id_is_none_when_events_absent` |
| FETCH-008 | P1 | v0.5.3 | `enableOrderBook` field: `True→True`, `False→False`, absent→`None` | Conservative `None` for absent field | `TestNormalization::test_enable_order_book_true_when_present` · `test_enable_order_book_false_when_false` · `test_enable_order_book_none_when_absent` |
| FETCH-009 | P1 | v0.5.3 | `tokens` field: list preserved, `[]` preserved, absent→`None`, non-list→`None` | Faithful representation; `None` only for structural absence | `TestNormalization::test_tokens_list_preserved` · `test_tokens_empty_list_preserved` · `test_tokens_none_when_absent` · `test_tokens_none_when_not_a_list` |
| FETCH-010 | P0 | v0.5.5b | `source_timestamp` is event start time from Gamma `startDate` (not fetch time) | `source_timestamp == parsed(startDate)` — fixed event property | `TestNormalization::test_source_timestamp_is_event_start_time_from_gamma_start_date` |
| FETCH-011 | P0 | v0.5.5b | `startDate → source_timestamp` + `endDate → end_date` chain yields correct structural duration | `end_date - source_timestamp == event span in seconds` | `TestNormalization::test_duration_field_mapping_startDate_to_source_timestamp_and_endDate_to_end_date` |

---

### 3.2 Discovery Acceptance Scenarios

| ID | Pri | Introduced | Scenario | Expected Result | Automated Test |
|----|-----|------------|----------|-----------------|----------------|
| DISC-ACC-001 | P0 | v0.4.1 | Market passes all 5 rules (active, order book, tokens, dates, duration) | `candidate_count=1` | `TestCandidateSelection::test_valid_market_is_a_candidate` · `TestDiscoveryIsTheSoleSelector::test_valid_5m_market_becomes_candidate` |
| DISC-ACC-002 | P1 | v0.4.1 | Multiple valid markets all become candidates | `candidate_count=N` | `TestCandidateSelection::test_multiple_valid_markets_all_become_candidates` |
| DISC-ACC-003 | P1 | v0.3.8 | Duration exactly at lower boundary (240s) | Accepted | `TestDurationRejection::test_passes_lower_boundary` |
| DISC-ACC-004 | P1 | v0.3.8 | Duration exactly at upper boundary (360s) | Accepted | `TestDurationRejection::test_passes_upper_boundary` |
| DISC-ACC-005 | P0 | v0.5.5a | Near-expiry market: total duration valid, remaining time small | Accepted — discovery does not check remaining time | `TestDurationRejection::test_duration_filter_uses_total_market_duration_not_remaining_time` · `TestDurationRejection::test_valid_5m_market_near_expiry_is_not_rejected_by_discovery` · `TestDurationSemantics::*` |
| DISC-ACC-006 | P2 | v0.3.9 | Symbol not extractable from question or slug | Still a candidate — symbol fallback, never a rejection | `TestSymbolFallbackNotRejection::*` |

---

### 3.3 Discovery Rejection Scenarios

| ID | Pri | Introduced | Rejection Reason | Input Condition | Automated Test |
|----|-----|------------|-----------------|-----------------|----------------|
| DISC-REJ-001 | P0 | v0.4.1 | `INACTIVE` | `active=False` | `TestInactiveRejection::test_inactive_market_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_inactive_active_false_fetch_passes_discovery_rejects` |
| DISC-REJ-002 | P0 | v0.4.1 | `INACTIVE` | `closed=True` | `TestInactiveRejection::test_closed_market_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_inactive_closed_true_fetch_passes_discovery_rejects` |
| DISC-REJ-003 | P1 | v0.4.1 | `INACTIVE` | `active=False` and `closed=True` | Counted as one rejection | `TestInactiveRejection::test_inactive_and_closed_counts_as_one_rejection` |
| DISC-REJ-004 | P0 | v0.5.3 | `NO_ORDER_BOOK` | `enable_order_book=False` | `TestNoOrderBookRejection::test_enable_order_book_false_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_no_order_book_false_fetch_passes_discovery_rejects` |
| DISC-REJ-005 | P0 | v0.5.3 | `NO_ORDER_BOOK` | `enable_order_book=None` (field absent) | Conservative reject | `TestNoOrderBookRejection::test_enable_order_book_none_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_no_order_book_absent_field_fetch_passes_discovery_rejects` |
| DISC-REJ-006 | P0 | v0.5.3 | `EMPTY_TOKENS` | `tokens=[]` | `TestEmptyTokensRejection::test_empty_tokens_list_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_empty_tokens_list_fetch_passes_discovery_rejects` |
| DISC-REJ-007 | P0 | v0.5.3 | `EMPTY_TOKENS` | `tokens=None` (field absent) | Conservative reject | `TestEmptyTokensRejection::test_tokens_none_is_rejected` |
| DISC-REJ-008 | P0 | v0.4.1 | `MISSING_DATES` | `source_timestamp=None` | `TestMissingDatesRejection::test_missing_source_timestamp_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_missing_start_date_fetch_passes_discovery_rejects` |
| DISC-REJ-009 | P0 | v0.4.1 | `MISSING_DATES` | `end_date=None` | `TestMissingDatesRejection::test_missing_end_date_is_rejected` · `TestDiscoveryIsTheSoleSelector::test_missing_end_date_fetch_passes_discovery_rejects` |
| DISC-REJ-010 | P0 | v0.3.8 | `DURATION_OUT_OF_RANGE` | Total duration < 240s (e.g., 120s, 180s, 239s) | `TestDurationRejection::test_rejects_one_second_below_lower_boundary` · `test_duration_out_of_range_rejects_120s_total_duration` · `test_duration_out_of_range_rejects_180s_total_duration` |
| DISC-REJ-011 | P0 | v0.3.8 | `DURATION_OUT_OF_RANGE` | Total duration > 360s (e.g., 600s, 3600s, 86400s) | `TestDurationRejection::test_rejects_one_second_above_upper_boundary` · `test_duration_out_of_range_rejects_600s_total_duration` · `test_rejects_hourly_duration` |

---

### 3.4 Discovery Rule Priority Scenarios

Rules are applied in order; the first failing rule wins.

| ID | Pri | Scenario | Expected First Reason | Automated Test |
|----|-----|---------|-----------------------|----------------|
| DISC-PRI-001 | P1 | `active=False` + `source_timestamp=None` | `INACTIVE` (not `MISSING_DATES`) | `TestInactiveRejection::test_inactive_takes_priority_over_missing_dates` |
| DISC-PRI-002 | P1 | `active=False` + `enable_order_book=False` | `INACTIVE` (not `NO_ORDER_BOOK`) | `TestInactiveRejection::test_inactive_takes_priority_over_no_order_book` |
| DISC-PRI-003 | P1 | `enable_order_book=False` + `tokens=[]` | `NO_ORDER_BOOK` (not `EMPTY_TOKENS`) | `TestNoOrderBookRejection::test_no_order_book_takes_priority_over_empty_tokens` |
| DISC-PRI-004 | P1 | `enable_order_book=False` + `source_timestamp=None` | `NO_ORDER_BOOK` (not `MISSING_DATES`) | `TestNoOrderBookRejection::test_no_order_book_takes_priority_over_missing_dates` |
| DISC-PRI-005 | P1 | `tokens=[]` + `source_timestamp=None` | `EMPTY_TOKENS` (not `MISSING_DATES`) | `TestEmptyTokensRejection::test_empty_tokens_takes_priority_over_missing_dates` |
| DISC-PRI-006 | P1 | `source_timestamp=None` + wrong duration | `MISSING_DATES` (not `DURATION_OUT_OF_RANGE`) | `TestMissingDatesRejection::test_missing_dates_takes_priority_over_duration` |

---

### 3.5 Duration Semantics Scenarios

| ID | Pri | Scenario | What Is Verified | Automated Test |
|----|-----|----------|-----------------|----------------|
| DUR-001 | P0 | Market started 4m ago, ends in 1m (total=300s, remaining=60s) | Accepted — total duration checked, not remaining | `TestDurationRejection::test_duration_filter_uses_total_market_duration_not_remaining_time` · `TestDurationSemantics::test_near_expiry_valid_5m_market_passes_full_pipeline` |
| DUR-002 | P0 | Market in final 30 seconds (total=300s, remaining=30s) | Accepted — structurally valid 5m market | `TestDurationRejection::test_valid_5m_market_near_expiry_is_not_rejected_by_discovery` · `TestDurationSemantics::test_final_30s_market_with_300s_total_duration_is_candidate` |
| DUR-003 | P1 | Duration exactly 240s (lower boundary) | Accepted | `TestDurationRejection::test_passes_lower_boundary` |
| DUR-004 | P1 | Duration exactly 360s (upper boundary) | Accepted | `TestDurationRejection::test_passes_upper_boundary` |
| DUR-005 | P1 | Duration 239s (one below lower boundary) | `DURATION_OUT_OF_RANGE` | `TestDurationRejection::test_rejects_one_second_below_lower_boundary` |
| DUR-006 | P1 | Duration 361s (one above upper boundary) | `DURATION_OUT_OF_RANGE` | `TestDurationRejection::test_rejects_one_second_above_upper_boundary` |
| DUR-007 | P0 | Near-expiry valid + short + long + inactive in same batch | Only near-expiry valid is a candidate | `TestDurationRejection::test_mixed_payload_keeps_valid_5m_market_even_when_near_expiry` · `TestDurationSemantics::test_mixed_payload_near_expiry_valid_market_survives_with_invalid_durations` |
| DUR-008 | P0 | `source_timestamp` = event start, `end_date` = event end; difference = structural event span | Named semantic lock: duration = event span, not an ambiguous calculation | `TestDurationRejection::test_duration_uses_canonical_structural_time_fields` |

---

### 3.6 Mixed Payload Scenarios

| ID | Pri | Scenario | Expected Result | Automated Test |
|----|-----|----------|-----------------|----------------|
| MIX-001 | P0 | Payload with 1 valid + 1 per each rejection reason (6 markets total) | `candidate_count=1`; all 5 rejection reasons counted | `TestRejectionBreakdown::test_mixed_reasons_counted_separately` · `TestDiscoveryIsTheSoleSelector::test_mixed_payload_only_valid_candidates_survive` |
| MIX-002 | P1 | All markets invalid (different reasons) | `candidate_count=0`; breakdown sums to total | `TestRejectionBreakdown::test_rejected_count_equals_sum_of_breakdown` |
| MIX-003 | P1 | All markets valid | `candidate_count=fetched_count` | `TestCandidateSelection::test_multiple_valid_markets_all_become_candidates` |
| MIX-004 | P0 | Near-expiry valid + structurally-invalid duration markets | Near-expiry valid survives | `TestDurationSemantics::test_mixed_payload_near_expiry_valid_market_survives_with_invalid_durations` |
| MIX-005 | P1 | `fetched_count = candidate_count + rejected_count` invariant | Always holds | `TestRejectionBreakdown::test_fetched_equals_candidate_plus_rejected` |

---

### 3.7 Sync Propagation Scenarios

| ID | Pri | Scenario | Expected Result | Automated Test |
|----|-----|----------|-----------------|----------------|
| SYNC-001 | P0 | Valid candidates written to registry as UP+DOWN pairs | Registry contains exactly `candidate_count × 2` entries | `TestMarketSyncService::test_full_happy_path` · `TestSyncRespectsDiscovery::test_sync_writes_only_discovery_candidates` |
| SYNC-002 | P0 | Invalid (rejected) markets must not appear in registry | Registry free of rejected market IDs | `TestSyncDiscoveryIntegration::test_inactive_market_not_written` · `TestSyncRespectsDiscovery::test_sync_writes_only_discovery_candidates` |
| SYNC-003 | P0 | All invalid payload → registry stays empty | `written=0`, `len(registry)=0` | `TestSyncRespectsDiscovery::test_sync_all_invalid_payload_writes_nothing` |
| SYNC-004 | P1 | Duplicate run → `skipped_duplicate` counted, no double-write | `written=0`, `skipped_duplicate=N` on second run | `TestMarketSyncService::test_duplicate_run_counts_skipped_duplicate` |
| SYNC-005 | P1 | Mapping failure (invalid market_id) → `skipped_mapping` counted | Other valid markets still written | `TestMarketSyncService::test_mapping_failure_is_counted_and_skipped` |
| SYNC-006 | P1 | Client error → registry untouched | Exception propagates; `len(registry)=0` | `TestMarketSyncService::test_client_error_propagates` |
| SYNC-007 | P0 | Near-expiry valid market written to registry via full sync | `{id}-up` and `{id}-down` in registry | `TestDurationSemantics::test_sync_writes_near_expiry_valid_market` |
| SYNC-008 | P1 | `DiscoveryService` can be injected (testability / override) | Custom discovery service evaluate() is called | `TestSyncDiscoveryIntegration::test_discovery_service_is_injected_and_used` |

---

### 3.8 API Response Scenarios

| ID | Pri | Scenario | Expected Result | Automated Test |
|----|-----|----------|-----------------|----------------|
| API-001 | P1 | `POST /discover` returns 200 | `status_code=200` | `test_discover_returns_200` |
| API-002 | P1 | `POST /discover` response shape | Has `fetched_count`, `candidate_count`, `rejected_count`, `rejection_breakdown` keys | `test_discover_response_shape` |
| API-003 | P0 | `POST /discover` all valid → `candidate_count=fetched_count` | Counts match | `test_discover_all_valid_become_candidates` · `test_discover_endpoint_all_valid_payload` |
| API-004 | P0 | `POST /discover` mixed payload → only valid candidates counted | `candidate_count < fetched_count` | `test_discover_no_candidates_all_rejected` · `test_discover_endpoint_mixed_payload_returns_only_candidates` |
| API-005 | P0 | `POST /discover` does NOT write to registry | `len(registry)=0` after call | `test_discover_does_not_write_to_registry` |
| API-006 | P1 | `POST /discover` timeout → 504 | `status_code=504` | `test_discover_timeout_returns_504` |
| API-007 | P1 | `POST /discover` upstream HTTP error → 502 | `status_code=502` | `test_discover_upstream_http_error_returns_502` |
| API-008 | P1 | `rejection_breakdown` contains all 5 reason keys | Keys: `inactive`, `no_order_book`, `empty_tokens`, `missing_dates`, `duration_out_of_range` | `test_discover_breakdown_all_keys_present` |
| API-009 | P1 | `POST /sync` response shape | Has `fetched_count`, `mapped_count`, `written_count`, etc. | `test_sync_success_response_shape` |
| API-010 | P1 | `POST /sync` timeout → 504 | `status_code=504` | `test_sync_timeout_returns_504` |
| API-011 | P1 | `POST /sync` HTTP error → 502 | `status_code=502` | `test_sync_upstream_http_error_returns_502` |

---

### 3.9 Edge Case Scenarios

| ID | Pri | Scenario | Expected Result | Automated Test |
|----|-----|----------|-----------------|----------------|
| EDGE-001 | P2 | Empty market list input to `DiscoveryService.evaluate([])` | `fetched_count=0`, all breakdown keys present with 0 | `TestCandidateSelection::test_empty_input_returns_zero_result` |
| EDGE-002 | P2 | All 5 breakdown keys always present (even when count=0) | Never `KeyError` | `TestRejectionBreakdown::test_all_reason_keys_present_in_empty_result` |
| EDGE-003 | P2 | Multiple markets with same rejection reason | Breakdown count accumulates correctly | `TestRejectionBreakdown::test_multiple_same_reason_accumulates` |
| EDGE-004 | P2 | `candidate_ids` preserved in input order | Order maintained | `TestCandidateSelection::test_candidate_ids_preserved_in_order` |
| EDGE-005 | P2 | Symbol extraction — no coin match | Fallback to slug then market_id; still a candidate | `TestSymbolFallbackNotRejection::test_market_with_no_extractable_symbol_and_slug_is_still_a_candidate` |
| EDGE-006 | P2 | `event_id` absent → fallback to `market_id` in mapper | Domain Market gets market_id as event_id | `TestMarketMapper::test_falls_back_to_market_id_when_event_id_none` |
| EDGE-007 | P2 | `PolymarketClient.ping()` failure modes | Returns False (never raises) | `TestPing::test_returns_false_on_timeout` · `test_returns_false_on_http_error` |

---

### 3.11 Sync / Registry Behavior Scenarios (v0.5.6)

These scenarios lock the contracts governing how discovery candidates flow into
the `InMemoryMarketRegistry` and what the registry looks like after sync.

**Registry key contract:** `{market_id}-up` and `{market_id}-down`
**Write semantic:** Add-only. `DuplicateMarketError` on re-add → `skipped_duplicate` incremented.
**Update semantic:** None. Re-syncing the same market with changed fields preserves the original entry.
**Stale market handling:** No automatic removal or deactivation — registry is append-only.

| ID | Pri | Introduced | Scenario | Expected Result | Automated Test |
|----|-----|------------|----------|-----------------|----------------|
| SRB-001 | P0 | v0.5.6 | Valid 5m market produces UP + DOWN registry entries | 2 entries; keys `{id}-up` / `{id}-down`; `written=2` | `TestSyncRegistryContractC1::test_sync_adds_new_valid_candidate_to_registry` · `test_registry_key_format_is_market_id_hyphen_side` |
| SRB-002 | P0 | v0.5.6 | Written market fields match source payload | `side`, `timeframe=M5`, `status=ACTIVE`, `source_timestamp`, `end_date`, `event_id` all correct | `TestSyncRegistryContractC1::test_registry_market_fields_are_populated_correctly` |
| SRB-003 | P0 | v0.5.6 | Same valid market synced twice → no duplicate entry | Registry count unchanged; second run `written=0`, `skipped_duplicate=2` | `TestSyncRegistryContractC2::test_sync_repeated_same_market_does_not_create_duplicate` |
| SRB-004 | P1 | v0.5.6 | `SyncResult.skipped_duplicate` accurately counts all skipped re-adds | 2 candidates × 2 sides = 4 skipped on full re-sync | `TestSyncRegistryContractC2::test_sync_result_counts_skipped_duplicates_correctly` |
| SRB-005 | P0 | v0.5.6 | Re-sync of market with changed content keeps original registry entry (first-write-wins) | Original symbol / fields unchanged; second run `written=0`, `skipped_duplicate=2` | `TestSyncRegistryContractC3::test_sync_second_pass_same_market_preserves_original_fields_no_update` |
| SRB-006 | P0 | v0.5.6 | Each of the 5 rejection reasons independently prevents registry write | `written=0` for INACTIVE/CLOSED/NO_ORDER_BOOK/EMPTY_TOKENS/MISSING_DATES/DURATION_OUT_OF_RANGE | `TestSyncRegistryContractC4::test_sync_does_not_add_inactive_active_false` · `test_sync_does_not_add_inactive_closed_true` · `test_sync_does_not_add_no_order_book` · `test_sync_does_not_add_empty_tokens` · `test_sync_does_not_add_missing_dates` · `test_sync_does_not_add_duration_out_of_range` |
| SRB-007 | P0 | v0.5.6 | Mixed payload: new + pre-existing + invalid + duplicate → deterministic final state | Only new candidates written; existing skipped; invalid excluded; final registry exactly correct | `TestSyncRegistryContractC5::test_sync_mixed_payload_results_in_expected_registry_state` |
| SRB-008 | P1 | v0.5.6 | Multiple valid candidates all written in same sync | `N candidates × 2 = 2N` registry entries | `TestSyncRegistryContractC5::test_sync_multiple_valid_candidates_all_written` |
| SRB-009 | P0 | v0.5.6 | (Scenario G) Previously-valid market becomes inactive on next sync → stays in registry | Original UP + DOWN entries unchanged; no automatic removal | `TestPreviouslyValidMarketBecomingInvalid::test_market_stays_in_registry_after_becoming_inactive` · `test_market_stays_in_registry_after_losing_order_book` |
| SRB-010 | P0 | v0.5.6 | `POST /sync` response summary is consistent with actual registry final state | `fetched_count`, `written_count` match registry `len()` and entry IDs | `test_sync_endpoint_response_summary_matches_registry_final_state` |

---

### 3.12 Rejection Observability Scenarios (v0.5.9)

These scenarios lock the contract that `SyncResult` and `SyncResponse` expose
rejection counts and per-reason breakdowns from `DiscoveryService`.

**Observability contract:** `rejected_count` + `rejection_breakdown` are present in both
`SyncResult` (service layer) and `SyncResponse` (HTTP layer). All 5 breakdown keys are
always present. Observability is read-only — it does not affect which markets are written.

| ID | Pri | Introduced | Scenario | Expected Result | Automated Test |
|----|-----|------------|----------|-----------------|----------------|
| ROB-001 | P0 | v0.5.9 | Sync with 3 rejected markets → `rejected_count=3` | `rejected_count` equals number of discovery-rejected markets | `TestRejectedCountSurfacesNonCandidates::test_sync_summary_includes_rejected_count_for_non_candidates` |
| ROB-002 | P1 | v0.5.9 | All valid → `rejected_count=0` | Zero rejections when all markets pass | `TestRejectedCountSurfacesNonCandidates::test_all_valid_means_zero_rejected` |
| ROB-003 | P1 | v0.5.9 | All rejected → `fetched=0`, `rejected_count=total` | Partition is complete and accurate | `TestRejectedCountSurfacesNonCandidates::test_all_rejected_means_zero_fetched` |
| ROB-004 | P0 | v0.5.9 | `fetched + rejected_count = total input` invariant | Partition always sums to full input | `TestRejectedCountDistinctFromFetched::test_sync_summary_rejected_count_is_distinct_from_fetched_candidates` |
| ROB-005 | P1 | v0.5.9 | Empty input: both counters zero, invariant holds | `fetched=0`, `rejected_count=0`, sum=0 | `TestRejectedCountDistinctFromFetched::test_partition_holds_for_empty_input` |
| ROB-006 | P1 | v0.5.9 | Single valid input: `fetched=1`, `rejected_count=0` | Partition correct for minimal case | `TestRejectedCountDistinctFromFetched::test_partition_holds_for_single_valid` |
| ROB-007 | P1 | v0.5.9 | Single invalid input: `fetched=0`, `rejected_count=1` | Partition correct for minimal rejected case | `TestRejectedCountDistinctFromFetched::test_partition_holds_for_single_invalid` |
| ROB-008 | P0 | v0.5.9 | One market per rejection reason + one valid → breakdown has 1 per reason | Per-reason breakdown deterministic | `TestRejectionBreakdownDeterministic::test_sync_summary_rejection_breakdown_is_deterministic` |
| ROB-009 | P0 | v0.5.9 | All 5 breakdown keys present even when no rejections | Never `KeyError`; all values 0 | `TestRejectionBreakdownDeterministic::test_all_keys_present_even_when_no_rejections` |
| ROB-010 | P1 | v0.5.9 | All 5 breakdown keys present for empty input | Consistent shape regardless of input | `TestRejectionBreakdownDeterministic::test_all_keys_present_for_empty_input` |
| ROB-011 | P1 | v0.5.9 | Two markets same rejection reason → breakdown count accumulates | `inactive=2` not `inactive=1` | `TestRejectionBreakdownDeterministic::test_multiple_rejections_same_reason_accumulate` |
| ROB-012 | P0 | v0.5.9 | `POST /sync` API response includes `rejected_count` + `rejection_breakdown` | HTTP layer passes through both fields correctly | `test_sync_api_response_matches_service_rejection_observability` |
| ROB-013 | P0 | v0.5.9 | Observability does not change which markets are written to registry | Registry contains only candidates; rejected markets absent | `TestObservabilityDoesNotAffectBehavior::test_rejection_observability_does_not_change_candidate_or_registry_behavior` |
| ROB-014 | P0 | v0.5.9 | All 5 rejection reasons: none of rejected markets enter registry | `{id}-up`/`{id}-down` present only for valid candidate | `TestObservabilityDoesNotAffectBehavior::test_rejected_markets_not_in_registry_after_sync` |

---

### 3.14 Mapping Failure Semantics Scenarios (v0.5.14)

These scenarios lock the contract that mapping failures (Gate 2) are distinct from
discovery rejections (Gate 1) and registry duplicates (Gate 3), and that the
three-gate pipeline invariant holds deterministically.

**Three pipeline gates:**
- Gate 1 (Discovery): `rejected_count` — markets that never become candidates
- Gate 2 (Mapping): `skipped_mapping` — candidates that fail domain object creation
- Gate 3 (Registry): `skipped_duplicate` — mapped Markets already in registry

**Pipeline invariant:** `(fetched − skipped_mapping) × MARKETS_PER_CANDIDATE = mapped`
**Partition invariant:** `mapped = written + skipped_duplicate`

| ID | Pri | Introduced | Scenario | Expected Result | Automated Test |
|----|-----|------------|----------|-----------------|----------------|
| MFS-001 | P0 | v0.5.14 | Discovery-passing candidate with invalid domain fields (blank market_id, no event_id/slug) → mapping failure | `skipped_mapping=1`, `mapped=0`, `written=0` | `TestMappingFailureIncrementsSkippedMapping::test_successful_candidate_with_mapper_failure_increments_skipped_mapping` |
| MFS-002 | P0 | v0.5.14 | Mapping failure must not write anything to registry | `len(registry)=0` after failed mapping | `TestMappingFailureIncrementsSkippedMapping::test_skipped_mapping_does_not_add_to_registry` |
| MFS-003 | P1 | v0.5.14 | Multiple mapping failures accumulate | `skipped_mapping=N` for N bad candidates | `TestMappingFailureIncrementsSkippedMapping::test_multiple_mapping_failures_accumulate` |
| MFS-004 | P0 | v0.5.14 | Discovery-rejected markets do not increment skipped_mapping | Gate 1 and Gate 2 counters are mutually exclusive | `TestSkippedMappingDistinctness::test_skipped_mapping_is_distinct_from_rejected_count_and_duplicate_count` |
| MFS-005 | P0 | v0.5.14 | One candidate per gate in same payload → counters are mutually exclusive | `skipped_duplicate=2`, `skipped_mapping=1`, `rejected_count=0` | `TestSkippedMappingDistinctness::test_gate1_gate2_gate3_are_mutually_exclusive_counters` |
| MFS-006 | P1 | v0.5.14 | `skipped_mapping` counts failed candidates, not zero-produced Market objects | 3 failed candidates → `skipped_mapping=3`, `mapped=0` (not 6) | `TestSkippedMappingDistinctness::test_skipped_mapping_counter_counts_candidates_not_market_objects` |
| MFS-007 | P0 | v0.5.14 | `POST /sync` API response exposes `skipped_mapping_count` matching service layer | `skipped_mapping_count=0` when no failures; matches `SyncResult.skipped_mapping` | `test_sync_api_response_matches_service_mapping_failure_semantics` |
| MFS-008 | P1 | v0.5.14 | `skipped_mapping_count` field is always present in SyncResponse JSON | Never missing from response shape | `test_sync_api_response_skipped_mapping_count_field_is_present` |
| MFS-009 | P0 | v0.5.14 | Mixed payload: 1 success + 1 duplicate + 1 mapping failure → deterministic summary | `fetched=3`, `skipped_mapping=1`, `mapped=4`, `written=2`, `skipped_duplicate=2` | `TestMixedPayloadDeterminism::test_mixed_payload_with_success_duplicate_and_mapping_failure_produces_deterministic_summary` |
| MFS-010 | P1 | v0.5.14 | All candidates fail mapping → pipeline invariant holds with all-zero output | `mapped=0`, `written=0`, `skipped_duplicate=0`; invariant: `(N−N)×2=0` | `TestMixedPayloadDeterminism::test_pipeline_invariant_holds_for_all_mapping_failures` |
| MFS-011 | P1 | v0.5.14 | All candidates succeed → `skipped_mapping=0`, `mapped = fetched × 2` | Pipeline invariant: `(N−0)×2=mapped` | `TestMixedPayloadDeterminism::test_pipeline_invariant_holds_for_all_successful` |
| MFS-012 | P0 | v0.5.14 | Pipeline and partition invariants verified at both service layer and HTTP layer | Docs, runtime, and API agree on all mapping failure semantics | `test_docs_runtime_and_summary_contract_align_for_mapping_failure` |

---

### 3.15 Pipeline Edge-State Contract Scenarios (v0.5.15)

These scenarios lock the deterministic, cross-layer-consistent behaviour of the five
canonical edge states across the full fetch → discovery → map → registry pipeline.

**Assessment**: Status A — edge state behaviour was already consistent end-to-end.
No production changes were required; these tests codify and cross-layer-lock contracts
that previously existed only as scattered unit/integration checks.

**Cross-layer invariants (hold for every edge state):**
- `discover.candidate_count == sync.fetched_count`
- `discover.fetched_count == sync.fetched_count + sync.rejected_count`
- `mapped = written + skipped_duplicate`
- `(fetched − skipped_mapping) × MARKETS_PER_CANDIDATE = mapped`

| ID | Pri | Introduced | Edge State | Scenario | Expected Result | Automated Test |
|----|-----|------------|------------|----------|-----------------|----------------|
| PES-001 | P0 | v0.5.15 | EMPTY | Empty input at service layer | All counters zero; all 5 taxonomy keys present; registry unchanged | `TestEmptyInputEdgeState::test_empty_input_sync_service_produces_all_zero_edge_state` |
| PES-002 | P0 | v0.5.15 | EMPTY | Empty input at /discover HTTP layer | fetched=0, candidate=0, rejected=0, breakdown all-zero | `TestEmptyInputEdgeState::test_empty_input_discover_http_produces_all_zero_edge_state` |
| PES-003 | P0 | v0.5.15 | EMPTY | Empty input cross-layer invariants | discover/sync aligned; partition trivially zero; taxonomy keys complete | `TestEmptyInputEdgeState::test_empty_input_cross_layer_invariants_hold` |
| PES-004 | P0 | v0.5.15 | ALL-REJECTED | All markets rejected; service layer | rejected_count=N, fetched=0, written=0, registry empty | `TestAllRejectedEdgeState::test_all_rejected_sync_service_produces_rejection_only_edge_state` |
| PES-005 | P1 | v0.5.15 | ALL-REJECTED | Registry stays empty after all-rejected sync | len(registry)==0 | `TestAllRejectedEdgeState::test_all_rejected_registry_stays_empty` |
| PES-006 | P0 | v0.5.15 | ALL-REJECTED | Cross-layer partition invariant | discover.fetched == sync.fetched + sync.rejected; candidate_count==0 | `TestAllRejectedEdgeState::test_all_rejected_cross_layer_partition_invariant` |
| PES-007 | P0 | v0.5.15 | ALL-MAP-FAILED | All map-fail candidates; service layer | skipped_mapping=N, mapped=0, written=0, rejected=0 | `TestAllMappingFailedEdgeState::test_all_mapping_failed_sync_service_produces_mapping_failure_only_edge_state` |
| PES-008 | P1 | v0.5.15 | ALL-MAP-FAILED | Registry unchanged after all-mapping-failed | len(registry)==0 | `TestAllMappingFailedEdgeState::test_all_mapping_failed_registry_unchanged` |
| PES-009 | P0 | v0.5.15 | ALL-MAP-FAILED | Cross-layer candidate alignment + pipeline invariant | discover.candidate_count == sync.fetched_count; (fetched−skipped_mapping)×2=mapped=0 | `TestAllMappingFailedEdgeState::test_all_mapping_failed_cross_layer_candidate_alignment` |
| PES-010 | P0 | v0.5.15 | ALL-DUPLICATE | All-duplicate state; service layer | written=0, skipped_duplicate=2N, mapped=2N, fetched=N | `TestAllDuplicateEdgeState::test_all_duplicate_sync_service_produces_duplicate_only_edge_state` |
| PES-011 | P1 | v0.5.15 | ALL-DUPLICATE | Registry count unchanged after all-duplicate sync | count unchanged | `TestAllDuplicateEdgeState::test_all_duplicate_registry_count_unchanged` |
| PES-012 | P0 | v0.5.15 | ALL-DUPLICATE | Partition invariant for all-duplicate | mapped == written + skipped_duplicate; written==0 | `TestAllDuplicateEdgeState::test_all_duplicate_partition_invariant` |
| PES-013 | P0 | v0.5.15 | ALL-NEW-VALID | Clean happy-path edge state; service layer | written=2N, all skip counters zero, registry=2N | `TestAllNewValidEdgeState::test_all_new_valid_sync_service_produces_clean_happy_path_edge_state` |
| PES-014 | P0 | v0.5.15 | ALL-NEW-VALID | Cross-layer candidate alignment + all written | candidate_count==fetched_count; written==2N; no rejections | `TestAllNewValidEdgeState::test_all_new_valid_cross_layer_candidate_alignment` |
| PES-015 | P1 | v0.5.15 | ALL-NEW-VALID | Rejection breakdown all-zero at both endpoints | All 5 taxonomy keys present; all zero | `TestAllNewValidEdgeState::test_all_new_valid_rejection_breakdown_all_zero` |
| PES-016 | P0 | v0.5.15 | ALL STATES | Cross-layer invariants hold for empty/all-rejected/all-new-valid simultaneously | Invariants 1–3 + taxonomy completeness verified per edge state | `test_discover_and_sync_edge_states_remain_cross_layer_consistent` |

---

### 3.10 Retired / Deprecated Scenarios

These scenarios **must not** be used as regression criteria. They described
behaviour that was intentionally removed.

| ID | Retired In | Scenario | Why Retired |
|----|-----------|----------|-------------|
| RET-001 | v0.5.4 | `fetch_candidates()` pre-filters markets before normalisation | Method removed — DiscoveryService is the sole candidate filter |
| RET-002 | v0.5.4 | `_is_5m_candidate()` raw-dict gate inside fetcher | Method removed — was duplicate logic; DiscoveryService covers all rules |
| RET-003 | v0.5.4 | `TestFetchCandidates` test class (10 tests) | Tests for removed method; deleted |
| RET-004 | v0.5.4 | `TestDurationFilter` test class (13 tests) | Tests for removed method; deleted |

---

## 4. Automation Mapping

### Current coverage summary

| Category | Total Scenarios | Fully Automated | Partially Automated | Manual Only |
|----------|-----------------|-----------------|---------------------|-------------|
| Fetch | 11 | 11 | 0 | 0 |
| Discovery Acceptance | 6 | 6 | 0 | 0 |
| Discovery Rejection | 11 | 11 | 0 | 0 |
| Rule Priority | 6 | 6 | 0 | 0 |
| Duration Semantics | 8 | 8 | 0 | 0 |
| Mixed Payload | 5 | 5 | 0 | 0 |
| Sync Propagation | 8 | 8 | 0 | 0 |
| API Response | 11 | 11 | 0 | 0 |
| Edge Cases | 7 | 7 | 0 | 0 |
| Sync Registry Behavior | 10 | 10 | 0 | 0 |
| Registry Lifecycle | 11 | 11 | 0 | 0 |
| Sync Summary Semantics | 12 | 12 | 0 | 0 |
| Rejection Observability | 14 | 14 | 0 | 0 |
| Rejection Taxonomy Contract | 15 | 15 | 0 | 0 |
| Discover/Sync Contract Alignment | 10 | 10 | 0 | 0 |
| Cross-Layer Field Semantics | 9 | 9 | 0 | 0 |
| Mapper Multiplicity Contract | 14 | 14 | 0 | 0 |
| Mapping Failure Semantics | 12 | 12 | 0 | 0 |
| Pipeline Edge-State Contract | 16 | 16 | 0 | 0 |
| Fetcher Input Normalization Contract | 34 | 34 | 0 | 0 |
| **Total** | **230** | **230** | **0** | **0** |

### Known automation gaps

| Gap | Risk | Recommended Action |
|-----|------|-------------------|
| Real Gamma API integration (live HTTP) | API shape changes undetected | E2E/contract test suite (future milestone) |
| `POST /sync` endpoint at integration level (real fetcher+discovery, mock client) | Sync endpoint response mismatch | ✅ Covered in v0.5.6 — `test_sync_endpoint_response_summary_matches_registry_final_state` |
| Concurrent registry writes | Race condition on parallel syncs | Applicable only when scheduler is added |
| `end_date` field on `POST /sync` response | Payload drift | Currently no sync response includes per-market details |

---

## 5. Regression Execution Plan

### Smoke regression (run on every PR merge)

**Criteria:** P0 scenarios only — fundamental contracts.

```bash
python -m pytest backend/tests/ -m "not slow" -k "
  test_valid_market_is_a_candidate or
  test_no_candidate_filtering_applied or
  test_fetch_returns_all_markets_including_invalid_ones or
  test_duration_filter_uses_total_market_duration_not_remaining_time or
  test_valid_5m_market_near_expiry_is_not_rejected_by_discovery or
  test_inactive_market_is_rejected or
  test_enable_order_book_false_is_rejected or
  test_empty_tokens_list_is_rejected or
  test_missing_source_timestamp_is_rejected or
  test_sync_writes_only_discovery_candidates or
  test_sync_all_invalid_payload_writes_nothing or
  test_discover_does_not_write_to_registry or
  test_discover_endpoint_mixed_payload_returns_only_candidates or
  TestDiscoveryIsTheSoleSelector or
  TestSyncRespectsDiscovery or
  TestDurationSemantics or
  TestSyncRegistryContractC1 or
  TestSyncRegistryContractC4 or
  TestSyncRegistryContractC5 or
  TestPreviouslyValidMarketBecomingInvalid or
  test_sync_endpoint_response_summary_matches_registry_final_state
" -v
```

Covers: FETCH-001/002, DISC-ACC-001/005, DISC-REJ-001/004/005/006/007/008/009/010/011, DUR-001/002/007, SYNC-001/002/003/007, API-003/004/005, SRB-001/002/006/007/009/010

### Standard regression (run before every release)

**Criteria:** P0 + P1 scenarios — all production-relevant contracts.

```bash
python -m pytest backend/tests/ -v
```

All 381 tests. Current runtime: ~1.0 seconds.

### Full regression (run after major architecture changes)

**Criteria:** All active scenarios + manual review of retired scenarios.

```bash
# Run all automated tests
python -m pytest backend/tests/ -v

# Manual checklist:
# [ ] Verify fetch_candidates() does not exist in market_fetcher.py
# [ ] Verify _is_5m_candidate() does not exist in market_fetcher.py
# [ ] Verify DiscoveryService has all 5 rejection rules
# [ ] Verify no production caller bypasses DiscoveryService for candidate selection
# [ ] Verify duration calculation uses end_date - source_timestamp (grep for "now()")
```

---

## 6. How to Update This Document

When a new version changes behaviour in the covered layers:

1. Add a row to **Section 2** (Version Changelog)
2. Add new scenarios to the relevant **Section 3.x** table
3. If behaviour is removed, add a row to **Section 3.10** (Retired)
4. Update the **automation mapping** counts in Section 4
5. Update the "Last updated" line at the top

**Do not delete retired scenarios** — they record intentional decisions.
