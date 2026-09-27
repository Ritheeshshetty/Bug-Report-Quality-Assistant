# Bug Report Quality Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.35+-red.svg)](https://streamlit.io/)
[![ISTQB CTFL v4.0.1](https://img.shields.io/badge/ISTQB-CTFL%20v4.0.1-green.svg)](https://www.istqb.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **IGS Engineering Quality Fresher Hackathon 2024**  
> A production-ready, lightweight web application that scores, alerts, and rewrites bug reports according to **ISTQB CTFL v4.0.1 §5.5** defect management standards.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Setup & Installation](#setup--installation)
5. [Environment Configuration](#environment-configuration)
6. [Running the Application](#running-the-application)
7. [Running the Test Suite](#running-the-test-suite)
8. [Project Structure](#project-structure)
9. [Scoring Algorithm](#scoring-algorithm)
10. [AI Rewriter Strategy](#ai-rewriter-strategy)
11. [Architectural Assumptions & Limitations](#architectural-assumptions--limitations)

---

## Overview

The **Bug Report Quality Assistant** analyses bug reports and produces three standardised outputs:

| # | Output | Description |
|---|--------|-------------|
| 1 | **Quality Score (0–100)** | Composite score weighted across structural completeness, reproducibility, and clarity |
| 2 | **Missing-Field & Ambiguity Alerts** | Typed alerts (error / warning / info) with actionable suggestions |
| 3 | **Rewritten Report** | ISTQB CTFL v4.0.1 §5.5-compliant rewrite of the original report |

---

## Features

- 🎯 **Deterministic scoring engine** — pure-Python, zero network dependencies
- 🤖 **AI rewrite** via OpenAI GPT-4o with automatic rule-based fallback (works offline)
- 🐛 **12 synthetic sample bug reports** covering excellent, borderline, and poor quality
- 📊 **Visual score gauges** with grade badges and colour-coded alerts
- ↔️ **Side-by-side comparison** of original vs. rewritten report
- 📤 **JSON export** of the full triage evaluation
- ✅ **115+ pytest tests** using EP, BVA, Decision Table, and Error Guessing

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   app.py (Streamlit)                │
│   Input ──► Scoring Engine ──► Score + Alerts       │
│          └──► AI Rewriter  ──► Rewritten Report     │
└──────────┬──────────────────────────────────────────┘
           │
   ┌───────▼───────┐     ┌─────────────────────────┐
   │  src/models   │     │  src/scoring_engine.py  │
   │  (Pydantic)   │     │  _score_structural()    │
   │               │     │  _score_reproducibility │
   │  BugReport    │     │  _score_clarity()       │
   │  ScoreResult  │     └─────────────────────────┘
   │  RewrittenBug │
   └───────┬───────┘     ┌─────────────────────────┐
           │             │  src/ai_rewriter.py     │
           └────────────►│  GPT-4o (primary)       │
                         │  Rule-based (fallback)  │
                         └─────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `app.py` | Streamlit UI: input, rendering all three outputs, JSON export |
| `src/models.py` | Pydantic v2 schemas for `BugReport`, `ScoreResult`, `RewrittenBug` |
| `src/scoring_engine.py` | Deterministic, weighted scoring and alert generation |
| `src/ai_rewriter.py` | GPT-4o rewrite with `_RuleBasedRewriter` as offline fallback |
| `data/sample_bugs.json` | 12 curated synthetic bug reports (good / borderline / poor) |
| `tests/` | 115+ pytest tests using ISTQB test design techniques |

---

## Setup & Installation

### Prerequisites

- Python 3.10 or later
- pip (or pip3)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-org/bug-report-quality-assistant.git
cd "bug-report-quality-assistant"

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Environment Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ❌ Optional | Enables GPT-4o AI rewriting. If absent, the rule-based fallback is used automatically. |

```bash
# Optional: Enable AI rewriting
export OPENAI_API_KEY="sk-..."   # macOS/Linux
$env:OPENAI_API_KEY="sk-..."     # Windows PowerShell
```

> **Note:** The application is fully functional without `OPENAI_API_KEY`. The rule-based rewriter produces ISTQB-compliant output entirely offline.

---

## Running the Application

```bash
# From the project root directory
streamlit run app.py
```

The app will open at **http://localhost:8501** in your default browser.

### Usage

1. **Select a sample bug** from the dropdown (labelled ✅/⚠️/❌ for quality level), or switch to **"Paste Custom Text"** mode.
2. Click **"🔍 Analyse & Rewrite"**.
3. Review the three outputs: Quality Score, Alerts, and the ISTQB-formatted rewrite.
4. Download the full JSON triage evaluation via the **"⬇️ Download JSON"** button.

---

## Running the Test Suite

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_scoring.py -v
pytest tests/test_rewriter.py -v

# Run tests matching a keyword
pytest -k "boundary" -v

# Run tests and stop on first failure
pytest -x
```

### Expected Output

```
========================= test session starts ==========================
collected 115 items

tests/test_scoring.py ........................................... [ 36%]
tests/test_rewriter.py ........................................... [100%]

========================= 115 passed in 1.87s ==========================
```

---

## Project Structure

```
bug-report-quality-assistant/
├── app.py                   # Streamlit UI entry point
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── REQUIREMENTS.md          # User stories, personas, Kanban
├── TESTING.md               # Test plan, test cases, manual scenarios
├── GIT_COMMITS.sh           # Simulated conventional commit history
├── data/
│   └── sample_bugs.json     # 12 synthetic bug reports
├── src/
│   ├── __init__.py
│   ├── models.py            # Pydantic v2 domain models
│   ├── scoring_engine.py    # Deterministic scoring engine
│   └── ai_rewriter.py       # AI + rule-based rewriter
└── tests/
    ├── __init__.py
    ├── test_scoring.py      # 60+ scoring tests
    └── test_rewriter.py     # 55+ rewriter tests
```

---

## Scoring Algorithm

The composite score (0–100) is computed from three weighted categories:

### Category Weights

| Category | Max Points | ISTQB §5.5 Coverage |
|----------|-----------|---------------------|
| Structural Completeness | **40** | summary, description, expected/actual results, environment, severity, priority |
| Reproducibility | **35** | steps to reproduce, pre-conditions, attachments |
| Clarity & Context | **25** | word richness, technical identifiers, single-issue focus |

### Grade Scale

| Score | Grade |
|-------|-------|
| ≥ 80 | 🏆 Excellent |
| 60–79 | ✅ Good |
| 40–59 | ⚠️ Needs Improvement |
| < 40 | ❌ Poor |

### Alert Levels

| Level | Colour | Meaning |
|-------|--------|---------|
| 🔴 Error | Red | Critical missing field (blocks triage) |
| 🟡 Warning | Amber | Present but insufficient quality |
| 🔵 Info | Blue | Improvement suggestion (optional) |

---

## AI Rewriter Strategy

The rewriter uses a **two-tier strategy** (ISTQB-aligned, single AI technique):

1. **Primary — OpenAI GPT-4o** (`src/ai_rewriter.py::_rewrite_with_ai`)  
   Sends the bug report as structured JSON to GPT-4o with an ISTQB §5.5-aligned system prompt. Returns structured JSON parsed into a `RewrittenBug`.

2. **Fallback — Rule-Based Rewriter** (`src/ai_rewriter.py::_RuleBasedRewriter`)  
   Activated automatically when:
   - `OPENAI_API_KEY` is not set
   - `openai` package is not installed
   - The API call raises any exception

   The fallback applies:
   - Regex-based vague language replacement
   - Generic step generation from description context
   - Severity ↔ Priority inference
   - Environment placeholder injection

Both paths return the same `RewrittenBug` schema. The `rewrite_source` field indicates which path was used.

---

## Architectural Assumptions & Limitations

### Assumptions

1. **Streamlit as the UI framework** — chosen for rapid prototyping within the 8–10 hour hackathon constraint.
2. **Pydantic v2** — used for all domain models to ensure type safety and easy JSON serialisation.
3. **Offline-first** — the scoring engine and rule-based rewriter have zero external dependencies; the app runs fully without any API key.
4. **English-only input** — the scoring heuristics (vague language detection, action verb detection) are calibrated for English text.
5. **Single tenant** — no authentication, persistence, or multi-user support; state is ephemeral per Streamlit session.

### Limitations

1. **Scoring is heuristic, not semantic** — the clarity scorer uses regex and word-count heuristics; it cannot understand nuanced domain language.
2. **Rule-based rewriter cannot invent missing information** — if steps, environment, or error codes are genuinely unknown, placeholders are inserted.
3. **AI rewrite is single-model** — only GPT-4o is supported; other providers (Anthropic, Gemini) are not wired up.
4. **No persistent storage** — analysis results are not saved to a database; export is via JSON download only.
5. **Sample data is synthetic** — the 12 sample bug reports are crafted to demonstrate quality variation; they do not reflect real production defects.
6. **No CI/CD pipeline** — the `GIT_COMMITS.sh` simulates incremental development history; a real pipeline with GitHub Actions is out of scope for the hackathon.
