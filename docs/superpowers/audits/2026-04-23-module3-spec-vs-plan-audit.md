# Module 3 Spec vs Plan Audit — 2026-04-23

**Spec:** `docs/superpowers/specs/2026-04-23-module3-photos-testimonials-design.md` (1,134 lines)
**Plan:** `docs/superpowers/plans/2026-04-23-module3-photos-testimonials.md` (18,715 lines)
**Audit date:** 2026-04-23
**Total issues:** 38
**Methodology:** Line-by-line comparison of every spec requirement against plan implementation code.

## Context

This audit replaces a prior 56-issue audit from an earlier session whose item numbering was lost. Of the original 56 issues:
- Batch 1 (14 schema errors) was applied to the spec before the plan was generated
- Batch 2 (4 compliance-critical items, Items 28-31) was applied to the plan
- 1 item from Batch 3 (Error 23, revoked_reason param mismatch) was fixed during Batch 2 work
- Remaining batches (3-5) were never tracked in a durable document

This 38-issue list is the new baseline for Module 3 issue tracking.

---

## Issues by Severity

### HIGH (3)

#### Issue #6 — INVALID VALUE
- **Spec:** Section 3, line 529 (referencing line 111) — duplicate rejection message must be: "This photo appears to be identical to the existing [angle] photo. If this is intentional (re-take), please modify the file or use the replace option."
- **Plan:** Task 15, line ~10322 — uses: "This exact photo has already been uploaded for this angle"
- **Problem:** The spec gives an exact message string. The plan uses a different, less helpful message that omits the replace option guidance.

#### Issue #10 — UX GAP
- **Spec:** Section 5, lines 651-655 — two upload modes required: per-slot AND bulk mode with drag-to-slot staging area. Session cannot be marked complete while unassigned photos exist.
- **Plan:** Task 14, session_view.html template (lines ~9500-10200) — implements per-slot upload only.
- **Problem:** Bulk upload mode with drag-to-slot staging is completely missing. This is a major workflow feature for staff uploading multiple photos at once.

#### Issue #14 — UX GAP
- **Spec:** Section 4, lines 621-624 — blocking dialog when staff attempts advertising/case_study use with only testimonial-form consent, with specific message text and 3 action options.
- **Plan:** Entire plan reviewed — no blocking dialog implemented anywhere.
- **Problem:** The consent_service backend enforces the restriction, but the spec requires a specific UI dialog with 3 options when a staff member attempts the action. Staff could be confused when advertising use is silently blocked without explanation.

---

### MEDIUM (14)

#### Issue #3 — SCHEMA ERROR
- **Spec:** Section 2.9, lines 256-271 — `testimonial_send_log` has exactly these columns: `id, testimonial_id, touch_number, scheduled_for, sent_at, opened_at, clicked_at, status, created_at`.
- **Plan:** Task 1, lines 262-265 — adds 4 extra columns: `personalized_opening TEXT DEFAULT ''`, `is_personalized INTEGER NOT NULL DEFAULT 0`, `warning_3day_sent_at TIMESTAMP`, `skip_send_window INTEGER NOT NULL DEFAULT 0`.
- **Problem:** These support the auto-escalation feature (spec line 730) but the spec does not define them as schema columns. The plan invents schema to implement the feature.

#### Issue #4 — INVALID VALUE
- **Spec:** Section 2.9, line 266 — `testimonial_send_log.status` valid values: `scheduled, sent, opened, clicked, cancelled, suppressed, bounced`.
- **Plan:** Task 1, line 261 — adds `failed` as an additional status value.
- **Problem:** Plan introduces a status not in the spec. The spec's bounce/suppress/cancel statuses should cover failure modes.

#### Issue #11 — UX GAP
- **Spec:** Section 5, line 656 — mobile-friendly: `capture="environment"` attribute for iPad camera access.
- **Plan:** Task 14, session_view.html — file input uses `accept="image/jpeg,image/png,image/heic,image/webp"` but does NOT include `capture="environment"`.
- **Problem:** iPad camera access won't work as designed without this attribute.

#### Issue #12 — UX GAP
- **Spec:** Section 5, line 662 — retake reason dropdown: "bad lighting, patient position, camera issue, other".
- **Plan:** Task 15, patients_api.py retake endpoint (lines ~10380-10470) — accepts `retake_reason` as free-form `Form("")` text.
- **Problem:** The spec requires a specific dropdown with 4 options; the plan accepts any text.

#### Issue #13 — UX GAP
- **Spec:** Section 5, line 671 — "Visual diff: show previous session values next to each input as reference" for measurements.
- **Plan:** Task 14, session_view.html measurement form (lines ~9700-9900) — renders measurement inputs but does NOT show previous session values alongside.
- **Problem:** Missing reference data that helps staff catch measurement entry errors.

#### Issue #17 — UX GAP
- **Spec:** Section 5, lines 632-636 — session type auto-suggestion based on patient history (first=baseline, middle=mid_treatment, 5+ without final=suggest final, post-final=followup).
- **Plan:** Task 14, sessions.py `create_session` (lines ~9300-9400) — creates sessions with a default type but no auto-suggestion logic.
- **Problem:** Auto-suggestion is a time-saving UX feature for staff that the spec requires.

#### Issue #18 — UX GAP
- **Spec:** Section 5, lines 643-644 — explicit cycle creation prompt: "Patient's previous cycle ended on [date]. Is this new session part of a new treatment cycle?" with [Yes, start Cycle N+1] / [No, follow-up].
- **Plan:** Task 14, sessions.py — auto-creates cycles without prompting.
- **Problem:** The spec explicitly says "Do not silently create cycles." The plan silently creates them.

#### Issue #19 — UX GAP
- **Spec:** Section 5, line 677 — measurement override with reason: staff can save out-of-range values with required explanatory note stored in `patient_measurements.notes`.
- **Plan:** Task 15, patients_api.py `save_measurements` (lines 10476-10547) — hard rejects out-of-range values with `errors.append()`.
- **Problem:** Staff loses ability to record unusual but legitimate measurements.

#### Issue #20 — UX GAP
- **Spec:** Section 7, line 834 — gallery alt text format: "Before and after [treatment area] -- patient after [N] Zerona sessions" (no names).
- **Plan:** Task 10, gallery_service.py `generate_gallery_html` — builds HTML but no explicit alt text matching the spec format.
- **Problem:** Alt text is important for accessibility and SEO. The spec gives a specific format.

#### Issue #25 — UX GAP
- **Spec:** Section 9, line 977 — bulk tag assignment "for segmentation in Module 1 campaigns".
- **Plan:** Task 19, patients_hub.py (lines 14342-14345) — implements bulk action as `UPDATE patients SET tier = ?`, which overwrites the tier column.
- **Problem:** Overwriting `tier` with a tag value could destroy existing tier data. Spec implies a separate tagging system.

#### Issue #30 — COMPLIANCE
- **Spec:** Section 4, line 601 — consent revocation requires `revoked_reason` as free text, **required**.
- **Plan:** Task 4, consent_service.py `revoke_patient_consent` — validates reason is non-empty in service code, but route-level enforcement is not explicitly verified.
- **Problem:** If reason is optional in the route handler, it violates the spec's requirement.

#### Issue #33 — INVALID VALUE
- **Spec:** Section 2.4, lines 119-120 — measurement points: `waist, hips, thighs_left, thighs_right, arms_left, arms_right, chest, under_bust`.
- **Plan:** Task 22, test_case_study.py (lines 17832-17841) — uses different names: `upper_abdomen, lower_abdomen, chest, arms`.
- **Problem:** Test data doesn't match spec's measurement point names, which could mask bugs in aggregate calculations.

#### Issue #34 — UX GAP
- **Spec:** Section 7, line 826 — gallery output: "Schedule Your Consultation CTA button every 3-5 patients".
- **Plan:** Task 10, gallery_service.py — `generate_gallery_html` does not show explicit CTA button insertion every 3-5 patients.
- **Problem:** Missing a marketing-important element from the gallery output.

#### Issue #42 — UX GAP
- **Spec:** Section 8, lines 895-908 — case study generation should produce 9 specific sections: hero summary, clinical overview, patient cohort statistics, 3-5 featured patient stories, aggregated results, methodology footnote, Dr. Banning bio, Erchonia clinical context, conclusion.
- **Plan:** Task 11, case_study_service.py — delegates to Claude via `prompts/case_study.txt`, but plan doesn't include the prompt template content.
- **Problem:** The 9 required sections must be in the prompt. Cannot verify compliance without seeing prompt content.

#### Issue #43 — UX GAP
- **Spec:** Section 8, lines 933-938 — language rules: exact calculated numbers (no rounding), specific methodology footnote text, observed language only, no absolute claims, Claude flags medical claims.
- **Plan:** Task 11, case_study_service.py — these rules should be in the prompt template. Plan doesn't include the prompt template content.
- **Problem:** Same as #42 — prompt content not visible for verification.

---

### LOW (21)

#### Issue #1 — SCHEMA ERROR
- **Spec:** Section 2.8, line 236 — `testimonials` table ends with `created_at`; no `updated_at` column.
- **Plan:** Task 1, line 244 — adds `updated_at TIMESTAMP`.
- **Problem:** Extra column not in spec. Not harmful but not authorized.

#### Issue #2 — SCHEMA ERROR
- **Spec:** Section 2.12, lines 322-341 — `case_studies` table has no `version_number` column. Versioning is via `superseded_by` references.
- **Plan:** Task 1, line 320 — adds `version_number INTEGER NOT NULL DEFAULT 1`.
- **Problem:** Redundant with superseding-record approach. Not contradictory but beyond spec.

#### Issue #5 — BEYOND SPEC
- **Spec:** Section 11, lines 1038-1050 — exactly 10 config values specified.
- **Plan:** Task 2, lines 658-660 — adds 2 extra: `testimonial_escalation_warning_days` and `testimonial_escalation_fallback_days`.
- **Problem:** Support the auto-escalation feature but were invented by the plan.

#### Issue #7 — BEYOND SPEC
- **Spec:** Section 4, line 588 — consent upload UI captures "document template version (dropdown)" without specifying values.
- **Plan:** Task 13, lines 8412-8417 — adds `DOCUMENT_TYPES` list with 4 types.
- **Problem:** Plan invents specific dropdown values. Spec left this open intentionally.

#### Issue #8 — FUNCTION MISMATCH
- **Spec:** Section 6, line 784 — flagged testimonial notifications should use "existing Mailgun".
- **Plan:** Task 9, lines 5665-5680 — uses `from app.services.email_service import send_notification`.
- **Problem:** Spec says "existing Mailgun" suggesting `mailgun_service` should be used directly.

#### Issue #9 — FUNCTION MISMATCH
- **Spec:** Section 6, line 784 — bounce handling notifications should use "existing Mailgun".
- **Plan:** Task 9, lines 5836-5886 — uses `from app.services.email_service import send_notification`.
- **Problem:** Same as #8.

#### Issue #15 — UX GAP
- **Spec:** Section 9, line 976 — keyboard shortcuts: `/` search, `n` new session, `u` consent upload.
- **Plan:** Task 19, patients_hub.html (lines 14859-14865) — only implements `/` shortcut.
- **Problem:** Missing `n` and `u` keyboard shortcuts.

#### Issue #16 — UX GAP
- **Spec:** Section 5, line 638 — "Finalize Session" dedicated admin action button.
- **Plan:** Task 14, sessions.py — type change goes through generic `update_session` endpoint.
- **Problem:** Functionally possible but spec calls for a dedicated action.

#### Issue #21 — UX GAP
- **Spec:** Section 7, line 835 — clean filenames for WordPress: `zerona-progress-patient-a-session-1-front.jpg`.
- **Plan:** Task 10, gallery_service.py — no filename formatting matching spec's pattern.
- **Problem:** Cosmetic, but spec specifies a pattern.

#### Issue #23 — BEYOND SPEC
- **Spec:** Section 10, lines 1012-1021 — exactly 6 scheduled jobs.
- **Plan:** Task 21, scheduler.py (lines 16323-16598) — adds 7th job: `escalate_stalled_reviews_job`.
- **Problem:** Spec lists 6 jobs. Escalation logic was likely intended as part of existing jobs.

#### Issue #24 — BEYOND SPEC
- **Spec:** Section 6, line 730 — auto-escalation described in 2 sentences.
- **Plan:** Task 21, scheduler.py (lines 16323-16500) — full separate job with configurable thresholds, dedup column, skip flag.
- **Problem:** Over-engineering relative to spec's 2-sentence description. Functionally aligned.

#### Issue #26 — UX GAP
- **Spec:** Section 9, lines 985-990 — Patient Detail tabs: Overview, Sessions, Consents, Testimonials, Content Usage, Notes all in one page.
- **Plan:** Task 19, patient_detail.py/html — Sessions, Consents, Testimonials tabs link to separate route pages.
- **Problem:** Functionally complete but UX is navigate-away instead of tab-switching.

#### Issue #27 — UX GAP
- **Spec:** Section 9, lines 992-997 — Patient Data Export on patient detail page.
- **Plan:** Task 15, patients_api.py — export is an API endpoint, not on the patient detail page.
- **Problem:** Export is implemented; placement differs from spec.

#### Issue #31 — UX GAP
- **Spec:** Section 4, lines 602-606 — on consent revocation: auto-scan, flag, generate admin task list view, send email, one-click gallery removal.
- **Plan:** Task 4, consent_service.py — implements flagging and email. Admin task list as a separate view is missing.
- **Problem:** Core workflow implemented; dedicated task list view missing.

#### Issue #35 — UX GAP
- **Spec:** Section 7, lines 865-868 — gallery photo ordering options: recent first (default), alphabetical, by treatment area, manual.
- **Plan:** Task 17, galleries.py — no ordering options exposed in admin UI.
- **Problem:** Default ordering works but admin cannot choose alternatives.

#### Issue #36 — UX GAP
- **Spec:** Section 7, line 868 — patient privacy: first-name-only or initials, no identifying details.
- **Plan:** Task 17, gallery_admin.html — admin view shows `first_name + last_name[0]`. Published gallery privacy handling not explicitly verified.
- **Problem:** Admin view acceptable; published gallery display not verified.

#### Issue #37 — BEYOND SPEC
- **Spec:** Section 10, line 1028 — failure handling: email "via Mailgun".
- **Plan:** Task 21, scheduler.py (line 15578) — uses `email_service.send_notification`.
- **Problem:** Same pattern as #8/#9.

#### Issue #38 — UX GAP
- **Spec:** Section 4, lines 617-620 — consent status UI with tooltip/info icon explaining scope limitations.
- **Plan:** Task 19, patient_detail.html — implements visual hierarchy (solid/outlined checkmarks) but no tooltip.
- **Problem:** Tooltip explanation missing.

#### Issue #40 — UX GAP
- **Spec:** Section 8, lines 874-882 — case study readiness indicator with specific messages and thresholds (20+/10-19/<10).
- **Plan:** Task 18, case_study_admin.html (lines 13517-13530) — implements green/yellow/red levels via `get_readiness_indicator()`.
- **Problem:** Likely matches but exact threshold/message verification not possible from plan code alone.

#### Issue #41 — UX GAP
- **Spec:** Section 8, line 893 — case study patient selection: min 1, max 8.
- **Plan:** Task 18, case_studies.py — enforces max 8 server-side, checks min 1 server-side, but no client-side min validation.
- **Problem:** Server validation present; no client-side UX message for min 1.

#### Issue #44 — UX GAP (note: was originally classified as BEYOND SPEC but is actually a structural gap)
- **Spec:** Section 13, lines 1068-1109 — prompt files should be separate: `prompts/testimonial_draft.txt`, `prompts/testimonial_request.txt`, `prompts/case_study.txt`, `prompts/patient_selection.txt`.
- **Plan:** Tasks 9 and 11 — prompt content is inline in Python service files. No separate prompt files created.
- **Problem:** Spec calls for separate prompt files for maintainability.

---

## Summary Table

| Severity | Count | Issue Numbers |
|----------|-------|---------------|
| HIGH | 3 | #6, #10, #14 |
| MEDIUM | 14 | #3, #4, #11, #12, #13, #17, #18, #19, #20, #25, #30, #33, #34, #42, #43 |
| LOW | 21 | #1, #2, #5, #7, #8, #9, #15, #16, #21, #23, #24, #26, #27, #31, #35, #36, #37, #38, #40, #41, #44 |

| Category | Count |
|----------|-------|
| UX Gap | 22 |
| Beyond Spec | 5 |
| Schema Error | 3 |
| Invalid Value | 3 |
| Function Mismatch | 2 |
| Compliance | 1 |
