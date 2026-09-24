# PSD Download And Material Feedback Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver PSD export as one visible action and generate textured frame/trim results using role-specific AI calls with clear fallback feedback.

**Architecture:** The frontend owns a small PSD action state machine that generates only when necessary and always proceeds to authenticated download. The layered renderer resolves references per role, falling back from frame/trim references to panel references while keeping each role's own prompt and shared geometry mask.

**Tech Stack:** Next.js, React, TypeScript, FastAPI, Python, NumPy, Pillow.

---

### Task 1: Role-Specific Material Fallback

**Files:**
- Modify: `backend/rendering/layered_render.py`
- Modify: `backend/test_layered_render.py`

- [ ] Add a failing test that supplies only panel references and asserts separate panel, frame, and trim material calls.
- [ ] Resolve frame/trim references from their own role first and panel references second.
- [ ] Record inheritance and provider-failure notes without changing the geometry masks.
- [ ] Run the layered-render regression subset.
- [ ] Commit as `fix: generate textured frame and trim materials`.

### Task 2: One-Click PSD Generation And Download

**Files:**
- Modify: `frontend/src/app/render/page.tsx`
- Modify: `frontend/src/lib/renderApi.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] Add `materialMode` and `materialNote` to `RenderTask`.
- [ ] Replace separate generate/download handlers with one busy-state action that generates when needed and immediately downloads.
- [ ] Raise 4K PSD generation and download timeouts to five minutes.
- [ ] Render material mode, inheritance information, and fallback failures in the result area.
- [ ] Run `npm run build`.
- [ ] Commit as `fix: make psd export and material fallback visible`.

### Task 3: Regression And Delivery

- [ ] Run focused rendering checks.
- [ ] Run the CAD baseline and accept only the established nine unrelated failures.
- [ ] Confirm the worktree is clean.
- [ ] Push to `feat/semicircle-handles-and-quote-form-improvements` and fast-forward the local feature checkout.
