# Test Plan — Bug Report Quality Assistant

> **Standard:** ISTQB CTFL v4.0.1  
> **Project:** IGS Engineering Quality Fresher Hackathon 2026  
> **Scope:** `src/scoring_engine.py`, `src/ai_rewriter.py`, `src/models.py`  
> **Test Design Techniques:** Equivalence Partitioning (EP), Boundary Value Analysis (BVA), Decision Table Testing, Error Guessing, State Transition Testing

---

## 1. Test Objectives

1. Verify that the scoring engine produces scores within the valid range (0–100) for all input classes.
2. Confirm that grade thresholds (80 / 60 / 40) behave correctly at exact boundary values.
3. Validate that all ISTQB §5.5 fields generate appropriate alerts when missing or malformed.
4. Ensure the rule-based rewriter always produces a valid `RewrittenBug` without network access.
5. Confirm that the AI rewrite path degrades gracefully to the fallback on any failure.
6. Verify that vague language is detected and removed by the rewriter.

---

## 2. Test Scope

### In Scope

| Module | Functions Tested |
|--------|-----------------|
| `src/scoring_engine.py` | `score_bug_report()`, `_score_structural()`, `_score_reproducibility()`, `_score_clarity()`, `_step_quality()`, `_has_vague_language()`, `_word_count()` |
| `src/ai_rewriter.py` | `rewrite_bug_report()`, `_RuleBasedRewriter.rewrite()`, all sub-methods, `_detect_vague_language_in_bug()` |
| `src/models.py` | `BugReport`, `Environment.is_empty()`, `Environment.filled_fields()`, `ScoreResult.grade_from_score()`, `ScoreBreakdown.total` |

### Out of Scope

- Streamlit UI rendering (requires browser automation; out of hackathon scope)
- Live OpenAI API calls (mocked in all tests)
- Database persistence (not implemented)

---

## 3. Test Environment

| Item | Value |
|------|-------|
| Python | 3.10+ |
| pytest | ≥ 8.2.0 |
| pytest-cov | ≥ 5.0.0 |
| Network access | Not required (offline-only tests) |
| OS | Windows 11 / Ubuntu 22.04 / macOS 13+ |

---

## 4. Test Cases — Scoring Engine

Test IDs use the format `TS-XXX` (Test Scoring).

### 4.1 Equivalence Partitioning — Input Quality Classes

| Test ID | Class | Input | Expected Outcome | Technique |
|---------|-------|-------|-----------------|-----------|
| TS-001 | **Valid – Complete** | All ISTQB §5.5 fields present and detailed | Score ≥ 70, grade "Excellent" or "Good" | EP |
| TS-002 | **Valid – Borderline** | Steps present, environment missing | Score 40–69, grade "Needs Improvement" or "Good" | EP |
| TS-003 | **Invalid – Empty** | All fields empty / default | Score < 10, grade "Poor" | EP |
| TS-004 | **Invalid – Vague** | Summary and description contain ≥ 3 vague phrases | Score < 40, grade "Poor" | EP |
| TS-005 | **Partial – Missing Steps** | All fields present except steps_to_reproduce | Score reduced by ~15–20 pts vs. complete | EP |
| TS-006 | **Partial – Missing Env** | All fields present except environment | Score reduced by ~6 pts vs. complete | EP |
| TS-007 | **Partial – Missing Severity** | severity = "" | Warning alert generated for "severity" field | EP |
| TS-008 | **Partial – Missing Priority** | priority = "" | Warning alert generated for "priority" field | EP |

### 4.2 Boundary Value Analysis — Score Thresholds

| Test ID | Boundary | Input Score | Expected Grade | Technique |
|---------|----------|------------|---------------|-----------|
| TS-010 | Lower bound | 0.0 | "Poor" | BVA |
| TS-011 | Poor → NI boundary (below) | 39.9 | "Poor" | BVA |
| TS-012 | Poor → NI boundary (at) | 40.0 | "Needs Improvement" | BVA |
| TS-013 | NI → Good boundary (below) | 59.9 | "Needs Improvement" | BVA |
| TS-014 | NI → Good boundary (at) | 60.0 | "Good" | BVA |
| TS-015 | Good → Excellent boundary (below) | 79.9 | "Good" | BVA |
| TS-016 | Good → Excellent boundary (at) | 80.0 | "Excellent" | BVA |
| TS-017 | Upper bound | 100.0 | "Excellent" | BVA |

### 4.3 Boundary Value Analysis — Step Count

| Test ID | Steps Count | Expected Quality Ratio | Technique |
|---------|------------|----------------------|-----------|
| TS-020 | 0 steps | 0.0 (no score) | BVA |
| TS-021 | 1 step | > 0.0, count penalty applied | BVA |
| TS-022 | 2 steps | Score > 1 step; penalty lifted | BVA |
| TS-023 | 10 steps (upper ideal) | Near-maximum ratio | BVA |
| TS-024 | 11 steps (over ideal) | Slight quality penalty applied | BVA |

### 4.4 Decision Table — Structural Field Combinations

| Test ID | Summary | Description | Expected | Actual | Env | Severity | Priority | Expected Alerts |
|---------|---------|-------------|----------|--------|-----|----------|----------|-----------------|
| TS-030 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 errors |
| TS-031 | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | error: summary |
| TS-032 | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | error: description |
| TS-033 | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | error: expected_result |
| TS-034 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | error: actual_result |
| TS-035 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | error: environment |
| TS-036 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | warning: severity |
| TS-037 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | warning: priority |
| TS-038 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 7 alerts (all critical) |

### 4.5 Clarity Scoring — Technical Identifier Detection

| Test ID | Input Contains | Expected Tech Score Contribution |
|---------|---------------|----------------------------------|
| TS-040 | Version number (e.g., `v2.7.3`) | +1.5 pts |
| TS-041 | URL (e.g., `https://app.example.com`) | +2.0 pts |
| TS-042 | Error class (e.g., `TokenExpiredError`) | +2.0 pts |
| TS-043 | Domain acronym (e.g., `JWT`, `API`) | +1.0 pts |
| TS-044 | No technical identifiers | 0 pts; info alert generated |

---

## 5. Test Cases — Rewriter

Test IDs use the format `TR-XXX` (Test Rewriter).

### 5.1 Equivalence Partitioning — Input Quality Classes

| Test ID | Class | Input | Expected Output | Technique |
|---------|-------|-------|-----------------|-----------|
| TR-001 | Complete | All fields present | Fields preserved, minor formatting applied | EP |
| TR-002 | Empty | All fields empty | Placeholders generated; ≥ 3 steps synthesised | EP |
| TR-003 | Vague | Vague language in summary/description | Vague phrases replaced; improvements list populated | EP |
| TR-004 | Missing Steps | No steps_to_reproduce | ≥ 3 generic steps generated from description | EP |
| TR-005 | Missing Env | Empty environment block | `Not specified` placeholders for os/browser/version | EP |
| TR-006 | Missing Severity | severity = "" | Severity inferred from priority or defaults to "Medium" | EP |
| TR-007 | Missing Priority | priority = "" | Priority inferred from severity or defaults to "P3" | EP |

### 5.2 Boundary Value Analysis — Step Generation

| Test ID | Steps Input | Expected Steps Output | Technique |
|---------|------------|----------------------|-----------|
| TR-010 | 0 steps | ≥ 3 generated steps | BVA |
| TR-011 | 1 step | 1 step preserved, no generation | BVA |
| TR-012 | 10 steps | 10 steps preserved | BVA |
| TR-013 | 20 steps | 20 steps preserved | BVA |

### 5.3 Severity ↔ Priority Inference — Decision Table

| Test ID | Input Severity | Input Priority | Expected Severity Out | Expected Priority Out |
|---------|---------------|---------------|----------------------|----------------------|
| TR-020 | "" | "P1" | "Critical" | "P1" |
| TR-021 | "" | "P2" | "High" | "P2" |
| TR-022 | "" | "P3" | "Medium" | "P3" |
| TR-023 | "" | "P4" | "Low" | "P4" |
| TR-024 | "Critical" | "" | "Critical" | "P1" |
| TR-025 | "High" | "" | "High" | "P2" |
| TR-026 | "Medium" | "" | "Medium" | "P3" |
| TR-027 | "Low" | "" | "Low" | "P4" |
| TR-028 | "" | "" | any valid | any valid | 

### 5.4 Fallback Behaviour — Error Guessing

| Test ID | Scenario | Expected Behaviour |
|---------|----------|-------------------|
| TR-030 | `OPENAI_API_KEY` not set | `rewrite_source = "rule_based"` |
| TR-031 | `openai` package not installed | `rewrite_source = "rule_based"` |
| TR-032 | API call raises `Exception` | Fallback used; `rewrite_source = "rule_based"` |
| TR-033 | API returns malformed JSON | Fallback used; no exception propagates |
| TR-034 | Unicode input (Japanese/French) | Valid `RewrittenBug` returned without exception |
| TR-035 | Extremely long description (10,000 chars) | Valid `RewrittenBug` returned without exception |
| TR-036 | Whitespace-only fields | Treated as absent; placeholders/synthesis applied |

### 5.5 State Transition — Rewrite Source

```
      ┌─────────────────────────────────┐
      │      rewrite_bug_report()       │
      └───────────┬─────────────────────┘
                  │
      ┌───────────▼───────────┐
      │ OPENAI_API_KEY set?   │
      │ openai installed?     │
      └──────┬────────┬───────┘
           YES        NO
             │          │
   ┌─────────▼──┐  ┌────▼──────────────┐
   │ API call   │  │ Rule-based path   │
   │ attempt    │  │ (RULE_BASED)      │
   └──┬──────┬──┘  └───────────────────┘
    OK     FAIL
     │       │
     │   ┌───▼───────────────┐
     │   │ Rule-based path   │
     │   │ (RULE_BASED)      │
     │   └───────────────────┘
  ┌──▼──────────────┐
  │ AI path (AI)    │
  └─────────────────┘
```

States: `AI`, `RULE_BASED`  
Transitions tested in: `TR-030` through `TR-033` + `test_ai_path_returns_rewritten_bug_when_successful`

---

## 6. Manual Verification Scenarios

These scenarios are performed by a human tester using the Streamlit UI.

### MV-01 — End-to-End Complete Report Flow

**Precondition:** App running at http://localhost:8501, no OPENAI_API_KEY set.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Select "✅ Complete – Login Token Expiry (Good)" | Bug report loaded |
| 2 | Click "🔍 Analyse & Rewrite" | Spinner shown briefly |
| 3 | Observe Quality Score | Score ≥ 70, grade "Excellent" or "Good" |
| 4 | Observe alert banners | Zero or one alert maximum |
| 5 | Observe comparison panel | Original and rewritten displayed side-by-side |
| 6 | Source badge visible | "⚙️ Rule-Based Rewrite" badge shown |
| 7 | Click "⬇️ Download JSON" | JSON file downloads; parses without error |

### MV-02 — End-to-End Poor Report Flow

| Step | Action | Expected |
|------|--------|----------|
| 1 | Select "❌ Poor – App Crashes (No Detail)" | Bug report loaded |
| 2 | Click "🔍 Analyse & Rewrite" | Analysis runs |
| 3 | Observe Quality Score | Score < 40, grade "Poor" |
| 4 | Observe alerts | ≥ 4 alerts; at least 2 with severity "error" |
| 5 | Observe rewrite panel | Rewrite has generated steps; no "doesn't work" language |
| 6 | Improvements list | ≥ 2 improvements listed |

### MV-03 — Custom Text Input

| Step | Action | Expected |
|------|--------|----------|
| 1 | Switch to "✏️ Paste Custom Text" mode | Text area displayed |
| 2 | Enter: `"Login is broken"` (minimal) | Text accepted |
| 3 | Enter Bug ID: `CUSTOM-TEST` | ID accepted |
| 4 | Click "🔍 Analyse & Rewrite" | Analysis runs without error |
| 5 | Observe score | Score < 30 (minimal report) |
| 6 | Observe rewrite | Generated steps and expected result present |

### MV-04 — Sidebar Scoring Weights Visibility

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open sidebar | Sidebar visible |
| 2 | Observe scoring weights | 40/35/25 correctly displayed |
| 3 | Observe grade scale | ≥80 / 60–79 / 40–59 / <40 correctly displayed |

### MV-05 — JSON Export Structure

| Step | Action | Expected |
|------|--------|----------|
| 1 | Analyse any report | Analysis completes |
| 2 | Click "👁️ Preview JSON payload" | JSON shown in code block |
| 3 | Verify top-level keys | `export_metadata`, `original_report`, `score_result`, `rewritten_report` present |
| 4 | Verify `export_metadata.standard` | Value: `"ISTQB CTFL v4.0.1 §5.5"` |
| 5 | Click "⬇️ Download JSON" | File downloads |
| 6 | Open in JSON editor | Parses without error |

---

## 7. Test Metrics & Exit Criteria

| Metric | Target | Actual (last run) |
|--------|--------|-------------------|
| Total automated test cases | ≥ 100 | **108** |
| Test pass rate | 100% | **100%** (108 / 108) |
| Code coverage (src/) | ≥ 80% | **95%** |
| Manual verification pass rate | 5 / 5 scenarios | — (manual) |
| Defects blocking submission | 0 | **0** |

---

## 8. Defect Classification

| Severity | Description | Example |
|----------|-------------|---------|
| **Critical (P1)** | Blocks core functionality; app cannot start or analyse | ImportError on startup |
| **High (P2)** | Core feature broken but workaround exists | Scoring always returns 0 |
| **Medium (P3)** | Output incorrect but app usable | Vague language not replaced |
| **Low (P4)** | UI cosmetic issue | Button label typo |

---

## 9. Test Execution Commands

```bash
# Full test suite
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing -v

# Scoring tests only
pytest tests/test_scoring.py -v

# Rewriter tests only  
pytest tests/test_rewriter.py -v

# BVA tests only
pytest -k "boundary or bva or BVA" -v

# Stop on first failure
pytest -x -v

# Generate HTML report
pytest --html=test_report.html --self-contained-html
```

---

## 10. Coverage Report (Last Run)

Generated via `pytest --cov=src --cov-report=term-missing`.

| Module | Statements | Missed | Coverage | Missed Lines |
|--------|-----------|--------|----------|--------------|
| `src/__init__.py` | 0 | 0 | **100%** | — |
| `src/ai_rewriter.py` | 157 | 2 | **99%** | 221–222 |
| `src/models.py` | 122 | 12 | **90%** | 115–117, 122, 126, 129–130, 133–134, 166, 171, 200 |
| `src/scoring_engine.py` | 160 | 7 | **96%** | 134–135, 269–270, 314, 321, 403 |
| **TOTAL** | **439** | **21** | **95%** | |

### Test Class Inventory

#### `tests/test_scoring.py` — 57 tests

| Class | Tests |
|-------|-------|
| `TestWordCount` | 5 |
| `TestVagueLanguageDetection` | 4 |
| `TestStepQuality` | 6 |
| `TestStructuralScoring` | 9 |
| `TestReproducibilityScoring` | 6 |
| `TestClarityScoring` | 7 |
| `TestScoreBugReport` | 20 |

#### `tests/test_rewriter.py` — 51 tests

| Class | Tests |
|-------|-------|
| `TestRuleBasedRewriterStructure` | 5 |
| `TestRuleBasedRewriterSummary` | 3 |
| `TestRuleBasedRewriterSteps` | 7 |
| `TestRuleBasedRewriterExpectedActual` | 4 |
| `TestRuleBasedRewriterEnvironment` | 4 |
| `TestRuleBasedRewriterSeverityPriority` | 8 |
| `TestRuleBasedRewriterImprovements` | 5 |
| `TestRuleBasedRewriterVagueLanguage` | 3 |
| `TestVagueLanguageDetector` | 3 |
| `TestRewriteBugReportPublicAPI` | 9 |
