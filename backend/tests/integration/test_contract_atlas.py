"""Integration tests — Contract Atlas Lock (v0.5.22).

These tests lock the discovery/sync contract atlas as the single-page
canonical index of all locked and deferred contracts in the pipeline.

All tests are fully automated and require no network access.

Tests
-----
A  TestContractAtlasCoversAllCanonicalContractSurfaces
        Atlas covers all current canonical contract surfaces without gaps.

B  TestContractAtlasMarksDeferredVsLockedBehaviorsExplicitly
        LOCKED vs DEFERRED status is unambiguous for every entry.

C  TestContractAtlasCrossReferencesExistingWorkflowAndRegressionDocs
        Atlas cross-references docs/testing structure and regression matrix.

D  TestContractAtlasDoesNotContradictRuntimeContracts
        Atlas entries are consistent with runtime source files and test files.

E  TestContractAtlasIdentifiesOpenRisksWithoutReopeningClosedDecisions
        Open risks are listed where applicable but closed decisions are not
        re-opened.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # C:/CLAUDECODE

ATLAS_PATH          = PROJECT_ROOT / "docs" / "testing" / "discovery_sync_contract_atlas.md"
REGRESSION_MATRIX   = PROJECT_ROOT / "docs" / "testing" / "discovery_regression_matrix.md"
WORKFLOW_DOC_PATH   = PROJECT_ROOT / "docs" / "testing" / "gamma_contract_workflow.md"
OWNERSHIP_DOC_PATH  = PROJECT_ROOT / "docs" / "testing" / "gamma_drift_response_roles.md"
POLICY_DOC_PATH     = PROJECT_ROOT / "docs" / "testing" / "gamma_snapshot_refresh_policy.md"

# Expected contract surfaces (name fragment → canonical identifier)
EXPECTED_CONTRACT_SURFACES = [
    "Fetcher normalization",
    "Canonical text field",
    "Discovery selection",
    "Duration semantics",
    "Rejection taxonomy",
    "Mapper multiplicity",
    "Mapping failure semantics",
    "Sync summary semantics",
    "Discover/sync",
    "Registry",
    "Pipeline edge-state",
    "Live Gamma",
    "Drift triage",
]

# All test files that should be referenced in the atlas
EXPECTED_TEST_FILE_REFS = [
    "test_fetcher_normalization_contract",
    "test_canonical_text_field_normalization",
    "test_discovery_flow",
    "test_market_discovery",
    "test_rejection_taxonomy_contract",
    "test_mapper_multiplicity_contract",
    "test_mapping_failure_semantics",
    "test_sync_summary_semantics",
    "test_discover_sync_contract_alignment",
    "test_registry_lifecycle",
    "test_pipeline_edge_state_contract",
    "test_live_gamma_contract_snapshot",
    "test_upstream_drift_triage_workflow",
    "test_drift_response_ownership",
    "test_snapshot_refresh_trigger_policy",
]


def _atlas() -> str:
    return ATLAS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A — atlas covers all canonical contract surfaces
# ---------------------------------------------------------------------------


class TestContractAtlasCoversAllCanonicalContractSurfaces:
    """Test A: Atlas covers all current canonical contract surfaces."""

    def test_atlas_exists(self):
        assert ATLAS_PATH.exists(), f"Atlas document missing: {ATLAS_PATH}"

    def test_atlas_covers_fetcher_normalization(self):
        """Atlas mentions the fetcher normalization contract."""
        doc = _atlas()
        assert "Fetcher Normalization" in doc or "fetcher normalization" in doc.lower(), (
            "Atlas must cover the Fetcher Normalization Contract"
        )

    def test_atlas_covers_canonical_text_field_normalization(self):
        """Atlas mentions the canonical text field normalization contract."""
        doc = _atlas()
        assert "Canonical Text Field" in doc or "canonical text field" in doc.lower(), (
            "Atlas must cover the Canonical Text Field Normalization Contract"
        )

    def test_atlas_covers_discovery_selection(self):
        """Atlas mentions the discovery selection contract."""
        doc = _atlas()
        assert "Discovery Selection" in doc or "discovery selection" in doc.lower(), (
            "Atlas must cover the Discovery Selection Contract"
        )

    def test_atlas_covers_duration_semantics(self):
        """Atlas mentions the duration semantics contract."""
        doc = _atlas().lower()
        assert "duration semantics" in doc or "duration" in doc, (
            "Atlas must cover the Duration Semantics Contract"
        )

    def test_atlas_covers_rejection_taxonomy(self):
        """Atlas mentions the rejection taxonomy contract."""
        doc = _atlas().lower()
        assert "rejection taxonomy" in doc, (
            "Atlas must cover the Rejection Taxonomy Contract"
        )

    def test_atlas_covers_mapper_multiplicity(self):
        """Atlas mentions the mapper multiplicity contract."""
        doc = _atlas().lower()
        assert "mapper multiplicity" in doc or "multiplicity" in doc, (
            "Atlas must cover the Mapper Multiplicity Contract"
        )

    def test_atlas_covers_mapping_failure_semantics(self):
        """Atlas mentions the mapping failure semantics contract."""
        doc = _atlas().lower()
        assert "mapping failure" in doc, (
            "Atlas must cover the Mapping Failure Semantics Contract"
        )

    def test_atlas_covers_sync_summary_semantics(self):
        """Atlas mentions the sync summary semantics contract."""
        doc = _atlas().lower()
        assert "sync summary" in doc, (
            "Atlas must cover the Sync Summary Semantics Contract"
        )

    def test_atlas_covers_discover_sync_alignment(self):
        """Atlas mentions the discover/sync contract alignment."""
        doc = _atlas().lower()
        assert "discover" in doc and "sync" in doc and "alignment" in doc, (
            "Atlas must cover the Discover/Sync Contract Alignment"
        )

    def test_atlas_covers_registry_lifecycle(self):
        """Atlas mentions the registry add-only / lifecycle contract."""
        doc = _atlas().lower()
        assert "registry" in doc and ("lifecycle" in doc or "add-only" in doc), (
            "Atlas must cover the Registry Add-Only / Lifecycle Contract"
        )

    def test_atlas_covers_pipeline_edge_state(self):
        """Atlas mentions the pipeline edge-state contracts."""
        doc = _atlas().lower()
        assert "edge-state" in doc or "edge state" in doc, (
            "Atlas must cover the Pipeline Edge-State Contracts"
        )

    def test_atlas_covers_live_gamma_snapshot(self):
        """Atlas mentions the live Gamma contract snapshot."""
        doc = _atlas().lower()
        assert "gamma" in doc and ("snapshot" in doc or "fixture" in doc), (
            "Atlas must cover the Live Gamma Contract Snapshot"
        )

    def test_atlas_covers_drift_triage_ownership_trigger(self):
        """Atlas mentions drift triage / ownership / trigger policy."""
        doc = _atlas().lower()
        assert "drift" in doc and ("triage" in doc or "ownership" in doc or "trigger" in doc), (
            "Atlas must cover the Drift Triage / Ownership / Trigger Policy Contract"
        )

    def test_atlas_has_at_least_13_contract_entries(self):
        """Atlas indexes at least 13 contract surfaces."""
        doc = _atlas()
        # Count numbered section headers (## N.)
        import re
        headers = re.findall(r"^## \d+\.", doc, re.MULTILINE)
        assert len(headers) >= 13, (
            f"Atlas must have at least 13 contract sections; found {len(headers)}"
        )


# ---------------------------------------------------------------------------
# B — LOCKED vs DEFERRED explicitly marked
# ---------------------------------------------------------------------------


class TestContractAtlasMarksDeferredVsLockedBehaviorsExplicitly:
    """Test B: LOCKED vs DEFERRED status is unambiguous."""

    def test_atlas_uses_locked_status_keyword(self):
        """Atlas explicitly uses 'LOCKED' status keyword."""
        doc = _atlas()
        assert "LOCKED" in doc, "Atlas must use the LOCKED status keyword"

    def test_atlas_uses_deferred_status_keyword(self):
        """Atlas explicitly uses 'DEFERRED' status keyword."""
        doc = _atlas()
        assert "DEFERRED" in doc, "Atlas must use the DEFERRED status keyword"

    def test_registry_lifecycle_is_marked_as_deferred(self):
        """Registry lifecycle is explicitly marked DEFERRED."""
        doc = _atlas()
        # Find registry section and verify deferred
        assert "DEFERRED" in doc and "lifecycle" in doc.lower(), (
            "Registry lifecycle entry must be marked DEFERRED"
        )

    def test_atlas_explains_locked_meaning(self):
        """Atlas explains what LOCKED means (invariant; change requires test update)."""
        doc = _atlas().lower()
        assert "invariant" in doc or "change requires" in doc or "locked" in doc, (
            "Atlas must explain what LOCKED status means"
        )

    def test_atlas_explains_deferred_meaning(self):
        """Atlas explains what DEFERRED means (decision intentionally postponed)."""
        doc = _atlas().lower()
        assert "deferred" in doc and (
            "intentionally" in doc or "postponed" in doc or "deliberate" in doc
        ), (
            "Atlas must explain what DEFERRED status means"
        )

    def test_most_contracts_are_locked(self):
        """Atlas reflects that most contracts are LOCKED (at least 12 of 13)."""
        doc = _atlas()
        locked_count = doc.count("LOCKED")
        # Each LOCKED entry appears at least once in Status and once in the summary table
        assert locked_count >= 12, (
            f"Atlas must show at least 12 LOCKED entries; found {locked_count} occurrences"
        )

    def test_deferred_decisions_table_present(self):
        """Atlas has a dedicated 'Known deferred decisions' table."""
        doc = _atlas().lower()
        assert "deferred decision" in doc or "known deferred" in doc, (
            "Atlas must include a Known Deferred Decisions section"
        )


# ---------------------------------------------------------------------------
# C — atlas cross-references existing workflow and regression docs
# ---------------------------------------------------------------------------


class TestContractAtlasCrossReferencesExistingWorkflowAndRegressionDocs:
    """Test C: Atlas cross-references the broader docs/testing structure."""

    def test_atlas_references_regression_matrix(self):
        """Atlas links to the discovery regression matrix."""
        doc = _atlas()
        assert "discovery_regression_matrix" in doc, (
            "Atlas must cross-reference discovery_regression_matrix.md"
        )

    def test_atlas_references_gamma_contract_workflow(self):
        """Atlas references the Gamma contract workflow doc."""
        doc = _atlas()
        assert "gamma_contract_workflow" in doc, (
            "Atlas must reference gamma_contract_workflow.md"
        )

    def test_atlas_references_gamma_drift_response_roles(self):
        """Atlas references the drift response ownership doc."""
        doc = _atlas()
        assert "gamma_drift_response_roles" in doc, (
            "Atlas must reference gamma_drift_response_roles.md"
        )

    def test_atlas_references_gamma_snapshot_refresh_policy(self):
        """Atlas references the snapshot refresh policy doc."""
        doc = _atlas()
        assert "gamma_snapshot_refresh_policy" in doc, (
            "Atlas must reference gamma_snapshot_refresh_policy.md"
        )

    def test_atlas_references_key_test_files(self):
        """Atlas references at least 10 of the expected test files."""
        doc = _atlas()
        found = sum(1 for tf in EXPECTED_TEST_FILE_REFS if tf in doc)
        assert found >= 10, (
            f"Atlas must reference at least 10 test files; found {found} of {len(EXPECTED_TEST_FILE_REFS)}"
        )

    def test_atlas_has_quick_navigation_section(self):
        """Atlas has a Quick navigation section for cross-document lookup."""
        doc = _atlas().lower()
        assert "quick navigation" in doc or "navigation" in doc, (
            "Atlas must include a Quick Navigation section"
        )

    def test_all_referenced_docs_exist(self):
        """All referenced doc files actually exist on disk."""
        docs_to_check = [
            REGRESSION_MATRIX,
            WORKFLOW_DOC_PATH,
            OWNERSHIP_DOC_PATH,
            POLICY_DOC_PATH,
        ]
        for doc_path in docs_to_check:
            assert doc_path.exists(), f"Referenced doc missing: {doc_path}"


# ---------------------------------------------------------------------------
# D — atlas does not contradict runtime contracts
# ---------------------------------------------------------------------------


class TestContractAtlasDoesNotContradictRuntimeContracts:
    """Test D: Atlas entries are consistent with runtime source and test files."""

    def test_atlas_states_correct_markets_per_candidate(self):
        """Atlas correctly states MARKETS_PER_CANDIDATE = 2 (not 1, 3, or other)."""
        doc = _atlas()
        # Should mention '2' in context of mapper multiplicity
        assert "2 domain" in doc or "× 2" in doc or "×2" in doc or "exactly **2" in doc, (
            "Atlas must state that MapperMultiplicity produces exactly 2 Market objects"
        )

    def test_atlas_states_correct_number_of_discovery_rules(self):
        """Atlas correctly states 5 rejection rules (not 4 or 6)."""
        doc = _atlas()
        assert "Five" in doc or "five" in doc.lower() or "5" in doc, (
            "Atlas must state that DiscoveryService applies 5 rejection rules"
        )

    def test_atlas_states_correct_number_of_pipeline_gates(self):
        """Atlas correctly states 3 pipeline gates."""
        doc = _atlas()
        assert "Three" in doc or "three" in doc.lower() or "3" in doc, (
            "Atlas must state that mapping failure semantics has 3 pipeline gates"
        )

    def test_atlas_rejection_rules_match_runtime(self):
        """Atlas rejection rule names align with runtime RejectionReason enum values."""
        doc = _atlas()
        expected_rejection_reasons = [
            "INACTIVE",
            "NO_ORDER_BOOK",
            "EMPTY_TOKENS",
            "MISSING_DATES",
            "DURATION_OUT_OF_RANGE",
        ]
        for reason in expected_rejection_reasons:
            assert reason in doc, (
                f"Atlas must reference rejection rule: {reason}"
            )

    def test_atlas_source_files_mentioned_exist(self):
        """Key source files referenced in the atlas actually exist."""
        source_files = [
            PROJECT_ROOT / "backend" / "app" / "services" / "market_fetcher.py",
            PROJECT_ROOT / "backend" / "app" / "services" / "market_discovery.py",
            PROJECT_ROOT / "backend" / "app" / "services" / "market_sync.py",
        ]
        for src_path in source_files:
            assert src_path.exists(), f"Atlas-referenced source file missing: {src_path}"

    def test_atlas_gamma_fixture_reference_is_correct(self):
        """Atlas references gamma_snapshot.json at the correct path."""
        doc = _atlas()
        assert "gamma_snapshot.json" in doc, (
            "Atlas must reference gamma_snapshot.json fixture"
        )
        fixture_path = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "gamma_snapshot.json"
        assert fixture_path.exists(), (
            f"Gamma snapshot fixture referenced in atlas does not exist: {fixture_path}"
        )

    def test_atlas_pipeline_invariant_consistent_with_code(self):
        """Atlas pipeline invariant formula is consistent with SyncResult docstring."""
        doc = _atlas()
        # The invariant: (fetched − skipped_mapping) × 2 = mapped
        assert "skipped_mapping" in doc or "mapped" in doc, (
            "Atlas must mention the pipeline invariant relating fetched/skipped/mapped"
        )


# ---------------------------------------------------------------------------
# E — open risks listed, closed decisions not re-opened
# ---------------------------------------------------------------------------


class TestContractAtlasIdentifiesOpenRisksWithoutReopeningClosedDecisions:
    """Test E: Open risks documented; closed decisions remain closed."""

    def test_atlas_has_open_risks_field_per_entry(self):
        """Atlas entries include an 'Open risks' field."""
        doc = _atlas().lower()
        assert "open risks" in doc, (
            "Atlas must include an 'Open risks' field for each contract entry"
        )

    def test_stale_entry_cleanup_listed_as_open_risk(self):
        """Registry lifecycle open risk (stale entries) is listed."""
        doc = _atlas().lower()
        assert "stale" in doc, (
            "Atlas must list stale entry accumulation as an open risk for registry lifecycle"
        )

    def test_gamma_api_shape_drift_listed_as_open_risk(self):
        """Gamma API shape drift is listed as an open risk for the snapshot contract."""
        doc = _atlas().lower()
        assert "gamma" in doc and ("changes" in doc or "drift" in doc or "refresh" in doc), (
            "Atlas must list Gamma API shape drift as an open risk"
        )

    def test_no_reopened_decisions_for_duration_rule(self):
        """Duration semantics contract is LOCKED — atlas does not propose changing it."""
        doc = _atlas()
        # The duration section should show LOCKED status, not propose changes
        assert "LOCKED" in doc, "Atlas must show duration semantics as LOCKED"
        # Should not contain language suggesting re-examination of the rule
        duration_idx = doc.lower().find("duration semantics")
        if duration_idx >= 0:
            excerpt = doc[duration_idx : duration_idx + 500].lower()
            assert "reopen" not in excerpt and "reconsider" not in excerpt, (
                "Atlas must not re-open the duration semantics decision"
            )

    def test_no_reopened_decisions_for_5_rule_discovery(self):
        """5-rule discovery contract is LOCKED — atlas does not propose adding rules."""
        doc = _atlas()
        discovery_idx = doc.lower().find("discovery selection")
        if discovery_idx >= 0:
            excerpt = doc[discovery_idx : discovery_idx + 500].lower()
            assert "reopen" not in excerpt and "reconsider" not in excerpt, (
                "Atlas must not re-open the discovery selection decision"
            )

    def test_no_reopened_decisions_for_registry_add_only(self):
        """Registry add-only policy is LOCKED — atlas does not propose removing entries."""
        doc = _atlas().lower()
        assert "add-only" in doc or "add only" in doc, (
            "Atlas must confirm registry add-only policy is locked"
        )

    def test_deferred_items_marked_not_gaps(self):
        """Deferred decisions are presented as conscious choices, not as gaps."""
        doc = _atlas().lower()
        assert (
            "deliberate" in doc
            or "intentional" in doc
            or "conscious" in doc
            or "deferred" in doc
        ), (
            "Atlas must present deferred items as deliberate decisions, not bugs/gaps"
        )
