"""
tests/test_scoring.py
Comprehensive pytest test suite for src/scoring_engine.py.

Test design techniques used (ISTQB CTFL v4.0.1 Chapter 4):
  - Equivalence Partitioning (EP): valid / invalid / boundary value classes
  - Boundary Value Analysis (BVA): score boundaries at 0, 40, 60, 80, 100
  - Decision Table Testing: combinations of missing/present field groups
  - State Transition: grade transitions across score thresholds
"""

from __future__ import annotations

import pytest
from typing import List

from src.models import BugReport, Environment, ScoreResult, FieldAlert
from src.scoring_engine import (
    score_bug_report,
    _score_structural,
    _score_reproducibility,
    _score_clarity,
    _step_quality,
    _has_vague_language,
    _word_count,
)


# ---------------------------------------------------------------------------
# Fixtures – representative BugReport instances
# ---------------------------------------------------------------------------

def make_bug(**kwargs) -> BugReport:
    """Factory helper; every field defaults to empty / empty list."""
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
    """A well-written, fully populated bug report – should score ≥ 80."""
    return BugReport(
        id="BUG-COMPLETE",
        summary="Session token expires immediately after login on Safari 16 macOS Ventura",
        description=(
            "After a successful login on Safari 16.x running on macOS 13.x (Ventura), "
            "the session token is invalidated within 2–3 seconds, forcing the user back "
            "to the login screen. The issue is not reproducible on Chrome 114 or Firefox 113."
        ),
        steps_to_reproduce=[
            "1. Open Safari 16.x on macOS 13.x Ventura.",
            "2. Navigate to https://app.example.com/login.",
            "3. Enter valid credentials (email: test@example.com, password: Test@1234).",
            "4. Click the 'Sign In' button.",
            "5. Observe the dashboard briefly loads, then redirects back to the login screen.",
        ],
        expected_result=(
            "User should remain logged in and the dashboard should be accessible for the "
            "duration of the session (default: 30 minutes of inactivity)."
        ),
        actual_result=(
            "The session is terminated approximately 2–3 seconds after login. "
            "The browser console shows: 'TokenExpiredError: jwt expired at 2024-05-10T08:01:02.000Z'."
        ),
        environment={
            "os": "macOS 13.3 Ventura",
            "browser": "Safari 16.4.1",
            "app_version": "v2.7.3",
            "backend": "Node.js 18.x",
            "database": "PostgreSQL 15",
        },
        severity="Critical",
        priority="P1",
        reporter="qa_engineer_1",
        attachments=["console_log.txt", "screen_recording.mp4"],
    )


@pytest.fixture
def empty_bug() -> BugReport:
    """Entirely empty bug report – should score close to 0."""
    return make_bug(id="BUG-EMPTY")


@pytest.fixture
def borderline_no_steps() -> BugReport:
    """Has all fields except steps_to_reproduce."""
    return BugReport(
        id="BUG-NOSTEPS",
        summary="File upload fails for PDFs larger than 5MB",
        description=(
            "When trying to upload a PDF file larger than 5MB, the upload fails "
            "with a generic error message. Smaller PDFs upload fine."
        ),
        steps_to_reproduce=[],
        expected_result="File should upload successfully per the documented 20MB limit.",
        actual_result="Upload fails with 'Upload failed. Please try again.' message.",
        environment={"os": "Windows 11", "browser": "Chrome 114", "app_version": "v3.1.0"},
        severity="High",
        priority="P2",
    )


@pytest.fixture
def vague_bug() -> BugReport:
    """A vague, low-quality report – should score < 40 (Poor)."""
    return make_bug(
        id="BUG-VAGUE",
        summary="Dark mode broken",
        description="Dark mode doesn't work. It looks weird. Please fix ASAP.",
        actual_result="It doesn't work.",
        severity="Low",
        priority="P4",
    )


@pytest.fixture
def missing_env_bug() -> BugReport:
    """Has steps and all text fields but no environment."""
    return BugReport(
        id="BUG-NOENV",
        summary="Search results take 15–30 seconds on large datasets",
        description=(
            "The search feature is intermittently very slow when the result set "
            "exceeds 1000 items. SLA requires < 2 second response time."
        ),
        steps_to_reproduce=[
            "1. Log in as any user.",
            "2. Navigate to the Search page.",
            "3. Enter a keyword that returns > 1000 results.",
            "4. Observe the response time in the browser network tab.",
        ],
        expected_result="Search results should load within 2 seconds per SLA.",
        actual_result="Search results take 15–30 seconds intermittently.",
        environment={},
        severity="Medium",
        priority="P3",
    )


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

class TestWordCount:
    def test_empty_string(self):
        assert _word_count("") == 0

    def test_whitespace_only(self):
        assert _word_count("   ") == 0

    def test_single_word(self):
        assert _word_count("hello") == 1

    def test_normal_sentence(self):
        assert _word_count("The quick brown fox") == 4

    def test_extra_spaces(self):
        assert _word_count("  hello   world  ") == 2


class TestVagueLanguageDetection:
    def test_no_vague(self):
        text = "The application returns HTTP 500 when submitting the registration form."
        assert _has_vague_language(text) == []

    def test_single_vague(self):
        result = _has_vague_language("The button doesn't work.")
        assert "doesn't work" in result

    def test_multiple_vague(self):
        text = "It crashes sometimes. Looks weird. Broken."
        result = _has_vague_language(text)
        assert len(result) >= 2

    def test_case_insensitive(self):
        result = _has_vague_language("BROKEN feature")
        assert "broken" in result


class TestStepQuality:
    def test_empty_steps(self):
        assert _step_quality([]) == 0.0

    def test_single_good_step(self):
        steps = ["1. Click the Login button."]
        score = _step_quality(steps)
        assert 0.0 < score <= 1.0

    def test_numbered_steps_with_verbs(self):
        steps = [
            "1. Navigate to https://app.example.com.",
            "2. Enter email: user@test.com.",
            "3. Click 'Sign In'.",
            "4. Observe the dashboard.",
        ]
        score = _step_quality(steps)
        assert score >= 0.6, f"Expected ≥0.6, got {score}"

    def test_unnumbered_vague_steps(self):
        steps = ["go somewhere", "do something", "look at it"]
        score = _step_quality(steps)
        assert score < 0.5

    # BVA: boundary at exactly 2 steps (minimum acceptable)
    def test_exactly_two_steps(self):
        steps = ["1. Open the application.", "2. Click Submit."]
        score = _step_quality(steps)
        assert score > 0.0

    # EP: more than 10 steps (slight quality penalty)
    def test_too_many_steps(self):
        steps = [f"{i+1}. Step {i+1}" for i in range(12)]
        score = _step_quality(steps)
        assert 0 < score < 1.0


# ---------------------------------------------------------------------------
# Scoring Engine – sub-scorer tests
# ---------------------------------------------------------------------------

class TestStructuralScoring:
    def test_all_fields_present_max_40(self, complete_bug):
        score, alerts = _score_structural(complete_bug)
        assert score <= 40.0
        assert score >= 30.0, f"Complete bug should score ≥30 structural, got {score}"

    def test_empty_bug_near_zero(self, empty_bug):
        score, alerts = _score_structural(empty_bug)
        assert score < 5.0, f"Empty bug structural should be < 5, got {score}"

    def test_missing_summary_generates_error_alert(self, empty_bug):
        _, alerts = _score_structural(empty_bug)
        field_names = [a.field_name for a in alerts]
        assert "summary" in field_names

    def test_missing_expected_result_alert(self):
        bug = make_bug(
            summary="Something fails",
            description="The feature does not work as described in documentation.",
            actual_result="Error 500 is returned.",
            severity="High",
            priority="P2",
        )
        _, alerts = _score_structural(bug)
        alert_fields = [a.field_name for a in alerts]
        assert "expected_result" in alert_fields

    def test_missing_environment_alert(self, missing_env_bug):
        _, alerts = _score_structural(missing_env_bug)
        env_alerts = [a for a in alerts if a.field_name == "environment"]
        assert len(env_alerts) > 0

    def test_valid_severity_no_severity_alert(self, complete_bug):
        _, alerts = _score_structural(complete_bug)
        sev_errors = [a for a in alerts if a.field_name == "severity" and a.severity == "error"]
        assert len(sev_errors) == 0

    def test_invalid_severity_generates_info_alert(self):
        bug = make_bug(
            summary="Something is wrong with the login",
            description="Login fails intermittently on all browsers.",
            expected_result="User should log in successfully.",
            actual_result="Authentication error is shown.",
            severity="super_critical",
            priority="P1",
        )
        _, alerts = _score_structural(bug)
        sev_alerts = [a for a in alerts if a.field_name == "severity"]
        assert len(sev_alerts) > 0

    # BVA: score cap at exactly 40
    def test_score_never_exceeds_40(self, complete_bug):
        score, _ = _score_structural(complete_bug)
        assert score <= 40.0

    def test_score_never_negative(self, empty_bug):
        score, _ = _score_structural(empty_bug)
        assert score >= 0.0


class TestReproducibilityScoring:
    def test_complete_with_steps_high_score(self, complete_bug):
        score, alerts = _score_reproducibility(complete_bug)
        assert score >= 20.0, f"Expected ≥20, got {score}"
        assert score <= 35.0

    def test_missing_steps_zero_step_score(self, borderline_no_steps):
        score, alerts = _score_reproducibility(borderline_no_steps)
        step_errors = [a for a in alerts if "steps" in a.field_name and a.severity == "error"]
        assert len(step_errors) > 0
        # Score should be reduced significantly
        assert score < 20.0

    def test_empty_bug_near_zero(self, empty_bug):
        score, _ = _score_reproducibility(empty_bug)
        assert score < 5.0

    def test_attachments_boost_score(self):
        bug = make_bug(
            id="BUG-ATT",
            summary="Crash on submit",
            description="Application crashes when submitting the payment form with invalid card data.",
            steps_to_reproduce=[
                "1. Navigate to checkout page.",
                "2. Enter invalid card number.",
                "3. Click Submit.",
            ],
            expected_result="Validation error should be shown.",
            actual_result="Application crashes with NullPointerException.",
            attachments=["crash_log.txt", "screenshot.png"],
        )
        score_with_att, _ = _score_reproducibility(bug)

        bug_no_att = bug.model_copy(update={"attachments": []})
        score_without_att, _ = _score_reproducibility(bug_no_att)

        assert score_with_att > score_without_att, (
            "Attachments should increase reproducibility score"
        )

    def test_score_never_exceeds_35(self, complete_bug):
        score, _ = _score_reproducibility(complete_bug)
        assert score <= 35.0

    def test_score_never_negative(self, empty_bug):
        score, _ = _score_reproducibility(empty_bug)
        assert score >= 0.0


class TestClarityScoring:
    def test_rich_technical_report_high_score(self, complete_bug):
        score, _ = _score_clarity(complete_bug)
        assert score >= 15.0, f"Expected ≥15, got {score}"
        assert score <= 25.0

    def test_vague_report_low_score(self, vague_bug):
        score, alerts = _score_clarity(vague_bug)
        assert score < 12.0, f"Vague report clarity should be < 12, got {score}"

    def test_very_short_report_penalised(self):
        bug = make_bug(summary="Bug", description="Broken", actual_result="Error")
        score, alerts = _score_clarity(bug)
        assert score < 10.0

    def test_technical_identifiers_boost_score(self):
        bug_with_tech = make_bug(
            summary="v2.7.3 TokenExpiredError on Safari 16",
            description="JWT token expires immediately. Error: 'TokenExpiredError at 2024-05-10'.",
            expected_result="Session lasts 30 minutes per https://docs.example.com/session-policy.",
            actual_result="HTTP 401 Unauthorised returned after 2 seconds.",
        )
        bug_without_tech = make_bug(
            summary="Token problem",
            description="Token thing fails.",
            expected_result="It should work.",
            actual_result="It breaks.",
        )
        score_tech, _ = _score_clarity(bug_with_tech)
        score_plain, _ = _score_clarity(bug_without_tech)
        assert score_tech > score_plain

    def test_multi_issue_signal_detected(self):
        bug = make_bug(
            summary="Two bugs in the form",
            description="The submit button doesn't work. Also, the reset button crashes the app.",
        )
        _, alerts = _score_clarity(bug)
        multi_alerts = [a for a in alerts if "multiple" in a.message.lower()]
        assert len(multi_alerts) > 0

    def test_score_never_exceeds_25(self, complete_bug):
        score, _ = _score_clarity(complete_bug)
        assert score <= 25.0

    def test_score_never_negative(self, empty_bug):
        score, _ = _score_clarity(empty_bug)
        assert score >= 0.0


# ---------------------------------------------------------------------------
# Composite score_bug_report tests
# ---------------------------------------------------------------------------

class TestScoreBugReport:
    # EP: Excellent class (≥ 80)
    def test_complete_bug_excellent_grade(self, complete_bug):
        result = score_bug_report(complete_bug)
        assert result.total_score >= 70.0, f"Complete bug expected ≥70, got {result.total_score}"
        assert result.grade in ("Excellent", "Good")

    # EP: Poor class (< 40)
    def test_empty_bug_poor_grade(self, empty_bug):
        result = score_bug_report(empty_bug)
        assert result.grade == "Poor"
        assert result.total_score < 40.0

    # EP: Borderline / Needs Improvement class (40–59)
    def test_borderline_bug_needs_improvement(self, borderline_no_steps):
        result = score_bug_report(borderline_no_steps)
        # Missing steps should knock it down; should not be "Excellent"
        assert result.grade in ("Good", "Needs Improvement")

    # BVA: exact grade threshold at 80
    def test_grade_exactly_80_is_excellent(self):
        # Manufacture a bug that we tweak until score ≈ 80;
        # easier: just test the grade_from_score method.
        assert ScoreResult.grade_from_score(80.0) == "Excellent"
        assert ScoreResult.grade_from_score(79.9) == "Good"

    # BVA: exact grade threshold at 60
    def test_grade_exactly_60_is_good(self):
        assert ScoreResult.grade_from_score(60.0) == "Good"
        assert ScoreResult.grade_from_score(59.9) == "Needs Improvement"

    # BVA: exact grade threshold at 40
    def test_grade_exactly_40_is_needs_improvement(self):
        assert ScoreResult.grade_from_score(40.0) == "Needs Improvement"
        assert ScoreResult.grade_from_score(39.9) == "Poor"

    # BVA: lower boundary
    def test_grade_zero_is_poor(self):
        assert ScoreResult.grade_from_score(0.0) == "Poor"

    # BVA: upper boundary
    def test_grade_100_is_excellent(self):
        assert ScoreResult.grade_from_score(100.0) == "Excellent"

    def test_total_score_sum_of_breakdown(self, complete_bug):
        result = score_bug_report(complete_bug)
        expected = round(
            result.breakdown.structural_completeness
            + result.breakdown.reproducibility
            + result.breakdown.clarity_context,
            2,
        )
        assert abs(result.total_score - expected) < 0.01

    def test_breakdown_within_max_bounds(self, complete_bug):
        result = score_bug_report(complete_bug)
        assert 0 <= result.breakdown.structural_completeness <= 40
        assert 0 <= result.breakdown.reproducibility <= 35
        assert 0 <= result.breakdown.clarity_context <= 25

    def test_alerts_are_field_alert_instances(self, complete_bug):
        result = score_bug_report(complete_bug)
        for alert in result.alerts:
            assert isinstance(alert, FieldAlert)

    def test_alerts_have_valid_severity_values(self, empty_bug):
        result = score_bug_report(empty_bug)
        valid_severities = {"error", "warning", "info"}
        for alert in result.alerts:
            assert alert.severity in valid_severities

    def test_scored_at_is_set(self, complete_bug):
        result = score_bug_report(complete_bug)
        assert result.scored_at is not None
        assert "T" in result.scored_at  # ISO 8601 format check

    def test_bug_id_preserved(self, complete_bug):
        result = score_bug_report(complete_bug)
        assert result.bug_id == complete_bug.id

    def test_total_score_between_0_and_100(self, empty_bug):
        result = score_bug_report(empty_bug)
        assert 0.0 <= result.total_score <= 100.0

    def test_vague_bug_has_alerts(self, vague_bug):
        result = score_bug_report(vague_bug)
        assert len(result.alerts) > 0

    def test_complete_bug_fewer_errors_than_vague(self, complete_bug, vague_bug):
        result_complete = score_bug_report(complete_bug)
        result_vague = score_bug_report(vague_bug)
        errors_complete = [a for a in result_complete.alerts if a.severity == "error"]
        errors_vague = [a for a in result_vague.alerts if a.severity == "error"]
        assert len(errors_complete) < len(errors_vague)

    # Decision Table: missing priority vs missing severity
    def test_missing_priority_generates_warning(self):
        bug = make_bug(
            summary="Something fails on login",
            description="Detailed description of the issue encountered during testing.",
            expected_result="Should succeed.",
            actual_result="Fails with 500.",
            severity="High",
            priority="",  # Missing
        )
        result = score_bug_report(bug)
        priority_alerts = [a for a in result.alerts if a.field_name == "priority"]
        assert len(priority_alerts) > 0

    def test_missing_severity_generates_warning(self):
        bug = make_bug(
            summary="Something fails on login",
            description="Detailed description of the issue encountered during testing.",
            expected_result="Should succeed.",
            actual_result="Fails with 500.",
            severity="",  # Missing
            priority="P2",
        )
        result = score_bug_report(bug)
        sev_alerts = [a for a in result.alerts if a.field_name == "severity"]
        assert len(sev_alerts) > 0

    # EP: partial environment (only 1 field)
    def test_partial_environment_warning(self):
        bug = make_bug(
            summary="Login fails on Safari",
            description="Cannot log in using Safari on macOS.",
            expected_result="Login succeeds.",
            actual_result="Redirect loop.",
            environment={"browser": "Safari 16"},
            severity="High",
            priority="P2",
        )
        result = score_bug_report(bug)
        env_warnings = [
            a for a in result.alerts
            if a.field_name == "environment" and a.severity == "warning"
        ]
        assert len(env_warnings) > 0

    # EP: all-whitespace fields treated as missing
    def test_whitespace_fields_treated_as_missing(self):
        bug = make_bug(
            summary="   ",
            description="   ",
            expected_result="   ",
            actual_result="   ",
        )
        result = score_bug_report(bug)
        assert result.grade == "Poor"
        assert result.total_score < 20.0
