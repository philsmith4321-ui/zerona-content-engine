# Module 3: Before/After Photos + Testimonial Collection + Case Studies — Design Spec

**Goal:** Standardize photo documentation, manage consent rigorously, automate testimonial gathering, and generate publication-ready case studies. This module feeds content back into the existing Review Queue and WordPress publishing pipeline.

**Architecture:** Builds on Module 1 (Mailgun sending), Module 2 (GHL contact linkage), the existing `content_pieces` review queue, and the WordPress integration. No new external API dependencies. Core principle: consent is sacred — checked at query time, enforced by scope+source, audit-logged on every use.

**Tech Stack:** FastAPI, SQLite (sync sqlite3), Jinja2+HTMX+Tailwind, Pillow + pillow-heif (image processing), Anthropic Claude API, APScheduler, existing Mailgun + WordPress integrations.

---

## 1. Patient Identity Reconciliation

Three modules create three patient-adjacent records. This section defines how they reconcile.

### The Problem

| Source | Table | Origin |
|--------|-------|--------|
| CSV import (Module 1) | `patients` | Bulk import of ~7,500 existing patients |
| GHL webhook (Module 2) | `ghl_contacts` | New leads who come through GHL CRM |
| Walk-in (Module 3) | — | Patient arrives at practice without prior digital record |

### The Solution

**`patients` is the canonical patient record.** All Module 3 tables reference `patients.id`.

- Add `ghl_contact_id TEXT` column to `patients` table (nullable) — links to the GHL mirror when applicable.
- When a GHL contact converts to a paying Zerona patient, staff creates or links a `patients` record via admin UI.
- Add "Create New Patient" admin action for walk-ins not in CSV import and not from GHL.
- `ghl_contacts` remains a read-only mirror of GHL data. It is never the source of truth for patient identity.
- Matching logic: when linking, check email first (exact match), then phone (normalized), then manual staff confirmation.

---

## 2. Database Schema

### Migration: `005_create_photo_testimonial_tables.sql`

**New tables (16 total):**

#### 2.1 Treatment Cycles

```sql
CREATE TABLE IF NOT EXISTS patient_treatment_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    cycle_number INTEGER NOT NULL DEFAULT 1,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(patient_id, cycle_number)
);
```

Groups sessions into treatment cycles. A patient may have multiple cycles (e.g., returns 6 months later for another round).

#### 2.2 Photo Sessions

```sql
CREATE TABLE IF NOT EXISTS patient_photo_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    cycle_id INTEGER REFERENCES patient_treatment_cycles(id),
    session_number INTEGER NOT NULL,
    session_date DATE NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'mid_treatment',
        -- baseline, mid_treatment, final, followup, incomplete
    notes TEXT DEFAULT '',
    completed_at TIMESTAMP,
    testimonial_request_eligible_at TIMESTAMP,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_patient ON patient_photo_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_type ON patient_photo_sessions(session_type);
```

`testimonial_request_eligible_at` is set when BOTH conditions are met: `session_type='final'` AND session is complete (all 6 photos + all 8 measurements + `completed_at` set).

#### 2.3 Photos

```sql
CREATE TABLE IF NOT EXISTS patient_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES patient_photo_sessions(id),
    angle TEXT NOT NULL,
        -- front, side_left, side_right, 45_degree_left, 45_degree_right, back
    file_path TEXT NOT NULL,
    preview_path TEXT,
    thumbnail_path TEXT,
    file_hash TEXT NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    is_current INTEGER NOT NULL DEFAULT 1,
    superseded_at TIMESTAMP,
    superseded_by INTEGER REFERENCES patient_photos(id),
    retake_reason TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_photos_session ON patient_photos(session_id);
CREATE INDEX IF NOT EXISTS idx_photos_current ON patient_photos(session_id, angle, is_current);
```

Six required angles per session. Versioned — re-uploads create new records with `is_current=1`, old records get `is_current=0` + `superseded_at`. File hash (SHA-256) prevents duplicate uploads within the same session.

#### 2.4 Measurements

```sql
CREATE TABLE IF NOT EXISTS patient_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES patient_photo_sessions(id),
    measurement_point TEXT NOT NULL,
        -- waist, hips, thighs_left, thighs_right, arms_left, arms_right, chest, under_bust
    value_inches REAL NOT NULL,
    measured_by TEXT DEFAULT '',
    measured_at TIMESTAMP,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, measurement_point)
);
```

8 measurement points per session. `waist`, `hips`, `thighs_left`, `thighs_right`, `arms_left`, `arms_right` are included in aggregate "total inches lost" calculations. `chest` and `under_bust` are tracked for clinical use only, excluded from marketing aggregates.

#### 2.5 Session Type History

```sql
CREATE TABLE IF NOT EXISTS session_type_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES patient_photo_sessions(id),
    old_type TEXT NOT NULL,
    new_type TEXT NOT NULL,
    changed_by TEXT DEFAULT '',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT DEFAULT ''
);
```

Audit trail for session type changes. Logged automatically when session type is edited.

#### 2.6 Consent Documents

```sql
CREATE TABLE IF NOT EXISTS consent_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    document_path TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'media_release_v1',
    signed_date DATE NOT NULL,
    uploaded_by TEXT DEFAULT '',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Parent table for uploaded signed consent forms. One document can ground multiple scope grants. `document_path` uses UUID filenames: `/uploads/consents/{patient_id}/{uuid}.{ext}`.

#### 2.7 Patient Consents

```sql
CREATE TABLE IF NOT EXISTS patient_consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    scope TEXT NOT NULL,
        -- website, social, advertising, email_testimonial, case_study
    consent_source TEXT NOT NULL DEFAULT 'signed_document',
        -- signed_document, testimonial_form, manual_staff_entry
    source_document_id INTEGER REFERENCES consent_documents(id),
    granted_at TIMESTAMP NOT NULL,
    granted_by TEXT DEFAULT '',
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP,
    revoked_by TEXT DEFAULT '',
    revoked_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_consents_patient ON patient_consents(patient_id);
CREATE INDEX IF NOT EXISTS idx_consents_scope ON patient_consents(patient_id, scope);
```

One row per scope per grant. `consent_source` determines legal weight:
- `signed_document`: strongest — valid for all scopes including advertising and case study
- `testimonial_form`: valid for website, social, email_testimonial only — NOT valid for advertising or case_study
- `manual_staff_entry`: intermediate — valid for all scopes, staff takes responsibility

#### 2.8 Testimonials

```sql
CREATE TABLE IF NOT EXISTS testimonials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    session_id INTEGER REFERENCES patient_photo_sessions(id),
    cycle_id INTEGER REFERENCES patient_treatment_cycles(id),
    token TEXT UNIQUE,
    token_expires_at TIMESTAMP,
    rating INTEGER,
    text TEXT DEFAULT '',
    video_path TEXT,
    status TEXT NOT NULL DEFAULT 'requested',
        -- requested, submitted, declined_this_time, declined_permanent,
        -- expired_no_response, flagged
    flag_reason TEXT,
    submitted_at TIMESTAMP,
    consent_website INTEGER DEFAULT 0,
    consent_social INTEGER DEFAULT 0,
    consent_advertising INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_testimonials_patient ON testimonials(patient_id);
CREATE INDEX IF NOT EXISTS idx_testimonials_token ON testimonials(token);
CREATE INDEX IF NOT EXISTS idx_testimonials_status ON testimonials(status);
```

`video_path` is nullable — stubbed for future public video upload (gated by `ENABLE_TESTIMONIAL_VIDEO_UPLOAD` feature flag). Admin-only video attach populates this field.

#### 2.9 Testimonial Send Log

```sql
CREATE TABLE IF NOT EXISTS testimonial_send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    testimonial_id INTEGER NOT NULL REFERENCES testimonials(id),
    touch_number INTEGER NOT NULL,
        -- 1 = initial request, 2 = reminder 1, 3 = reminder 2
    scheduled_for TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'scheduled',
        -- scheduled, sent, opened, clicked, cancelled, suppressed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_send_log_testimonial ON testimonial_send_log(testimonial_id);
CREATE INDEX IF NOT EXISTS idx_send_log_status ON testimonial_send_log(status);
```

Tracks the 3-touch send cadence. `cancelled` = patient responded before this touch fired. `suppressed` = patient opted out between scheduling and sending.

#### 2.10 Patient Preferences

```sql
CREATE TABLE IF NOT EXISTS patient_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    preference_type TEXT NOT NULL,
        -- testimonial_requests, marketing_emails
    value TEXT NOT NULL DEFAULT 'all',
        -- all, none, final_only
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(patient_id, preference_type)
);
```

Two-tier opt-out system. `testimonial_requests='none'` permanently suppresses automated testimonial emails. Independent from CAN-SPAM marketing email unsubscribes.

#### 2.11 Content Usage Log

```sql
CREATE TABLE IF NOT EXISTS content_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    photo_id INTEGER REFERENCES patient_photos(id),
    testimonial_id INTEGER REFERENCES testimonials(id),
    used_in TEXT NOT NULL,
        -- WordPress post URL, gallery page URL, external URL, etc.
    scope_used TEXT NOT NULL,
        -- website, social, advertising, case_study
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    removal_status TEXT NOT NULL DEFAULT 'active',
        -- active, removal_pending, removed, kept_despite_flag
    removal_requested_at TIMESTAMP,
    removal_requested_by TEXT,
    removal_reason TEXT,
    removed_at TIMESTAMP,
    removed_by TEXT,
    kept_despite_flag_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_patient ON content_usage_log(patient_id);
CREATE INDEX IF NOT EXISTS idx_usage_removal ON content_usage_log(removal_status);
```

Every published use of a patient's likeness or words is logged here. On consent revocation, all active uses under that scope are flagged as `removal_pending`. Staff resolves each: remove content, or explicitly keep with documented reason.

#### 2.12 Case Studies

```sql
CREATE TABLE IF NOT EXISTS case_studies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    patients_included_count INTEGER NOT NULL DEFAULT 0,
    featured_patient_ids TEXT DEFAULT '[]',
    aggregate_data TEXT DEFAULT '{}',
    generated_markdown TEXT DEFAULT '',
    edited_markdown TEXT,
    metadata_json TEXT DEFAULT '{}',
    wp_post_id INTEGER,
    wp_post_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
        -- draft, reviewed, published
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    published_by TEXT
);
```

#### 2.13 Case Study Selections

```sql
CREATE TABLE IF NOT EXISTS case_study_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_study_id INTEGER NOT NULL REFERENCES case_studies(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    recommended_by_ai INTEGER NOT NULL DEFAULT 0,
    recommendation_reasoning TEXT DEFAULT '',
    selected_by_admin INTEGER NOT NULL DEFAULT 0,
    selection_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Tracks Claude's recommendations vs admin's final picks for featured patients.

#### 2.14 Case Study Overrides

```sql
CREATE TABLE IF NOT EXISTS case_study_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_study_id INTEGER NOT NULL REFERENCES case_studies(id),
    metric_name TEXT NOT NULL,
    original_value TEXT NOT NULL,
    override_value TEXT NOT NULL,
    reason TEXT NOT NULL,
    overridden_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.15 Gallery Versions

```sql
CREATE TABLE IF NOT EXISTS gallery_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gallery_slug TEXT NOT NULL DEFAULT 'zerona-results',
    wp_page_id INTEGER,
    patients_included TEXT DEFAULT '[]',
    photo_ids_included TEXT DEFAULT '[]',
    patient_count INTEGER NOT NULL DEFAULT 0,
    generated_html TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    published_by TEXT,
    is_current INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT ''
);
```

Snapshot of every gallery generation. `is_current=1` marks the live version.

#### 2.16 WordPress Media Uploads

```sql
CREATE TABLE IF NOT EXISTS wp_media_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_photo_id INTEGER NOT NULL REFERENCES patient_photos(id),
    wp_media_id INTEGER NOT NULL,
    wp_media_url TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wp_media_photo ON wp_media_uploads(patient_photo_id);
```

Tracks photos uploaded to WordPress media library to prevent re-uploading.

### Schema Modifications

#### Alter `patients` table (in migration 005):

```sql
ALTER TABLE patients ADD COLUMN ghl_contact_id TEXT;
CREATE INDEX IF NOT EXISTS idx_patients_ghl ON patients(ghl_contact_id);
```

Links the canonical patient record to the GHL contacts mirror when applicable.

---

## 3. File Storage & Image Processing

### Dependencies

Add to `requirements.txt`:
```
Pillow>=11.0,<12.0
pillow-heif>=0.18.0
```

### Config Values

```
MAX_PHOTO_UPLOAD_MB=25
MAX_VIDEO_UPLOAD_MB=200
MAX_CONSENT_UPLOAD_MB=15
```

### Upload Accepts

- Photos: JPEG, PNG, HEIC, WebP
- Consent docs: PDF, JPG, PNG, HEIC
- Videos (admin-only): MP4, MOV, AVI, WebM

### HEIC Handling

Convert to JPEG on upload via `pillow-heif`. Register HEIF opener with Pillow at app startup.

### EXIF Processing

1. `ImageOps.exif_transpose()` before any resize (fixes iPhone sideways photos)
2. Strip all EXIF metadata from preview and thumbnail versions (removes GPS, camera serial, etc.)
3. Preserve EXIF on original for internal clinical reference

### Generated Sizes

| Size | Longest side | Quality | Filename | Purpose |
|------|-------------|---------|----------|---------|
| Thumbnail | 400px | JPEG 85 | `{angle}_thumb.jpg` | Admin grids, session browsing |
| Preview | 1200px | JPEG 85 | `{angle}_preview.jpg` | Side-by-side comparisons, gallery |
| Original | Untouched | Original | `{angle}_original.{ext}` | Case study publication, high-res |

### Storage Paths

```
/uploads/photos/{patient_id}/{session_id}/{angle}_original.{ext}
/uploads/photos/{patient_id}/{session_id}/{angle}_preview.jpg
/uploads/photos/{patient_id}/{session_id}/{angle}_thumb.jpg
/uploads/consents/{patient_id}/{uuid}.{ext}
/uploads/videos/{patient_id}/{testimonial_id}.{ext}
```

### Security

- Consent documents: NEVER served publicly. Authenticated route `/admin/consents/{document_id}/view` streams file after auth check.
- Add `/uploads/` to `.gitignore`.
- Consent document filenames use UUIDs, not sequential IDs.

### Deduplication

SHA-256 hash stored per photo. Reject duplicate uploads within the same session.

### Processing

- Synchronous during upload (small files, fast operation)
- Wrap in try/except — if thumbnail generation fails, save original anyway, log error
- Background job retries failed thumbnails every 30 minutes
- Admin action: "Regenerate thumbnails" per session or globally

---

## 4. Consent System

### Three Consent Sources

| Source | Legal Weight | Valid For |
|--------|-------------|-----------|
| `signed_document` | Strongest | All scopes (website, social, advertising, email_testimonial, case_study) |
| `testimonial_form` | Limited | website, social, email_testimonial ONLY |
| `manual_staff_entry` | Intermediate | All scopes (staff takes responsibility) |

### Scope Enforcement Matrix

| Scope | signed_document | testimonial_form | manual_staff_entry |
|-------|:-:|:-:|:-:|
| website | Yes | Yes | Yes |
| social | Yes | Yes | Yes |
| email_testimonial | Yes | Yes | Yes |
| advertising | Yes | **No** | Yes |
| case_study | Yes | **No** | Yes |

### Core Function

```python
def patient_has_active_consent(
    patient_id: int,
    scope: str,
    required_source: Optional[str] = None,
    as_of_date: Optional[datetime] = None,
) -> bool:
```

Used EVERYWHERE consent is checked. Accepts optional `required_source` to enforce signed-document-only for advertising/case_study scopes. Checks: scope matches, `granted_at <= as_of_date`, `expires_at` is null or > `as_of_date`, `revoked_at` is null.

For advertising and case_study scopes, automatically requires `consent_source IN ('signed_document', 'manual_staff_entry')` even if `required_source` is not explicitly passed.

### Consent Grant Workflow

1. Staff uploads one scanned consent form (PDF/JPG/PNG/HEIC, max 15MB)
2. UI captures: document template version (dropdown), signed date, per-scope checkboxes matching what patient checked on paper
3. System creates one `consent_documents` record + N `patient_consents` records (one per checked scope)
4. Default expiration: 2 years from `granted_at` (configurable via `CONSENT_DEFAULT_EXPIRATION_YEARS`)
5. Staff can override expiration per grant

### Consent from Testimonial Form

Testimonial form checkboxes create `patient_consents` records with `consent_source='testimonial_form'` and `source_document_id=NULL`. These are valid for website/social/email_testimonial but NOT for advertising or case_study.

Upgrade path: if patient later signs a full release, the signed document consent supersedes testimonial-form consent for the same scope. Both records preserved in history.

### Revocation

- Always soft: `revoked_at` timestamp + `revoked_reason` (free text, required) + `revoked_by`
- On revocation, system auto-scans `content_usage_log` for all active uses under that patient+scope
- Flags matching entries as `removal_status='removal_pending'`
- Generates admin task list: "Content to review after [patient] revoked [scope] consent"
- Sends email notification to Chris directly for urgent cases (published gallery content)
- Emergency gallery removal: one-click "Remove this patient from gallery now" action

### Expiration

- Default: 2 years from `granted_at` (configurable via `CONSENT_DEFAULT_EXPIRATION_YEARS=2`)
- Nightly APScheduler job:
  - 30-day lookahead: surfaces in admin "Consent Expiring Soon" dashboard
  - Expired consents: auto-sets `revoked_at` with `revoked_reason='expired'`, flags affected content

### Consent UI

- Per-patient consent status shows all scopes with visual hierarchy:
  - Signed document: solid green checkmark + "Signed consent on file"
  - Testimonial form: outlined checkmark + "Web form consent — limited scope"
  - Tooltip/info icon explains what each can and can't be used for
- Blocking dialog when staff attempts advertising/case_study use with only testimonial-form consent:
  - "Patient [Name] has not signed a media release — only provided web-form consent. Advertising use requires a signed release."
  - Options: [Upload signed document] [Request signed release via email] [Exclude from this publication]

---

## 5. Photo Session & Measurement Workflow

### Session Creation

- Session type auto-suggested from patient history:
  - First session → suggest `baseline`
  - Middle sessions → suggest `mid_treatment`
  - 5+ sessions with no `final` → suggest `final` as option
  - Post-final → suggest `followup`
- Type always editable after creation, changes logged in `session_type_history`
- "Finalize Session" admin action: changes `mid_treatment` → `final`, triggers testimonial scheduler if session is also complete

### Treatment Cycles

- `patient_treatment_cycles` groups sessions into cycles
- First session auto-creates cycle 1 if none exists
- New cycle created when a session is added after a previous cycle's `final` session
- Gallery auto-picks up latest complete cycle's photos
- Staff can choose which cycle's photos to feature in case studies

### Photo Upload UI

- All 6 angle slots shown as visual grid with placeholders
- Two upload modes:
  - **Per-slot**: click specific angle slot, select file
  - **Bulk**: "Upload multiple photos" → multi-select → photos appear in "Unassigned" staging area → staff drags each to correct angle slot
- Progress bar: "X of 6 angles uploaded"
- Session cannot be marked complete while unassigned photos exist or angle slots are empty
- Mobile-friendly: `capture="environment"` attribute for iPad camera access

### Re-takes (Versioning)

- New upload for existing angle creates new record with `is_current=1`
- Previous photo: `is_current=0`, `superseded_at` set, `superseded_by` references new photo
- Prompt for `retake_reason` on re-upload (dropdown: bad lighting, patient position, camera issue, other)
- Version history viewable per angle with option to restore older version as current
- All queries filter `is_current=1` by default

### Measurements

- Single form with all 8 measurement points
- Partial saves allowed (enter what you know, come back later)
- Session completion requires all 8 measurements filled
- Visual diff: show previous session values next to each input as reference

### Measurement Validation

- **Soft validation**: if value differs from previous session by >4 inches, show "Confirm unusual value" prompt. Staff can confirm and save.
- **Hard validation**: reject values outside plausible range (e.g., waist <15 or >80 inches). Catches typos like "325" instead of "32.5".
- **Override with reason**: staff can save out-of-range values with required explanatory note.

### Session Completion

Requires ALL of:
1. All 6 photo angles uploaded (all `is_current=1`)
2. All 8 measurements recorded
3. No unassigned photos in staging

Sets `completed_at` timestamp. If `session_type='final'`, also sets `testimonial_request_eligible_at`.

### Session Archival

- "Archive Session" action (soft-delete via `archived_at` timestamp)
- Archived sessions excluded from all lists, counts, gallery, case study queries
- Visible in hidden "Archived Sessions" admin view for audit
- No hard delete through UI

---

## 6. Testimonial Collection

### Trigger

`testimonial_request_eligible_at` set when session is both `final` and complete (all 6 photos + all 8 measurements + `completed_at`).

APScheduler `check_testimonial_requests` job runs daily at 9am CT, finds eligible sessions.

### Multiple Cycles

- New treatment cycle = new testimonial request eligible
- Guard: if patient submitted a testimonial in the last 90 days, skip automated request and flag for manual staff decision
- One-testimonial-per-cycle, not per-patient-lifetime

### 3-Touch Cadence

| Touch | Default Day | Content | Review Required |
|-------|------------|---------|-----------------|
| 1 | Day 7 | Claude-personalized opening + static body | Yes (content review queue) |
| 2 | Day 14 | Fully static "gentle reminder" | No (auto-send) |
| 3 | Day 21 | Fully static "last chance" | No (auto-send) |

All intervals configurable: `TESTIMONIAL_REQUEST_INITIAL_DAYS`, `TESTIMONIAL_REQUEST_REMINDER_1_DAYS`, `TESTIMONIAL_REQUEST_REMINDER_2_DAYS`.

Each touch logged in `testimonial_send_log` with status tracking.

After Touch 3 with no response: mark `testimonials.status='expired_no_response'`.

### Touch 1 Personalization

- Claude generates 1-2 sentence personalized opening referencing patient data (sessions completed, time span, measurement progress)
- If personalization data is thin (minimal sessions, no notable changes), fall back to static template
- Generated opening goes through content review queue before sending
- Auto-escalation: if approval pending >3 days past scheduled send, email notification to Chris. If still pending 5 days past, send static fallback version automatically.

### Send Window

- Tuesday-Thursday only, 10am-2pm America/Chicago
- If scheduled send falls outside window, push to next eligible window

### Suppression Checks

- Re-check `patient_preferences` at send time (not just schedule time)
- If patient opted out between scheduling and sending, cancel send and mark `testimonial_send_log.status='suppressed'`
- If patient responded to earlier touch, cancel remaining touches and mark `status='cancelled'`

### Public Testimonial Form (`/testimonial/{token}`)

- Signed, single-use token (URL-safe, `secrets.token_urlsafe(32)`)
- Token expires after 30 days (`TESTIMONIAL_TOKEN_EXPIRY_DAYS=30`)
- Fields:
  - Star rating (1-5, required)
  - Text testimonial (optional, 2000 char max)
  - Consent checkboxes: website, social, advertising
  - No video upload field (hidden behind `ENABLE_TESTIMONIAL_VIDEO_UPLOAD=false` feature flag)
- Two decline options:
  - "Not this time" → sets `status='declined_this_time'`, cancels remaining touches, patient eligible for future cycles
  - "No thanks, please don't ask me again" → sets `status='declined_permanent'`, sets `patient_preferences.testimonial_requests='none'`
- Mailto link at bottom: "Want to share a video testimonial? Email it to [practice email]"

### Quality Check on Submission

Two-layer check — deterministic first, then Claude:

1. **Deterministic flags** (no API call needed):
   - Rating <= 2 → flag as `low_rating`
   - Empty text with low rating → flag as `low_rating_no_context`

2. **Keyword scan** (belt-and-suspenders, always runs):
   - Scan for adverse event terms: "side effect", "burn", "pain", "injury", "hospital", "doctor", "emergency", "allergic", "reaction", "complaint", "sue", "lawyer", "regulatory", "FDA", "malpractice"
   - If ANY keyword matches → flag as `adverse_event_keyword`

3. **Claude check** (runs if not already flagged by deterministic checks):
   - Check for: medical complaints, adverse event language, confused content (wrong treatment described)
   - If Claude flags → flag as `adverse_event_ai` or `confused_content`

4. **If EITHER deterministic OR Claude check flags**: set `testimonials.status='flagged'`, store `flag_reason`. Send immediate email notification to Chris (not just admin queue). Skip auto-generation of social posts.

5. **Non-flagged 3+ star testimonials**: Claude generates 3 content drafts:
   - Short social post (Facebook/Instagram)
   - Longer caption
   - Blog paragraph for case study
   - Drafts inserted into `content_pieces` with `content_type='testimonial_derived'`, category='social_proof'
   - Each draft respects consent scopes granted on submission

### Admin Video Attach

- Staff can manually upload video to existing testimonial record
- Storage: `/uploads/videos/{patient_id}/{testimonial_id}.{ext}`
- Accepts: MP4, MOV, AVI, WebM. Max 200MB (`MAX_VIDEO_UPLOAD_MB`)
- HTML5 `<video>` playback in admin UI with download link fallback
- Poster frame: extract first frame using Pillow if MP4, otherwise no poster

### Opt-Out System

- `patient_preferences` table with two-tier opt-out
- Email footer: one-click permanent opt-out link
- Suppression checked at send time, not just schedule time

---

## 7. Gallery Generator

### Generation Flow

1. Admin creates gallery instance (or selects existing to regenerate)
2. System queries qualifying patients: complete final session + `patient_has_active_consent(scope='website')`
3. Admin reviews patient list, can include/exclude individuals
4. Preview rendered in-app (dry-run option: preview without publishing)
5. Admin clicks "Push to WordPress" to publish

### Output Format

- Static HTML, semantic markup (`<article>`, `<figure>`, `<figcaption>`, heading hierarchy)
- Vertically laid out, one section per patient
- Before (baseline) on left, after (final) on right (stacked on mobile)
- Session count + progress summary below each pair
- "Schedule Your Consultation" CTA button every 3-5 patients
- No JavaScript dependencies — renders consistently across all WordPress themes

### Photo Delivery to WordPress

- Upload preview-size images (1200px) to WordPress media library via REST API
- Track in `wp_media_uploads` table — check before re-uploading (dedup)
- Generated gallery embeds `<img>` tags pointing to WordPress-hosted URLs
- Alt text: "Before and after [treatment area] — patient after [N] Zerona sessions" (no names)
- Clean filenames: `zerona-progress-patient-a-session-1-front.jpg`

### WordPress Page Management

- Configurable page slug (default: `/zerona-results`)
- First generation creates page; subsequent regenerations update existing page
- Store WP page ID in `gallery_versions`
- Preserve URL/slug across regenerations
- Support "Publish as draft" for testing

### Gallery Updates

- Manual "Regenerate Gallery" action only — never auto-regenerate
- Change indicators on admin page:
  - "Last generated: [date]"
  - "X new patients would be added"
  - "Y patients would be removed (consent revoked/expired)"
  - "Z patients have updated photos"
- Emergency consent revocation: one-click "Remove this patient from gallery now" — regenerates excluding that patient, logs as emergency removal

### Gallery Drift Detection (Safety Net)

Daily APScheduler job `check_gallery_drift`: for each published gallery, compares currently included patients against today's qualifying set. Flags patients currently in gallery whose consent has been revoked/expired but haven't been removed. Surfaces as dashboard alert.

### Version History

`gallery_versions` table stores snapshot of each generation: patients included, photo IDs, timestamp, publisher. `is_current=1` marks live version.

### Photo Ordering

- Default: most recent completion date first
- Admin alternatives: alphabetical by first initial, by treatment area, manual order
- Within patient section: baseline first, final second, side by side
- Patient privacy: first-name-only or initials, no identifying details beyond consented testimonial text

---

## 8. Case Study Generator

### Readiness Indicator (Soft, Not a Gate)

| Qualifying Patients | Indicator | Message |
|---------------------|-----------|---------|
| 20+ | Green | "Ready to generate a strong case study" |
| 10-19 | Yellow | "Generation possible but results will be limited" |
| <10 | Red | "Not recommended — too few for meaningful aggregates" |

Generation always allowed. `patients_included_count` stored in `case_studies` table.

### Generation Flow

1. Admin clicks "Generate Case Study"
2. **Patient selection screen**: Claude recommends 3-5 from qualifying pool with reasoning. Selection logic prioritizes:
   1. Consent scope (must have `case_study` consent from signed document)
   2. Rating (4-5 stars)
   3. Measurement delta magnitude (weighted by baseline — smaller frame not penalized)
   4. Testimonial text quality (Claude evaluates length, specificity)
   5. Photo completeness (all 6 angles, baseline + final)
3. Recommendations logged in `case_study_selections`. Admin confirms/swaps (min 1, max 8).
4. **Review Aggregate Numbers screen**: calculated metrics displayed, admin can override any value with required reason (logged in `case_study_overrides`)
5. **Claude generates structured sections** from real data:
   - Hero summary
   - Clinical overview
   - Patient cohort statistics
   - 3-5 featured patient stories (from testimonials)
   - Aggregated results
   - Methodology footnote
   - Dr. Banning bio
   - Erchonia clinical context
   - Conclusion
6. Admin previews full rendered document, can edit any section inline
7. Both generated draft (`generated_markdown`) and admin-edited final (`edited_markdown`) saved
8. Push to WordPress as blog post draft with embedded before/after gallery
9. All featured patients logged in `content_usage_log`

### Aggregate Metrics

Calculated from baseline→final measurement deltas:

**6 included measurement points**: waist, hips, thighs_left, thighs_right, arms_left, arms_right

**Excluded from aggregate** (tracked per-patient for clinical use): chest, under_bust

**Metrics calculated:**
- Average total inches lost
- Median total inches lost
- Range (min, max)
- Average satisfaction rating
- Percentage rating 4+ stars
- Average sessions completed
- Patient count
- Optional: demographic breakdown (age range, gender distribution) — togglable in generation UI

### Language Rules

- Use exact calculated numbers (no rounding/approximation)
- Methodology footnote: "Results based on [N] patients who completed the full Zerona Z6 protocol between [start] and [end]. Measurements taken at baseline and final session using standardized 6-point body measurement protocol."
- Observed language only: "patients in this cohort lost an average of X inches"
- No absolute claims: "clinically proven", "guaranteed", etc.
- Claude flags anything resembling medical claims for admin review

---

## 9. Admin UI & Navigation

### Sidebar Restructure

```
CONTENT
  Overview
  Review Queue
  Calendar
  Library
  Blog Posts

OUTREACH
  Campaigns
  Referrals
  Patients          ← NEW

INSIGHTS
  Analytics
  Logs

SYSTEM
  Settings
```

Section labels: small, uppercase, muted color. No collapse/expand — purely visual grouping.

### Patients Hub (`/dashboard/patients`)

- **Search bar**: find patient by name, email, phone (top of page, "/" keyboard shortcut)
- **Quick stats row**: total patients, active consents, incomplete sessions, testimonials awaiting response, consents expiring this month
- **Action cards**: Import CSV, New Session, Upload Consent, Generate Gallery, Generate Case Study
- **Recent activity feed**: last 10 patient-related events
- **Tabbed navigation**: All Patients, Sessions, Consents, Testimonials, Galleries, Case Studies
- **Keyboard shortcuts**: `/` search, `n` new session, `u` consent upload

### Patient Detail (`/dashboard/patients/{patient_id}`)

Horizontal tabs:
- **Overview** (default): basic info, session timeline, consent status, lifetime stats
- **Sessions**: all sessions with photos and measurements
- **Consents**: consent history with document links, visual source indicators
- **Testimonials**: submitted testimonials and request history
- **Content Usage**: audit log of published uses
- **Notes**: free-form admin notes

### Breadcrumbs

All patient-related pages: `Patients > Sessions > [Patient Name] > Session 4`

### Dashboard Overview Tiles

Add to main dashboard:
- "Consent Expiring Soon" (next 30 days count)
- "Testimonials Awaiting Response" (requested, not yet submitted)
- "Sessions Incomplete" (created but not all photos/measurements)

---

## 10. Scheduled Jobs (APScheduler Additions)

| Job ID | Schedule | Purpose |
|--------|----------|---------|
| `check_testimonial_requests` | Daily 9am CT | Find eligible sessions, generate personalized openings, create send log entries |
| `send_testimonial_emails` | Daily 10am CT, Tue-Thu only | Send approved/due testimonial emails within the send window |
| `check_consent_expirations` | Daily 1am CT | 30-day lookahead warnings, auto-revoke expired, flag affected content |
| `retry_failed_thumbnails` | Every 30 min | Retry thumbnail generation for photos where preview/thumb failed |
| `cleanup_expired_tokens` | Daily 2am CT | Mark testimonials with expired tokens as `expired_no_response`, invalidate URLs |
| `check_gallery_drift` | Daily 3am CT | Compare published galleries against current qualifying patients, flag drift |

---

## 11. Configuration Values

Add to `app/config.py` Settings class and `.env.example`:

```python
# Module 3: Photos & Testimonials
max_photo_upload_mb: int = 25
max_video_upload_mb: int = 200
max_consent_upload_mb: int = 15
consent_default_expiration_years: int = 2
testimonial_request_initial_days: int = 7
testimonial_request_reminder_1_days: int = 14
testimonial_request_reminder_2_days: int = 21
enable_testimonial_video_upload: bool = False
testimonial_token_expiry_days: int = 30
gallery_default_slug: str = "zerona-results"
```

---

## 12. New Dependencies

Add to `requirements.txt`:

```
Pillow>=11.0,<12.0
pillow-heif>=0.18.0
```

---

## 13. File Structure (New Files)

| File | Responsibility |
|------|---------------|
| `migrations/005_create_photo_testimonial_tables.sql` | All new tables + patients.ghl_contact_id |
| `app/services/photo_service.py` | Image processing, thumbnails, HEIC conversion, hash dedup |
| `app/services/consent_service.py` | Consent checks, grant/revoke workflows, expiration logic |
| `app/services/testimonial_service.py` | Token generation, send cadence, quality checks, content draft generation |
| `app/services/gallery_service.py` | Gallery generation, WP photo upload, version management |
| `app/services/case_study_service.py` | Aggregate calculations, patient selection, Claude generation, WP publishing |
| `app/services/measurement_service.py` | Measurement validation, delta calculations, aggregate stats |
| `app/photo_db.py` | DB functions: sessions, photos, measurements, cycles |
| `app/consent_db.py` | DB functions: consent documents, patient consents, preferences |
| `app/testimonial_db.py` | DB functions: testimonials, send log, token management |
| `app/gallery_db.py` | DB functions: gallery versions, WP media uploads, content usage log |
| `app/case_study_db.py` | DB functions: case studies, selections, overrides |
| `app/routes/patients_hub.py` | Hub page, search, quick stats, action cards |
| `app/routes/patient_detail.py` | Per-patient detail view with tabs |
| `app/routes/sessions.py` | Session CRUD, photo upload, measurement entry |
| `app/routes/consents.py` | Consent document upload, grant/revoke UI, secure file serving |
| `app/routes/testimonials.py` | Testimonial admin views + public form |
| `app/routes/galleries.py` | Gallery generation, preview, publishing |
| `app/routes/case_studies.py` | Case study generation flow |
| `app/routes/patients_api.py` | API endpoints: photo upload, measurement save, consent actions, etc. |
| `app/templates/patients_hub.html` | Patients hub with tabs |
| `app/templates/patient_detail.html` | Per-patient detail with horizontal tabs |
| `app/templates/session_view.html` | Session photo grid + measurement form |
| `app/templates/session_list.html` | Cross-patient session list |
| `app/templates/consent_upload.html` | Consent document upload + scope grant form |
| `app/templates/consent_status.html` | Per-patient consent dashboard |
| `app/templates/testimonial_form.html` | Public testimonial submission form (no auth) |
| `app/templates/testimonial_list.html` | Admin testimonial list + detail |
| `app/templates/gallery_admin.html` | Gallery management + patient selection |
| `app/templates/gallery_preview.html` | Gallery preview before publishing |
| `app/templates/case_study_admin.html` | Case study generation flow |
| `app/templates/case_study_preview.html` | Case study preview before publishing |
| `prompts/testimonial_draft.txt` | Claude prompt for generating social/blog drafts from testimonials |
| `prompts/testimonial_request.txt` | Claude prompt for personalized email openings |
| `prompts/case_study.txt` | Claude prompt for structured case study sections |
| `prompts/patient_selection.txt` | Claude prompt for recommending featured patients |
| `tests/test_photo_testimonial_flow.py` | E2E test: session → photos → measurements → consent → gallery → revocation |

### Modified Files

| File | Change |
|------|--------|
| `requirements.txt` | Add Pillow, pillow-heif |
| `app/config.py` | Add Module 3 settings |
| `app/main.py` | Register new routers, ensure /uploads dirs exist |
| `app/templates/base.html` | Restructure sidebar into grouped sections |
| `app/templates/dashboard.html` | Add consent/testimonial/session overview tiles |
| `app/services/scheduler.py` | Add 6 new scheduled jobs |
| `.env.example` | Add Module 3 env vars |
| `.gitignore` | Add `/uploads/` |
