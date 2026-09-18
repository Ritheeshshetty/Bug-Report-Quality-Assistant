"""
src/scoring_engine.py
Deterministic rule-based scoring engine for Bug Report Quality Assistant.

Weights (ISTQB CTFL v4.0.1 §5.5 coverage):
  - Structural Completeness : 40 pts  (presence of ISTQB fields)
  - Reproducibility         : 35 pts  (quality of steps_to_reproduce)
  - Clarity & Context       : 25 pts  (narrative richness, specificity)

All scoring logic is pure-Python with no external dependencies beyond Pydantic.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Tuple

from src.models import (
    BugReport,
    FieldAlert,
    ScoreBreakdown,
    ScoreResult,
)


# ---------------------------------------------------------------------------
# Constants & Helpers
# ---------------------------------------------------------------------------

# Vague / noise words that reduce clarity score
_VAGUE_PHRASES = [
    "doesn't work", "not working", "broken", "weird", "strange",
    "sometimes", "occasionally", "random", "always", "never",
    "something", "something wrong", "please fix", "asap",
    "it crashes", "crashes", "bug", "issue",
]

# Action verbs expected in reproduction steps
_ACTION_VERBS = re.compile(
    r"\b(click|tap|navigate|enter|open|select|press|submit|scroll|"
    r"login|log in|sign in|fill|choose|upload|download|search|verify|"
    r"observe|wait|go to|launch|refresh|clear|type|confirm)\b",
    re.IGNORECASE,
)

# Severity & priority valid values
_VALID_SEVERITIES = {"critical", "high", "medium", "low", "trivial"}
_VALID_PRIORITIES = {"p1", "p2", "p3", "p4"}


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _has_vague_language(text: str) -> List[str]:
    text_lower = text.lower()
    return [p for p in _VAGUE_PHRASES if p in text_lower]


def _step_quality(steps: List[str]) -> float:
    """
    Return a quality ratio 0.0–1.0 for a list of reproduction steps.
    Penalises: too few steps, missing action verbs, very short text per step.
    Rewards: numbered steps, specific values (URLs, selectors, data).
    """
    if not steps:
        return 0.0

    numbered_ok = sum(
        1 for s in steps if re.match(r"^\s*\d+[\.\)]\s+\w", s)
    ) / len(steps)

    verb_ok = sum(
        1 for s in steps if _ACTION_VERBS.search(s)
    ) / len(steps)

    avg_words = sum(_word_count(s) for s in steps) / len(steps)
    length_ok = min(avg_words / 8.0, 1.0)   # 8 words per step is a good baseline

    # Ideal step count: 4–10
    count = len(steps)
    if count < 2:
        count_penalty = 0.5
    elif count <= 10:
        count_penalty = 1.0
    else:
        count_penalty = 0.85   # too many steps may reflect poor clarity

    raw = (numbered_ok * 0.30 + verb_ok * 0.40 + length_ok * 0.30) * count_penalty
    return min(raw, 1.0)


# ---------------------------------------------------------------------------
# Structural Completeness  (max 40 pts)
# ---------------------------------------------------------------------------

def _score_structural(bug: BugReport) -> Tuple[float, List[FieldAlert]]:
    """
    Evaluate presence and basic validity of ISTQB §5.5 structural fields.

    Field weights within this category:
      summary          8
      description      8
      expected_result  6
      actual_result    6
      environment      6
      severity         3
      priority         3
    Total            = 40
    """
    alerts: List[FieldAlert] = []
    score = 0.0

    # --- Summary (max 8) ---
    if not bug.summary.strip():
        alerts.append(FieldAlert(
            field_name="summary",
            severity="error",
            message="Summary is missing.",
            suggestion="Add a concise one-line title: <component> <verb> <impact>."
        ))
    else:
        wc = _word_count(bug.summary)
        if wc < 3:
            score += 4.0
            alerts.append(FieldAlert(
                field_name="summary",
                severity="warning",
                message="Summary is very short (< 3 words).",
                suggestion="Expand to clearly identify the component, action, and symptom."
            ))
        elif wc > 25:
            score += 5.0
            alerts.append(FieldAlert(
                field_name="summary",
                severity="info",
                message="Summary is quite long (> 25 words). Consider tightening.",
            ))
        else:
            score += 8.0

    # --- Description (max 8) ---
    if not bug.description.strip():
        alerts.append(FieldAlert(
            field_name="description",
            severity="error",
            message="Description is missing.",
            suggestion="Provide context, impact, and frequency of the defect."
        ))
    else:
        wc = _word_count(bug.description)
        vague = _has_vague_language(bug.description)
        base = 8.0
        if vague:
            base -= min(len(vague) * 1.0, 4.0)
            alerts.append(FieldAlert(
                field_name="description",
                severity="warning",
                message=f"Description contains vague language: {', '.join(repr(p) for p in vague[:3])}.",
                suggestion="Replace vague phrases with specific, observable behaviour."
            ))
        if wc < 10:
            base -= 3.0
            alerts.append(FieldAlert(
                field_name="description",
                severity="warning",
                message="Description is very brief (< 10 words).",
                suggestion="Add context: when it happens, who is affected, business impact."
            ))
        score += max(base, 0.0)

    # --- Expected Result (max 6) ---
    if not bug.expected_result.strip():
        alerts.append(FieldAlert(
            field_name="expected_result",
            severity="error",
            message="Expected result is missing.",
            suggestion="Describe the observable outcome the system should produce."
        ))
    else:
        wc = _word_count(bug.expected_result)
        score += 6.0 if wc >= 5 else 3.0
        if wc < 5:
            alerts.append(FieldAlert(
                field_name="expected_result",
                severity="warning",
                message="Expected result is too brief.",
                suggestion="Be specific: reference measurable outcomes, timeouts, or UI states."
            ))

    # --- Actual Result (max 6) ---
    if not bug.actual_result.strip():
        alerts.append(FieldAlert(
            field_name="actual_result",
            severity="error",
            message="Actual result is missing.",
            suggestion="Describe exactly what happens, including error messages and codes."
        ))
    else:
        wc = _word_count(bug.actual_result)
        vague = _has_vague_language(bug.actual_result)
        base = 6.0
        if vague:
            base -= min(len(vague) * 1.0, 3.0)
            alerts.append(FieldAlert(
                field_name="actual_result",
                severity="warning",
                message=f"Actual result uses vague language: {', '.join(repr(p) for p in vague[:3])}.",
                suggestion="Include error codes, stack trace excerpts, or specific UI text."
            ))
        if wc < 4:
            base -= 2.0
            alerts.append(FieldAlert(
                field_name="actual_result",
                severity="warning",
                message="Actual result is too brief.",
            ))
        score += max(base, 0.0)

    # --- Environment (max 6) ---
    env = bug.env
    if env.is_empty():
        alerts.append(FieldAlert(
            field_name="environment",
            severity="error",
            message="Environment details are entirely missing.",
            suggestion="Include OS, browser/client version, and application version at minimum."
        ))
    else:
        filled = env.filled_fields()
        env_score = min(filled * 1.5, 6.0)
        score += env_score
        if filled < 3:
            alerts.append(FieldAlert(
                field_name="environment",
                severity="warning",
                message=f"Environment is partially specified ({filled} field(s) provided).",
                suggestion="Add OS version, browser version, and app version."
            ))

    # --- Severity (max 3) ---
    if not bug.severity.strip():
        alerts.append(FieldAlert(
            field_name="severity",
            severity="warning",
            message="Severity is not specified.",
            suggestion="Assign one of: Critical, High, Medium, Low, Trivial."
        ))
    elif bug.severity.lower() not in _VALID_SEVERITIES:
        score += 1.5
        alerts.append(FieldAlert(
            field_name="severity",
            severity="info",
            message=f"Unrecognised severity value: '{bug.severity}'.",
        ))
    else:
        score += 3.0

    # --- Priority (max 3) ---
    if not bug.priority.strip():
        alerts.append(FieldAlert(
            field_name="priority",
            severity="warning",
            message="Priority is not specified.",
            suggestion="Assign one of: P1 (Critical), P2 (High), P3 (Medium), P4 (Low)."
        ))
    elif bug.priority.upper() not in {p.upper() for p in _VALID_PRIORITIES}:
        score += 1.5
        alerts.append(FieldAlert(
            field_name="priority",
            severity="info",
            message=f"Unrecognised priority value: '{bug.priority}'.",
        ))
    else:
        score += 3.0

    return round(min(score, 40.0), 2), alerts


# ---------------------------------------------------------------------------
# Reproducibility  (max 35 pts)
# ---------------------------------------------------------------------------

def _score_reproducibility(bug: BugReport) -> Tuple[float, List[FieldAlert]]:
    """
    Evaluate how well the report enables a developer to reproduce the defect.

    Sub-criteria:
      steps_to_reproduce quality  20 pts
      pre-conditions / data        8 pts (inferred from step text & description)
      attachments / evidence       7 pts
    """
    alerts: List[FieldAlert] = []
    score = 0.0

    # --- Steps to reproduce (max 20) ---
    if not bug.steps_to_reproduce:
        alerts.append(FieldAlert(
            field_name="steps_to_reproduce",
            severity="error",
            message="Steps to reproduce are missing.",
            suggestion=(
                "List numbered steps a developer can follow to reproduce the defect. "
                "Include specific data values, URLs, and user roles."
            )
        ))
    else:
        quality = _step_quality(bug.steps_to_reproduce)
        step_score = quality * 20.0
        score += step_score

        if quality < 0.5:
            alerts.append(FieldAlert(
                field_name="steps_to_reproduce",
                severity="warning",
                message="Steps to reproduce are present but lack specificity or action verbs.",
                suggestion="Use imperative verbs (Click, Enter, Navigate). Include exact data."
            ))
        elif quality < 0.75:
            alerts.append(FieldAlert(
                field_name="steps_to_reproduce",
                severity="info",
                message="Steps to reproduce could be more detailed or numbered.",
            ))

    # --- Pre-conditions / test data (max 8, inferred) ---
    combined_text = " ".join([bug.description] + bug.steps_to_reproduce).lower()
    pre_signals = [
        ("log in", 2), ("logged in", 2), ("registered user", 2),
        ("test data", 2), ("sample", 1), ("account", 1),
        ("admin", 1), ("environment", 1), ("prerequisite", 2),
        ("before", 1), ("setup", 2), ("precondition", 3),
        ("existing", 1),
    ]
    pre_score = 0.0
    for phrase, pts in pre_signals:
        if phrase in combined_text:
            pre_score += pts
    pre_score = min(pre_score, 8.0)
    score += pre_score

    if pre_score < 2.0:
        alerts.append(FieldAlert(
            field_name="steps_to_reproduce",
            severity="info",
            message="Pre-conditions or required test data are not mentioned.",
            suggestion="State which user role, data state, or setup is required to reproduce."
        ))

    # --- Attachments / evidence (max 7) ---
    if not bug.attachments:
        alerts.append(FieldAlert(
            field_name="attachments",
            severity="info",
            message="No attachments provided.",
            suggestion="Attach screenshots, screen recordings, or log files to accelerate triage."
        ))
    else:
        count = len(bug.attachments)
        score += min(count * 2.5, 7.0)

    return round(min(score, 35.0), 2), alerts


# ---------------------------------------------------------------------------
# Clarity & Context  (max 25 pts)
# ---------------------------------------------------------------------------

def _score_clarity(bug: BugReport) -> Tuple[float, List[FieldAlert]]:
    """
    Evaluate narrative clarity, specificity, and actionability.

    Sub-criteria:
      word richness / specificity  10 pts
      technical identifiers        8 pts  (version numbers, error codes, URLs)
      single-issue focus           7 pts
    """
    alerts: List[FieldAlert] = []
    score = 0.0

    full_text = " ".join(filter(None, [
        bug.summary, bug.description,
        bug.expected_result, bug.actual_result,
        *bug.steps_to_reproduce
    ]))

    # --- Word richness / specificity (max 10) ---
    total_words = _word_count(full_text)
    vague = _has_vague_language(full_text)

    if total_words < 20:
        richness = 2.0
        alerts.append(FieldAlert(
            field_name="description",
            severity="warning",
            message="Report is very short overall (< 20 words total).",
            suggestion="Provide more context, impact description, and specific observations."
        ))
    elif total_words < 50:
        richness = 5.0
    elif total_words < 100:
        richness = 7.5
    else:
        richness = 10.0

    vague_penalty = min(len(vague) * 1.0, 5.0)
    richness = max(richness - vague_penalty, 0.0)
    score += richness

    # --- Technical identifiers (max 8) ---
    # Look for version numbers, error codes, URLs, HTTP codes, log excerpts
    tech_patterns = [
        (r"\bv?\d+\.\d+[\.\d]*\b", 1.5),       # version numbers
        (r"https?://\S+", 2.0),                   # URLs
        (r"\b[A-Z][a-zA-Z]+Error\b", 2.0),       # error class names
        (r"\b\d{3}\b", 1.0),                      # HTTP status codes / error codes
        (r"Error\s+\d+:", 2.0),                   # Twilio-style error codes
        (r"[A-Z]{2,}-\d{3,}", 1.5),              # JIRA-style IDs
        (r"\b(SKU|API|JWT|OTP|BOM|HAR)\b", 1.0), # domain acronyms
    ]
    tech_score = 0.0
    for pattern, pts in tech_patterns:
        if re.search(pattern, full_text):
            tech_score += pts
    tech_score = min(tech_score, 8.0)
    score += tech_score

    if tech_score < 2.0:
        alerts.append(FieldAlert(
            field_name="description",
            severity="info",
            message="Report lacks technical identifiers (version numbers, error codes, URLs).",
            suggestion="Include exact version strings, error codes, or relevant URLs."
        ))

    # --- Single-issue focus (max 7) ---
    # Heuristic: check for conjunctions that might signal multiple bugs
    multi_issue_signals = re.findall(
        r"\b(also|additionally|furthermore|another issue|second bug|another bug)\b",
        full_text, re.IGNORECASE
    )
    if multi_issue_signals:
        score += 3.5
        alerts.append(FieldAlert(
            field_name="description",
            severity="warning",
            message="Report may describe multiple issues (detected: "
                    f"'{multi_issue_signals[0]}').",
            suggestion="File separate bug reports for each distinct defect."
        ))
    else:
        score += 7.0

    return round(min(score, 25.0), 2), alerts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_bug_report(bug: BugReport) -> ScoreResult:
    """
    Compute the composite quality score for a BugReport.

    Returns a ScoreResult containing:
      - total_score (0–100)
      - per-category breakdown
      - list of FieldAlert objects
      - human-readable grade
    """
    struct_score, struct_alerts = _score_structural(bug)
    repro_score, repro_alerts = _score_reproducibility(bug)
    clarity_score, clarity_alerts = _score_clarity(bug)

    all_alerts = struct_alerts + repro_alerts + clarity_alerts
    total = struct_score + repro_score + clarity_score

    breakdown = ScoreBreakdown(
        structural_completeness=struct_score,
        reproducibility=repro_score,
        clarity_context=clarity_score,
    )

    return ScoreResult(
        bug_id=bug.id,
        total_score=round(total, 2),
        grade=ScoreResult.grade_from_score(total),
        breakdown=breakdown,
        alerts=all_alerts,
        scored_at=datetime.now(timezone.utc).isoformat(),
    )
