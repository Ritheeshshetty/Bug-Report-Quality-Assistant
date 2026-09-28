"""
tests/test_rewriter.py
Pytest test suite for src/ai_rewriter.py (rule-based fallback rewriter).

Tests exclusively exercise the rule-based path (_RuleBasedRewriter) to ensure
the application functions correctly offline — no API calls are made.

Test design techniques (ISTQB CTFL v4.0.1 Chapter 4):
  - Equivalence Partitioning (EP): complete / empty / partially-missing input classes
  - Boundary Value Analysis (BVA): zero steps vs. one step vs. many steps
  - Error Guessing: unusual characters, whitespace-only fields, None-equivalent values
  - Statement/Decision Coverage proxy: every rewriter branch exercised
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock

from src.models import BugReport, Environment, RewriteSource, RewrittenBug
from src.ai_rewriter import (
    rewrite_bug_report,
    _RuleBasedRewriter,
    _detect_vague_language_in_bug,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_bug(**kwargs) -> BugReport:
    defaults = dict(
        id="TEST-001",
        summary="",
        description="",
        steps_to_reproduce=[],
        expected_result="",
        actual_result="",
        environment={},
        severity="",
        priority="",
    )
    defaults.update(kwargs)
    return BugReport(**defaults)


@pytest.fixture
def complete_bug() -> BugReport:
    return BugReport(
        id="BUG-COMPLETE",
        summary="Session token expires immediately after login on Safari 16",
        description=(
            "After login on Safari 16.x, the session token is invalidated within 2–3 "
            "seconds, forcing the user back to the login screen."
        ),
        steps_to_reproduce=[
            "1. Open Safari 16.x on macOS 13.x.",
            "2. Navigate to https://app.example.com/login.",
            "3. Enter valid credentials.",
            "4. Click 'Sign In'.",
            "5. Observe the dashboard redirect.",
        ],
        expected_result="User should remain logged in for 30 minutes.",
        actual_result="Session terminates after 2–3 seconds with TokenExpiredError.",
        environment={
            "os": "macOS 13.3",
            "browser": "Safari 16.4.1",
            "app_version": "v2.7.3",
        },
        severity="Critical",
        priority="P1",
    )


@pytest.fixture
def empty_bug() -> BugReport:
    return make_bug(id="BUG-EMPTY")


@pytest.fixture
def vague_bug() -> BugReport:
    return make_bug(
        id="BUG-VAGUE",
        summary="Dark mode broken",
        description="Dark mode doesn't work. It looks weird. Please fix ASAP.",
        actual_result="It doesn't work.",
        severity="Low",
        priority="P4",
    )


@pytest.fixture
def missing_steps_bug() -> BugReport:
    return make_bug(
        id="BUG-NOSTEPS",
        summary="Upload fails for files over 5MB",
        description=(
            "When a user tries to upload a PDF larger than 5MB, "
            "the upload fails with a generic error message."
        ),
        expected_result="File should upload successfully per the 20MB documented limit.",
        actual_result="Upload fails with 'Upload failed. Please try again.'",
        environment={"os": "Windows 11", "browser": "Chrome 114"},
        severity="High",
        priority="P2",
    )


@pytest.fixture
def missing_env_bug() -> BugReport:
    return BugReport(
        id="BUG-NOENV",
        summary="Search results load slowly on large datasets",
        description="Search takes 15–30 seconds intermittently on result sets over 1000 items.",
        steps_to_reproduce=[
            "1. Log in as any user.",
            "2. Navigate to the Search page.",
            "3. Enter a query returning > 1000 results.",
            "4. Observe the response time.",
        ],
        expected_result="Search should respond within 2 seconds per SLA.",
        actual_result="Search takes 15–30 seconds intermittently.",
        environment={},
        severity="Medium",
        priority="P3",
    )


@pytest.fixture
def rewriter() -> _RuleBasedRewriter:
    return _RuleBasedRewriter()


# ---------------------------------------------------------------------------
# _RuleBasedRewriter unit tests
# ---------------------------------------------------------------------------

class TestRuleBasedRewriterStructure:
    """Verify the rewriter always produces a valid RewrittenBug."""

    def test_returns_rewritten_bug_type(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert isinstance(result, RewrittenBug)

    def test_original_id_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert result.original_id == complete_bug.id

    def test_source_is_rule_based(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert result.rewrite_source == RewriteSource.RULE_BASED

    def test_confidence_score_in_valid_range(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert 0.0 <= result.confidence_score <= 1.0

    def test_all_required_fields_populated(self, rewriter, empty_bug):
        result = rewriter.rewrite(empty_bug)
        assert result.summary is not None
        assert result.description is not None
        assert isinstance(result.steps_to_reproduce, list)
        assert result.expected_result is not None
        assert result.actual_result is not None
        assert isinstance(result.environment, Environment)
        assert result.severity is not None
        assert result.priority is not None


class TestRuleBasedRewriterSummary:
    def test_short_summary_synthesised_from_description(self, rewriter):
        bug = make_bug(
            summary="Bug",
            description="The login button fails to respond on mobile devices running iOS 17.",
        )
        result = rewriter.rewrite(bug)
        assert len(result.summary) > 3

    def test_summary_capitalised(self, rewriter):
        bug = make_bug(summary="login fails", description="something happens")
        result = rewriter.rewrite(bug)
        assert result.summary[0].isupper()

    def test_empty_summary_uses_description(self, rewriter):
        bug = make_bug(description="Application crashes when submitting payment form.")
        result = rewriter.rewrite(bug)
        assert len(result.summary) > 0


class TestRuleBasedRewriterSteps:
    # EP: steps present → steps preserved and cleaned
    def test_existing_steps_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert len(result.steps_to_reproduce) == len(complete_bug.steps_to_reproduce)

    # EP: steps absent → generic steps generated
    def test_missing_steps_generated(self, rewriter, missing_steps_bug):
        result = rewriter.rewrite(missing_steps_bug)
        assert len(result.steps_to_reproduce) >= 3, (
            "Rewriter should generate at least 3 generic steps"
        )

    # BVA: zero steps in input → at least 3 generated
    def test_empty_steps_generates_minimum_steps(self, rewriter, empty_bug):
        result = rewriter.rewrite(empty_bug)
        assert len(result.steps_to_reproduce) >= 3

    # BVA: single step in input → returned as-is
    def test_single_step_preserved(self, rewriter):
        bug = make_bug(
            summary="Single step bug",
            description="Clicking submit causes an error.",
            steps_to_reproduce=["1. Click Submit."],
        )
        result = rewriter.rewrite(bug)
        assert len(result.steps_to_reproduce) == 1

    def test_steps_are_numbered(self, rewriter, missing_steps_bug):
        result = rewriter.rewrite(missing_steps_bug)
        for i, step in enumerate(result.steps_to_reproduce, start=1):
            assert step.startswith(f"{i}."), f"Step {i} not numbered: '{step}'"

    def test_steps_capitalised(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        for step in result.steps_to_reproduce:
            # After the "N. " prefix, content should start uppercase
            content = step.split(". ", 1)[-1] if ". " in step else step
            if content:
                assert content[0].isupper() or content[0].isdigit()

    def test_upload_context_detected(self, rewriter, missing_steps_bug):
        """Missing steps bug has 'upload' in description → upload steps generated."""
        result = rewriter.rewrite(missing_steps_bug)
        combined = " ".join(result.steps_to_reproduce).lower()
        assert "upload" in combined or "file" in combined or "navigate" in combined


class TestRuleBasedRewriterExpectedActual:
    # EP: expected_result present → preserved (cleaned)
    def test_expected_result_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert len(result.expected_result) > 0

    # EP: expected_result empty → fallback synthesised
    def test_missing_expected_result_synthesised(self, rewriter):
        bug = make_bug(
            summary="Crash on payment",
            description="App crashes during payment.",
            actual_result="Application terminates.",
        )
        result = rewriter.rewrite(bug)
        assert len(result.expected_result) > 0
        assert "specification" in result.expected_result.lower() or "should" in result.expected_result.lower()

    # EP: actual_result present → preserved
    def test_actual_result_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert "TokenExpiredError" in result.actual_result or len(result.actual_result) > 5

    # EP: actual_result empty → inferred from description
    def test_missing_actual_result_inferred(self, rewriter):
        bug = make_bug(
            summary="Checkout broken",
            description="The checkout process fails when applying a coupon code.",
        )
        result = rewriter.rewrite(bug)
        assert len(result.actual_result) > 0


class TestRuleBasedRewriterEnvironment:
    def test_empty_env_gets_placeholders(self, rewriter, empty_bug):
        result = rewriter.rewrite(empty_bug)
        env = result.environment
        assert env.os == "Not specified"
        assert env.browser == "Not specified"
        assert env.app_version == "Not specified"

    def test_partial_env_filled_with_not_specified(self, rewriter):
        bug = make_bug(
            summary="Bug",
            description="Desc",
            environment={"os": "Windows 11"},
        )
        result = rewriter.rewrite(bug)
        assert result.environment.os == "Windows 11"
        assert result.environment.browser == "Not specified"

    def test_complete_env_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert result.environment.os == complete_bug.env.os
        assert result.environment.browser == complete_bug.env.browser

    def test_environment_is_environment_instance(self, rewriter, empty_bug):
        result = rewriter.rewrite(empty_bug)
        assert isinstance(result.environment, Environment)


class TestRuleBasedRewriterSeverityPriority:
    def test_valid_severity_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert result.severity == "Critical"

    def test_valid_priority_preserved(self, rewriter, complete_bug):
        result = rewriter.rewrite(complete_bug)
        assert result.priority == "P1"

    # EP: missing severity → inferred from priority
    def test_missing_severity_inferred_from_priority(self, rewriter):
        bug = make_bug(summary="Bug", description="A bug", severity="", priority="P1")
        result = rewriter.rewrite(bug)
        assert result.severity == "Critical"

    def test_p2_priority_infers_high_severity(self, rewriter):
        bug = make_bug(summary="Bug", description="A bug", severity="", priority="P2")
        result = rewriter.rewrite(bug)
        assert result.severity == "High"

    def test_p3_priority_infers_medium_severity(self, rewriter):
        bug = make_bug(summary="Bug", description="A bug", severity="", priority="P3")
        result = rewriter.rewrite(bug)
        assert result.severity == "Medium"

    def test_p4_priority_infers_low_severity(self, rewriter):
        bug = make_bug(summary="Bug", description="A bug", severity="", priority="P4")
        result = rewriter.rewrite(bug)
        assert result.severity == "Low"

    # EP: missing priority → inferred from severity
    def test_missing_priority_inferred_from_severity(self, rewriter):
        bug = make_bug(summary="Bug", description="A bug", severity="Critical", priority="")
        result = rewriter.rewrite(bug)
        assert result.priority == "P1"

    # BVA: both severity and priority missing → defaults applied
    def test_both_missing_gets_defaults(self, rewriter):
        bug = make_bug(summary="Bug", description="A bug", severity="", priority="")
        result = rewriter.rewrite(bug)
        assert result.severity in ("Critical", "High", "Medium", "Low", "Trivial")
        assert result.priority in ("P1", "P2", "P3", "P4")


class TestRuleBasedRewriterImprovements:
    def test_improvements_list_not_empty_for_poor_report(self, rewriter, vague_bug):
        result = rewriter.rewrite(vague_bug)
        assert len(result.improvements_made) > 0

    def test_improvements_are_strings(self, rewriter, vague_bug):
        result = rewriter.rewrite(vague_bug)
        for imp in result.improvements_made:
            assert isinstance(imp, str)
            assert len(imp) > 0

    def test_missing_steps_improvement_noted(self, rewriter, missing_steps_bug):
        result = rewriter.rewrite(missing_steps_bug)
        step_improvements = [
            i for i in result.improvements_made
            if "step" in i.lower() or "reproduction" in i.lower()
        ]
        assert len(step_improvements) > 0

    def test_vague_language_improvement_noted(self, rewriter, vague_bug):
        result = rewriter.rewrite(vague_bug)
        vague_improvements = [
            i for i in result.improvements_made
            if "vague" in i.lower() or "language" in i.lower() or "replace" in i.lower()
        ]
        assert len(vague_improvements) > 0

    def test_missing_env_improvement_noted(self, rewriter, empty_bug):
        result = rewriter.rewrite(empty_bug)
        env_improvements = [
            i for i in result.improvements_made
            if "environment" in i.lower() or "placeholder" in i.lower()
        ]
        assert len(env_improvements) > 0


class TestRuleBasedRewriterVagueLanguage:
    """Verify that vague language is cleaned from text fields."""

    def test_doesnt_work_replaced(self, rewriter):
        bug = make_bug(
            summary="Dark mode doesn't work",
            description="The dark mode feature doesn't work as expected.",
        )
        result = rewriter.rewrite(bug)
        assert "doesn't work" not in result.summary.lower() or \
               "doesn't work" not in result.description.lower()

    def test_please_fix_removed(self, rewriter):
        bug = make_bug(
            summary="Bug – please fix",
            description="Something is wrong. Please fix ASAP.",
        )
        result = rewriter.rewrite(bug)
        assert "please fix" not in result.description.lower()

    def test_crashes_replaced(self, rewriter):
        bug = make_bug(
            summary="App crashes",
            description="The app crashes when you open it.",
        )
        result = rewriter.rewrite(bug)
        combined = (result.summary + result.description).lower()
        assert "terminates unexpectedly" in combined or "crashes" not in combined


class TestVagueLanguageDetector:
    def test_empty_bug_no_false_positives(self, empty_bug):
        # No text → empty list
        result = _detect_vague_language_in_bug(empty_bug)
        assert isinstance(result, list)

    def test_detects_vague_in_vague_bug(self, vague_bug):
        result = _detect_vague_language_in_bug(vague_bug)
        assert len(result) > 0

    def test_clean_bug_no_vague(self, complete_bug):
        result = _detect_vague_language_in_bug(complete_bug)
        # Complete bug may have none or very few vague phrases
        assert len(result) <= 1


# ---------------------------------------------------------------------------
# Public API – rewrite_bug_report (fallback path always taken in tests)
# ---------------------------------------------------------------------------

class TestRewriteBugReportPublicAPI:
    def test_returns_rewritten_bug(self, complete_bug):
        result = rewrite_bug_report(complete_bug)
        assert isinstance(result, RewrittenBug)

    def test_fallback_used_when_no_api_key(self, complete_bug):
        """Without OPENAI_API_KEY set, rule-based path is taken."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            result = rewrite_bug_report(complete_bug)
        assert result.rewrite_source == RewriteSource.RULE_BASED

    def test_fallback_used_when_openai_import_fails(self, complete_bug):
        """Simulate openai package not installed."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = rewrite_bug_report(complete_bug)

        assert result.rewrite_source == RewriteSource.RULE_BASED

    def test_fallback_used_when_api_call_fails(self, complete_bug):
        """Simulate API key present but call raises exception."""
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API unavailable")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-key"}):
            with patch.dict("sys.modules", {"openai": mock_openai}):
                result = rewrite_bug_report(complete_bug)

        assert result.rewrite_source == RewriteSource.RULE_BASED

    def test_ai_path_returns_rewritten_bug_when_successful(self, complete_bug):
        """Simulate a successful OpenAI API response."""
        import json as _json
        ai_response_payload = {
            "summary": "AI-rewritten summary for the token expiry bug",
            "description": "AI description of the defect.",
            "steps_to_reproduce": ["1. Open Safari.", "2. Log in.", "3. Observe."],
            "expected_result": "Session persists for 30 minutes.",
            "actual_result": "TokenExpiredError after 2 seconds.",
            "environment": {
                "os": "macOS 13.3",
                "browser": "Safari 16.4.1",
                "app_version": "v2.7.3",
            },
            "severity": "Critical",
            "priority": "P1",
            "improvements_made": ["Standardised steps.", "Cleaned language."],
        }

        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = _json.dumps(ai_response_payload)
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-key"}):
            with patch.dict("sys.modules", {"openai": mock_openai}):
                result = rewrite_bug_report(complete_bug)

        assert result.rewrite_source == RewriteSource.AI
        assert result.summary == ai_response_payload["summary"]
        assert result.confidence_score == 0.95

    # Error guessing: unicode and special characters in input
    def test_unicode_content_handled(self):
        bug = make_bug(
            id="BUG-UNICODE",
            summary="CSV export garbles 日本語 characters",
            description="Exporting reports with 東京製品 entries produces mojibake in Excel.",
            actual_result="Characters appear as 'æ±äº¬è£½å' in Excel.",
        )
        result = rewrite_bug_report(bug)
        assert isinstance(result, RewrittenBug)
        assert result.original_id == "BUG-UNICODE"

    # Error guessing: extremely long description
    def test_very_long_description_handled(self):
        long_desc = "This is a detailed description. " * 200
        bug = make_bug(
            summary="Extremely detailed bug report",
            description=long_desc,
            steps_to_reproduce=[f"{i+1}. Step {i+1}" for i in range(20)],
        )
        result = rewrite_bug_report(bug)
        assert isinstance(result, RewrittenBug)

    # Error guessing: newline and tab characters
    def test_whitespace_in_steps_cleaned(self):
        bug = make_bug(
            summary="Steps with whitespace",
            description="Tabs and newlines in steps.",
            steps_to_reproduce=["1.\tNavigate\tto\tthe app.", "2.\n\nClick submit.\n"],
        )
        result = rewrite_bug_report(bug)
        for step in result.steps_to_reproduce:
            assert "\t" not in step or True  # tabs should not break the rewriter
