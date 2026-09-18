"""
src/ai_rewriter.py
Bug report rewriter for Bug Report Quality Assistant.

Strategy:
  1. PRIMARY – OpenAI GPT-4o via the openai SDK (requires OPENAI_API_KEY env var).
  2. FALLBACK – Deterministic rule-based rewriter that always works offline.

The module auto-detects which strategy to use:
  - If OPENAI_API_KEY is set and the openai package is installed → AI mode.
  - Otherwise → rule-based fallback (no API calls, no external network).

Both strategies return a `RewrittenBug` with the same schema so callers
are completely decoupled from the rewrite source.
"""

from __future__ import annotations

import json
import logging
import os
import re
import textwrap
from typing import List, Optional

from src.models import (
    BugReport,
    Environment,
    RewriteSource,
    RewrittenBug,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template for AI mode (ISTQB §5.5 aligned)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = textwrap.dedent("""
You are an ISTQB-certified QA Engineer specialising in defect management.
Rewrite the provided bug report strictly following ISTQB CTFL v4.0.1 Section 5.5
defect attributes.

OUTPUT RULES (strict JSON — no markdown fences):
{
  "summary": "<concise, action-oriented title: Component + Verb + Symptom>",
  "description": "<one paragraph: context, affected users, business impact, frequency>",
  "steps_to_reproduce": ["1. <imperative verb> ...", "2. ...", ...],
  "expected_result": "<observable, measurable expected state>",
  "actual_result": "<observable actual state with exact error text/codes if available>",
  "environment": {
    "os": "<OS name and version or 'Not specified'>",
    "browser": "<browser and version or 'Not specified'>",
    "app_version": "<version or 'Not specified'>",
    "backend": "<stack or 'Not specified'>",
    "database": "<DB or 'Not specified'>"
  },
  "severity": "<Critical | High | Medium | Low | Trivial>",
  "priority": "<P1 | P2 | P3 | P4>",
  "improvements_made": ["<short description of each improvement>"]
}

Guidelines:
- Use imperative verbs in every step (Click, Navigate, Enter, Select, Observe).
- Replace vague phrases ('doesn't work', 'broken') with specific observable behaviour.
- Infer missing environment details as 'Not specified' — never fabricate versions.
- Keep summary under 20 words.
- Produce 3–8 numbered reproduction steps.
""").strip()


# ---------------------------------------------------------------------------
# AI Rewriter (OpenAI GPT-4o)
# ---------------------------------------------------------------------------

def _rewrite_with_ai(bug: BugReport) -> Optional[RewrittenBug]:
    """
    Attempt to rewrite using OpenAI GPT-4o.
    Returns None if the SDK is unavailable or the API call fails.
    """
    try:
        import openai  # type: ignore
    except ImportError:
        logger.debug("openai package not installed; skipping AI rewrite.")
        return None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.debug("OPENAI_API_KEY not set; skipping AI rewrite.")
        return None

    client = openai.OpenAI(api_key=api_key)

    user_message = json.dumps({
        "id": bug.id,
        "summary": bug.summary,
        "description": bug.description,
        "steps_to_reproduce": bug.steps_to_reproduce,
        "expected_result": bug.expected_result,
        "actual_result": bug.actual_result,
        "environment": bug.environment if isinstance(bug.environment, dict)
                       else bug.environment.model_dump(exclude_none=True),
        "severity": bug.severity,
        "priority": bug.priority,
    }, indent=2)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        env_data = data.get("environment", {})
        env = Environment.from_dict(env_data) if isinstance(env_data, dict) else Environment()

        return RewrittenBug(
            original_id=bug.id,
            summary=data.get("summary", bug.summary),
            description=data.get("description", bug.description),
            steps_to_reproduce=data.get("steps_to_reproduce", bug.steps_to_reproduce),
            expected_result=data.get("expected_result", bug.expected_result),
            actual_result=data.get("actual_result", bug.actual_result),
            environment=env,
            severity=data.get("severity", bug.severity or "Medium"),
            priority=data.get("priority", bug.priority or "P3"),
            rewrite_source=RewriteSource.AI,
            improvements_made=data.get("improvements_made", []),
            confidence_score=0.95,
        )
    except Exception as exc:
        logger.warning("AI rewrite failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Rule-Based Fallback Rewriter
# ---------------------------------------------------------------------------

class _RuleBasedRewriter:
    """
    Deterministic rewriter that applies a fixed set of transformations to
    produce an ISTQB-compliant report without any network calls.
    """

    # Vague → specific replacement map
    _REPLACEMENTS = {
        r"\bdoesn[''`]?t work\b": "does not function as expected",
        r"\bnot working\b": "fails to operate as designed",
        r"\bbroken\b": "non-functional",
        r"\bweird\b": "unexpected",
        r"\bstrange\b": "anomalous",
        r"\bsometimes\b": "intermittently (frequency: unconfirmed)",
        r"\boccasionally\b": "intermittently",
        r"\bplease fix\b": "",
        r"\bASAP\b": "",
        r"\bit crashes\b": "the application terminates unexpectedly",
        r"\bcrashes\b": "terminates unexpectedly",
    }

    def _clean_text(self, text: str) -> str:
        result = text
        for pattern, replacement in self._REPLACEMENTS.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        # Collapse multiple spaces
        result = re.sub(r"  +", " ", result).strip()
        return result

    def _build_summary(self, bug: BugReport) -> str:
        summary = self._clean_text(bug.summary)
        if not summary or len(summary.split()) < 3:
            # Synthesise from description
            desc_words = bug.description.split()[:12]
            summary = " ".join(desc_words) + ("..." if len(bug.description.split()) > 12 else "")
        # Ensure title case for first word
        if summary:
            summary = summary[0].upper() + summary[1:]
        return summary

    def _build_description(self, bug: BugReport) -> str:
        desc = self._clean_text(bug.description)
        if not desc:
            desc = (
                f"The defect '{bug.summary}' has been observed in the application. "
                "Further investigation is required to determine root cause and impact."
            )
        return desc

    def _build_steps(self, bug: BugReport) -> List[str]:
        if bug.steps_to_reproduce:
            cleaned = []
            for i, step in enumerate(bug.steps_to_reproduce, start=1):
                step_text = re.sub(r"^\s*\d+[\.\)]\s*", "", step).strip()
                step_text = self._clean_text(step_text)
                if step_text:
                    # Ensure step starts with capital letter
                    step_text = step_text[0].upper() + step_text[1:]
                    cleaned.append(f"{i}. {step_text}")
            return cleaned if cleaned else self._generate_generic_steps(bug)
        return self._generate_generic_steps(bug)

    def _generate_generic_steps(self, bug: BugReport) -> List[str]:
        """Generate minimal plausible steps from description context."""
        steps = [
            "1. Set up the required test environment (see Environment section).",
            "2. Log in with appropriate user credentials.",
        ]
        desc_lower = (bug.description + " " + bug.summary).lower()

        if any(w in desc_lower for w in ["upload", "file"]):
            steps.append("3. Navigate to the file upload section.")
            steps.append("4. Select the relevant file for upload and initiate the upload.")
        elif any(w in desc_lower for w in ["search", "query", "filter"]):
            steps.append("3. Navigate to the search or filter interface.")
            steps.append("4. Enter the relevant search query and submit.")
        elif any(w in desc_lower for w in ["login", "sign in", "log in", "auth"]):
            steps.append("3. Enter valid credentials on the login page.")
            steps.append("4. Click 'Sign In' and observe the result.")
        elif any(w in desc_lower for w in ["dark mode", "theme", "colour", "color"]):
            steps.append("3. Navigate to Settings > Appearance.")
            steps.append("4. Toggle the Dark Mode switch.")
        else:
            steps.append("3. Navigate to the feature described in the summary.")
            steps.append("4. Perform the action that triggers the defect.")

        steps.append(f"{len(steps) + 1}. Observe the actual result and compare to the expected result.")
        return steps

    def _build_expected(self, bug: BugReport) -> str:
        if bug.expected_result.strip():
            result = self._clean_text(bug.expected_result)
            return result[0].upper() + result[1:] if result else result
        return (
            "The application should behave according to documented specifications "
            "without errors, data corruption, or unexpected termination."
        )

    def _build_actual(self, bug: BugReport) -> str:
        if bug.actual_result.strip():
            actual = self._clean_text(bug.actual_result)
            return actual[0].upper() + actual[1:] if actual else actual
        # Try to extract from description
        desc = self._clean_text(bug.description)
        if desc:
            return f"Based on the report: {desc}"
        return "The system behaves incorrectly as described in the summary. Exact error output unavailable."

    def _build_environment(self, bug: BugReport) -> Environment:
        env = bug.env
        if env.is_empty():
            return Environment(
                os="Not specified",
                browser="Not specified",
                app_version="Not specified",
            )
        # Fill in blanks with "Not specified"
        return Environment(
            os=env.os or "Not specified",
            browser=env.browser or "Not specified",
            app_version=env.app_version or "Not specified",
            backend=env.backend or None,
            database=env.database or None,
            extra=env.extra,
        )

    def _build_severity(self, bug: BugReport) -> str:
        valid = {"Critical", "High", "Medium", "Low", "Trivial"}
        if bug.severity in valid:
            return bug.severity
        # Infer from priority
        infer_map = {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}
        return infer_map.get(bug.priority.upper(), "Medium")

    def _build_priority(self, bug: BugReport) -> str:
        valid = {"P1", "P2", "P3", "P4"}
        if bug.priority.upper() in valid:
            return bug.priority.upper()
        # Infer from severity
        infer_map = {"Critical": "P1", "High": "P2", "Medium": "P3", "Low": "P4"}
        return infer_map.get(bug.severity, "P3")

    def _detect_improvements(self, bug: BugReport, rewritten: "RewrittenBug") -> List[str]:
        improvements = []
        if not bug.steps_to_reproduce and rewritten.steps_to_reproduce:
            improvements.append("Generated reproduction steps from description context.")
        if not bug.expected_result.strip() and rewritten.expected_result:
            improvements.append("Synthesised expected result from documentation standards.")
        if not bug.actual_result.strip() and rewritten.actual_result:
            improvements.append("Inferred actual result from description narrative.")
        if bug.env.is_empty():
            improvements.append("Added environment placeholder fields.")
        if not bug.severity.strip():
            improvements.append(f"Assigned severity '{rewritten.severity}' inferred from priority.")
        if not bug.priority.strip():
            improvements.append(f"Assigned priority '{rewritten.priority}' inferred from severity.")

        vague_found = _detect_vague_language_in_bug(bug)
        if vague_found:
            improvements.append(f"Replaced vague language: {', '.join(repr(v) for v in vague_found[:3])}.")
        if not improvements:
            improvements.append("Standardised formatting to ISTQB CTFL v4.0.1 §5.5 template.")
        return improvements

    def rewrite(self, bug: BugReport) -> RewrittenBug:
        summary = self._build_summary(bug)
        description = self._build_description(bug)
        steps = self._build_steps(bug)
        expected = self._build_expected(bug)
        actual = self._build_actual(bug)
        environment = self._build_environment(bug)
        severity = self._build_severity(bug)
        priority = self._build_priority(bug)

        rewritten = RewrittenBug(
            original_id=bug.id,
            summary=summary,
            description=description,
            steps_to_reproduce=steps,
            expected_result=expected,
            actual_result=actual,
            environment=environment,
            severity=severity,
            priority=priority,
            rewrite_source=RewriteSource.RULE_BASED,
            improvements_made=[],
            confidence_score=0.72,
        )
        rewritten.improvements_made = self._detect_improvements(bug, rewritten)
        return rewritten


# ---------------------------------------------------------------------------
# Helper used by both paths
# ---------------------------------------------------------------------------

def _detect_vague_language_in_bug(bug: BugReport) -> List[str]:
    from src.scoring_engine import _has_vague_language  # local import to avoid circular
    text = f"{bug.summary} {bug.description} {bug.actual_result}"
    return _has_vague_language(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_rule_based = _RuleBasedRewriter()


def rewrite_bug_report(bug: BugReport) -> RewrittenBug:
    """
    Rewrite a bug report into ISTQB CTFL v4.0.1 §5.5 format.

    Attempts AI rewrite first (GPT-4o via OpenAI SDK); automatically
    falls back to the deterministic rule-based rewriter if:
      - openai package is not installed
      - OPENAI_API_KEY environment variable is not set
      - The API call fails for any reason

    Args:
        bug: Input BugReport (can be vague / incomplete).

    Returns:
        RewrittenBug with `rewrite_source` indicating which path was used.
    """
    ai_result = _rewrite_with_ai(bug)
    if ai_result is not None:
        logger.info("Bug %s rewritten using AI (GPT-4o).", bug.id)
        return ai_result

    logger.info("Bug %s rewritten using rule-based fallback.", bug.id)
    return _rule_based.rewrite(bug)
