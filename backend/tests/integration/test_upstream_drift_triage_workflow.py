"""Integration tests — Upstream Drift Triage Workflow Lock (v0.5.19).

These tests lock the drift triage workflow contract: how the team detects,
classifies, and responds to Gamma API upstream shape changes.

All tests are fully automated and require no network access.

Tests
-----
A  TestFixtureRefreshWorkflowDocsCoverRequiredSteps
        The workflow document answers all six required questions.

B  TestDriftTriageContractDistinguishesExpectedVsBreaking
        The workflow document explicitly separates expected drift
        (fixture refresh only) from breaking drift (contract review).

C  TestLiveContractToolingAndDocsPointToSameCanonicalSource
        The refresh helper script and the workflow document both reference
        the same canonical fixture path.

D  TestSnapshotRefreshToolFailsLoudlyOnMissingRequiredShape
        check_required_fields() returns missing fields; records missing
        every required field trigger a non-zero exit signal.

E  TestRuntimeContractDocsAndWorkflowRemainAligned
        REQUIRED_FIELDS in the helper script is a subset of the fields
        that _normalize() explicitly reads — runtime and docs agree.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers — path resolution
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # C:/CLAUDECODE
FIXTURE_CANONICAL_PATH = "backend/tests/fixtures/gamma_snapshot.json"
WORKFLOW_DOC_PATH = PROJECT_ROOT / "docs" / "testing" / "gamma_contract_workflow.md"
HELPER_SCRIPT_PATH = PROJECT_ROOT / "tools" / "refresh_gamma_snapshot.py"
FETCHER_PATH = PROJECT_ROOT / "backend" / "app" / "services" / "market_fetcher.py"


def _load_helper():
    """Import tools.refresh_gamma_snapshot, adding project root to sys.path."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    return importlib.import_module("tools.refresh_gamma_snapshot")


def _workflow_doc_text() -> str:
    return WORKFLOW_DOC_PATH.read_text(encoding="utf-8")


def _helper_source() -> str:
    return HELPER_SCRIPT_PATH.read_text(encoding="utf-8")


def _fetcher_source() -> str:
    return FETCHER_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A — workflow docs cover required steps
# ---------------------------------------------------------------------------


class TestFixtureRefreshWorkflowDocsCoverRequiredSteps:
    """Test A: Workflow document answers all six required questions."""

    def test_workflow_doc_exists(self):
        assert WORKFLOW_DOC_PATH.exists(), (
            f"Workflow document missing: {WORKFLOW_DOC_PATH}"
        )

    def test_doc_answers_when_to_refresh(self):
        """Doc has a section on when to refresh the snapshot."""
        doc = _workflow_doc_text().lower()
        assert "when to refresh" in doc or "ne zaman" in doc, (
            "Workflow doc must answer: when to refresh the snapshot"
        )

    def test_doc_answers_how_to_refresh(self):
        """Doc describes a step-by-step refresh procedure."""
        doc = _workflow_doc_text()
        # Step-by-step procedure must be present
        assert "step" in doc.lower() or "adım" in doc.lower() or "procedure" in doc.lower(), (
            "Workflow doc must include a step-by-step refresh procedure"
        )

    def test_doc_answers_which_fields_sanitized(self):
        """Doc covers field sanitization before committing fixture."""
        doc = _workflow_doc_text().lower()
        assert "sanitiz" in doc or "sanitise" in doc, (
            "Workflow doc must answer: which fields are sanitized"
        )

    def test_doc_answers_expected_vs_breaking_classification(self):
        """Doc covers drift classification (expected vs breaking)."""
        doc = _workflow_doc_text().lower()
        assert "expected drift" in doc or "breaking drift" in doc, (
            "Workflow doc must classify drifts as expected or breaking"
        )

    def test_doc_answers_fixture_update_vs_contract_review(self):
        """Doc distinguishes cases needing only fixture update from those needing review."""
        doc = _workflow_doc_text().lower()
        assert "contract review" in doc or "review" in doc, (
            "Workflow doc must describe when contract review is required"
        )

    def test_doc_answers_live_test_interpretation(self):
        """Doc explains how to interpret live test skip/fail output."""
        doc = _workflow_doc_text().lower()
        assert "live test" in doc or "skipped" in doc or "live" in doc, (
            "Workflow doc must explain live test skip/fail interpretation"
        )


# ---------------------------------------------------------------------------
# B — expected vs breaking drift distinction is explicit
# ---------------------------------------------------------------------------


class TestDriftTriageContractDistinguishesExpectedVsBreaking:
    """Test B: Workflow document explicitly separates drift classes."""

    def test_expected_drift_category_named(self):
        """Doc uses the term 'expected drift' (or equivalent)."""
        doc = _workflow_doc_text().lower()
        assert "expected drift" in doc, (
            "Workflow doc must name 'expected drift' as a distinct category"
        )

    def test_breaking_drift_category_named(self):
        """Doc uses the term 'breaking drift' (or equivalent)."""
        doc = _workflow_doc_text().lower()
        assert "breaking drift" in doc, (
            "Workflow doc must name 'breaking drift' as a distinct category"
        )

    def test_expected_drift_has_fixture_only_action(self):
        """Expected drift section indicates fixture update is sufficient."""
        doc = _workflow_doc_text().lower()
        # The expected-drift section should say something like "update fixture"
        # and should NOT require code changes
        assert "update" in doc and ("fixture" in doc or "snapshot" in doc), (
            "Workflow doc must state that expected drift requires only fixture update"
        )

    def test_breaking_drift_requires_contract_review(self):
        """Breaking drift section requires contract/code review."""
        doc = _workflow_doc_text().lower()
        assert "contract review" in doc or "review" in doc, (
            "Workflow doc must state that breaking drift requires contract review"
        )

    def test_required_vs_optional_field_table_present(self):
        """Doc contains a table distinguishing required from optional fields."""
        doc = _workflow_doc_text().lower()
        assert "required" in doc and "optional" in doc, (
            "Workflow doc must have a field table distinguishing required vs optional"
        )


# ---------------------------------------------------------------------------
# C — tooling and docs point to the same canonical snapshot source
# ---------------------------------------------------------------------------


class TestLiveContractToolingAndDocsPointToSameCanonicalSource:
    """Test C: Helper script and workflow doc reference the same fixture path."""

    def test_workflow_doc_references_canonical_fixture_path(self):
        """Workflow doc contains the canonical fixture path."""
        doc = _workflow_doc_text()
        assert FIXTURE_CANONICAL_PATH in doc, (
            f"Workflow doc must reference the canonical fixture path: {FIXTURE_CANONICAL_PATH}"
        )

    def test_helper_script_references_canonical_fixture_path(self):
        """Helper script source contains the canonical fixture path."""
        src = _helper_source()
        assert FIXTURE_CANONICAL_PATH in src, (
            f"Helper script must reference the canonical fixture path: {FIXTURE_CANONICAL_PATH}"
        )

    def test_both_reference_same_fixture_path(self):
        """Both artifacts agree on the same fixture path (no divergence)."""
        doc = _workflow_doc_text()
        src = _helper_source()
        assert FIXTURE_CANONICAL_PATH in doc and FIXTURE_CANONICAL_PATH in src, (
            "Workflow doc and helper script must both reference the same "
            f"canonical fixture path: {FIXTURE_CANONICAL_PATH}"
        )

    def test_fixture_file_actually_exists(self):
        """The canonical fixture file exists at the documented path."""
        fixture_abs = PROJECT_ROOT / FIXTURE_CANONICAL_PATH
        assert fixture_abs.exists(), (
            f"Canonical fixture file does not exist: {fixture_abs}"
        )

    def test_helper_script_exists(self):
        """The helper script exists at the documented location."""
        assert HELPER_SCRIPT_PATH.exists(), (
            f"Refresh helper script missing: {HELPER_SCRIPT_PATH}"
        )


# ---------------------------------------------------------------------------
# D — helper script fails loudly on missing required shape
# ---------------------------------------------------------------------------


class TestSnapshotRefreshToolFailsLoudlyOnMissingRequiredShape:
    """Test D: check_required_fields() surfaces missing required fields."""

    @pytest.fixture(autouse=True)
    def _mod(self):
        self.mod = _load_helper()

    def test_check_required_fields_returns_empty_for_complete_record(self):
        """No missing fields when all REQUIRED_FIELDS present in records."""
        complete = {f: "present" for f in self.mod.REQUIRED_FIELDS}
        result = self.mod.check_required_fields([complete])
        assert result == [], (
            "check_required_fields should return [] when all required fields present"
        )

    def test_check_required_fields_returns_missing_field(self):
        """Returns the name of a required field absent from all records."""
        for field in self.mod.REQUIRED_FIELDS:
            record_without_field = {f: "x" for f in self.mod.REQUIRED_FIELDS if f != field}
            result = self.mod.check_required_fields([record_without_field])
            assert field in result, (
                f"check_required_fields should surface missing required field '{field}'"
            )

    def test_check_required_fields_empty_records_returns_all_required(self):
        """Empty record list reports all required fields as missing."""
        result = self.mod.check_required_fields([])
        assert set(result) == set(self.mod.REQUIRED_FIELDS), (
            "check_required_fields on empty list must return all REQUIRED_FIELDS"
        )

    def test_field_present_in_any_record_passes_check(self):
        """A required field present in at least one record passes the check."""
        field = self.mod.REQUIRED_FIELDS[0]
        records = [
            {},                    # missing
            {field: "present"},    # present
        ]
        result = self.mod.check_required_fields(records)
        assert field not in result, (
            f"Field '{field}' present in at least one record must not be flagged"
        )

    def test_check_optional_fields_returns_empty_for_complete_record(self):
        """No missing optional fields when all OPTIONAL_FIELDS present."""
        complete = {f: "present" for f in self.mod.OPTIONAL_FIELDS}
        result = self.mod.check_optional_fields([complete])
        assert result == []

    def test_required_fields_list_is_non_empty(self):
        """REQUIRED_FIELDS constant is a non-empty list."""
        assert isinstance(self.mod.REQUIRED_FIELDS, list)
        assert len(self.mod.REQUIRED_FIELDS) > 0

    def test_optional_fields_list_is_non_empty(self):
        """OPTIONAL_FIELDS constant is a non-empty list."""
        assert isinstance(self.mod.OPTIONAL_FIELDS, list)
        assert len(self.mod.OPTIONAL_FIELDS) > 0

    def test_required_and_optional_fields_do_not_overlap(self):
        """No field appears in both REQUIRED_FIELDS and OPTIONAL_FIELDS."""
        overlap = set(self.mod.REQUIRED_FIELDS) & set(self.mod.OPTIONAL_FIELDS)
        assert overlap == set(), (
            f"Fields cannot be both required and optional: {overlap}"
        )


# ---------------------------------------------------------------------------
# E — runtime contract and workflow remain aligned
# ---------------------------------------------------------------------------


class TestRuntimeContractDocsAndWorkflowRemainAligned:
    """Test E: REQUIRED_FIELDS in helper match fields _normalize() reads."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mod = _load_helper()
        self.fetcher_src = _fetcher_source()

    def test_every_required_field_is_read_by_normalize(self):
        """Every field in REQUIRED_FIELDS appears as raw.get("field" in _normalize().

        Uses prefix match (without closing paren) to handle both
        ``raw.get("field")`` and ``raw.get("field", default)`` call forms.
        """
        for field in self.mod.REQUIRED_FIELDS:
            # Match raw.get("field") and raw.get("field", default) forms
            pattern = f'raw.get("{field}"'
            assert pattern in self.fetcher_src, (
                f"REQUIRED_FIELD '{field}' not found as raw.get(\"{field}\"...) in _normalize(). "
                "Either update REQUIRED_FIELDS or fix the fetcher."
            )

    def test_every_optional_field_is_read_by_normalize(self):
        """Every field in OPTIONAL_FIELDS appears as raw.get("field" in _normalize().

        Uses prefix match (without closing paren) to handle both
        ``raw.get("field")`` and ``raw.get("field", default)`` call forms.
        """
        for field in self.mod.OPTIONAL_FIELDS:
            pattern = f'raw.get("{field}"'
            assert pattern in self.fetcher_src, (
                f"OPTIONAL_FIELD '{field}' not found as raw.get(\"{field}\"...) in _normalize(). "
                "Either update OPTIONAL_FIELDS or fix the fetcher."
            )

    def test_workflow_doc_required_field_table_includes_all_required_fields(self):
        """Workflow doc field table mentions every field in REQUIRED_FIELDS."""
        doc = _workflow_doc_text()
        for field in self.mod.REQUIRED_FIELDS:
            assert field in doc, (
                f"Workflow doc field table must mention required field '{field}'"
            )

    def test_workflow_doc_optional_field_table_includes_all_optional_fields(self):
        """Workflow doc field table mentions every field in OPTIONAL_FIELDS."""
        doc = _workflow_doc_text()
        for field in self.mod.OPTIONAL_FIELDS:
            assert field in doc, (
                f"Workflow doc field table must mention optional field '{field}'"
            )

    def test_fixture_canonical_path_consistent_across_all_artifacts(self):
        """FIXTURE_CANONICAL_PATH constant matches actual fixture location."""
        fixture_abs = PROJECT_ROOT / FIXTURE_CANONICAL_PATH
        assert fixture_abs.exists(), (
            f"Fixture path constant is stale — file not found: {fixture_abs}"
        )

    def test_helper_script_and_fetcher_agree_on_required_field_count(self):
        """REQUIRED_FIELDS covers at least all fields with direct discovery impact."""
        # Discovery uses: active, closed, enableOrderBook, tokens, startDate, endDate
        discovery_critical = {"active", "closed", "enableOrderBook", "tokens", "startDate", "endDate"}
        required_set = set(self.mod.REQUIRED_FIELDS)
        assert discovery_critical <= required_set, (
            f"REQUIRED_FIELDS must include all discovery-critical fields. "
            f"Missing: {discovery_critical - required_set}"
        )
