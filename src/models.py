"""
src/models.py
Pydantic data models for Bug Report Quality Assistant.
ISTQB CTFL v4.0.1 Section 5.5 defect attributes are represented as fields.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    TRIVIAL = "Trivial"
    UNKNOWN = ""


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    UNKNOWN = ""


class RewriteSource(str, Enum):
    AI = "ai"
    RULE_BASED = "rule_based"


# ---------------------------------------------------------------------------
# Core Domain Models
# ---------------------------------------------------------------------------

class Environment(BaseModel):
    """Execution environment captured with the bug (ISTQB 5.5 attribute)."""
    os: Optional[str] = Field(None, description="Operating system and version")
    browser: Optional[str] = Field(None, description="Browser name and version")
    app_version: Optional[str] = Field(None, description="Application version under test")
    backend: Optional[str] = Field(None, description="Server-side technology stack")
    database: Optional[str] = Field(None, description="Database engine and version")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Any additional env keys")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Environment":
        known = {"os", "browser", "app_version", "backend", "database"}
        extra = {k: v for k, v in data.items() if k not in known}
        base = {k: data.get(k) for k in known}
        return cls(**base, extra=extra)

    def is_empty(self) -> bool:
        return (
            not self.os
            and not self.browser
            and not self.app_version
            and not self.backend
            and not self.database
            and not self.extra
        )

    def filled_fields(self) -> int:
        count = 0
        for f in [self.os, self.browser, self.app_version, self.backend, self.database]:
            if f:
                count += 1
        count += len(self.extra)
        return count


class BugReport(BaseModel):
    """
    Raw / input bug report.
    Maps to ISTQB CTFL v4.0.1 Section 5.5 defect attributes.
    """
    id: str = Field(..., description="Unique defect identifier (ISTQB: identifier)")
    label: Optional[str] = Field(None, description="Display label (UI helper)")
    summary: str = Field("", description="Short, descriptive title (ISTQB: summary)")
    description: str = Field("", description="Detailed narrative (ISTQB: description)")
    steps_to_reproduce: List[str] = Field(
        default_factory=list,
        description="Numbered steps to replicate the defect (ISTQB: steps to reproduce)"
    )
    expected_result: str = Field(
        "", description="What should happen (ISTQB: expected results)"
    )
    actual_result: str = Field(
        "", description="What actually happens (ISTQB: actual results)"
    )
    environment: Union[Environment, Dict[str, Any]] = Field(
        default_factory=Environment,
        description="Environment info (ISTQB: environment)"
    )
    severity: str = Field("", description="Defect severity (ISTQB: severity)")
    priority: str = Field("", description="Business priority (ISTQB: priority)")
    reporter: Optional[str] = Field(None, description="Who filed the report (ISTQB: date/author)")
    attachments: List[str] = Field(
        default_factory=list,
        description="File references – logs, screenshots, recordings"
    )

    @field_validator("environment", mode="before")
    @classmethod
    def coerce_environment(cls, v: Any) -> Environment:
        if isinstance(v, dict):
            return Environment.from_dict(v)
        if isinstance(v, Environment):
            return v
        return Environment()

    @property
    def env(self) -> Environment:
        if isinstance(self.environment, dict):
            return Environment.from_dict(self.environment)
        return self.environment  # type: ignore[return-value]

    def has_steps(self) -> bool:
        return len(self.steps_to_reproduce) > 0

    def has_environment(self) -> bool:
        env = self.env
        return not env.is_empty()

    def word_count(self) -> int:
        text = f"{self.summary} {self.description} {self.expected_result} {self.actual_result}"
        return len(text.split())


# ---------------------------------------------------------------------------
# Scoring Models
# ---------------------------------------------------------------------------

class FieldAlert(BaseModel):
    """A single missing-field or ambiguity alert."""
    field_name: str
    severity: str = "warning"   # "error" | "warning" | "info"
    message: str
    suggestion: Optional[str] = None


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of the composite score."""
    structural_completeness: float = Field(
        ..., ge=0.0, le=40.0,
        description="Score for presence of ISTQB structural fields (max 40)"
    )
    reproducibility: float = Field(
        ..., ge=0.0, le=35.0,
        description="Score for quality of reproduction steps (max 35)"
    )
    clarity_context: float = Field(
        ..., ge=0.0, le=25.0,
        description="Score for narrative clarity and contextual richness (max 25)"
    )

    @property
    def total(self) -> float:
        return round(
            self.structural_completeness + self.reproducibility + self.clarity_context, 2
        )

    def as_dict(self) -> Dict[str, float]:
        return {
            "Structural Completeness (40)": self.structural_completeness,
            "Reproducibility (35)": self.reproducibility,
            "Clarity & Context (25)": self.clarity_context,
            "Total (100)": self.total,
        }


class ScoreResult(BaseModel):
    """Composite scoring result for a bug report."""
    bug_id: str
    total_score: float = Field(..., ge=0.0, le=100.0)
    grade: str          # "Excellent" | "Good" | "Needs Improvement" | "Poor"
    breakdown: ScoreBreakdown
    alerts: List[FieldAlert]
    scored_at: Optional[str] = None

    @classmethod
    def grade_from_score(cls, score: float) -> str:
        if score >= 80:
            return "Excellent"
        if score >= 60:
            return "Good"
        if score >= 40:
            return "Needs Improvement"
        return "Poor"

    @property
    def has_critical_alerts(self) -> bool:
        return any(a.severity == "error" for a in self.alerts)


# ---------------------------------------------------------------------------
# Rewriter Models
# ---------------------------------------------------------------------------

class RewrittenBug(BaseModel):
    """
    Standardised rewritten bug report conforming to ISTQB CTFL v4.0.1 Section 5.5.
    """
    original_id: str
    summary: str = Field(..., description="Concise, action-oriented title")
    description: str = Field(..., description="Context and impact statement")
    steps_to_reproduce: List[str] = Field(
        ..., description="Numbered, deterministic reproduction steps"
    )
    expected_result: str = Field(..., description="Observable expected state")
    actual_result: str = Field(..., description="Observable actual state with error details")
    environment: Environment = Field(..., description="Complete environment block")
    severity: str = Field(..., description="Assigned severity level")
    priority: str = Field(..., description="Assigned priority level")
    rewrite_source: RewriteSource = Field(
        RewriteSource.RULE_BASED,
        description="Whether rewrite was AI-assisted or rule-based"
    )
    improvements_made: List[str] = Field(
        default_factory=list,
        description="Human-readable list of improvements applied"
    )
    confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Rewriter confidence (1.0 = full AI, 0.5–0.9 = rule-based)"
    )
