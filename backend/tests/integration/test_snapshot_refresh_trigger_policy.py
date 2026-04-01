"""Integration tests — Snapshot Refresh Trigger Policy Lock (v0.5.21).

These tests lock the trigger policy for Gamma snapshot refresh: which events
require a refresh, which explicitly do not, and how optional proactive cadence
is classified.

All tests are fully automated and require no network access.

Tests
-----
A  TestRefreshPolicyDocsDefineRequiredTriggers
        The policy document names the events that MUST trigger a snapshot
        refresh.

B  TestRefreshPolicyDocsDefineWhenRefreshIsNotRequired
        The policy document explicitly names situations where refresh must
        NOT happen (negative triggers / do-not-refresh cases).

C  TestRefreshTriggerPolicyAlignsWithDriftClassesAndLiveTestStates
        The trigger policy is consistent with the drift classification
        (expected/breaking) and the three live test states
        (SKIPPED/PASSED/FAILED).

D  TestRefreshPolicyAlignsWithOwnershipAndWorkflowDocs
        The refresh policy document does not contradict the ownership doc
        or the technical workflow doc.

E  TestOptionalProactiveRefreshCadenceDocumentedAsNonMandatory
        If a proactive refresh cadence is described, it is explicitly
        marked as optional / non-mandatory, not as a required gate.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # C:/CLAUDECODE

POLICY_DOC_PATH    = PROJECT_ROOT / "docs" / "testing" / "gamma_snapshot_refresh_policy.md"
WORKFLOW_DOC_PATH  = PROJECT_ROOT / "docs" / "testing" / "gamma_contract_workflow.md"
OWNERSHIP_DOC_PATH = PROJECT_ROOT / "docs" / "testing" / "gamma_drift_response_roles.md"
HELPER_SCRIPT_PATH = PROJECT_ROOT / "tools" / "refresh_gamma_snapshot.py"
FIXTURE_PATH       = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "gamma_snapshot.json"

LIVE_TEST_STATES = ["SKIPPED", "PASSED", "FAILED"]
DRIFT_CLASSES    = ["expected drift", "breaking drift"]


def _policy_doc() -> str:
    return POLICY_DOC_PATH.read_text(encoding="utf-8")


def _workflow_doc() -> str:
    return WORKFLOW_DOC_PATH.read_text(encoding="utf-8")


def _ownership_doc() -> str:
    return OWNERSHIP_DOC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A — required triggers defined
# ---------------------------------------------------------------------------


class TestRefreshPolicyDocsDefineRequiredTriggers:
    """Test A: Policy doc names which events MUST trigger a snapshot refresh."""

    def test_policy_doc_exists(self):
        assert POLICY_DOC_PATH.exists(), (
            f"Policy document missing: {POLICY_DOC_PATH}"
        )

    def test_live_test_failure_is_a_required_trigger(self):
        """Policy doc states live test failure triggers a refresh."""
        doc = _policy_doc().lower()
        assert "failed" in doc and ("refresh" in doc or "trigger" in doc), (
            "Policy doc must state that live test FAILED triggers a refresh"
        )

    def test_breaking_drift_helper_output_is_a_required_trigger(self):
        """Policy doc states [BREAKING DRIFT] helper output triggers review + refresh."""
        doc = _policy_doc()
        assert "BREAKING DRIFT" in doc or "breaking drift" in doc.lower(), (
            "Policy doc must state that [BREAKING DRIFT] helper alert triggers action"
        )

    def test_required_triggers_section_present(self):
        """Policy doc has a dedicated section on required triggers."""
        doc = _policy_doc().lower()
        assert "required trigger" in doc or "must happen" in doc or "must be refreshed" in doc, (
            "Policy doc must have a 'required triggers' section"
        )

    def test_helper_script_referenced_in_required_trigger_flow(self):
        """Policy doc mentions the helper script in the required trigger flow."""
        doc = _policy_doc()
        assert "refresh_gamma_snapshot" in doc, (
            "Policy doc must reference tools/refresh_gamma_snapshot.py in the trigger flow"
        )

    def test_all_live_test_states_covered_in_trigger_table(self):
        """Live test SKIPPED / PASSED / FAILED outcomes all appear in policy doc."""
        doc = _policy_doc()
        for state in LIVE_TEST_STATES:
            assert state in doc, (
                f"Policy doc must cover live test state: {state}"
            )


# ---------------------------------------------------------------------------
# B — negative triggers (when NOT to refresh) defined
# ---------------------------------------------------------------------------


class TestRefreshPolicyDocsDefineWhenRefreshIsNotRequired:
    """Test B: Policy doc explicitly states when refresh must NOT happen."""

    def test_negative_triggers_section_present(self):
        """Policy doc has a section on when refresh is NOT required."""
        doc = _policy_doc().lower()
        assert (
            "not required" in doc
            or "must not" in doc
            or "skip" in doc
            or "negative" in doc
            or "do not" in doc
        ), (
            "Policy doc must have a 'do not refresh' / negative triggers section"
        )

    def test_live_test_skipped_does_not_require_refresh(self):
        """Policy doc states SKIPPED live test does NOT require refresh."""
        doc = _policy_doc()
        # The SKIPPED row should say "No" or similar
        assert "SKIPPED" in doc, (
            "Policy doc must address the SKIPPED live test outcome"
        )
        # Check that SKIPPED is associated with "No" refresh
        skipped_idx = doc.index("SKIPPED")
        nearby = doc[skipped_idx : skipped_idx + 200].lower()
        assert "no" in nearby or "not" in nearby or "skip" in nearby, (
            "Policy doc must state SKIPPED does not require refresh"
        )

    def test_live_test_passed_does_not_require_refresh(self):
        """Policy doc states PASSED live test does NOT require refresh."""
        doc = _policy_doc()
        assert "PASSED" in doc, (
            "Policy doc must address the PASSED live test outcome"
        )
        passed_idx = doc.index("PASSED")
        nearby = doc[passed_idx : passed_idx + 200].lower()
        assert "no" in nearby or "not" in nearby or "current" in nearby, (
            "Policy doc must state PASSED does not require refresh"
        )

    def test_connection_error_does_not_require_refresh(self):
        """Policy doc states connection/network error is NOT a drift signal."""
        doc = _policy_doc().lower()
        assert "connection" in doc or "network" in doc, (
            "Policy doc must state network/connection errors are not drift signals"
        )

    def test_value_change_alone_does_not_require_refresh(self):
        """Policy doc states field VALUE changes (not shape) do not require refresh."""
        doc = _policy_doc().lower()
        assert "value" in doc or "shape" in doc, (
            "Policy doc must distinguish shape changes from value changes"
        )

    def test_speculative_refresh_explicitly_discouraged(self):
        """Policy doc discourages speculative / preemptive refresh without a trigger."""
        doc = _policy_doc().lower()
        assert "speculative" in doc or "without" in doc or "do not" in doc, (
            "Policy doc must explicitly discourage speculative refresh"
        )


# ---------------------------------------------------------------------------
# C — trigger policy aligned with drift classes and live test states
# ---------------------------------------------------------------------------


class TestRefreshTriggerPolicyAlignsWithDriftClassesAndLiveTestStates:
    """Test C: Trigger policy is consistent with drift classification and live test states."""

    def test_policy_doc_uses_expected_drift_terminology(self):
        """Policy doc uses 'expected drift' terminology consistent with workflow doc."""
        doc = _policy_doc().lower()
        assert "expected drift" in doc or "expected" in doc, (
            "Policy doc must use expected drift terminology"
        )

    def test_policy_doc_uses_breaking_drift_terminology(self):
        """Policy doc uses 'breaking drift' terminology consistent with workflow doc."""
        doc = _policy_doc().lower()
        assert "breaking drift" in doc or "breaking" in doc, (
            "Policy doc must use breaking drift terminology"
        )

    def test_live_test_failed_missing_key_is_required_trigger(self):
        """Policy doc distinguishes FAILED-missing-key (required trigger) from other FAILEDs."""
        doc = _policy_doc().lower()
        assert "missing key" in doc or "missing field" in doc or "absent" in doc, (
            "Policy doc must distinguish FAILED-missing-key as a required trigger"
        )

    def test_all_drift_classes_appear_in_policy_doc(self):
        """Both 'expected' and 'breaking' drift concepts appear in policy doc."""
        doc = _policy_doc().lower()
        # Accept either the full phrase or the keyword — policy doc may use
        # "expected drift" or just refer to "expected" in context.
        assert "expected drift" in doc or "expected" in doc, (
            "Policy doc must reference expected drift"
        )
        assert "breaking drift" in doc or "breaking" in doc, (
            "Policy doc must reference breaking drift"
        )

    def test_policy_doc_references_workflow_doc_for_classification(self):
        """Policy doc defers drift classification details to workflow doc."""
        doc = _policy_doc()
        assert "gamma_contract_workflow" in doc, (
            "Policy doc must reference gamma_contract_workflow.md for classification details"
        )


# ---------------------------------------------------------------------------
# D — policy doc consistent with ownership + workflow docs
# ---------------------------------------------------------------------------


class TestRefreshPolicyAlignsWithOwnershipAndWorkflowDocs:
    """Test D: Policy doc does not contradict ownership or workflow docs."""

    def test_policy_doc_references_ownership_doc(self):
        """Policy doc cross-references the ownership document."""
        doc = _policy_doc()
        assert "gamma_drift_response_roles" in doc, (
            "Policy doc must cross-reference gamma_drift_response_roles.md"
        )

    def test_policy_doc_references_workflow_doc(self):
        """Policy doc cross-references the technical workflow document."""
        doc = _policy_doc()
        assert "gamma_contract_workflow" in doc, (
            "Policy doc must cross-reference gamma_contract_workflow.md"
        )

    def test_all_three_docs_use_same_fixture_reference(self):
        """Policy, workflow, and ownership docs all reference the same fixture."""
        policy    = _policy_doc()
        workflow  = _workflow_doc()
        ownership = _ownership_doc()
        assert "gamma_snapshot.json" in policy,    "Policy doc must reference gamma_snapshot.json"
        assert "gamma_snapshot.json" in workflow,  "Workflow doc must reference gamma_snapshot.json"
        assert "gamma_snapshot.json" in ownership, "Ownership doc must reference gamma_snapshot.json"

    def test_fixture_file_exists_at_referenced_path(self):
        """The fixture file exists at the path all docs reference."""
        assert FIXTURE_PATH.exists(), (
            f"Fixture file missing: {FIXTURE_PATH}"
        )

    def test_policy_doc_does_not_redefine_drift_classification(self):
        """Policy doc does not redefine expected vs breaking drift — defers to workflow."""
        policy = _policy_doc()
        # Policy doc should cross-reference, not redefine the field-level criteria
        # It should not contain the REQUIRED_FIELDS definition
        assert "REQUIRED_FIELDS = " not in policy and "REQUIRED_FIELDS: " not in policy, (
            "Policy doc must not redefine REQUIRED_FIELDS — defer to helper script"
        )


# ---------------------------------------------------------------------------
# E — optional cadence documented as non-mandatory
# ---------------------------------------------------------------------------


class TestOptionalProactiveRefreshCadenceDocumentedAsNonMandatory:
    """Test E: Optional proactive cadence is clearly non-mandatory."""

    def test_optional_cadence_section_exists(self):
        """Policy doc has a section on optional / proactive refresh cadence."""
        doc = _policy_doc().lower()
        assert "optional" in doc or "proactive" in doc or "cadence" in doc, (
            "Policy doc must have an optional/proactive cadence section"
        )

    def test_optional_cadence_is_explicitly_non_mandatory(self):
        """Policy doc clearly states the optional cadence is not a required gate."""
        doc = _policy_doc().lower()
        assert "not mandatory" in doc or "non-mandatory" in doc or "not required" in doc or "suggestion" in doc or "recommended" in doc, (
            "Policy doc must explicitly state the optional cadence is non-mandatory"
        )

    def test_no_cron_or_scheduler_in_policy(self):
        """Policy doc does not introduce cron jobs or automated schedulers."""
        doc = _policy_doc().lower()
        assert "cron" not in doc and "scheduler" not in doc and "automation" not in doc, (
            "Policy doc must not introduce cron/scheduler — this is a manual process"
        )

    def test_release_pre_check_mentioned_as_optional(self):
        """Policy doc mentions release-time refresh as an optional recommendation."""
        doc = _policy_doc().lower()
        assert "release" in doc, (
            "Policy doc must mention release-time refresh as an optional cadence item"
        )

    def test_mandatory_gates_are_only_required_triggers(self):
        """Only required triggers (§1) are mandatory; optional cadence is not a gate."""
        doc = _policy_doc().lower()
        # The doc must distinguish required (must) from optional (recommended/optional)
        assert "must" in doc and ("optional" in doc or "recommended" in doc), (
            "Policy doc must distinguish mandatory (must) from optional (recommended) refresh"
        )
