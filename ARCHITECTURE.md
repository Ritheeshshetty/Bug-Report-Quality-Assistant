# Architecture — Bug Report Quality Assistant

> **Standard:** ISTQB CTFL v4.0.1 §5.5  
> **Project:** IGS Engineering Quality Fresher Hackathon 2026  
> **Last Updated:** September 2026

---

## 1. System Overview

The Bug Report Quality Assistant is a **single-process, offline-first web application** built on Streamlit. It accepts a bug report (structured JSON or free text), evaluates it against ISTQB CTFL v4.0.1 §5.5 defect attribute standards, and returns three outputs in a single synchronous pipeline:

| # | Output | Produced By |
|---|--------|------------|
| 1 | Quality Score (0–100) + Grade | `src/scoring_engine.py` |
| 2 | Field-level Alerts (error / warning / info) | `src/scoring_engine.py` |
| 3 | ISTQB-compliant Rewritten Report | `src/ai_rewriter.py` |

There is no database, no message queue, and no background worker. All computation completes within the request-response cycle of a single Streamlit button click.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        app.py  (Streamlit UI)                    │
│                                                                  │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐ │
│  │   Input Panel        │    │         Output Panel             │ │
│  │                     │    │  ┌────────────────────────────┐  │ │
│  │  • Dropdown sample  │    │  │  Output 1: Score Gauge     │  │ │
│  │  • JSON text area   │───►│  │  Output 2: Alert Banners   │  │ │
│  │  • Free-text mode   │    │  │  Output 3: Side-by-Side    │  │ │
│  └─────────────────────┘    │  │  Export:   JSON Download   │  │ │
│                             │  └────────────────────────────┘  │ │
└──────────────┬──────────────┴────────────────────────────────────┘
               │  BugReport (Pydantic v2)
               │
    ┌──────────┴────────────────────────────────┐
    │                                           │
    ▼                                           ▼
┌─────────────────────────┐       ┌─────────────────────────────┐
│  src/scoring_engine.py  │       │     src/ai_rewriter.py      │
│                         │       │                             │
│  _score_structural()    │       │  rewrite_bug_report()       │
│    └─ max 40 pts        │       │    ├─ _rewrite_with_ai()    │
│  _score_reproducibility │       │    │    └─ GPT-4o API call  │
│    └─ max 35 pts        │       │    └─ _RuleBasedRewriter    │
│  _score_clarity()       │       │         .rewrite()          │
│    └─ max 25 pts        │       │                             │
│                         │       │  rewrite_source:            │
│  Returns: ScoreResult   │       │    "ai" | "rule_based"      │
└─────────────────────────┘       └─────────────────────────────┘
          │                                     │
          └──────────────┬──────────────────────┘
                         │
                ┌────────▼────────┐
                │  src/models.py  │
                │  (Pydantic v2)  │
                │                 │
                │  BugReport      │
                │  Environment    │
                │  ScoreResult    │
                │  ScoreBreakdown │
                │  FieldAlert     │
                │  RewrittenBug   │
                │  RewriteSource  │
                └─────────────────┘
```

---

## 3. Component Responsibilities

### 3.1 `app.py` — Streamlit UI Layer

The single entry point and UI orchestrator. Responsibilities:

- Render three **input modes**: sample dropdown, JSON paste area, free-text area
- Parse raw input into a `BugReport` Pydantic model
- Call `score_bug_report()` and `rewrite_bug_report()` synchronously
- Render **Output 1**: composite score gauge with grade badge
- Render **Output 2**: colour-coded alert banners (🔴 error / 🟡 warning / 🔵 info)
- Render **Output 3**: side-by-side original vs. rewritten comparison
- Assemble the full **JSON export payload** and stream it as a download

**Does NOT contain:** any business logic, scoring rules, or rewrite transformations.

---

### 3.2 `src/models.py` — Domain Model Layer

Pydantic v2 schemas forming the shared data contract across all components.

```
models.py
│
├── Severity (Enum)         "Critical" | "High" | "Medium" | "Low" | "Trivial" | ""
├── Priority (Enum)         "P1" | "P2" | "P3" | "P4" | ""
├── RewriteSource (Enum)    "ai" | "rule_based"
│
├── Environment (BaseModel)
│   ├── os, browser, app_version, backend, database, extra: Dict
│   ├── is_empty() → bool
│   └── filled_fields() → int
│
├── BugReport (BaseModel)         ← PRIMARY INPUT
│   ├── id, label, summary, description
│   ├── steps_to_reproduce: List[str]
│   ├── expected_result, actual_result
│   ├── environment: Environment  (coerced from dict via @field_validator)
│   ├── severity, priority, reporter
│   ├── attachments: List[str]
│   ├── has_steps() → bool
│   ├── has_environment() → bool
│   └── word_count() → int
│
├── FieldAlert (BaseModel)        ← SCORING OUTPUT (alert)
│   ├── field_name: str
│   ├── severity: "error" | "warning" | "info"
│   ├── message: str
│   └── suggestion: Optional[str]
│
├── ScoreBreakdown (BaseModel)    ← SCORING OUTPUT (breakdown)
│   ├── structural_completeness: float  (0–40)
│   ├── reproducibility: float          (0–35)
│   ├── clarity_context: float          (0–25)
│   └── total (property) → float       (sum, rounded to 2dp)
│
├── ScoreResult (BaseModel)       ← SCORING OUTPUT (top-level)
│   ├── bug_id, total_score, grade, breakdown
│   ├── alerts: List[FieldAlert]
│   ├── scored_at: ISO-8601 timestamp
│   ├── grade_from_score(score) → str  (classmethod)
│   └── has_critical_alerts (property) → bool
│
└── RewrittenBug (BaseModel)      ← REWRITER OUTPUT
    ├── original_id, summary, description
    ├── steps_to_reproduce: List[str]
    ├── expected_result, actual_result
    ├── environment: Environment
    ├── severity, priority
    ├── rewrite_source: RewriteSource
    ├── improvements_made: List[str]
    └── confidence_score: Optional[float]  (0.0–1.0)
```

---

### 3.3 `src/scoring_engine.py` — Scoring Engine

A **pure-Python, deterministic, zero-network-dependency** scoring engine. Its public API is a single function:

```python
def score_bug_report(bug: BugReport) -> ScoreResult
```

Internally composed of three private sub-scorers:

#### Sub-scorer 1: `_score_structural()` → max 40 pts

Evaluates **presence and basic validity** of ISTQB §5.5 structural fields:

| Field | Max Pts | Alert Trigger |
|-------|---------|--------------|
| `summary` | 8 | Missing → error; < 3 words → warning; > 25 words → info |
| `description` | 8 | Missing → error; vague language → warning (−1pt/phrase, max −4); < 10 words → warning |
| `expected_result` | 6 | Missing → error; < 5 words → warning (score halved) |
| `actual_result` | 6 | Missing → error; vague language → warning (−1pt/phrase, max −3) |
| `environment` | 6 | Empty → error; < 3 fields filled → warning (1.5 pts/field, capped at 6) |
| `severity` | 3 | Missing → warning; unrecognised value → info (1.5 pts) |
| `priority` | 3 | Missing → warning; unrecognised value → info (1.5 pts) |

#### Sub-scorer 2: `_score_reproducibility()` → max 35 pts

Evaluates **developer ability to reproduce** the defect:

| Sub-criterion | Max Pts | Detail |
|--------------|---------|--------|
| `steps_to_reproduce` quality | 20 | `_step_quality()` ratio × 20: weighted by numbered format (30%), action verbs (40%), avg word length (30%), count penalty if < 2 or > 10 steps |
| Pre-conditions (inferred) | 8 | Keyword scan in description + steps for login, test data, prerequisite, setup, etc. (1–3 pts/signal, capped at 8) |
| Attachments / evidence | 7 | 2.5 pts per attachment, capped at 7 |

#### Sub-scorer 3: `_score_clarity()` → max 25 pts

Evaluates **narrative quality and actionability**:

| Sub-criterion | Max Pts | Detail |
|--------------|---------|--------|
| Word richness | 10 | < 20 words → 2 pts; 20–49 → 5 pts; 50–99 → 7.5 pts; ≥ 100 → 10 pts; −1 pt per vague phrase (max −5) |
| Technical identifiers | 8 | Regex patterns: version numbers (1.5), URLs (2.0), Error class names (2.0), HTTP codes (1.0), Twilio-style codes (2.0), JIRA IDs (1.5), domain acronyms (1.0). Capped at 8 |
| Single-issue focus | 7 | Multi-issue conjunctions detected ("also", "additionally", "another bug") → 3.5 pts + warning; else → 7 pts |

#### Grade Scale

```
total_score = structural + reproducibility + clarity

≥ 80.0  →  🏆 Excellent
≥ 60.0  →  ✅ Good
≥ 40.0  →  ⚠️  Needs Improvement
 < 40.0  →  ❌ Poor
```

---

### 3.4 `src/ai_rewriter.py` — Rewriter Layer

Implements a **two-tier rewrite strategy** behind a single public function:

```python
def rewrite_bug_report(bug: BugReport) -> RewrittenBug
```

#### Tier 1 — AI Path (`_rewrite_with_ai`)

Activated when **both** conditions are true:
- `OPENAI_API_KEY` environment variable is set and non-empty
- `openai` Python package is importable

Sends the `BugReport` as a structured JSON user message to `gpt-4o` with:
- `temperature=0.2` (high determinism)
- `max_tokens=1200`
- `response_format={"type": "json_object"}` (JSON mode, no markdown fences)
- An ISTQB §5.5-aligned system prompt specifying exact output schema

Returns `RewrittenBug` with `rewrite_source="ai"`, `confidence_score=0.95`.

Gracefully returns `None` (triggering fallback) on: `ImportError`, missing API key, or any `Exception` from the API call.

#### Tier 2 — Rule-Based Fallback (`_RuleBasedRewriter`)

Activated automatically when Tier 1 returns `None`. Deterministic, zero-network transformations:

| Method | Transformation |
|--------|---------------|
| `_clean_text()` | Regex-based vague phrase replacement map (11 patterns) |
| `_build_summary()` | Preserves + cleans; synthesises from description if < 3 words |
| `_build_steps()` | Preserves existing steps (cleaned); generates generic steps if empty |
| `_generate_generic_steps()` | Context-aware step generation from description keywords (upload, search, login, dark mode) |
| `_build_expected()` | Preserves + cleans; synthesises ISTQB-standard placeholder if missing |
| `_build_actual()` | Preserves + cleans; infers from description if missing |
| `_build_environment()` | Fills empty env fields with `"Not specified"` placeholders |
| `_build_severity()` | Preserves valid value; infers from priority (P1→Critical, P2→High, P3→Medium, P4→Low) |
| `_build_priority()` | Preserves valid value; infers from severity (Critical→P1, High→P2, Medium→P3, Low→P4) |
| `_detect_improvements()` | Produces human-readable list of transformations applied |

Returns `RewrittenBug` with `rewrite_source="rule_based"`, `confidence_score=0.72`.

#### Rewriter State Machine

```
rewrite_bug_report(bug)
        │
        ▼
  OPENAI_API_KEY set?
  openai importable?
        │
    YES ├──────────────────────────────────────────────────────┐
        ▼                                                      │
  _rewrite_with_ai(bug)                                        │
        │                                                      │
   ┌────┴────┐                                                 │
   │ Success │ ──► RewrittenBug(rewrite_source="ai",          │
   └─────────┘     confidence_score=0.95)                     │
        │                                                      │
   ┌────┴────┐                                                 │
   │ Failure │ ──► returns None                               │
   └─────────┘          │                           NO ◄──────┘
                        └──────────────┐             │
                                       ▼             ▼
                              _RuleBasedRewriter.rewrite(bug)
                                       │
                                       ▼
                          RewrittenBug(rewrite_source="rule_based",
                                       confidence_score=0.72)
```

---

### 3.5 `data/sample_bugs.json`

12 curated synthetic `BugReport` objects spanning:
- **✅ Excellent / Good** (4 reports) — all ISTQB fields populated, specific language
- **⚠️ Borderline** (4 reports) — partial fields, mild vague language
- **❌ Poor** (4 reports) — minimal or missing fields, vague language throughout

Used by the Streamlit dropdown for demonstration without the user needing to author a report.

---

## 4. Data Flow — End to End

```
User Input
    │
    │  (JSON string or free text)
    ▼
app.py: parse input
    │
    ├── JSON mode  → json.loads() → BugReport(**data)
    └── Text mode  → BugReport(id=..., description=raw_text)
    │
    ▼
BugReport (Pydantic v2 validated object)
    │
    ├──────────────────────────────────────────────────────────────┐
    │                                                              │
    ▼                                                              ▼
score_bug_report(bug)                               rewrite_bug_report(bug)
    │                                                              │
    ├─ _score_structural()   → (float, [FieldAlert])              │
    ├─ _score_reproducibility() → (float, [FieldAlert])           │
    └─ _score_clarity()      → (float, [FieldAlert])             │
    │                                                              │
    ▼                                                              ▼
ScoreResult                                            RewrittenBug
  ├── total_score: float                                 ├── summary, description
  ├── grade: str                                         ├── steps_to_reproduce
  ├── breakdown: ScoreBreakdown                          ├── expected_result
  └── alerts: List[FieldAlert]                          ├── actual_result
                                                         ├── environment
                                                         ├── severity, priority
                                                         ├── rewrite_source
                                                         ├── improvements_made
                                                         └── confidence_score
    │                                                              │
    └──────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
                    app.py: render outputs
                           │
                 ┌─────────┴────────────┐
                 │                      │
                 ▼                      ▼
          UI display              JSON Export Payload
                              {
                                "export_metadata": {...},
                                "original_report": BugReport,
                                "score_result": ScoreResult,
                                "rewritten_report": RewrittenBug
                              }
```

---

## 5. Dependency Graph

```
app.py
  ├── src.models         (BugReport, ScoreResult, RewrittenBug)
  ├── src.scoring_engine (score_bug_report)
  └── src.ai_rewriter    (rewrite_bug_report)

src.scoring_engine
  └── src.models         (BugReport, FieldAlert, ScoreBreakdown, ScoreResult)

src.ai_rewriter
  ├── src.models         (BugReport, Environment, RewriteSource, RewrittenBug)
  └── src.scoring_engine (_has_vague_language — local import to avoid circular)

src.models
  └── pydantic           (BaseModel, Field, field_validator)
```

**No circular imports.** The one cross-module call (`ai_rewriter` → `scoring_engine._has_vague_language`) is resolved via a local import inside the function body.

---

## 6. External Dependencies

| Package | Version | Role | Required? |
|---------|---------|------|-----------|
| `pydantic` | ≥ 2.6.0 | Domain models, validation, JSON serialisation | ✅ Always |
| `streamlit` | ≥ 1.35.0 | Web UI framework | ✅ Always |
| `python-dotenv` | ≥ 1.0.0 | Load `.env` file for `OPENAI_API_KEY` | ✅ Always |
| `openai` | ≥ 1.30.0 | GPT-4o API client | ❌ Optional (graceful fallback) |
| `pytest` | ≥ 8.2.0 | Test runner | 🧪 Test only |
| `pytest-cov` | ≥ 5.0.0 | Code coverage reporting | 🧪 Test only |

The application is **fully functional with zero API keys** — the `openai` package can be installed but the key absent, or the package itself absent entirely. Both cases fall through to the rule-based rewriter.

---

## 7. Project Structure

```
bug-report-quality-assistant/
│
├── app.py                  # Streamlit UI — entry point
├── requirements.txt        # Runtime + test dependencies
│
├── src/
│   ├── __init__.py
│   ├── models.py           # Pydantic v2 domain models (shared contract)
│   ├── scoring_engine.py   # Deterministic scoring (pure Python, no network)
│   └── ai_rewriter.py      # GPT-4o + rule-based fallback rewriter
│
├── data/
│   └── sample_bugs.json    # 12 synthetic bug reports (good / borderline / poor)
│
├── tests/
│   ├── __init__.py
│   ├── test_scoring.py     # 60+ scoring tests (EP, BVA, Decision Table)
│   └── test_rewriter.py    # 55+ rewriter tests (EP, BVA, Error Guessing)
│
├── README.md               # Setup, usage, algorithm reference
├── REQUIREMENTS.md         # User stories, personas, Kanban board
├── ARCHITECTURE.md         # This document
├── TESTING.md              # Test plan, test cases, manual scenarios
├── GIT_COMMITS.sh          # Conventional commit history simulation
├── kanban.html             # Visual Kanban board
└── .env.example            # Environment variable template
```

---

## 8. Key Design Decisions

### 8.1 Streamlit over FastAPI + React

**Decision:** Use Streamlit as the sole UI and server framework.  
**Rationale:** Streamlit eliminates the need for a separate frontend build pipeline. For an 8–10 hour hackathon with a single developer, this provides a 3–4× speed advantage over a FastAPI + React architecture.  
**Trade-off:** Streamlit is not suitable for multi-user production deployment (no session isolation, no horizontal scaling). Tracked as T-07/T-08 in the backlog.

### 8.2 Pydantic v2 for all Domain Models

**Decision:** Every data structure is a Pydantic `BaseModel`.  
**Rationale:** Pydantic v2 provides type-safe construction, auto-validation of field constraints (e.g., `ge=0.0, le=40.0` on score fields), and free JSON serialisation/deserialisation via `.model_dump()`. It also catches malformed input at the model boundary rather than inside business logic.

### 8.3 Scoring Engine is Pure Python

**Decision:** Zero external dependencies in `scoring_engine.py` (only stdlib `re`, `datetime` + Pydantic models).  
**Rationale:** Offline-first is a hard requirement. The scoring engine must produce identical results without network access, enabling local testing, CI pipelines, and demos without API credentials.

### 8.4 Two-Tier Rewriter with Transparent Source Tracking

**Decision:** Always produce a `RewrittenBug`; the `rewrite_source` field tells the caller which path was used.  
**Rationale:** The caller (`app.py`) does not need to know which rewriter ran. The UI displays a source badge ("🤖 AI Rewrite" vs. "⚙️ Rule-Based Rewrite") by inspecting `rewrite_source`, but the data contract is identical. This decoupling makes testing each tier independently straightforward.

### 8.5 ISTQB §5.5 as the Scoring Anchor

**Decision:** All scoring weights and alert rules are explicitly mapped to ISTQB CTFL v4.0.1 §5.5 defect attributes.  
**Rationale:** Using a published international standard makes the scoring defensible, auditable, and teachable. It also provides a clear boundary for what fields matter and why.

---

## 9. Future Architecture Considerations

| Concern | Current State | Future Direction |
|---------|--------------|-----------------|
| **Persistence** | None (ephemeral session) | SQLite → PostgreSQL for analysis history |
| **API surface** | Internal function calls only | FastAPI REST endpoints (`/score`, `/rewrite`, `/export`) |
| **Multi-user** | Single-tenant Streamlit | FastAPI + React frontend with session auth |
| **AI providers** | GPT-4o only | Provider abstraction layer (Anthropic Claude, Gemini, local Ollama) |
| **Scoring quality** | Regex heuristics | spaCy NLP for POS-aware clarity scoring |
| **CI/CD** | Manual test run | GitHub Actions: lint → test → coverage gate → deploy |
| **Bulk analysis** | One report at a time | CSV/JSON batch upload endpoint |
