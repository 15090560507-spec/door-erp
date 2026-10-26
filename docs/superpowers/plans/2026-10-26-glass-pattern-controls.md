# Glass Pattern Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove glass decoration from bars and make all internal-line pattern controls effective.

**Architecture:** Keep the existing generator and parameter keys. Give bars an early non-glass branch, respect explicit zero inset, and use spacing for grid paired-line width while preserving divider centers/counts. Expose only relevant shared B2/B4 controls through a small testable frontend scope helper.

**Tech Stack:** ezdxf, Python unittest, React/TypeScript, Node tests, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-glass-pattern-controls-design.md`

## Constraints

- Keep the current form layout and H/H+ structural geometry.
- The user confirmed: spacing controls paired-line gap; preserve counts and equal divider-center positions.
- Exclude account data, template assets, previous metadata input changes, and the DXF transport implementation from this patch.

## Tasks

- [x] Reproduce extra glass/perimeter, zero inset fallback, ineffective grid spacing, and silent range caps with real-DXF tests in `backend/test_glass_pattern_controls.py`.
- [x] In `backend/drawing.py`, draw bars before glass decorations, retain zero inset, reject invalid dimensions, and connect grid paired-line width to spacing.
- [x] In `frontend/src/lib/glassPatternControls.ts` and its Node test, define display labels and B2/B4 parameter applicability without changing stored option strings.
- [x] In `frontend/src/components/DoorForm.tsx`, add optional Select display labels and render only controls used by each active region, including a bar-pitch label for vertical-only patterns.
- [x] Update the legacy grid tests in `backend/test_cad_new_options.py` to assert configured paired-line width rather than hard-coded 15mm, without weakening center/count assertions.
- [x] Run geometry, cache/download, metadata, frontend tests, type checking, lint, and desktop/mobile verification. Record the user's confirmed spacing interpretation and existing baseline failures in the verification record.
- [x] Reviewed and pushed repair commit `ad9abc7` to the authorized branch. Tencent Cloud deployment is still required.
