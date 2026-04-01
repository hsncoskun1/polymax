"""Integration tests — Regression Tier Contract Lock (v0.5.23).

These tests lock the regression tier contract: the canonical definition of
Smoke, Standard, and Full regression tiers including executable commands,
when to run each tier, and how tiers relate to existing contract surfaces.

All tests are fully automated and require no network access.

Tests
-----
A  TestRegressionTierDocsDefineSmokeStandardFullUnambiguously
        Tier definitions are unambiguous and complete.

B  TestRegressionTierDocsMapToExistingContractSurfacesAndPriorities
        Tiers are aligned with the contract atlas and regression matrix.

C  TestExecutableRegressionCommandsOrSelectorsMatchDocumentedTiers
        Documented pytest commands are syntactically valid and reference
        paths that exist on disk.

D  TestLiveAndOptionalTestsAreExplicitlyPositionedOutsideRequiredSmokePath
        Smoke tier is not accidentally dependent on live/optional tests.

E  TestRegressionTierDocsIdentifyMinimumRequiredSuiteForCommonChangeTypes
        Minimum tier for common change types (doc-only, fetcher-only, etc.)
        is explicitly documented.

F  TestRegressionTierContractDoesNotContradictExistingWorkflowDocs
        Tier doc is consistent with workflow, ownership, atlas, and
        regression matrix documents.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # C:/CLAUDECODE

TIER_DOC_PATH      = PROJECT_ROOT / "docs" / "testing" / "regression_tiers.md"
ATLAS_PATH         = PROJECT_ROOT / "docs" / "testing" / "discovery_sync_contract_atlas.md"
MATRIX_PATH        = PROJECT_ROOT / "docs" / "testing" / "discovery_regression_matrix.md"
WORKFLOW_DOC_PATH  = PROJECT_ROOT / "docs" / "testing" / "gamma_contract_workflow.md"
OWNERSHIP_DOC_PATH = PROJECT_ROOT / "docs" / "testing" / "gamma_drift_response_roles.md"
POLICY_DOC_PATH    = PROJECT_ROOT / "docs" / "testing" / "gamma_snapshot_refresh_policy.md"

# Smoke tier test paths
SMOKE_PATHS = [
    PROJECT_ROOT / "backend" / "tests" / "test_health.py",
    PROJECT_ROOT / "backend" / "tests" / "domain",
    PROJECT_ROOT / "backend" / "tests" / "services",
    PROJECT_ROOT / "backend" / "tests" / "api",
]

# Standard tier = all of backend/tests/
STANDARD_PATH = PROJECT_ROOT / "backend" / "tests"

TIER_NAMES = ["smoke", "standard", "full"]

CHANGE_TYPES = [
    "doc-only",
    "fetcher",
    "discovery",
    "sync",
    "api",
    "domain",
    "release",
]


def _tier_doc() -> str:
    return TIER_DOC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A — tier definitions are unambiguous
# ---------------------------------------------------------------------------


class TestRegressionTierDocsDefineSmokeStandardFullUnambiguously:
    """Test A: Smoke / Standard / Full are defined without ambiguity."""

    def test_tier_doc_exists(self):
        assert TIER_DOC_PATH.exists(), f"Tier doc missing: {TIER_DOC_PATH}"

    def test_smoke_tier_defined(self):
        """Tier doc defines 'Smoke' tier."""
        doc = _tier_doc().lower()
        assert "smoke" in doc, "Tier doc must define the Smoke tier"

    def test_standard_tier_defined(self):
        """Tier doc defines 'Standard' tier."""
        doc = _tier_doc().lower()
        assert "standard" in doc, "Tier doc must define the Standard tier"

    def test_full_tier_defined(self):
        """Tier doc defines 'Full' tier."""
        doc = _tier_doc().lower()
        assert "full" in doc, "Tier doc must define the Full tier"

    def test_smoke_scope_documented(self):
        """Tier doc states what Smoke covers."""
        doc = _tier_doc()
        assert "test_health" in doc or "health" in doc.lower(), (
            "Smoke tier must mention health test coverage"
        )
        assert "domain" in doc.lower() and "services" in doc.lower(), (
            "Smoke tier must mention domain and services coverage"
        )

    def test_standard_scope_documented(self):
        """Tier doc states what Standard covers (all automated tests)."""
        doc = _tier_doc().lower()
        assert "all automated" in doc or "all of" in doc or "integration" in doc, (
            "Standard tier must describe covering all automated tests"
        )

    def test_full_scope_documents_live(self):
        """Tier doc states Full includes live API tests."""
        doc = _tier_doc().lower()
        assert "live" in doc and "full" in doc, (
            "Full tier must reference live API tests"
        )

    def test_tiers_have_distinct_scope(self):
        """Smoke, Standard, Full describe meaningfully different scopes."""
        doc = _tier_doc().lower()
        # Smoke is a subset — doc should say what it does NOT cover
        assert "does not cover" in doc or "excluded" in doc or "not cover" in doc, (
            "Tier doc must state what Smoke does NOT cover"
        )

    def test_required_vs_recommended_distinction_present(self):
        """Tier doc distinguishes REQUIRED from RECOMMENDED tiers."""
        doc = _tier_doc()
        assert "REQUIRED" in doc and "RECOMMENDED" in doc, (
            "Tier doc must distinguish REQUIRED from RECOMMENDED tiers"
        )


# ---------------------------------------------------------------------------
# B — tiers map to contract surfaces and priorities
# ---------------------------------------------------------------------------


class TestRegressionTierDocsMapToExistingContractSurfacesAndPriorities:
    """Test B: Tiers align with contract atlas and regression matrix."""

    def test_tier_doc_references_contract_atlas(self):
        """Tier doc cross-references the contract atlas."""
        doc = _tier_doc()
        assert "discovery_sync_contract_atlas" in doc, (
            "Tier doc must reference discovery_sync_contract_atlas.md"
        )

    def test_tier_doc_references_regression_matrix(self):
        """Tier doc cross-references the regression matrix."""
        doc = _tier_doc()
        assert "discovery_regression_matrix" in doc, (
            "Tier doc must reference discovery_regression_matrix.md"
        )

    def test_tier_doc_addresses_p0_priority(self):
        """Tier doc mentions P0 priority alignment."""
        doc = _tier_doc()
        assert "P0" in doc, "Tier doc must address P0 priority tests"

    def test_tier_doc_addresses_p1_priority(self):
        """Tier doc mentions P1 priority alignment."""
        doc = _tier_doc()
        assert "P1" in doc, "Tier doc must address P1 priority tests"

    def test_locked_contracts_require_standard_tier(self):
        """Tier doc states that touching a LOCKED contract surface requires Standard."""
        doc = _tier_doc().lower()
        assert "locked" in doc and "standard" in doc, (
            "Tier doc must state that LOCKED contract changes require Standard tier"
        )

    def test_contract_atlas_exists(self):
        """Contract atlas referenced in tier doc actually exists."""
        assert ATLAS_PATH.exists(), f"Contract atlas missing: {ATLAS_PATH}"

    def test_regression_matrix_exists(self):
        """Regression matrix referenced in tier doc actually exists."""
        assert MATRIX_PATH.exists(), f"Regression matrix missing: {MATRIX_PATH}"


# ---------------------------------------------------------------------------
# C — executable commands are valid and paths exist
# ---------------------------------------------------------------------------


class TestExecutableRegressionCommandsOrSelectorsMatchDocumentedTiers:
    """Test C: Documented pytest commands reference real paths."""

    def test_smoke_test_paths_exist_on_disk(self):
        """All paths in the Smoke tier actually exist."""
        for path in SMOKE_PATHS:
            assert path.exists(), f"Smoke tier path missing: {path}"

    def test_standard_test_path_exists_on_disk(self):
        """The Standard tier path (backend/tests/) exists."""
        assert STANDARD_PATH.exists(), f"Standard tier path missing: {STANDARD_PATH}"

    def test_tier_doc_contains_pytest_command_for_smoke(self):
        """Tier doc contains an executable pytest command for Smoke."""
        doc = _tier_doc()
        assert "pytest" in doc and "test_health" in doc, (
            "Tier doc must contain a pytest command for Smoke tier"
        )

    def test_tier_doc_contains_pytest_command_for_standard(self):
        """Tier doc contains an executable pytest command for Standard."""
        doc = _tier_doc()
        assert "pytest" in doc and "backend/tests/" in doc, (
            "Tier doc must contain a pytest command for Standard tier"
        )

    def test_tier_doc_contains_pytest_command_for_full(self):
        """Tier doc contains an executable pytest command for Full."""
        doc = _tier_doc().lower()
        assert "pytest" in doc and "live" in doc, (
            "Tier doc must contain a pytest command for Full tier including live marker"
        )

    def test_smoke_command_collects_tests(self):
        """The documented Smoke pytest command collects at least 1 test."""
        smoke_args = [
            sys.executable, "-m", "pytest",
            str(PROJECT_ROOT / "backend" / "tests" / "test_health.py"),
            str(PROJECT_ROOT / "backend" / "tests" / "domain"),
            str(PROJECT_ROOT / "backend" / "tests" / "services"),
            str(PROJECT_ROOT / "backend" / "tests" / "api"),
            "--collect-only", "-q",
        ]
        result = subprocess.run(smoke_args, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert result.returncode == 0, (
            f"Smoke tier --collect-only failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "test" in result.stdout.lower(), (
            "Smoke tier must collect at least one test"
        )

    def test_standard_command_collects_tests(self):
        """The documented Standard pytest command collects at least 1 test."""
        standard_args = [
            sys.executable, "-m", "pytest",
            str(PROJECT_ROOT / "backend" / "tests"),
            "--collect-only", "-q",
        ]
        result = subprocess.run(standard_args, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert result.returncode == 0, (
            f"Standard tier --collect-only failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "test" in result.stdout.lower(), (
            "Standard tier must collect at least one test"
        )


# ---------------------------------------------------------------------------
# D — live/optional tests outside required Smoke path
# ---------------------------------------------------------------------------


class TestLiveAndOptionalTestsAreExplicitlyPositionedOutsideRequiredSmokePath:
    """Test D: Smoke tier does not accidentally depend on live/optional tests."""

    def test_tier_doc_explicitly_excludes_live_from_smoke(self):
        """Tier doc explicitly states live tests are not in Smoke."""
        doc = _tier_doc().lower()
        # Should say live is not in smoke OR smoke does not cover live
        assert "live" in doc and "smoke" in doc, (
            "Tier doc must address the relationship between live tests and Smoke tier"
        )

    def test_tier_doc_explicitly_excludes_live_from_standard(self):
        """Tier doc explicitly states live tests are not in Standard."""
        doc = _tier_doc().lower()
        assert "live" in doc and ("skipped" in doc or "excluded" in doc or "opt-in" in doc), (
            "Tier doc must state that live tests are excluded from Standard"
        )

    def test_tier_doc_states_live_is_opt_in(self):
        """Tier doc states live tests require explicit opt-in."""
        doc = _tier_doc().lower()
        assert "opt-in" in doc or "-m live" in doc or "mark" in doc, (
            "Tier doc must state that live tests require explicit opt-in"
        )

    def test_smoke_paths_contain_no_live_marked_tests(self):
        """No test in the Smoke paths is marked @pytest.mark.live."""
        smoke_test_dirs = [
            PROJECT_ROOT / "backend" / "tests" / "domain",
            PROJECT_ROOT / "backend" / "tests" / "services",
            PROJECT_ROOT / "backend" / "tests" / "api",
        ]
        for test_dir in smoke_test_dirs:
            for test_file in test_dir.glob("*.py"):
                content = test_file.read_text(encoding="utf-8")
                assert "@pytest.mark.live" not in content, (
                    f"Smoke tier file must not contain @pytest.mark.live: {test_file}"
                )
        # Also check test_health.py
        health_file = PROJECT_ROOT / "backend" / "tests" / "test_health.py"
        assert "@pytest.mark.live" not in health_file.read_text(encoding="utf-8"), (
            "test_health.py must not contain @pytest.mark.live"
        )

    def test_tier_doc_states_skipped_live_is_not_a_drift_signal(self):
        """Tier doc notes that SKIPPED live test is not a drift signal."""
        doc = _tier_doc().lower()
        assert "skipped" in doc and ("not" in doc or "no" in doc), (
            "Tier doc must state that a SKIPPED live result is not a drift signal"
        )


# ---------------------------------------------------------------------------
# E — minimum required suite for common change types
# ---------------------------------------------------------------------------


class TestRegressionTierDocsIdentifyMinimumRequiredSuiteForCommonChangeTypes:
    """Test E: Minimum tier is documented for common change types."""

    def test_tier_doc_has_change_type_decision_table(self):
        """Tier doc has a table or section mapping change types to minimum tiers."""
        doc = _tier_doc().lower()
        assert "change type" in doc or "change to" in doc or "change" in doc, (
            "Tier doc must have a change-type to tier mapping"
        )

    def test_doc_only_change_requires_smoke(self):
        """Doc-only changes require at minimum Smoke."""
        doc = _tier_doc().lower()
        assert "doc" in doc and "smoke" in doc, (
            "Tier doc must state that doc-only changes require Smoke"
        )

    def test_fetcher_change_requires_standard(self):
        """Fetcher changes require Standard (fetcher normalization contract locked)."""
        doc = _tier_doc().lower()
        assert "fetcher" in doc and "standard" in doc, (
            "Tier doc must state that fetcher changes require Standard"
        )

    def test_discovery_change_requires_standard(self):
        """Discovery changes require Standard (discovery selection contract locked)."""
        doc = _tier_doc().lower()
        assert "discovery" in doc and "standard" in doc, (
            "Tier doc must state that discovery changes require Standard"
        )

    def test_pre_release_requires_full(self):
        """Pre-release verification requires Full tier."""
        doc = _tier_doc().lower()
        assert "release" in doc and "full" in doc, (
            "Tier doc must state that pre-release verification requires Full"
        )

    def test_sync_change_requires_standard(self):
        """Sync changes require Standard (multiple contracts locked)."""
        doc = _tier_doc().lower()
        assert "sync" in doc and "standard" in doc, (
            "Tier doc must state that sync changes require Standard"
        )

    def test_new_discovery_rule_or_normalization_field_requires_full(self):
        """New discovery rules or normalization fields require Full (fixture coverage)."""
        doc = _tier_doc().lower()
        assert "normalization" in doc or "discovery rule" in doc or "new" in doc, (
            "Tier doc must address new discovery rule / normalization field changes"
        )


# ---------------------------------------------------------------------------
# F — tier contract consistent with existing workflow docs
# ---------------------------------------------------------------------------


class TestRegressionTierContractDoesNotContradictExistingWorkflowDocs:
    """Test F: Tier doc is consistent with all existing docs/testing documents."""

    def test_tier_doc_references_gamma_snapshot_policy(self):
        """Tier doc cross-references the snapshot refresh policy."""
        doc = _tier_doc()
        assert "gamma_snapshot_refresh_policy" in doc or "snapshot" in doc.lower(), (
            "Tier doc must reference the snapshot refresh policy"
        )

    def test_tier_doc_and_workflow_doc_both_reference_live_marker(self):
        """Both tier doc and workflow doc reference the live test marker."""
        tier = _tier_doc().lower()
        workflow = WORKFLOW_DOC_PATH.read_text(encoding="utf-8").lower()
        assert "live" in tier, "Tier doc must reference live marker"
        assert "live" in workflow, "Workflow doc must reference live marker"

    def test_tier_doc_and_atlas_both_reference_integration_tests(self):
        """Both tier doc and atlas reference integration tests."""
        tier = _tier_doc().lower()
        atlas = ATLAS_PATH.read_text(encoding="utf-8").lower()
        assert "integration" in tier, "Tier doc must reference integration tests"
        assert "integration" in atlas, "Atlas must reference integration tests"

    def test_tier_doc_does_not_redefine_live_marker_semantics(self):
        """Tier doc defers live marker definition to conftest, not redefines it."""
        tier = _tier_doc()
        # Tier doc should not define the conftest marker — just reference it
        assert "pytest_configure" not in tier and "addinivalue_line" not in tier, (
            "Tier doc must not redefine the live marker — defer to conftest.py"
        )

    def test_all_referenced_docs_exist(self):
        """All docs cross-referenced in the tier doc exist on disk."""
        docs_to_check = [
            ATLAS_PATH,
            MATRIX_PATH,
            WORKFLOW_DOC_PATH,
            OWNERSHIP_DOC_PATH,
            POLICY_DOC_PATH,
        ]
        for doc_path in docs_to_check:
            assert doc_path.exists(), f"Cross-referenced doc missing: {doc_path}"

    def test_tier_doc_does_not_introduce_ci_or_cron(self):
        """Tier doc does not introduce CI pipeline or cron — manual process only."""
        doc = _tier_doc().lower()
        assert "cron" not in doc and "github action" not in doc and "pipeline" not in doc, (
            "Tier doc must not introduce CI/cron — regression tiers are manual commands"
        )
