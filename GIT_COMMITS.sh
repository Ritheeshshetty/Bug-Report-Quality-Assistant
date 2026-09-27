#!/usr/bin/env bash
# GIT_COMMITS.sh
# =============================================================================
# Actual Git commit history for Bug Report Quality Assistant.
# Repository: https://github.com/Ritheeshshetty/Bug-Report-Quality-Assistant
# Author: Ritheeshshetty
#
# This file documents the real, chronological commit history as pushed
# to GitHub during the IGS Engineering Quality Fresher Hackathon 2026.
#
# To view history on a cloned repo:
#   git log --oneline
# =============================================================================

echo "=== Bug Report Quality Assistant — Actual Git Commit History ==="
echo ""

# ---------------------------------------------------------------------------
# Commit Reference Table (newest to oldest)
# Run: git log --oneline  to verify
# ---------------------------------------------------------------------------

# Hash      | Date                  | Author           | Message

# Commit 11 — 2026-09-27T19:47:39
# df684fe  Added JSON Support to my input
#
# Changes:
#   - parse_bug_from_text: JSON auto-detection routes to parse_bug_from_dict
#   - parse_bug_from_dict: field-alias normalisation
#       (title->summary, steps->steps_to_reproduce, expected->expected_result, etc.)
#   - Export payload unwrapping: detects original_report key and extracts it
#   - UI: success/warning banners for JSON and export payload detection
#   - UI: "Parsed fields preview" expander for pre-analysis verification
#   - Known-word detection: bare keywords (e.g. "Summary" alone on a line)
#       recognised as section headers without requiring a colon
#   - Input format guide expander with table of accepted labels and 3 writing styles
#   - Fixed double numbering in Steps to Reproduce rendering
#   - Hackathon year corrected: 2024 -> 2026 in app.py, TESTING.md, kanban.html

# Commit 10 — 2026-09-19T23:45:22
# a3069b4  Updated REQUIREMENTS.md file
#   - Revised user stories and acceptance criteria

# Commit 9 — 2026-09-19T23:37:57
# 22e8287  Added progress of Stage 3C of Kanban board
#   - Stage 3C tasks (test suite + docs) moved to Done
#   - Sprint completion badge updated

# Commit 8 — 2026-09-19T23:32:45
# e31331c  feat(schema): implement ISTQB bug report models and sample dataset
#   - src/models.py: refined Pydantic v2 schemas
#   - data/sample_bugs.json: 12 synthetic bug reports (all grade levels)

# Commit 7 — 2026-09-18T23:16:46
# e5c013e  Added progress of Stage 3A and Stage 3B of Kanban board
#   - Stage 3A (scoring engine) and 3B (AI rewriter) moved to Done

# Commit 6 — 2026-09-18T22:48:13
# 99636b6  feat(engine): implement rule-based scoring engine and report rewriter
#
#   - src/scoring_engine.py: composite scorer — 3 sub-scorers
#       * Structural Completeness  — 40 pts
#       * Reproducibility          — 35 pts
#       * Clarity and Context      — 25 pts
#   - src/ai_rewriter.py: dual-path rewriter (GPT-4o + rule-based fallback)
#   - tests/test_scoring.py: 56 tests (EP, BVA, Decision Table, State Transition)
#   - tests/test_rewriter.py: 52 tests (EP, BVA, Error Guessing, Coverage)
#   - Total: 108 tests | 100% pass | 95% code coverage

# Commit 5 — 2026-09-18T22:47:11
# 81d3c58  docs(stage2): add jira kanban evidence in docs
#   - docs/: Jira Kanban board screenshots
#   - kanban.html: interactive Kanban (Board / User Stories / Personas tabs)

# Commit 4 — 2026-09-18T21:18:57
# 2a883b5  feat(schema): implement ISTQB bug report models and sample dataset
#   - Initial src/models.py Pydantic v2 schemas
#   - BugReport, Environment, ScoreResult, FieldAlert, RewrittenBug

# Commit 3 — 2026-09-17T23:16:25
# 676b656  docs(stage2): define system architecture, data models, and scoring rubric
#   - ARCHITECTURE.md: component table, ASCII diagram, scoring rubric

# Commit 2 — 2026-09-17T20:37:47
# 48dc10c  docs(stage1): add requirements, user stories, and initial jira kanban evidence
#   - REQUIREMENTS.md: 3 personas, 4 INVEST user stories with Given/When/Then criteria
#   - Initial Kanban board (To Do / In Progress / Done)

# Commit 1 — 2026-09-16T22:50:14  [INITIAL COMMIT]
# 95f7641  docs: establish Stage 1 requirements, user stories, and initial kanban
#   - Project scaffold: src/, tests/, data/, docs/
#   - .gitignore, requirements.txt, README.md skeleton

# =============================================================================
# Summary
# =============================================================================
# Total commits : 11
# Contributors  : Ritheeshshetty
# Date range    : 2026-09-16 to 2026-09-27
# Branch        : master
# Remote        : https://github.com/Ritheeshshetty/Bug-Report-Quality-Assistant
# =============================================================================

echo ""
echo "=== 11 commits on master ==="
echo "Run: git log --oneline to verify"
echo "Repository: https://github.com/Ritheeshshetty/Bug-Report-Quality-Assistant"
