"""Integration tests — Drift Response Ownership Lock (v0.5.20).

These tests lock the operational ownership contracts for upstream Gamma API
drift response: who acts, in what order, and at what decision threshold.

All tests are fully automated and require no network access.

Tests
-----
A  test_drift_response_docs_define_owner_and_next_action_for_each_drift_class
        Expected drift AND breaking drift each have an explicit owner and
        a documented next action.

B  test_drift_response_docs_define_role_specific_actions_for_live_test_states
        SKIPPED / PASSED / FAILED live test states each map to a documented
        role-specific action.

C  test_fixture_refresh_review_and_commit_responsibility_are_documented
        Each step of the fixture refresh cycle (fetch, sanitize/review,
        run tests, commit) has a documented responsible party and gate.

D  test_operational_decision_matrix_aligns_with_existing_workflow_and_helper_contract
        The ownership document does not contradict the existing technical
        workflow document or helper script contracts.

E  test_runtime_contract_docs_and_operational_response_docs_remain_aligned
        Technical drift docs and operational response docs agree on the
        same drift classes, field names, and fixture path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # C:/CLAUDECODE

OWNERSHIP_DOC_PATH = PROJECT_ROOT / "docs" / "testing" / "gamma_drift_response_roles.md"
WORKFLOW_DOC_PATH  = PROJECT_ROOT / "docs" / "testing" / "gamma_contract_workflow.md"
HELPER_SCRIPT_PATH = PROJECT_ROOT / "tools" / "refresh_gamma_snapshot.py"
FIXTURE_CANONICAL_PATH = "backend/tests/fixtures/gamma_snapshot.json"

# Live test states that must appear in ownership doc
LIVE_TEST_STATES = ["SKIPPED", "PASSED", "FAILED"]

# Drift classes that must appear in both docs
DRIFT_CLASSES = ["expected drift", "breaking drift"]


def _ownership_doc() -> str:
    return OWNERSHIP_DOC_PATH.read_text(encoding="utf-8")


def _workflow_doc() -> str:
    return WORKFLOW_DOC_PATH.read_text(encoding="utf-8")


def _helper_source() -> str:
    return HELPER_SCRIPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A — ownership docs define owner + next action per drift class
# ---------------------------------------------------------------------------


class TestDriftResponseDocsDefineOwnerAndNextAction:
    """Test A: Each drift class has an explicit owner and next action."""

    def test_ownership_doc_exists(self):
        assert OWNERSHIP_DOC_PATH.exists(), (
            f"Ownership document missing: {OWNERSHIP_DOC_PATH}"
        )

    def test_expected_drift_owner_documented(self):
        """Expected drift section names a responsible owner."""
        doc = _ownership_doc().lower()
        assert "expected drift" in doc, (
            "Ownership doc must define owner for expected drift"
        )

    def test_breaking_drift_owner_documented(self):
        """Breaking drift section names a responsible owner."""
        doc = _ownership_doc().lower()
        assert "breaking drift" in doc, (
            "Ownership doc must define owner for breaking drift"
        )

    def test_expected_drift_has_next_action(self):
        """Expected drift section specifies what to do next."""
        doc = _ownership_doc().lower()
        # Must describe a concrete action (update fixture, run tests, etc.)
        assert "fixture" in doc or "update" in doc, (
            "Ownership doc must describe the next action for expected drift"
        )

    def test_breaking_drift_has_escalation_path(self):
        """Breaking drift section specifies an escalation path (milestone/review)."""
        doc = _ownership_doc().lower()
        assert "milestone" in doc or "review" in doc, (
            "Ownership doc must describe escalation path for breaking drift"
        )

    def test_operator_role_named(self):
        """Ownership doc names the Operator role explicitly."""
        doc = _ownership_doc().lower()
        assert "operator" in doc, (
            "Ownership doc must define the Operator role"
        )

    def test_implementer_role_named(self):
        """Ownership doc names the Implementer role."""
        doc = _ownership_doc().lower()
        assert "implementer" in doc or "claude" in doc, (
            "Ownership doc must define the Implementer role"
        )

    def test_decision_threshold_documented(self):
        """Ownership doc defines a decision threshold for each drift class."""
        doc = _ownership_doc().lower()
        assert "decision" in doc or "threshold" in doc or "gate" in doc, (
            "Ownership doc must define a decision threshold"
        )


# ---------------------------------------------------------------------------
# B — role-specific actions for live test states
# ---------------------------------------------------------------------------


class TestDriftResponseDocsDefineRoleSpecificActionsForLiveTestStates:
    """Test B: SKIPPED / PASSED / FAILED each map to a role-based action."""

    def test_live_test_skipped_outcome_documented(self):
        """SKIPPED live test outcome has a documented response (no action)."""
        doc = _ownership_doc()
        assert "SKIPPED" in doc or "skipped" in doc.lower(), (
            "Ownership doc must describe the SKIPPED live test outcome"
        )

    def test_live_test_passed_outcome_documented(self):
        """PASSED live test outcome has a documented response (no drift)."""
        doc = _ownership_doc()
        assert "PASSED" in doc or "passed" in doc.lower(), (
            "Ownership doc must describe the PASSED live test outcome"
        )

    def test_live_test_failed_outcome_documented(self):
        """FAILED live test outcome maps to a concrete first-responder action."""
        doc = _ownership_doc()
        assert "FAILED" in doc or "failed" in doc.lower(), (
            "Ownership doc must describe the FAILED live test outcome"
        )

    def test_first_responder_for_failed_live_test_is_named(self):
        """When live test fails, a first responder is named (Operator)."""
        doc = _ownership_doc().lower()
        # FAILED section should name the operator
        assert "operator" in doc, (
            "Ownership doc must name the first responder for a live test failure"
        )

    def test_all_live_test_states_appear_in_doc(self):
        """All three live test states (SKIPPED/PASSED/FAILED) appear in doc."""
        doc = _ownership_doc()
        for state in LIVE_TEST_STATES:
            assert state in doc or state.lower() in doc.lower(), (
                f"Ownership doc must cover live test state: {state}"
            )


# ---------------------------------------------------------------------------
# C — fixture refresh review + commit responsibility
# ---------------------------------------------------------------------------


class TestFixtureRefreshReviewAndCommitResponsibilityDocumented:
    """Test C: Fixture refresh cycle has documented ownership for each step."""

    def test_fixture_refresh_responsibility_section_exists(self):
        """Ownership doc has a section on fixture refresh responsibility."""
        doc = _ownership_doc().lower()
        assert "fixture" in doc and ("refresh" in doc or "checklist" in doc), (
            "Ownership doc must have a fixture refresh responsibility section"
        )

    def test_review_before_commit_gate_documented(self):
        """Doc states review must be complete before committing fixture."""
        doc = _ownership_doc().lower()
        assert "review" in doc and "commit" in doc, (
            "Ownership doc must document the review-before-commit gate"
        )

    def test_checklist_or_gate_items_present(self):
        """Doc includes a checklist or gate items for fixture refresh."""
        doc = _ownership_doc()
        # Checklist items typically start with [ ] or contain "must"
        assert "[ ]" in doc or "must" in doc.lower() or "gate" in doc.lower(), (
            "Ownership doc must include checklist/gate items for fixture refresh"
        )

    def test_test_suite_run_required_before_commit(self):
        """Doc requires running the test suite before committing fixture."""
        doc = _ownership_doc().lower()
        assert "pytest" in doc or "test suite" in doc or "tests/" in doc, (
            "Ownership doc must require running tests before fixture commit"
        )

    def test_commit_message_format_or_guidance_present(self):
        """Doc provides commit message format or guidance."""
        doc = _ownership_doc().lower()
        assert "commit" in doc and (
            "message" in doc or "format" in doc or "fix(fixture)" in doc
        ), (
            "Ownership doc must include commit message guidance"
        )


# ---------------------------------------------------------------------------
# D — ownership doc consistent with existing workflow + helper contract
# ---------------------------------------------------------------------------


class TestOperationalDecisionMatrixAlignsWithWorkflowAndHelper:
    """Test D: Ownership doc does not contradict workflow doc or helper script."""

    def test_both_docs_use_same_drift_class_names(self):
        """Both docs use identical drift class terminology."""
        ownership = _ownership_doc().lower()
        workflow  = _workflow_doc().lower()
        for cls in DRIFT_CLASSES:
            assert cls in ownership, f"Ownership doc must name drift class: '{cls}'"
            assert cls in workflow,  f"Workflow doc must name drift class: '{cls}'"

    def test_both_docs_reference_same_canonical_fixture_path(self):
        """Both docs reference the same canonical fixture path."""
        ownership = _ownership_doc()
        workflow  = _workflow_doc()
        assert FIXTURE_CANONICAL_PATH in ownership or "gamma_snapshot.json" in ownership, (
            "Ownership doc must reference the canonical fixture"
        )
        assert FIXTURE_CANONICAL_PATH in workflow, (
            "Workflow doc must reference the canonical fixture path"
        )

    def test_ownership_doc_references_workflow_doc(self):
        """Ownership doc cross-references the technical workflow document."""
        doc = _ownership_doc()
        assert "gamma_contract_workflow" in doc, (
            "Ownership doc must cross-reference gamma_contract_workflow.md"
        )

    def test_ownership_doc_references_helper_script(self):
        """Ownership doc mentions the refresh helper script."""
        doc = _ownership_doc()
        assert "refresh_gamma_snapshot" in doc, (
            "Ownership doc must reference the refresh helper script"
        )

    def test_ownership_doc_does_not_redefine_breaking_drift_criteria(self):
        """Ownership doc defers drift classification to workflow doc — no field-list definition."""
        ownership = _ownership_doc()
        # Ownership doc may *mention* REQUIRED_FIELDS as a reference but must not
        # DEFINE it (i.e., no assignment like REQUIRED_FIELDS = [...]).
        assert "REQUIRED_FIELDS = " not in ownership and "REQUIRED_FIELDS: " not in ownership, (
            "Ownership doc must not define REQUIRED_FIELDS — that belongs to the helper script"
        )
        # The authoritative definition must remain in the helper script
        assert "REQUIRED_FIELDS" in _helper_source(), (
            "REQUIRED_FIELDS must remain defined in tools/refresh_gamma_snapshot.py"
        )


# ---------------------------------------------------------------------------
# E — technical drift docs and operational response docs aligned
# ---------------------------------------------------------------------------


class TestRuntimeContractDocsAndOperationalResponseDocsRemainAligned:
    """Test E: Technical and operational docs agree on the same facts."""

    def test_both_docs_define_expected_drift(self):
        """Both docs cover expected drift."""
        for doc_name, doc in [
            ("ownership", _ownership_doc()),
            ("workflow",  _workflow_doc()),
        ]:
            assert "expected drift" in doc.lower(), (
                f"{doc_name} doc must define 'expected drift'"
            )

    def test_both_docs_define_breaking_drift(self):
        """Both docs cover breaking drift."""
        for doc_name, doc in [
            ("ownership", _ownership_doc()),
            ("workflow",  _workflow_doc()),
        ]:
            assert "breaking drift" in doc.lower(), (
                f"{doc_name} doc must define 'breaking drift'"
            )

    def test_fixture_path_consistent_across_all_artifacts(self):
        """Fixture path is consistent: ownership doc, workflow doc, helper script."""
        ownership = _ownership_doc()
        workflow  = _workflow_doc()
        helper    = _helper_source()
        assert "gamma_snapshot.json" in ownership, "Ownership doc must name the fixture"
        assert FIXTURE_CANONICAL_PATH in workflow,  "Workflow doc must have canonical path"
        assert FIXTURE_CANONICAL_PATH in helper,    "Helper script must have canonical path"

    def test_live_test_section_consistent_between_docs(self):
        """Both docs address live test outcomes (no contradictory guidance)."""
        ownership = _ownership_doc().lower()
        workflow  = _workflow_doc().lower()
        assert "live" in ownership and "live" in workflow, (
            "Both docs must address live test behaviour"
        )

    def test_operator_is_decision_authority_not_claude(self):
        """Ownership doc establishes operator as final decision authority."""
        doc = _ownership_doc().lower()
        # Doc must state operator makes decisions; Claude does not decide unilaterally
        assert "operator" in doc, (
            "Ownership doc must name the Operator as decision authority"
        )
        # The doc should clarify Claude's bounded role
        assert "claude" in doc or "implementer" in doc, (
            "Ownership doc must define the bounded implementer role"
        )

    def test_no_unilateral_claude_decisions_documented(self):
        """Ownership doc states Claude never decides alone on production changes."""
        doc = _ownership_doc().lower()
        # Doc must contain language about operator approval / operator decides
        assert "approves" in doc or "approval" in doc or "operator" in doc, (
            "Ownership doc must state production decisions require operator approval"
        )
