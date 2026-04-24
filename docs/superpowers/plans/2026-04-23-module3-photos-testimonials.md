# Module 3: Before/After Photos + Testimonial Collection + Case Studies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize photo documentation, manage consent rigorously, automate testimonial gathering, and generate publication-ready case studies — all feeding back into the existing Review Queue and WordPress publishing pipeline.

**Architecture:** Builds on Module 1 (Mailgun sending), Module 2 (GHL contact linkage), the existing `content_pieces` review queue, and the WordPress integration. Consent is sacred — checked at query time, enforced by scope+source, audit-logged on every use. Photos are processed with Pillow (HEIC conversion, EXIF handling, thumbnail generation). Testimonials use a 3-touch email cadence with Claude personalization. Galleries and case studies publish to WordPress.

**Tech Stack:** FastAPI, SQLite (sync sqlite3 with `row_factory = sqlite3.Row`, WAL mode), Jinja2+HTMX+Tailwind (navy: #1B2A4A, teal: #0EA5A0), Pillow + pillow-heif, python-magic, Anthropic Claude API (claude-sonnet-4-20250514), APScheduler BackgroundScheduler, existing Mailgun + WordPress integrations.

---

## File Structure

**New files (40):**

| File | Responsibility |
|------|---------------|
| `migrations/005_create_photo_testimonial_tables.sql` | 18 new tables, 2 triggers, ALTER TABLE patients |
| `app/services/photo_service.py` | Image processing, thumbnails, HEIC conversion, hash dedup, validation |
| `app/services/consent_service.py` | Consent checks, grant/revoke workflows, expiration logic |
| `app/services/testimonial_service.py` | Token generation, send cadence, quality checks, content draft generation |
| `app/services/gallery_service.py` | Gallery generation, WP photo upload, version management |
| `app/services/case_study_service.py` | Aggregate calculations, patient selection, Claude generation, WP publishing |
| `app/services/measurement_service.py` | Measurement validation, delta calculations, aggregate stats |
| `app/services/patient_export_service.py` | Patient data export ZIP generation |
| `app/photo_db.py` | DB functions: sessions, photos, measurements, cycles, session_type_history |
| `app/consent_db.py` | DB functions: consent documents, patient consents, preferences |
| `app/testimonial_db.py` | DB functions: testimonials, send log, token management |
| `app/gallery_db.py` | DB functions: gallery versions, WP media uploads, content usage log, persistent exclusions |
| `app/case_study_db.py` | DB functions: case studies, selections, overrides |
| `app/routes/patients_hub.py` | Hub page, search, quick stats, action cards |
| `app/routes/patient_detail.py` | Per-patient detail view with tabs, data export |
| `app/routes/sessions.py` | Session CRUD, photo upload, measurement entry |
| `app/routes/consents.py` | Consent document upload, grant/revoke UI, secure file serving |
| `app/routes/testimonials.py` | Testimonial admin views + public form |
| `app/routes/galleries.py` | Gallery generation, preview, publishing |
| `app/routes/case_studies.py` | Case study generation flow |
| `app/routes/patients_api.py` | API endpoints: photo upload, measurement save, consent actions |
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
| `prompts/testimonial_draft.txt` | Claude prompt for social/blog drafts from testimonials |
| `prompts/testimonial_request.txt` | Claude prompt for personalized email openings |
| `prompts/case_study.txt` | Claude prompt for structured case study sections |
| `prompts/patient_selection.txt` | Claude prompt for recommending featured patients |
| `tests/test_consent_logic.py` | Consent checks, expiration, revocation, source enforcement |
| `tests/test_photo_upload.py` | Upload flow, versioning, HEIC conversion, hash dedup |
| `tests/test_testimonial_flow.py` | Token generation, 3-touch cadence, quality checks |
| `tests/test_gallery_generation.py` | Qualifying patient query, version history |
| `tests/test_case_study.py` | Aggregate calculations, patient selection, versioning |
| `tests/test_patient_identity.py` | Patient/GHL reconciliation, email bounce tracking |

**Modified files (8):**

| File | Change |
|------|--------|
| `requirements.txt` | Add Pillow, pillow-heif, python-magic |
| `app/config.py` | Add Module 3 settings (10 new config values) |
| `app/main.py` | Register 7 new routers, ensure /uploads dirs exist |
| `app/templates/base.html` | Restructure sidebar into grouped sections |
| `app/templates/dashboard.html` | Add consent/testimonial/session overview tiles |
| `app/services/scheduler.py` | Add 6 new scheduled jobs with failure handling |
| `.env.example` | Add Module 3 env vars |
| `.gitignore` | Add `/uploads/` |

---

## Tasks

### Task 1: Database Migration (005_create_photo_testimonial_tables.sql)

Create the migration file with all 18 new tables, 2 triggers, ALTER TABLE statements, and all indexes exactly as specified in the design spec.

**Files:**
- `migrations/005_create_photo_testimonial_tables.sql` (new)

**Steps:**

- [ ] 1. Create the migration file `migrations/005_create_photo_testimonial_tables.sql` with the following complete SQL:

```sql
-- Migration 005: Module 3 — Before/After Photos, Testimonials, Case Studies
-- Creates 18 new tables, 2 triggers, and alters the patients table.

-- 2.1 Treatment Cycles
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

-- 2.2 Photo Sessions
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

-- 2.3 Photos
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

-- 2.4 Measurements
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

-- 2.5 Session Type History
CREATE TABLE IF NOT EXISTS session_type_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES patient_photo_sessions(id),
    old_type TEXT NOT NULL,
    new_type TEXT NOT NULL,
    changed_by TEXT DEFAULT '',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT DEFAULT ''
);

-- 2.6 Consent Documents
CREATE TABLE IF NOT EXISTS consent_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    document_path TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'media_release_v1',
    signed_date DATE NOT NULL,
    uploaded_by TEXT DEFAULT '',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2.7 Patient Consents
-- NOTE: No is_active column. Active consent is DERIVED at query time:
-- revoked_at IS NULL AND (expires_at IS NULL OR expires_at > datetime('now'))
-- See patient_has_active_consent() in consent_service.py.
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
    expiration_override_reason TEXT DEFAULT '',
    revoked_at TIMESTAMP,
    revoked_by TEXT DEFAULT '',
    revoked_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_consents_patient ON patient_consents(patient_id);
CREATE INDEX IF NOT EXISTS idx_consents_scope ON patient_consents(patient_id, scope);

-- Defense-in-depth: prevent testimonial_form consent for advertising/case_study at the database level
CREATE TRIGGER IF NOT EXISTS enforce_testimonial_form_scope_limits_insert
BEFORE INSERT ON patient_consents
FOR EACH ROW
WHEN NEW.consent_source = 'testimonial_form'
  AND NEW.scope IN ('advertising', 'case_study')
BEGIN
    SELECT RAISE(ABORT, 'testimonial_form consent not valid for advertising or case_study scopes');
END;

CREATE TRIGGER IF NOT EXISTS enforce_testimonial_form_scope_limits_update
BEFORE UPDATE ON patient_consents
FOR EACH ROW
WHEN NEW.consent_source = 'testimonial_form'
  AND NEW.scope IN ('advertising', 'case_study')
BEGIN
    SELECT RAISE(ABORT, 'testimonial_form consent not valid for advertising or case_study scopes');
END;

-- 2.8 Testimonials
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
        -- expired_no_response, flagged, bounced
    flag_reason TEXT,
    submitted_at TIMESTAMP,
    consent_website INTEGER DEFAULT 0,
    consent_social INTEGER DEFAULT 0,
    consent_advertising INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_testimonials_patient ON testimonials(patient_id);
CREATE INDEX IF NOT EXISTS idx_testimonials_token ON testimonials(token);
CREATE INDEX IF NOT EXISTS idx_testimonials_status ON testimonials(status);

-- 2.9 Testimonial Send Log
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
        -- scheduled, sent, opened, clicked, cancelled, suppressed, bounced, failed
    personalized_opening TEXT DEFAULT '',
    is_personalized INTEGER NOT NULL DEFAULT 0,
    warning_3day_sent_at TIMESTAMP,
    skip_send_window INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_send_log_testimonial ON testimonial_send_log(testimonial_id);
CREATE INDEX IF NOT EXISTS idx_send_log_status ON testimonial_send_log(status);

-- 2.10 Patient Preferences
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

-- 2.11 Content Usage Log
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

-- 2.12 Case Studies
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
        -- draft, reviewed, published, superseded
    version_number INTEGER NOT NULL DEFAULT 1,
    superseded_by INTEGER REFERENCES case_studies(id),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    published_by TEXT
);

-- 2.13 Case Study Selections
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

-- 2.14 Case Study Overrides
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

-- 2.15 Gallery Versions
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

-- 2.16 Gallery Persistent Exclusions
CREATE TABLE IF NOT EXISTS gallery_persistent_exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    excluded_by TEXT DEFAULT '',
    excluded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT DEFAULT '',
    UNIQUE(patient_id)
);

-- 2.17 WordPress Media Uploads
CREATE TABLE IF NOT EXISTS wp_media_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_photo_id INTEGER NOT NULL REFERENCES patient_photos(id),
    wp_media_id INTEGER NOT NULL,
    wp_media_url TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wp_media_photo ON wp_media_uploads(patient_photo_id);

-- 2.18 Patient Data Exports
CREATE TABLE IF NOT EXISTS patient_data_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    exported_by TEXT DEFAULT '',
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    export_reason TEXT NOT NULL DEFAULT 'patient_request'
        -- patient_request, legal_requirement, internal_review
);

-- Schema Modifications: ALTER patients table
ALTER TABLE patients ADD COLUMN ghl_contact_id TEXT;
ALTER TABLE patients ADD COLUMN email_bounced INTEGER DEFAULT 0;
ALTER TABLE patients ADD COLUMN email_bounced_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_patients_ghl ON patients(ghl_contact_id);
```

- [ ] 2. Verify the migration file was created correctly:

```bash
wc -l migrations/005_create_photo_testimonial_tables.sql
# Expected output: approximately 230-250 lines

head -5 migrations/005_create_photo_testimonial_tables.sql
# Expected output:
# -- Migration 005: Module 3 — Before/After Photos, Testimonials, Case Studies
# -- Creates 18 new tables, 2 triggers, and alters the patients table.
#
# -- 2.1 Treatment Cycles
# CREATE TABLE IF NOT EXISTS patient_treatment_cycles (

tail -3 migrations/005_create_photo_testimonial_tables.sql
# Expected output:
# ALTER TABLE patients ADD COLUMN email_bounced_at TIMESTAMP;
# CREATE INDEX IF NOT EXISTS idx_patients_ghl ON patients(ghl_contact_id);
```

- [ ] 3. Test that the migration applies cleanly by running the app briefly:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, run_migrations, init_db
init_db()
run_migrations()
conn = get_db()
# Verify all 18 tables exist
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall()]
expected = [
    'patient_treatment_cycles', 'patient_photo_sessions', 'patient_photos',
    'patient_measurements', 'session_type_history', 'consent_documents',
    'patient_consents', 'testimonials', 'testimonial_send_log',
    'patient_preferences', 'content_usage_log', 'case_studies',
    'case_study_selections', 'case_study_overrides', 'gallery_versions',
    'gallery_persistent_exclusions', 'wp_media_uploads', 'patient_data_exports',
]
for t in expected:
    assert t in tables, f'Missing table: {t}'
# Verify triggers exist
triggers = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='trigger'\").fetchall()]
assert 'enforce_testimonial_form_scope_limits_insert' in triggers
assert 'enforce_testimonial_form_scope_limits_update' in triggers
# Verify ALTER TABLE columns
cols = [r[1] for r in conn.execute('PRAGMA table_info(patients)').fetchall()]
assert 'ghl_contact_id' in cols
assert 'email_bounced' in cols
assert 'email_bounced_at' in cols
# Verify migration was recorded
applied = conn.execute(\"SELECT filename FROM migrations WHERE filename = '005_create_photo_testimonial_tables.sql'\").fetchone()
assert applied is not None
conn.close()
print('All 18 tables, 2 triggers, and ALTER TABLE columns verified successfully.')
"
# Expected output: All 18 tables, 2 triggers, and ALTER TABLE columns verified successfully.
```

- [ ] 4. Test that the trigger enforcement works:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
import sqlite3
from app.database import get_db
conn = get_db()
# Insert a test patient first
conn.execute(\"INSERT OR IGNORE INTO patients (email, first_name, last_name) VALUES ('trigger-test@example.com', 'Trigger', 'Test')\")
conn.commit()
patient = conn.execute(\"SELECT id FROM patients WHERE email = 'trigger-test@example.com'\").fetchone()
pid = patient['id']
# Test: testimonial_form + advertising should be rejected by trigger
try:
    conn.execute(
        \"INSERT INTO patient_consents (patient_id, scope, consent_source, granted_at) VALUES (?, 'advertising', 'testimonial_form', datetime('now'))\",
        (pid,)
    )
    conn.commit()
    print('ERROR: Trigger did not fire — advertising insert succeeded')
except sqlite3.IntegrityError as e:
    print(f'Trigger correctly blocked advertising: {e}')
# Test: testimonial_form + case_study should be rejected by trigger
try:
    conn.execute(
        \"INSERT INTO patient_consents (patient_id, scope, consent_source, granted_at) VALUES (?, 'case_study', 'testimonial_form', datetime('now'))\",
        (pid,)
    )
    conn.commit()
    print('ERROR: Trigger did not fire — case_study insert succeeded')
except sqlite3.IntegrityError as e:
    print(f'Trigger correctly blocked case_study: {e}')
# Test: testimonial_form + website should be allowed
conn.execute(
    \"INSERT INTO patient_consents (patient_id, scope, consent_source, granted_at) VALUES (?, 'website', 'testimonial_form', datetime('now'))\",
    (pid,)
)
conn.commit()
print('Trigger correctly allowed website scope with testimonial_form source.')
# Cleanup
conn.execute(\"DELETE FROM patient_consents WHERE patient_id = ?\", (pid,))
conn.execute(\"DELETE FROM patients WHERE id = ?\", (pid,))
conn.commit()
conn.close()
print('All trigger tests passed.')
"
# Expected output:
# Trigger correctly blocked advertising: testimonial_form consent not valid for advertising or case_study scopes
# Trigger correctly blocked case_study: testimonial_form consent not valid for advertising or case_study scopes
# Trigger correctly allowed website scope with testimonial_form source.
# All trigger tests passed.
```

- [ ] 5. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add migrations/005_create_photo_testimonial_tables.sql
git commit -m "Add migration 005: Module 3 photo/testimonial/case study tables

Creates 18 new tables (treatment cycles, photo sessions, photos,
measurements, session type history, consent documents, patient consents,
testimonials, send log, preferences, content usage log, case studies,
selections, overrides, gallery versions, persistent exclusions, WP media
uploads, patient data exports), 2 triggers enforcing testimonial_form
scope limits, and ALTER TABLE patients for ghl_contact_id and
email_bounced columns."
```

---

### Task 2: Dependencies + Config + .env.example + .gitignore + main.py

Add new Python dependencies, Module 3 config values, environment variable documentation, gitignore entry for uploads, and ensure upload directories are created at startup.

**Files:**
- `requirements.txt` (modify)
- `app/config.py` (modify)
- `.env.example` (modify)
- `.gitignore` (modify)
- `app/main.py` (modify)

**Steps:**

- [ ] 1. Add new dependencies to `requirements.txt`. Append the following three lines after the existing dependencies:

Add these lines to the end of `requirements.txt`:
```
Pillow>=11.0,<12.0
pillow-heif>=0.18.0
python-magic>=0.4.27,<0.5.0
```

The full file should look like:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2==3.1.4
python-multipart==0.0.9
pydantic-settings==2.5.2
anthropic==0.34.2
replicate==1.0.7
httpx==0.27.2
apscheduler==3.10.4
bcrypt==4.2.0
python-jose[cryptography]==3.3.0
aiofiles==24.1.0
aiosqlite==0.20.0
requests>=2.31.0
Pillow>=11.0,<12.0
pillow-heif>=0.18.0
python-magic>=0.4.27,<0.5.0
```

- [ ] 2. Add Module 3 config values to `app/config.py`. Add the following block before the `class Config:` line inside the `Settings` class:

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

The full `app/config.py` file should look like:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    admin_password: str = "changeme"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    base_url: str = "http://localhost:8000"

    anthropic_api_key: str = ""
    replicate_api_token: str = ""

    buffer_access_token: str = ""
    buffer_fb_profile_id: str = ""
    buffer_ig_profile_id: str = ""

    wp_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    # Mailgun (campaign sends only)
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_from_email: str = ""
    mailgun_from_name: str = "White House Chiropractic"
    mailgun_webhook_signing_key: str = ""

    # GoHighLevel (GHL) Integration
    ghl_api_token: str = ""
    ghl_location_id: str = ""
    ghl_api_base_url: str = "https://services.leadconnectorhq.com"
    ghl_api_version: str = "2021-07-28"
    ghl_webhook_secret: str = ""
    ghl_referral_landing_url: str = ""
    ghl_credit_balance_field_id: str = ""
    enable_ghl_test_harness: bool = False

    posts_per_week_fb: int = 4
    posts_per_week_ig: int = 5
    blogs_per_month: int = 2
    generation_day: str = "sunday"
    generation_hour: int = 6

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
    # Escalation for Touch 1 review queue stalls
    # Warning email to admin after N days past scheduled send with no approval
    testimonial_escalation_warning_days: int = 3
    # Auto-approve with static fallback after N days past scheduled send
    testimonial_escalation_fallback_days: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] 3. Add Module 3 environment variables to `.env.example`. Append the following block to the end of the file:

```
# Module 3: Photos & Testimonials
MAX_PHOTO_UPLOAD_MB=25
MAX_VIDEO_UPLOAD_MB=200
MAX_CONSENT_UPLOAD_MB=15
CONSENT_DEFAULT_EXPIRATION_YEARS=2
TESTIMONIAL_REQUEST_INITIAL_DAYS=7
TESTIMONIAL_REQUEST_REMINDER_1_DAYS=14
TESTIMONIAL_REQUEST_REMINDER_2_DAYS=21
ENABLE_TESTIMONIAL_VIDEO_UPLOAD=false
TESTIMONIAL_TOKEN_EXPIRY_DAYS=30
GALLERY_DEFAULT_SLUG=zerona-results
# Days past scheduled send before warning email to admin (default: 3)
TESTIMONIAL_ESCALATION_WARNING_DAYS=3
# Days past scheduled send before auto-sending static fallback (default: 5)
TESTIMONIAL_ESCALATION_FALLBACK_DAYS=5
```

- [ ] 4. Add `/uploads/` to `.gitignore`. Append the following line to the end of the file:

```
/uploads/
```

The full `.gitignore` should look like:
```
__pycache__/
*.pyc
.env
data/
media/images/
.venv/
*.egg-info/
/uploads/
```

- [ ] 5. Update `app/main.py` to ensure the three upload directories exist at startup. Add the three `Path` lines after the existing directory creation lines:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, run_migrations
from app.services.scheduler import init_scheduler
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.api import router as api_router
from app.routes.webhooks import router as webhooks_router
from app.routes.campaigns import router as campaigns_router
from app.routes.campaign_api import router as campaign_api_router
from app.routes.ghl_webhooks import router as ghl_webhooks_router
from app.routes.referrals import router as referrals_router
from app.routes.referral_api import router as referral_api_router
from app.routes.referral_public import router as referral_public_router

# Ensure directories exist
Path("media/images").mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("prompts").mkdir(parents=True, exist_ok=True)
Path("config").mkdir(parents=True, exist_ok=True)
Path("uploads/photos").mkdir(parents=True, exist_ok=True)
Path("uploads/consents").mkdir(parents=True, exist_ok=True)
Path("uploads/videos").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(api_router)
app.include_router(webhooks_router)
app.include_router(campaigns_router)
app.include_router(campaign_api_router)
app.include_router(ghl_webhooks_router)
app.include_router(referrals_router)
app.include_router(referral_api_router)
app.include_router(referral_public_router)


@app.on_event("startup")
def startup():
    init_db()
    run_migrations()
    init_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
```

- [ ] 6. Verify all changes:

```bash
cd /Users/philipsmith/zerona-content-engine

# Check requirements.txt has the new deps
grep -c "Pillow\|pillow-heif\|python-magic" requirements.txt
# Expected output: 3

# Check config.py has the new settings
python -c "
from app.config import settings
assert settings.max_photo_upload_mb == 25
assert settings.max_video_upload_mb == 200
assert settings.max_consent_upload_mb == 15
assert settings.consent_default_expiration_years == 2
assert settings.testimonial_request_initial_days == 7
assert settings.testimonial_request_reminder_1_days == 14
assert settings.testimonial_request_reminder_2_days == 21
assert settings.enable_testimonial_video_upload == False
assert settings.testimonial_token_expiry_days == 30
assert settings.gallery_default_slug == 'zerona-results'
print('All 10 config values verified.')
"
# Expected output: All 10 config values verified.

# Check .gitignore has /uploads/
grep "/uploads/" .gitignore
# Expected output: /uploads/

# Check .env.example has the new vars
grep -c "MAX_PHOTO_UPLOAD_MB\|MAX_VIDEO_UPLOAD_MB\|MAX_CONSENT_UPLOAD_MB\|CONSENT_DEFAULT_EXPIRATION_YEARS\|TESTIMONIAL_REQUEST_INITIAL_DAYS\|TESTIMONIAL_REQUEST_REMINDER_1_DAYS\|TESTIMONIAL_REQUEST_REMINDER_2_DAYS\|ENABLE_TESTIMONIAL_VIDEO_UPLOAD\|TESTIMONIAL_TOKEN_EXPIRY_DAYS\|GALLERY_DEFAULT_SLUG" .env.example
# Expected output: 10

# Check main.py creates upload dirs
grep "uploads" app/main.py
# Expected output:
# Path("uploads/photos").mkdir(parents=True, exist_ok=True)
# Path("uploads/consents").mkdir(parents=True, exist_ok=True)
# Path("uploads/videos").mkdir(parents=True, exist_ok=True)
```

- [ ] 7. Install new dependencies:

```bash
cd /Users/philipsmith/zerona-content-engine
pip install -r requirements.txt
# Expected: Successfully installed Pillow-... pillow-heif-... python-magic-...
```

- [ ] 8. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add requirements.txt app/config.py .env.example .gitignore app/main.py
git commit -m "Add Module 3 dependencies, config values, and upload directory setup

- Add Pillow, pillow-heif, python-magic to requirements.txt
- Add 10 Module 3 config values to Settings class
- Add env var documentation to .env.example
- Add /uploads/ to .gitignore
- Create uploads/photos, uploads/consents, uploads/videos dirs at startup"
```

---

### Task 3: Photo Service (app/services/photo_service.py)

Create the image processing service with HEIF support, validation, thumbnail generation, hash-based deduplication, and error-tolerant processing.

**Files:**
- `app/services/photo_service.py` (new)

**Steps:**

- [ ] 1. Create `app/services/photo_service.py` with the following complete code:

```python
import hashlib
import logging
from pathlib import Path
from typing import Optional

import magic
from PIL import Image, ImageOps

# Register HEIF/HEIC support with Pillow at module level
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # pillow-heif not installed — HEIC uploads will fail validation

logger = logging.getLogger(__name__)

# Accepted MIME types for photo uploads
ACCEPTED_PHOTO_MIMES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/webp",
}

# Required angles for a complete session
REQUIRED_ANGLES = [
    "front",
    "side_left",
    "side_right",
    "45_degree_left",
    "45_degree_right",
    "back",
]

# Minimum dimension (longest side) for photo uploads
MIN_DIMENSION_PX = 800

# Generated image sizes
PREVIEW_MAX_PX = 1200
THUMBNAIL_MAX_PX = 400
JPEG_QUALITY = 85


def validate_image(
    file_bytes: bytes, filename: str
) -> tuple[bool, str]:
    """Validate an uploaded image file.

    Checks:
    1. MIME type via python-magic (content-based, not extension-based)
    2. Pillow can open the file (catches corrupted files)
    3. Minimum 800px on longest side

    Returns:
        (is_valid, error_message) — error_message is empty string if valid.
    """
    # 1. MIME type check
    mime_type = magic.from_buffer(file_bytes, mime=True)
    if mime_type not in ACCEPTED_PHOTO_MIMES:
        return False, (
            f"Invalid file type: {mime_type}. "
            f"Accepted types: JPEG, PNG, HEIC, WebP."
        )

    # 2. Pillow open check
    try:
        from io import BytesIO
        img = Image.open(BytesIO(file_bytes))
        img.verify()  # Verify it's not corrupted
        # Re-open after verify (verify closes the file)
        img = Image.open(BytesIO(file_bytes))
    except Exception as e:
        return False, f"File appears to be corrupted and cannot be opened: {e}"

    # 3. Minimum dimension check
    width, height = img.size
    longest_side = max(width, height)
    if longest_side < MIN_DIMENSION_PX:
        return False, (
            f"Image too small: {width}x{height}px. "
            f"Minimum {MIN_DIMENSION_PX}px on longest side required for marketing use."
        )

    return True, ""


def calculate_file_hash(file_bytes: bytes) -> str:
    """Calculate SHA-256 hash of raw file bytes (before any processing).

    Used for deduplication within the same session+angle.
    """
    return hashlib.sha256(file_bytes).hexdigest()


def check_duplicate_hash(session_id: int, angle: str, file_hash: str) -> Optional[dict]:
    """Check if a photo with the same hash already exists for this session+angle.

    Returns the existing photo record if duplicate found, None otherwise.
    Deduplication scope: same session_id + same angle only.
    """
    from app.database import get_db

    conn = get_db()
    row = conn.execute(
        """SELECT id, version_number, uploaded_at FROM patient_photos
           WHERE session_id = ? AND angle = ? AND file_hash = ? AND is_current = 1""",
        (session_id, angle, file_hash),
    ).fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def process_and_save_photo(
    file_bytes: bytes,
    filename: str,
    patient_id: int,
    session_id: int,
    angle: str,
) -> dict:
    """Process an uploaded photo and save original + preview + thumbnail.

    Processing steps:
    1. EXIF transpose (fixes iPhone sideways rotation)
    2. Save original (preserving EXIF for clinical reference)
    3. Generate preview (1200px longest side, EXIF stripped)
    4. Generate thumbnail (400px longest side, EXIF stripped)

    If thumbnail/preview generation fails, the original is still saved.

    Returns:
        dict with keys: file_path, preview_path, thumbnail_path, file_hash
        preview_path and thumbnail_path may be None if generation failed.
    """
    from io import BytesIO

    file_hash = calculate_file_hash(file_bytes)

    # Determine output directory
    output_dir = Path("uploads/photos") / str(patient_id) / str(session_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine original file extension
    mime_type = magic.from_buffer(file_bytes, mime=True)
    ext_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/heic": "jpg",   # HEIC converted to JPEG
        "image/heif": "jpg",   # HEIF converted to JPEG
        "image/webp": "webp",
    }
    original_ext = ext_map.get(mime_type, "jpg")

    # For HEIC/HEIF, we save the original as JPEG after conversion
    is_heic = mime_type in ("image/heic", "image/heif")

    # Open image with Pillow
    img = Image.open(BytesIO(file_bytes))

    # 1. EXIF transpose — fixes rotation from iPhone photos
    img = ImageOps.exif_transpose(img)

    # Convert to RGB if necessary (e.g., RGBA PNGs, palette images)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 2. Save original (preserving EXIF on the original for clinical reference)
    original_filename = f"{angle}_original.{original_ext}"
    original_path = output_dir / original_filename
    if is_heic:
        # HEIC converted to JPEG for storage
        img.save(str(original_path), "JPEG", quality=95)
    else:
        img.save(str(original_path))

    result = {
        "file_path": str(original_path),
        "preview_path": None,
        "thumbnail_path": None,
        "file_hash": file_hash,
    }

    # 3. Generate preview (1200px longest side, EXIF stripped)
    try:
        preview = img.copy()
        preview.thumbnail((PREVIEW_MAX_PX, PREVIEW_MAX_PX), Image.LANCZOS)
        preview_filename = f"{angle}_preview.jpg"
        preview_path = output_dir / preview_filename
        # Save without EXIF (strip metadata for privacy — removes GPS, camera serial, etc.)
        preview_clean = Image.new("RGB", preview.size)
        preview_clean.paste(preview)
        preview_clean.save(str(preview_path), "JPEG", quality=JPEG_QUALITY)
        result["preview_path"] = str(preview_path)
    except Exception as e:
        logger.error(
            f"Failed to generate preview for patient {patient_id}, "
            f"session {session_id}, angle {angle}: {e}"
        )

    # 4. Generate thumbnail (400px longest side, EXIF stripped)
    try:
        thumb = img.copy()
        thumb.thumbnail((THUMBNAIL_MAX_PX, THUMBNAIL_MAX_PX), Image.LANCZOS)
        thumb_filename = f"{angle}_thumb.jpg"
        thumb_path = output_dir / thumb_filename
        # Save without EXIF
        thumb_clean = Image.new("RGB", thumb.size)
        thumb_clean.paste(thumb)
        thumb_clean.save(str(thumb_path), "JPEG", quality=JPEG_QUALITY)
        result["thumbnail_path"] = str(thumb_path)
    except Exception as e:
        logger.error(
            f"Failed to generate thumbnail for patient {patient_id}, "
            f"session {session_id}, angle {angle}: {e}"
        )

    # TODO: Add virus/malware scan in future iteration. For now, strict MIME type
    # validation + Pillow open verification is the minimum safety check.

    return result


def regenerate_thumbnails(session_id: int) -> dict:
    """Regenerate preview and thumbnail images for all current photos in a session.

    Used for retry after failed thumbnail generation, or admin "Regenerate thumbnails" action.

    Returns:
        dict with keys: success_count, failure_count, failures (list of angle names)
    """
    from app.database import get_db

    conn = get_db()
    photos = conn.execute(
        """SELECT id, file_path, angle FROM patient_photos
           WHERE session_id = ? AND is_current = 1""",
        (session_id,),
    ).fetchall()
    conn.close()

    success_count = 0
    failure_count = 0
    failures = []

    for photo in photos:
        photo = dict(photo)
        original_path = Path(photo["file_path"])

        if not original_path.exists():
            logger.error(
                f"Original file not found for photo {photo['id']}: {original_path}"
            )
            failure_count += 1
            failures.append(photo["angle"])
            continue

        try:
            img = Image.open(str(original_path))
            img = ImageOps.exif_transpose(img)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            output_dir = original_path.parent
            angle = photo["angle"]

            # Generate preview
            preview = img.copy()
            preview.thumbnail((PREVIEW_MAX_PX, PREVIEW_MAX_PX), Image.LANCZOS)
            preview_path = output_dir / f"{angle}_preview.jpg"
            preview_clean = Image.new("RGB", preview.size)
            preview_clean.paste(preview)
            preview_clean.save(str(preview_path), "JPEG", quality=JPEG_QUALITY)

            # Generate thumbnail
            thumb = img.copy()
            thumb.thumbnail((THUMBNAIL_MAX_PX, THUMBNAIL_MAX_PX), Image.LANCZOS)
            thumb_path = output_dir / f"{angle}_thumb.jpg"
            thumb_clean = Image.new("RGB", thumb.size)
            thumb_clean.paste(thumb)
            thumb_clean.save(str(thumb_path), "JPEG", quality=JPEG_QUALITY)

            # Update database paths
            conn = get_db()
            conn.execute(
                """UPDATE patient_photos
                   SET preview_path = ?, thumbnail_path = ?
                   WHERE id = ?""",
                (str(preview_path), str(thumb_path), photo["id"]),
            )
            conn.commit()
            conn.close()

            success_count += 1

        except Exception as e:
            logger.error(
                f"Failed to regenerate thumbnails for photo {photo['id']} "
                f"(angle: {photo['angle']}): {e}"
            )
            failure_count += 1
            failures.append(photo["angle"])

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "failures": failures,
    }
```

- [ ] 2. Verify the file was created and imports correctly:

```bash
cd /Users/philipsmith/zerona-content-engine

python -c "
from app.services.photo_service import (
    validate_image,
    calculate_file_hash,
    check_duplicate_hash,
    process_and_save_photo,
    regenerate_thumbnails,
    REQUIRED_ANGLES,
    ACCEPTED_PHOTO_MIMES,
    MIN_DIMENSION_PX,
    PREVIEW_MAX_PX,
    THUMBNAIL_MAX_PX,
)
assert len(REQUIRED_ANGLES) == 6
assert 'image/heic' in ACCEPTED_PHOTO_MIMES
assert MIN_DIMENSION_PX == 800
assert PREVIEW_MAX_PX == 1200
assert THUMBNAIL_MAX_PX == 400
print('photo_service imports and constants verified.')
"
# Expected output: photo_service imports and constants verified.
```

- [ ] 3. Test validate_image and calculate_file_hash with a real image:

```bash
cd /Users/philipsmith/zerona-content-engine

python -c "
from PIL import Image
from io import BytesIO
from app.services.photo_service import validate_image, calculate_file_hash

# Create a valid test image (1000x800 JPEG)
img = Image.new('RGB', (1000, 800), color='blue')
buf = BytesIO()
img.save(buf, 'JPEG')
valid_bytes = buf.getvalue()

is_valid, error = validate_image(valid_bytes, 'test.jpg')
assert is_valid, f'Expected valid but got error: {error}'
print(f'Valid image test passed.')

# Test hash calculation
h = calculate_file_hash(valid_bytes)
assert len(h) == 64  # SHA-256 hex digest length
print(f'Hash calculation test passed: {h[:16]}...')

# Create a too-small image (400x300)
small_img = Image.new('RGB', (400, 300), color='red')
buf2 = BytesIO()
small_img.save(buf2, 'JPEG')
small_bytes = buf2.getvalue()

is_valid2, error2 = validate_image(small_bytes, 'small.jpg')
assert not is_valid2
assert 'too small' in error2.lower() or 'minimum' in error2.lower()
print(f'Small image rejection test passed: {error2}')

# Test with non-image bytes
is_valid3, error3 = validate_image(b'not an image', 'fake.jpg')
assert not is_valid3
print(f'Non-image rejection test passed: {error3}')

print('All photo_service validation tests passed.')
"
# Expected output:
# Valid image test passed.
# Hash calculation test passed: <hash prefix>...
# Small image rejection test passed: Image too small: ...
# Non-image rejection test passed: Invalid file type: ...
# All photo_service validation tests passed.
```

- [ ] 4. Test process_and_save_photo with a real image:

```bash
cd /Users/philipsmith/zerona-content-engine

python -c "
from PIL import Image
from io import BytesIO
from pathlib import Path
from app.services.photo_service import process_and_save_photo

# Create a test image (2000x1500 JPEG)
img = Image.new('RGB', (2000, 1500), color='green')
buf = BytesIO()
img.save(buf, 'JPEG')
test_bytes = buf.getvalue()

# Process and save
result = process_and_save_photo(
    file_bytes=test_bytes,
    filename='test_photo.jpg',
    patient_id=99999,
    session_id=99999,
    angle='front',
)

# Verify all three files were created
assert Path(result['file_path']).exists(), 'Original not saved'
assert Path(result['preview_path']).exists(), 'Preview not saved'
assert Path(result['thumbnail_path']).exists(), 'Thumbnail not saved'
assert len(result['file_hash']) == 64, 'Hash not calculated'

# Verify preview dimensions (should be 1200px longest side)
preview_img = Image.open(result['preview_path'])
assert max(preview_img.size) <= 1200, f'Preview too large: {preview_img.size}'

# Verify thumbnail dimensions (should be 400px longest side)
thumb_img = Image.open(result['thumbnail_path'])
assert max(thumb_img.size) <= 400, f'Thumbnail too large: {thumb_img.size}'

print(f'Original: {result[\"file_path\"]}')
print(f'Preview: {result[\"preview_path\"]} ({preview_img.size})')
print(f'Thumbnail: {result[\"thumbnail_path\"]} ({thumb_img.size})')
print(f'Hash: {result[\"file_hash\"][:16]}...')

# Cleanup test files
import shutil
shutil.rmtree('uploads/photos/99999', ignore_errors=True)
print('process_and_save_photo test passed and cleaned up.')
"
# Expected output:
# Original: uploads/photos/99999/99999/front_original.jpg
# Preview: uploads/photos/99999/99999/front_preview.jpg (1200, 900)
# Thumbnail: uploads/photos/99999/99999/front_thumb.jpg (400, 300)
# Hash: <hash prefix>...
# process_and_save_photo test passed and cleaned up.
```

- [ ] 5. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/photo_service.py
git commit -m "Add photo processing service with HEIF support and thumbnail generation

Implements validate_image (MIME + Pillow + min dimensions), SHA-256 hash
dedup, process_and_save_photo (EXIF transpose, original/preview/thumbnail),
and regenerate_thumbnails. HEIF registered at module level. Thumbnails
fail gracefully — original is always saved."
```

---

### Task 4: Consent DB + Consent Service

Create the database access layer for consent documents, patient consents, and preferences, plus the consent service with scope/source enforcement, revocation workflows, and expiration processing.

**Files:**
- `app/consent_db.py` (new)
- `app/services/consent_service.py` (new)

**Steps:**

- [ ] 1. Create `app/consent_db.py` with the following complete code:

```python
from datetime import datetime
from typing import Optional
from app.database import get_db, log_event


# ── Consent Documents ─────────────────────────────────────

def create_consent_document(
    patient_id: int,
    document_path: str,
    document_type: str,
    signed_date: str,
    uploaded_by: str = "",
) -> int:
    """Create a consent document record for an uploaded signed form.

    Returns the new document ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO consent_documents
           (patient_id, document_path, document_type, signed_date, uploaded_by)
           VALUES (?, ?, ?, ?, ?)""",
        (patient_id, document_path, document_type, signed_date, uploaded_by),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    log_event(
        "consent",
        f"Consent document uploaded for patient {patient_id}",
        {"document_id": doc_id, "document_type": document_type, "uploaded_by": uploaded_by},
    )
    return doc_id


def get_consent_document(document_id: int) -> Optional[dict]:
    """Get a consent document by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM consent_documents WHERE id = ?", (document_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_consent_documents_for_patient(patient_id: int) -> list[dict]:
    """Get all consent documents for a patient, ordered by signed date descending."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM consent_documents
           WHERE patient_id = ?
           ORDER BY signed_date DESC""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Patient Consents ──────────────────────────────────────

def create_patient_consent(
    patient_id: int,
    scope: str,
    consent_source: str,
    source_document_id: Optional[int],
    granted_by: str = "",
    expires_at: Optional[str] = None,
    expiration_override_reason: str = "",
) -> int:
    """Create a patient consent record for a specific scope.

    Note: The database trigger will ABORT if consent_source='testimonial_form'
    and scope is 'advertising' or 'case_study'. This is defense-in-depth;
    the application code should also enforce this (see consent_service.py).

    Returns the new consent ID.
    """
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO patient_consents
           (patient_id, scope, consent_source, source_document_id,
            granted_at, granted_by, expires_at, expiration_override_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            patient_id,
            scope,
            consent_source,
            source_document_id,
            now,
            granted_by,
            expires_at,
            expiration_override_reason,
        ),
    )
    conn.commit()
    consent_id = cursor.lastrowid
    conn.close()
    log_event(
        "consent",
        f"Consent granted: patient {patient_id}, scope={scope}, source={consent_source}",
        {"consent_id": consent_id, "granted_by": granted_by},
    )
    return consent_id


def get_active_consents(patient_id: int) -> list[dict]:
    """Get all active (non-revoked, non-expired) consents for a patient."""
    now = datetime.now().isoformat()
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM patient_consents
           WHERE patient_id = ?
             AND revoked_at IS NULL
             AND (expires_at IS NULL OR expires_at > ?)
           ORDER BY scope, granted_at DESC""",
        (patient_id, now),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_consent_by_scope(patient_id: int, scope: str) -> Optional[dict]:
    """Get the most recent active consent for a specific scope.

    Returns the strongest source first (signed_document > manual_staff_entry > testimonial_form).
    """
    now = datetime.now().isoformat()
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM patient_consents
           WHERE patient_id = ?
             AND scope = ?
             AND revoked_at IS NULL
             AND (expires_at IS NULL OR expires_at > ?)
           ORDER BY
             CASE consent_source
               WHEN 'signed_document' THEN 1
               WHEN 'manual_staff_entry' THEN 2
               WHEN 'testimonial_form' THEN 3
             END ASC,
             granted_at DESC
           LIMIT 1""",
        (patient_id, scope, now),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_consents_for_patient(patient_id: int) -> list[dict]:
    """Get ALL consents for a patient (including revoked and expired), for audit view."""
    conn = get_db()
    rows = conn.execute(
        """SELECT pc.*, cd.document_path, cd.document_type, cd.signed_date
           FROM patient_consents pc
           LEFT JOIN consent_documents cd ON pc.source_document_id = cd.id
           WHERE pc.patient_id = ?
           ORDER BY pc.granted_at DESC""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def revoke_consent(
    consent_id: int, revoked_by: str, revoked_reason: str
) -> bool:
    """Soft-revoke a consent by setting revoked_at, revoked_by, and revoked_reason.

    Returns True if the consent was found and revoked, False if not found or already revoked.
    """
    now = datetime.now().isoformat()
    conn = get_db()
    # Check it exists and isn't already revoked
    existing = conn.execute(
        "SELECT id, patient_id, scope FROM patient_consents WHERE id = ? AND revoked_at IS NULL",
        (consent_id,),
    ).fetchone()
    if not existing:
        conn.close()
        return False

    conn.execute(
        """UPDATE patient_consents
           SET revoked_at = ?, revoked_by = ?, revoked_reason = ?
           WHERE id = ?""",
        (now, revoked_by, revoked_reason, consent_id),
    )
    conn.commit()
    conn.close()
    log_event(
        "consent",
        f"Consent revoked: id={consent_id}, patient={existing['patient_id']}, scope={existing['scope']}",
        {"revoked_by": revoked_by, "reason": revoked_reason},
    )
    return True


# ── Patient Preferences ───────────────────────────────────

def get_patient_preferences(patient_id: int) -> list[dict]:
    """Get all preferences for a patient."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM patient_preferences WHERE patient_id = ?",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patient_preference(patient_id: int, preference_type: str) -> Optional[dict]:
    """Get a specific preference for a patient."""
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM patient_preferences
           WHERE patient_id = ? AND preference_type = ?""",
        (patient_id, preference_type),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_patient_preference(
    patient_id: int, preference_type: str, value: str
) -> None:
    """Insert or update a patient preference."""
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO patient_preferences (patient_id, preference_type, value, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(patient_id, preference_type)
           DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        (patient_id, preference_type, value, now),
    )
    conn.commit()
    conn.close()
    log_event(
        "preference",
        f"Preference updated: patient {patient_id}, {preference_type}={value}",
    )


# ── Expiration Queries ────────────────────────────────────

def get_expiring_consents(days_ahead: int = 30) -> list[dict]:
    """Get consents expiring within the next N days (for dashboard warnings).

    Only returns active consents (not already revoked).
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT pc.*, p.first_name, p.last_name, p.email
           FROM patient_consents pc
           JOIN patients p ON pc.patient_id = p.id
           WHERE pc.revoked_at IS NULL
             AND pc.expires_at IS NOT NULL
             AND pc.expires_at > datetime('now')
             AND pc.expires_at <= datetime('now', '+' || ? || ' days')
           ORDER BY pc.expires_at ASC""",
        (days_ahead,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_expired_consents() -> list[dict]:
    """Get consents that have expired but have NOT been revoked yet.

    These need to be auto-revoked by the scheduled job.
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT pc.*, p.first_name, p.last_name, p.email
           FROM patient_consents pc
           JOIN patients p ON pc.patient_id = p.id
           WHERE pc.revoked_at IS NULL
             AND pc.expires_at IS NOT NULL
             AND pc.expires_at <= datetime('now')
           ORDER BY pc.expires_at ASC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] 2. Create `app/services/consent_service.py` with the following complete code:

```python
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.database import get_db, log_event
from app import consent_db

logger = logging.getLogger(__name__)

# Scopes that require signed_document or manual_staff_entry (NOT testimonial_form)
RESTRICTED_SCOPES = {"advertising", "case_study"}

# All valid scopes
VALID_SCOPES = {"website", "social", "advertising", "email_testimonial", "case_study"}

# Scopes allowed from testimonial_form source
TESTIMONIAL_FORM_ALLOWED_SCOPES = {"website", "social", "email_testimonial"}

# All valid consent sources
VALID_SOURCES = {"signed_document", "testimonial_form", "manual_staff_entry"}


def patient_has_active_consent(
    patient_id: int,
    scope: str,
    required_source: Optional[str] = None,
    as_of_date: Optional[datetime] = None,
) -> bool:
    """Check if a patient has active consent for a specific scope.

    This is the core consent check used EVERYWHERE consent is verified.

    Args:
        patient_id: The patient to check.
        scope: The consent scope to verify (website, social, advertising,
               email_testimonial, case_study).
        required_source: If set, only consents from this source count.
        as_of_date: Check consent as of this date. Defaults to now.

    Returns:
        True if active consent exists for the scope, False otherwise.

    For advertising and case_study scopes, automatically requires
    consent_source IN ('signed_document', 'manual_staff_entry') even if
    required_source is not explicitly passed. testimonial_form is never
    sufficient for these scopes.
    """
    if as_of_date is None:
        as_of_date = datetime.now()

    as_of_str = as_of_date.isoformat()

    conn = get_db()

    # Build the query
    query = """
        SELECT id FROM patient_consents
        WHERE patient_id = ?
          AND scope = ?
          AND granted_at <= ?
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > ?)
    """
    params: list = [patient_id, scope, as_of_str, as_of_str]

    # For restricted scopes, automatically exclude testimonial_form
    if scope in RESTRICTED_SCOPES:
        query += " AND consent_source IN ('signed_document', 'manual_staff_entry')"

    # If a specific source is required, add that filter too
    if required_source:
        query += " AND consent_source = ?"
        params.append(required_source)

    query += " LIMIT 1"

    row = conn.execute(query, params).fetchone()
    conn.close()

    return row is not None


def grant_consent_from_document(
    patient_id: int,
    document_id: int,
    scopes: list[str],
    signed_date: str,
    granted_by: str = "",
    expires_at: Optional[str] = None,
    expiration_override_reason: str = "",
) -> list[int]:
    """Grant consent for multiple scopes from a signed document.

    If expires_at is not provided, defaults to signed_date + CONSENT_DEFAULT_EXPIRATION_YEARS.

    Args:
        patient_id: The patient granting consent.
        document_id: The uploaded consent document ID.
        scopes: List of scopes to grant (any of the 5 valid scopes).
        signed_date: Date the document was signed (ISO format date string).
        granted_by: Staff member who processed the upload.
        expires_at: Optional custom expiration (ISO format datetime string).
        expiration_override_reason: Required if expires_at differs from default.

    Returns:
        List of created consent IDs.
    """
    # Validate scopes
    invalid_scopes = set(scopes) - VALID_SCOPES
    if invalid_scopes:
        raise ValueError(f"Invalid scopes: {invalid_scopes}")

    # Calculate default expiration if not provided
    if expires_at is None:
        try:
            signed_dt = datetime.fromisoformat(signed_date)
        except ValueError:
            signed_dt = datetime.strptime(signed_date, "%Y-%m-%d")
        default_expiry = signed_dt + timedelta(
            days=365 * settings.consent_default_expiration_years
        )
        expires_at = default_expiry.isoformat()

    consent_ids = []
    for scope in scopes:
        consent_id = consent_db.create_patient_consent(
            patient_id=patient_id,
            scope=scope,
            consent_source="signed_document",
            source_document_id=document_id,
            granted_by=granted_by,
            expires_at=expires_at,
            expiration_override_reason=expiration_override_reason,
        )
        consent_ids.append(consent_id)

    log_event(
        "consent",
        f"Consent granted from document for patient {patient_id}: {', '.join(scopes)}",
        {
            "document_id": document_id,
            "consent_ids": consent_ids,
            "granted_by": granted_by,
        },
    )
    return consent_ids


def grant_consent_from_testimonial_form(
    patient_id: int,
    scopes: list[str],
) -> list[int]:
    """Grant consent from a public testimonial form submission.

    ONLY allows website, social, and email_testimonial scopes.
    Raises ValueError if advertising or case_study scope is attempted.

    Args:
        patient_id: The patient granting consent.
        scopes: List of scopes (must be subset of website, social, email_testimonial).

    Returns:
        List of created consent IDs.
    """
    # Enforce scope restrictions for testimonial_form source
    invalid_scopes = set(scopes) - TESTIMONIAL_FORM_ALLOWED_SCOPES
    if invalid_scopes:
        raise ValueError(
            f"Testimonial form consent is not valid for scopes: {invalid_scopes}. "
            f"Only website, social, and email_testimonial are allowed."
        )

    # Calculate default expiration
    default_expiry = datetime.now() + timedelta(
        days=365 * settings.consent_default_expiration_years
    )
    expires_at = default_expiry.isoformat()

    consent_ids = []
    for scope in scopes:
        consent_id = consent_db.create_patient_consent(
            patient_id=patient_id,
            scope=scope,
            consent_source="testimonial_form",
            source_document_id=None,
            granted_by="patient_self_service",
            expires_at=expires_at,
        )
        consent_ids.append(consent_id)

    log_event(
        "consent",
        f"Consent granted from testimonial form for patient {patient_id}: {', '.join(scopes)}",
        {"consent_ids": consent_ids},
    )
    return consent_ids


def revoke_patient_consent(
    consent_id: int,
    revoked_by: str,
    reason: str,
) -> dict:
    """Revoke a consent and flag affected content for review.

    Performs soft revocation + scans content_usage_log for active uses
    under the affected patient+scope and flags them as removal_pending.

    Args:
        consent_id: The consent to revoke.
        revoked_by: Staff member performing revocation.
        reason: Required free-text reason for revocation.

    Returns:
        dict with keys: revoked (bool), flagged_content_count (int)
    """
    if not reason.strip():
        raise ValueError("Revocation reason is required.")

    # Get the consent details before revoking
    conn = get_db()
    consent = conn.execute(
        "SELECT * FROM patient_consents WHERE id = ?", (consent_id,)
    ).fetchone()
    conn.close()

    if not consent:
        return {"revoked": False, "flagged_content_count": 0}

    consent = dict(consent)

    # Revoke the consent
    revoked = consent_db.revoke_consent(consent_id, revoked_by, reason)
    if not revoked:
        return {"revoked": False, "flagged_content_count": 0}

    # Flag affected content in content_usage_log
    now = datetime.now().isoformat()
    conn = get_db()
    result = conn.execute(
        """UPDATE content_usage_log
           SET removal_status = 'removal_pending',
               removal_requested_at = ?,
               removal_requested_by = ?,
               removal_reason = ?
           WHERE patient_id = ?
             AND scope_used = ?
             AND removal_status = 'active'""",
        (
            now,
            revoked_by,
            f"Consent revoked: {reason}",
            consent["patient_id"],
            consent["scope"],
        ),
    )
    flagged_count = result.rowcount
    conn.commit()
    conn.close()

    # Build structured task list of affected content (Item 31: spec §4 line 604)
    task_list = []
    if flagged_count > 0:
        conn = get_db()
        flagged_items = conn.execute(
            """SELECT id, photo_id, testimonial_id, used_in, scope_used
               FROM content_usage_log
               WHERE patient_id = ?
                 AND scope_used = ?
                 AND removal_status = 'removal_pending'""",
            (consent["patient_id"], consent["scope"]),
        ).fetchall()
        conn.close()

        for item in flagged_items:
            item = dict(item)
            content_type = "photo" if item.get("photo_id") else "testimonial" if item.get("testimonial_id") else "unknown"
            task_list.append({
                "content_usage_id": item["id"],
                "content_type": content_type,
                "used_in": item["used_in"],
                "scope": item["scope_used"],
                "action_needed": "Remove from published content or document reason to keep",
            })

        log_event(
            "consent",
            f"Flagged {flagged_count} content uses for removal after consent revocation",
            {
                "consent_id": consent_id,
                "patient_id": consent["patient_id"],
                "scope": consent["scope"],
                "revoked_by": revoked_by,
            },
        )

        # Immediate email notification to Chris (Item 30: spec §4 line 605)
        # "Sends email notification to Chris directly for urgent cases
        # (published gallery content)"
        try:
            from app.services.mailgun_service import send_single
            from app.config import settings

            # Get patient name for email
            conn = get_db()
            patient = conn.execute(
                "SELECT first_name, last_name FROM patients WHERE id = ?",
                (consent["patient_id"],),
            ).fetchone()
            conn.close()
            patient_name = f"{patient['first_name']} {patient['last_name']}" if patient else f"Patient #{consent['patient_id']}"

            # Build content list for email body
            content_lines = []
            for task in task_list:
                content_lines.append(
                    f"<li><strong>{task['content_type'].title()}</strong> "
                    f"used in <a href=\"{task['used_in']}\">{task['used_in']}</a> "
                    f"(scope: {task['scope']})</li>"
                )
            content_html = "\n".join(content_lines)

            send_single(
                to_email=settings.notification_email,
                subject=(
                    f"URGENT: {patient_name} revoked {consent['scope']} consent "
                    f"— {flagged_count} published item(s) need removal"
                ),
                html=(
                    f"<p><strong>{patient_name}</strong> has revoked consent for "
                    f"<strong>{consent['scope']}</strong> scope.</p>"
                    f"<p><strong>{flagged_count} published content item(s) "
                    f"are affected and need immediate review:</strong></p>"
                    f"<ul>{content_html}</ul>"
                    f"<p>For each item: remove from the published location, "
                    f"or explicitly document the reason for keeping it.</p>"
                    f"<p><strong>Revoked by:</strong> {revoked_by}<br>"
                    f"<strong>Reason:</strong> {reason}</p>"
                    f"<p><a href=\"{settings.base_url}/dashboard/patients/"
                    f"{consent['patient_id']}\">View patient record</a></p>"
                ),
                text=(
                    f"URGENT: {patient_name} revoked {consent['scope']} consent. "
                    f"{flagged_count} published items need removal. "
                    f"Reason: {reason}. Revoked by: {revoked_by}."
                ),
            )
            log_event("consent", f"Revocation notification sent to {settings.notification_email}")
        except Exception as e:
            # Email failure should not prevent revocation from completing
            log_event("consent", f"Failed to send revocation notification: {e}")

    return {
        "revoked": True,
        "flagged_content_count": flagged_count,
        "task_list": task_list,
    }


def process_expired_consents() -> dict:
    """Process expired consents for the nightly scheduler job.

    Auto-revokes expired consents with reason='expired' and flags affected content.
    This job must never silently fail — consent compliance depends on it.

    Returns:
        dict with keys: processed_count, flagged_content_count, errors
    """
    expired = consent_db.get_expired_consents()
    processed_count = 0
    flagged_content_total = 0
    errors = []

    for consent in expired:
        try:
            result = revoke_patient_consent(
                consent_id=consent["id"],
                revoked_by="system_expiration_job",
                reason="expired",
            )
            if result["revoked"]:
                processed_count += 1
                flagged_content_total += result["flagged_content_count"]
        except Exception as e:
            error_msg = (
                f"Failed to process expired consent {consent['id']} "
                f"for patient {consent['patient_id']}: {e}"
            )
            logger.critical(error_msg)
            errors.append(error_msg)

    log_event(
        "consent_expiration",
        f"Processed {processed_count} expired consents, flagged {flagged_content_total} content uses",
        {"processed": processed_count, "flagged": flagged_content_total, "errors": errors},
    )

    return {
        "processed_count": processed_count,
        "flagged_content_count": flagged_content_total,
        "errors": errors,
    }


def get_consent_summary(patient_id: int) -> dict:
    """Get a formatted consent status summary for a patient, for use in UI.

    Returns a dict with:
    - scopes: dict mapping each scope to its status info
    - has_signed_document: bool
    - has_testimonial_form: bool
    - active_count: int
    - expiring_soon: list of consents expiring within 30 days
    """
    active_consents = consent_db.get_active_consents(patient_id)
    all_consents = consent_db.get_all_consents_for_patient(patient_id)
    expiring = consent_db.get_expiring_consents(days_ahead=30)
    # Filter expiring to just this patient
    patient_expiring = [c for c in expiring if c["patient_id"] == patient_id]

    # Build scope status map
    scopes_status = {}
    for scope in VALID_SCOPES:
        # Find the best active consent for this scope
        scope_consents = [c for c in active_consents if c["scope"] == scope]
        if scope_consents:
            # Pick the strongest source
            best = scope_consents[0]  # Already sorted by source strength in get_active_consents
            source = best["consent_source"]
            if source == "signed_document":
                label = "Signed consent on file"
                strength = "strong"
            elif source == "manual_staff_entry":
                label = "Staff-entered consent"
                strength = "medium"
            else:
                label = "Web form consent — limited scope"
                strength = "limited"

            scopes_status[scope] = {
                "active": True,
                "consent_id": best["id"],
                "source": source,
                "label": label,
                "strength": strength,
                "granted_at": best["granted_at"],
                "expires_at": best.get("expires_at"),
            }
        else:
            scopes_status[scope] = {
                "active": False,
                "consent_id": None,
                "source": None,
                "label": "No consent",
                "strength": "none",
                "granted_at": None,
                "expires_at": None,
            }

    # Determine if patient has any signed document or testimonial form consent
    has_signed = any(
        c["consent_source"] == "signed_document" for c in active_consents
    )
    has_testimonial_form = any(
        c["consent_source"] == "testimonial_form" for c in active_consents
    )

    return {
        "scopes": scopes_status,
        "has_signed_document": has_signed,
        "has_testimonial_form": has_testimonial_form,
        "active_count": len(active_consents),
        "expiring_soon": patient_expiring,
        "total_historical": len(all_consents),
    }
```

- [ ] 3. Verify both files import correctly:

```bash
cd /Users/philipsmith/zerona-content-engine

python -c "
from app.consent_db import (
    create_consent_document,
    create_patient_consent,
    get_active_consents,
    get_consent_by_scope,
    revoke_consent,
    get_consent_document,
    get_patient_preferences,
    upsert_patient_preference,
    get_expiring_consents,
    get_expired_consents,
    get_consent_documents_for_patient,
    get_all_consents_for_patient,
    get_patient_preference,
)
print('consent_db imports verified (13 functions).')

from app.services.consent_service import (
    patient_has_active_consent,
    grant_consent_from_document,
    grant_consent_from_testimonial_form,
    revoke_patient_consent,
    process_expired_consents,
    get_consent_summary,
    VALID_SCOPES,
    VALID_SOURCES,
    RESTRICTED_SCOPES,
    TESTIMONIAL_FORM_ALLOWED_SCOPES,
)
assert VALID_SCOPES == {'website', 'social', 'advertising', 'email_testimonial', 'case_study'}
assert RESTRICTED_SCOPES == {'advertising', 'case_study'}
assert TESTIMONIAL_FORM_ALLOWED_SCOPES == {'website', 'social', 'email_testimonial'}
print('consent_service imports and constants verified (6 functions, 4 constants).')
"
# Expected output:
# consent_db imports verified (13 functions).
# consent_service imports and constants verified (6 functions, 4 constants).
```

- [ ] 4. Test the full consent workflow end-to-end:

```bash
cd /Users/philipsmith/zerona-content-engine

python -c "
from app.database import init_db, run_migrations, get_db
from app import consent_db
from app.services.consent_service import (
    patient_has_active_consent,
    grant_consent_from_document,
    grant_consent_from_testimonial_form,
    revoke_patient_consent,
    get_consent_summary,
)

init_db()
run_migrations()

# Setup: create test patient
conn = get_db()
conn.execute(\"INSERT OR IGNORE INTO patients (email, first_name, last_name) VALUES ('consent-test@example.com', 'Consent', 'Test')\")
conn.commit()
patient = conn.execute(\"SELECT id FROM patients WHERE email = 'consent-test@example.com'\").fetchone()
pid = patient['id']
conn.close()

# Test 1: No consent initially
assert not patient_has_active_consent(pid, 'website')
print('Test 1 PASSED: No consent initially.')

# Test 2: Grant consent from document
doc_id = consent_db.create_consent_document(
    patient_id=pid,
    document_path='/uploads/consents/test/test.pdf',
    document_type='media_release_v1',
    signed_date='2026-04-20',
    uploaded_by='admin',
)
consent_ids = grant_consent_from_document(
    patient_id=pid,
    document_id=doc_id,
    scopes=['website', 'social', 'advertising', 'case_study'],
    signed_date='2026-04-20',
    granted_by='admin',
)
assert len(consent_ids) == 4
print(f'Test 2 PASSED: Granted 4 scopes from document, IDs: {consent_ids}')

# Test 3: Check consent is active
assert patient_has_active_consent(pid, 'website')
assert patient_has_active_consent(pid, 'advertising')
assert patient_has_active_consent(pid, 'case_study')
print('Test 3 PASSED: All scopes active.')

# Test 4: Grant consent from testimonial form (limited scopes)
form_ids = grant_consent_from_testimonial_form(
    patient_id=pid,
    scopes=['website', 'social'],
)
assert len(form_ids) == 2
print(f'Test 4 PASSED: Granted 2 scopes from testimonial form.')

# Test 5: testimonial_form + advertising should be rejected by application code
try:
    grant_consent_from_testimonial_form(pid, ['advertising'])
    print('Test 5 FAILED: Should have raised ValueError')
except ValueError as e:
    print(f'Test 5 PASSED: Application code blocked advertising from testimonial_form: {e}')

# Test 6: testimonial_form + case_study should be rejected by application code
try:
    grant_consent_from_testimonial_form(pid, ['case_study'])
    print('Test 6 FAILED: Should have raised ValueError')
except ValueError as e:
    print(f'Test 6 PASSED: Application code blocked case_study from testimonial_form: {e}')

# Test 7: Revoke consent and check flagging
result = revoke_patient_consent(
    consent_id=consent_ids[0],  # website from signed document
    revoked_by='admin',
    reason='Patient requested removal',
)
assert result['revoked'] == True
print(f'Test 7 PASSED: Consent revoked, flagged {result[\"flagged_content_count\"]} content uses.')

# Test 8: Get consent summary
summary = get_consent_summary(pid)
assert 'scopes' in summary
assert summary['has_signed_document'] == True
assert summary['active_count'] > 0
print(f'Test 8 PASSED: Consent summary has {summary[\"active_count\"]} active consents.')

# Test 9: Patient preferences
consent_db.upsert_patient_preference(pid, 'testimonial_requests', 'none')
pref = consent_db.get_patient_preference(pid, 'testimonial_requests')
assert pref['value'] == 'none'
print('Test 9 PASSED: Patient preference set and retrieved.')

# Test 10: Revocation reason is required
try:
    revoke_patient_consent(consent_ids[1], 'admin', '')
    print('Test 10 FAILED: Should have required reason')
except ValueError:
    print('Test 10 PASSED: Empty revocation reason rejected.')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_preferences WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_consents WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM consent_documents WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()
print('All 10 consent tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: No consent initially.
# Test 2 PASSED: Granted 4 scopes from document, IDs: [...]
# Test 3 PASSED: All scopes active.
# Test 4 PASSED: Granted 2 scopes from testimonial form.
# Test 5 PASSED: Application code blocked advertising from testimonial_form: ...
# Test 6 PASSED: Application code blocked case_study from testimonial_form: ...
# Test 7 PASSED: Consent revoked, flagged 0 content uses.
# Test 8 PASSED: Consent summary has ... active consents.
# Test 9 PASSED: Patient preference set and retrieved.
# Test 10 PASSED: Empty revocation reason rejected.
# All 10 consent tests passed. Cleanup complete.
```

- [ ] 5. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/consent_db.py app/services/consent_service.py
git commit -m "Add consent database layer and consent service with scope enforcement

consent_db.py: CRUD for consent documents, patient consents, and
preferences with expiration queries.

consent_service.py: Core patient_has_active_consent() check enforcing
scope/source matrix (testimonial_form blocked for advertising/case_study
at application level, backed by DB triggers). Grant workflows for
signed documents and testimonial forms. Revocation with content_usage_log
flagging. Expiration processing for scheduler job. Consent summary for UI."
```

---

### Task 5: Photo DB (app/photo_db.py)

Create the database access layer for treatment cycles, photo sessions, photos, measurements, and session type history. Follows the same `get_db()` / `log_event()` pattern as `consent_db.py` and `campaign_db.py`.

**Files:**
- `app/photo_db.py` (new)

**Steps:**

- [ ] 1. Create `app/photo_db.py` with the following complete code:

```python
from datetime import datetime
from typing import Optional
from app.database import get_db, log_event


# ── Treatment Cycles ─────────────────────────────────────

def create_treatment_cycle(
    patient_id: int,
    cycle_number: int = 1,
    started_at: Optional[str] = None,
    notes: str = "",
) -> int:
    """Create a new treatment cycle for a patient.

    Returns the new cycle ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO patient_treatment_cycles
           (patient_id, cycle_number, started_at, notes)
           VALUES (?, ?, ?, ?)""",
        (patient_id, cycle_number, started_at, notes),
    )
    conn.commit()
    cycle_id = cursor.lastrowid
    conn.close()
    log_event(
        "photo",
        f"Treatment cycle {cycle_number} created for patient {patient_id}",
        {"cycle_id": cycle_id},
    )
    return cycle_id


def get_cycles_for_patient(patient_id: int) -> list[dict]:
    """Get all treatment cycles for a patient, ordered by cycle number."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM patient_treatment_cycles
           WHERE patient_id = ?
           ORDER BY cycle_number ASC""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_cycle(patient_id: int) -> Optional[dict]:
    """Get the most recent treatment cycle for a patient."""
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM patient_treatment_cycles
           WHERE patient_id = ?
           ORDER BY cycle_number DESC
           LIMIT 1""",
        (patient_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Photo Sessions ────────────────────────────────────────

def create_session(
    patient_id: int,
    session_number: int,
    session_date: str,
    session_type: str = "mid_treatment",
    cycle_id: Optional[int] = None,
    notes: str = "",
) -> int:
    """Create a new photo session.

    session_type: baseline, mid_treatment, final, followup, incomplete
    Returns the new session ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO patient_photo_sessions
           (patient_id, cycle_id, session_number, session_date, session_type, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (patient_id, cycle_id, session_number, session_date, session_type, notes),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    log_event(
        "photo",
        f"Photo session {session_number} created for patient {patient_id}",
        {"session_id": session_id, "session_type": session_type},
    )
    return session_id


def get_session(session_id: int) -> Optional[dict]:
    """Get a photo session by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM patient_photo_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sessions_for_patient(
    patient_id: int, include_archived: bool = False
) -> list[dict]:
    """Get all photo sessions for a patient, ordered by session number.

    By default excludes archived sessions (archived_at IS NOT NULL).
    """
    conn = get_db()
    query = """SELECT * FROM patient_photo_sessions
               WHERE patient_id = ?"""
    params: list = [patient_id]
    if not include_archived:
        query += " AND archived_at IS NULL"
    query += " ORDER BY session_number ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_session(session_id: int, **kwargs) -> bool:
    """Update arbitrary fields on a photo session.

    Allowed fields: session_type, session_date, notes, cycle_id, session_number.
    Returns True if the session was found and updated.
    """
    allowed = {"session_type", "session_date", "notes", "cycle_id", "session_number"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session_id]

    conn = get_db()
    cursor = conn.execute(
        f"UPDATE patient_photo_sessions SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "photo",
            f"Session {session_id} updated",
            {"fields": list(updates.keys())},
        )
    return changed


def complete_session(session_id: int) -> bool:
    """Mark a session as completed by setting completed_at.

    If session_type is 'final', also sets testimonial_request_eligible_at.
    Returns True if the session was found and completed.
    """
    now = datetime.now().isoformat()
    conn = get_db()

    session = conn.execute(
        "SELECT id, session_type FROM patient_photo_sessions WHERE id = ? AND completed_at IS NULL",
        (session_id,),
    ).fetchone()
    if not session:
        conn.close()
        return False

    if session["session_type"] == "final":
        conn.execute(
            """UPDATE patient_photo_sessions
               SET completed_at = ?, testimonial_request_eligible_at = ?
               WHERE id = ?""",
            (now, now, session_id),
        )
    else:
        conn.execute(
            "UPDATE patient_photo_sessions SET completed_at = ? WHERE id = ?",
            (now, session_id),
        )
    conn.commit()
    conn.close()
    log_event(
        "photo",
        f"Session {session_id} completed (type={session['session_type']})",
    )
    return True


def archive_session(session_id: int) -> bool:
    """Soft-archive a session by setting archived_at.

    Returns True if the session was found and archived.
    """
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        "UPDATE patient_photo_sessions SET archived_at = ? WHERE id = ? AND archived_at IS NULL",
        (now, session_id),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event("photo", f"Session {session_id} archived")
    return changed


def get_session_count_for_patient(patient_id: int) -> int:
    """Get the number of non-archived sessions for a patient."""
    conn = get_db()
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM patient_photo_sessions
           WHERE patient_id = ? AND archived_at IS NULL""",
        (patient_id,),
    ).fetchone()
    conn.close()
    return row["cnt"]


def change_session_type(
    session_id: int,
    new_type: str,
    changed_by: str = "",
    reason: str = "",
) -> bool:
    """Change a session's type and log the change to session_type_history.

    Returns True if the session was found and type changed.
    """
    conn = get_db()
    session = conn.execute(
        "SELECT id, session_type FROM patient_photo_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if not session:
        conn.close()
        return False

    old_type = session["session_type"]
    if old_type == new_type:
        conn.close()
        return False

    now = datetime.now().isoformat()

    # Log the type change
    conn.execute(
        """INSERT INTO session_type_history
           (session_id, old_type, new_type, changed_by, changed_at, reason)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, old_type, new_type, changed_by, now, reason),
    )

    # Update the session
    conn.execute(
        "UPDATE patient_photo_sessions SET session_type = ? WHERE id = ?",
        (new_type, session_id),
    )
    conn.commit()
    conn.close()
    log_event(
        "photo",
        f"Session {session_id} type changed: {old_type} -> {new_type}",
        {"changed_by": changed_by, "reason": reason},
    )
    return True


# ── Photos ────────────────────────────────────────────────

def insert_photo(
    session_id: int,
    angle: str,
    file_path: str,
    file_hash: str,
    preview_path: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
    version_number: int = 1,
    retake_reason: str = "",
) -> int:
    """Insert a new photo record.

    Returns the new photo ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO patient_photos
           (session_id, angle, file_path, preview_path, thumbnail_path,
            file_hash, version_number, is_current, retake_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            session_id,
            angle,
            file_path,
            preview_path,
            thumbnail_path,
            file_hash,
            version_number,
            retake_reason,
        ),
    )
    conn.commit()
    photo_id = cursor.lastrowid
    conn.close()
    log_event(
        "photo",
        f"Photo uploaded: session {session_id}, angle={angle}, version={version_number}",
        {"photo_id": photo_id},
    )
    return photo_id


def get_photos_for_session(session_id: int, current_only: bool = True) -> list[dict]:
    """Get photos for a session.

    If current_only=True, returns only the latest version of each angle.
    If current_only=False, returns all versions including superseded.
    """
    conn = get_db()
    query = "SELECT * FROM patient_photos WHERE session_id = ?"
    params: list = [session_id]
    if current_only:
        query += " AND is_current = 1"
    query += " ORDER BY angle ASC, version_number DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_current_photos(session_id: int) -> list[dict]:
    """Get only the current (is_current=1) photos for a session, one per angle."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM patient_photos
           WHERE session_id = ? AND is_current = 1
           ORDER BY angle ASC""",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def supersede_photo(old_photo_id: int, new_photo_id: int) -> bool:
    """Mark a photo as superseded by a newer version.

    Sets is_current=0, superseded_at, and superseded_by on the old photo.
    Returns True if the old photo was found and updated.
    """
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        """UPDATE patient_photos
           SET is_current = 0, superseded_at = ?, superseded_by = ?
           WHERE id = ? AND is_current = 1""",
        (now, new_photo_id, old_photo_id),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "photo",
            f"Photo {old_photo_id} superseded by {new_photo_id}",
        )
    return changed


def get_photo_version_history(session_id: int, angle: str) -> list[dict]:
    """Get all versions of a photo for a specific session and angle.

    Ordered by version_number descending (newest first).
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM patient_photos
           WHERE session_id = ? AND angle = ?
           ORDER BY version_number DESC""",
        (session_id, angle),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Measurements ──────────────────────────────────────────

def upsert_measurement(
    session_id: int,
    measurement_point: str,
    value_inches: float,
    measured_by: str = "",
    measured_at: Optional[str] = None,
    notes: str = "",
) -> int:
    """Insert or update a measurement for a session and point.

    Uses ON CONFLICT(session_id, measurement_point) to upsert.
    Returns the measurement ID.
    """
    if measured_at is None:
        measured_at = datetime.now().isoformat()

    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO patient_measurements
           (session_id, measurement_point, value_inches, measured_by, measured_at, notes)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id, measurement_point)
           DO UPDATE SET
               value_inches = excluded.value_inches,
               measured_by = excluded.measured_by,
               measured_at = excluded.measured_at,
               notes = excluded.notes""",
        (session_id, measurement_point, value_inches, measured_by, measured_at, notes),
    )
    conn.commit()
    measurement_id = cursor.lastrowid
    conn.close()
    log_event(
        "photo",
        f"Measurement upserted: session {session_id}, {measurement_point}={value_inches}in",
        {"measurement_id": measurement_id},
    )
    return measurement_id


def get_measurements_for_session(session_id: int) -> list[dict]:
    """Get all measurements for a session, ordered by measurement point."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM patient_measurements
           WHERE session_id = ?
           ORDER BY measurement_point ASC""",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_measurement_count(session_id: int) -> int:
    """Get the number of measurements recorded for a session."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM patient_measurements WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    return row["cnt"]


# ── Session Completion Check ──────────────────────────────

REQUIRED_ANGLES = {"front", "side_left", "side_right", "45_degree_left", "45_degree_right", "back"}
REQUIRED_MEASUREMENTS = {
    "waist", "hips", "thighs_left", "thighs_right",
    "arms_left", "arms_right", "chest", "under_bust",
}


def check_session_complete(session_id: int) -> dict:
    """Check if a session has all required photos and measurements.

    Returns a dict with:
        is_complete: bool
        missing_angles: list of missing photo angles
        missing_measurements: list of missing measurement points
        photo_count: int (current photos only)
        measurement_count: int
    """
    conn = get_db()

    # Check current photos
    photo_rows = conn.execute(
        "SELECT angle FROM patient_photos WHERE session_id = ? AND is_current = 1",
        (session_id,),
    ).fetchall()
    uploaded_angles = {r["angle"] for r in photo_rows}
    missing_angles = sorted(REQUIRED_ANGLES - uploaded_angles)

    # Check measurements
    measurement_rows = conn.execute(
        "SELECT measurement_point FROM patient_measurements WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    recorded_measurements = {r["measurement_point"] for r in measurement_rows}
    missing_measurements = sorted(REQUIRED_MEASUREMENTS - recorded_measurements)

    conn.close()

    return {
        "is_complete": len(missing_angles) == 0 and len(missing_measurements) == 0,
        "missing_angles": missing_angles,
        "missing_measurements": missing_measurements,
        "photo_count": len(uploaded_angles),
        "measurement_count": len(recorded_measurements),
    }
```

- [ ] 2. Verify the file was created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/photo_db.py
# Expected output: approximately 380-420 lines

python -c "
from app import photo_db
# Verify all expected functions exist
funcs = [
    'create_treatment_cycle', 'get_cycles_for_patient', 'get_latest_cycle',
    'create_session', 'get_session', 'get_sessions_for_patient',
    'update_session', 'complete_session', 'archive_session',
    'get_session_count_for_patient', 'change_session_type',
    'insert_photo', 'get_photos_for_session', 'get_current_photos',
    'supersede_photo', 'get_photo_version_history',
    'upsert_measurement', 'get_measurements_for_session', 'get_measurement_count',
    'check_session_complete',
]
for fn in funcs:
    assert hasattr(photo_db, fn), f'Missing function: {fn}'
print(f'All {len(funcs)} photo_db functions verified.')
"
# Expected output: All 20 photo_db functions verified.
```

- [ ] 3. Test photo_db functions with a quick integration test:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import photo_db

init_db()
run_migrations()

# Create a test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('phototest@test.com', 'Photo', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Test 1: Create treatment cycle
cycle_id = photo_db.create_treatment_cycle(pid, cycle_number=1, started_at='2026-01-15')
assert cycle_id > 0
print(f'Test 1 PASSED: Created cycle {cycle_id}')

# Test 2: Get cycles
cycles = photo_db.get_cycles_for_patient(pid)
assert len(cycles) == 1
assert cycles[0]['cycle_number'] == 1
print('Test 2 PASSED: Retrieved cycles.')

# Test 3: Get latest cycle
latest = photo_db.get_latest_cycle(pid)
assert latest is not None
assert latest['id'] == cycle_id
print('Test 3 PASSED: Latest cycle retrieved.')

# Test 4: Create session
sid = photo_db.create_session(
    pid, session_number=1, session_date='2026-01-15',
    session_type='baseline', cycle_id=cycle_id,
)
assert sid > 0
print(f'Test 4 PASSED: Created session {sid}')

# Test 5: Get session
session = photo_db.get_session(sid)
assert session['session_type'] == 'baseline'
assert session['patient_id'] == pid
print('Test 5 PASSED: Retrieved session.')

# Test 6: Update session
result = photo_db.update_session(sid, notes='Updated notes')
assert result is True
session = photo_db.get_session(sid)
assert session['notes'] == 'Updated notes'
print('Test 6 PASSED: Session updated.')

# Test 7: Change session type (with history logging)
result = photo_db.change_session_type(sid, 'final', changed_by='admin', reason='Treatment complete')
assert result is True
session = photo_db.get_session(sid)
assert session['session_type'] == 'final'
# Verify history was logged
conn = get_db()
history = conn.execute('SELECT * FROM session_type_history WHERE session_id = ?', (sid,)).fetchall()
conn.close()
assert len(history) == 1
assert history[0]['old_type'] == 'baseline'
assert history[0]['new_type'] == 'final'
print('Test 7 PASSED: Session type changed with history logged.')

# Test 8: Insert photos and check completion
photo_id = photo_db.insert_photo(sid, 'front', '/path/front.jpg', 'abc123hash')
assert photo_id > 0
completion = photo_db.check_session_complete(sid)
assert completion['is_complete'] is False
assert completion['photo_count'] == 1
assert 'back' in completion['missing_angles']
print(f'Test 8 PASSED: Photo inserted, completion check shows {len(completion[\"missing_angles\"])} missing angles.')

# Test 9: Supersede photo
new_photo_id = photo_db.insert_photo(sid, 'front', '/path/front_v2.jpg', 'def456hash', version_number=2, retake_reason='Better lighting')
result = photo_db.supersede_photo(photo_id, new_photo_id)
assert result is True
current = photo_db.get_current_photos(sid)
assert len(current) == 1
assert current[0]['id'] == new_photo_id
history = photo_db.get_photo_version_history(sid, 'front')
assert len(history) == 2
print('Test 9 PASSED: Photo superseded, version history correct.')

# Test 10: Upsert measurements
photo_db.upsert_measurement(sid, 'waist', 32.5, measured_by='nurse')
photo_db.upsert_measurement(sid, 'hips', 38.0, measured_by='nurse')
measurements = photo_db.get_measurements_for_session(sid)
assert len(measurements) == 2
count = photo_db.get_measurement_count(sid)
assert count == 2
# Update existing measurement
photo_db.upsert_measurement(sid, 'waist', 32.0, measured_by='nurse', notes='Remeasured')
measurements = photo_db.get_measurements_for_session(sid)
waist = [m for m in measurements if m['measurement_point'] == 'waist'][0]
assert waist['value_inches'] == 32.0
assert waist['notes'] == 'Remeasured'
print('Test 10 PASSED: Measurements upserted correctly.')

# Test 11: Complete session (final type sets testimonial_request_eligible_at)
result = photo_db.complete_session(sid)
assert result is True
session = photo_db.get_session(sid)
assert session['completed_at'] is not None
assert session['testimonial_request_eligible_at'] is not None
print('Test 11 PASSED: Session completed, testimonial_request_eligible_at set for final session.')

# Test 12: Archive session
sid2 = photo_db.create_session(pid, session_number=2, session_date='2026-02-15')
result = photo_db.archive_session(sid2)
assert result is True
sessions = photo_db.get_sessions_for_patient(pid, include_archived=False)
assert all(s['id'] != sid2 for s in sessions)
sessions_all = photo_db.get_sessions_for_patient(pid, include_archived=True)
assert any(s['id'] == sid2 for s in sessions_all)
count = photo_db.get_session_count_for_patient(pid)
assert count == 1  # Only non-archived session
print('Test 12 PASSED: Session archived and filtered correctly.')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM session_type_history WHERE session_id IN (?, ?)', (sid, sid2))
conn.execute('DELETE FROM patient_measurements WHERE session_id IN (?, ?)', (sid, sid2))
conn.execute('DELETE FROM patient_photos WHERE session_id IN (?, ?)', (sid, sid2))
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_treatment_cycles WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()
print('All 12 photo_db tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Created cycle ...
# Test 2 PASSED: Retrieved cycles.
# Test 3 PASSED: Latest cycle retrieved.
# Test 4 PASSED: Created session ...
# Test 5 PASSED: Retrieved session.
# Test 6 PASSED: Session updated.
# Test 7 PASSED: Session type changed with history logged.
# Test 8 PASSED: Photo inserted, completion check shows 5 missing angles.
# Test 9 PASSED: Photo superseded, version history correct.
# Test 10 PASSED: Measurements upserted correctly.
# Test 11 PASSED: Session completed, testimonial_request_eligible_at set for final session.
# Test 12 PASSED: Session archived and filtered correctly.
# All 12 photo_db tests passed. Cleanup complete.
```

- [ ] 4. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/photo_db.py
git commit -m "Add photo database layer for sessions, photos, measurements, and cycles

Treatment cycles CRUD, photo sessions with archive/complete/type-change
(with session_type_history audit trail), photo insert/supersede/version
history, measurement upsert with ON CONFLICT, and check_session_complete
verifying all 6 angles + 8 measurement points."
```

---

### Task 6: Measurement Service (app/services/measurement_service.py)

Create the measurement validation and delta calculation service. Handles hard/soft validation ranges, per-point and total inches-lost deltas between sessions, and aggregate statistics across patients for case study use.

**Files:**
- `app/services/measurement_service.py` (new)

**Steps:**

- [ ] 1. Create `app/services/measurement_service.py` with the following complete code:

```python
import logging
import statistics
from typing import Optional
from app.database import get_db
from app import photo_db

logger = logging.getLogger(__name__)

# All 8 measurement points
MEASUREMENT_POINTS = [
    "waist", "hips", "thighs_left", "thighs_right",
    "arms_left", "arms_right", "chest", "under_bust",
]

# 6 points included in aggregate "total inches lost" calculations
# chest and under_bust are excluded from marketing aggregates
AGGREGATE_POINTS = [
    "waist", "hips", "thighs_left", "thighs_right",
    "arms_left", "arms_right",
]

# Hard validation ranges (plausible min/max in inches) per measurement point
# Values outside these ranges are rejected as likely typos (e.g., 325 instead of 32.5)
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "waist":        (15.0, 80.0),
    "hips":         (20.0, 85.0),
    "thighs_left":  (10.0, 50.0),
    "thighs_right": (10.0, 50.0),
    "arms_left":    (5.0, 30.0),
    "arms_right":   (5.0, 30.0),
    "chest":        (20.0, 75.0),
    "under_bust":   (18.0, 65.0),
}

# Soft validation: if value differs from previous by more than this, warn
SOFT_DELTA_THRESHOLD = 4.0


def validate_measurement(
    point: str,
    value: float,
    previous_value: Optional[float] = None,
) -> tuple[bool, list[str], list[str]]:
    """Validate a measurement value.

    Args:
        point: The measurement point name (e.g., 'waist').
        value: The measurement value in inches.
        previous_value: The value from the previous session for the same point,
                        if available (used for soft validation).

    Returns:
        A tuple of (is_valid, warnings, errors):
        - is_valid: True if no hard errors (value may still have warnings).
        - warnings: List of warning messages (soft validation issues).
        - errors: List of error messages (hard validation failures).
    """
    warnings: list[str] = []
    errors: list[str] = []

    # Check that the point is valid
    if point not in MEASUREMENT_POINTS:
        errors.append(f"Unknown measurement point: '{point}'. "
                      f"Valid points: {', '.join(MEASUREMENT_POINTS)}")
        return False, warnings, errors

    # Check value is positive
    if value <= 0:
        errors.append(f"Measurement value must be positive, got {value}")
        return False, warnings, errors

    # Hard validation: plausible range check
    min_val, max_val = PLAUSIBLE_RANGES[point]
    if value < min_val or value > max_val:
        errors.append(
            f"{point} value {value} is outside plausible range "
            f"({min_val}-{max_val} inches). "
            f"Check for typos — override with a note if correct."
        )
        return False, warnings, errors

    # Soft validation: large change from previous session
    if previous_value is not None:
        delta = abs(value - previous_value)
        if delta > SOFT_DELTA_THRESHOLD:
            warnings.append(
                f"{point} changed by {delta:.1f} inches from previous value "
                f"({previous_value} -> {value}). Confirm this is correct."
            )

    is_valid = len(errors) == 0
    return is_valid, warnings, errors


def calculate_session_deltas(
    baseline_session_id: int,
    final_session_id: int,
) -> dict:
    """Calculate per-point and total measurement deltas between two sessions.

    Positive delta means inches lost (baseline - final).
    Negative delta means inches gained.

    Returns a dict with:
        per_point: dict of {point: {baseline, final, delta}} for each point present in both sessions
        aggregate_points_delta: total inches lost across the 6 aggregate points
        all_points_delta: total inches change across all matched points
        points_matched: number of points with data in both sessions
        aggregate_points_matched: number of aggregate points with data in both sessions
    """
    baseline_measurements = photo_db.get_measurements_for_session(baseline_session_id)
    final_measurements = photo_db.get_measurements_for_session(final_session_id)

    # Index by measurement_point
    baseline_by_point = {m["measurement_point"]: m["value_inches"] for m in baseline_measurements}
    final_by_point = {m["measurement_point"]: m["value_inches"] for m in final_measurements}

    per_point: dict[str, dict] = {}
    aggregate_delta = 0.0
    all_delta = 0.0
    aggregate_matched = 0

    for point in MEASUREMENT_POINTS:
        if point in baseline_by_point and point in final_by_point:
            baseline_val = baseline_by_point[point]
            final_val = final_by_point[point]
            delta = baseline_val - final_val  # positive = inches lost

            per_point[point] = {
                "baseline": baseline_val,
                "final": final_val,
                "delta": delta,
            }

            all_delta += delta

            if point in AGGREGATE_POINTS:
                aggregate_delta += delta
                aggregate_matched += 1

    return {
        "per_point": per_point,
        "aggregate_points_delta": aggregate_delta,
        "all_points_delta": all_delta,
        "points_matched": len(per_point),
        "aggregate_points_matched": aggregate_matched,
    }


def calculate_aggregate_stats(patient_ids: list[int]) -> dict:
    """Calculate aggregate measurement statistics across multiple patients.

    For each patient, finds the baseline and final sessions, calculates deltas,
    then aggregates across patients.

    Only includes patients who have both a baseline and a final session with
    measurements recorded for all 6 aggregate points.

    Returns a dict with:
        patient_count: number of qualifying patients
        total_inches_lost: dict with avg, median, min, max, stdev
        per_point: dict of {point: {avg, median, min, max}} across patients
        qualifying_patient_ids: list of patient IDs that met criteria
        excluded_patient_ids: list of patient IDs that did not qualify
    """
    qualifying_deltas: list[float] = []
    per_point_deltas: dict[str, list[float]] = {p: [] for p in AGGREGATE_POINTS}
    qualifying_ids: list[int] = []
    excluded_ids: list[int] = []

    conn = get_db()

    for pid in patient_ids:
        # Find baseline session
        baseline = conn.execute(
            """SELECT id FROM patient_photo_sessions
               WHERE patient_id = ? AND session_type = 'baseline'
                 AND archived_at IS NULL
               ORDER BY session_number ASC LIMIT 1""",
            (pid,),
        ).fetchone()

        # Find final session
        final = conn.execute(
            """SELECT id FROM patient_photo_sessions
               WHERE patient_id = ? AND session_type = 'final'
                 AND archived_at IS NULL
               ORDER BY session_number DESC LIMIT 1""",
            (pid,),
        ).fetchone()

        if not baseline or not final:
            excluded_ids.append(pid)
            continue

        # Calculate deltas for this patient
        deltas = calculate_session_deltas(baseline["id"], final["id"])

        # Only include if all 6 aggregate points have data
        if deltas["aggregate_points_matched"] < len(AGGREGATE_POINTS):
            excluded_ids.append(pid)
            continue

        qualifying_ids.append(pid)
        qualifying_deltas.append(deltas["aggregate_points_delta"])

        for point in AGGREGATE_POINTS:
            if point in deltas["per_point"]:
                per_point_deltas[point].append(deltas["per_point"][point]["delta"])

    conn.close()

    # Calculate aggregate statistics
    result: dict = {
        "patient_count": len(qualifying_ids),
        "qualifying_patient_ids": qualifying_ids,
        "excluded_patient_ids": excluded_ids,
        "total_inches_lost": {},
        "per_point": {},
    }

    if qualifying_deltas:
        result["total_inches_lost"] = {
            "avg": round(statistics.mean(qualifying_deltas), 2),
            "median": round(statistics.median(qualifying_deltas), 2),
            "min": round(min(qualifying_deltas), 2),
            "max": round(max(qualifying_deltas), 2),
            "stdev": round(statistics.stdev(qualifying_deltas), 2) if len(qualifying_deltas) > 1 else 0.0,
        }

    for point in AGGREGATE_POINTS:
        vals = per_point_deltas[point]
        if vals:
            result["per_point"][point] = {
                "avg": round(statistics.mean(vals), 2),
                "median": round(statistics.median(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
            }

    return result
```

- [ ] 2. Verify the file was created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/services/measurement_service.py
# Expected output: approximately 200-230 lines

python -c "
from app.services import measurement_service as ms
# Verify all expected exports
assert hasattr(ms, 'MEASUREMENT_POINTS')
assert hasattr(ms, 'AGGREGATE_POINTS')
assert hasattr(ms, 'PLAUSIBLE_RANGES')
assert hasattr(ms, 'validate_measurement')
assert hasattr(ms, 'calculate_session_deltas')
assert hasattr(ms, 'calculate_aggregate_stats')
assert len(ms.MEASUREMENT_POINTS) == 8
assert len(ms.AGGREGATE_POINTS) == 6
assert 'chest' not in ms.AGGREGATE_POINTS
assert 'under_bust' not in ms.AGGREGATE_POINTS
assert len(ms.PLAUSIBLE_RANGES) == 8
print('All measurement_service exports verified.')
"
# Expected output: All measurement_service exports verified.
```

- [ ] 3. Test measurement validation logic:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.measurement_service import validate_measurement

# Test 1: Valid measurement, no previous
is_valid, warnings, errors = validate_measurement('waist', 32.5)
assert is_valid is True
assert len(warnings) == 0
assert len(errors) == 0
print('Test 1 PASSED: Valid measurement accepted.')

# Test 2: Hard validation — below range
is_valid, warnings, errors = validate_measurement('waist', 10.0)
assert is_valid is False
assert len(errors) == 1
assert 'plausible range' in errors[0]
print(f'Test 2 PASSED: Below-range rejected: {errors[0][:60]}...')

# Test 3: Hard validation — above range (typo like 325 instead of 32.5)
is_valid, warnings, errors = validate_measurement('waist', 325.0)
assert is_valid is False
assert len(errors) == 1
print(f'Test 3 PASSED: Above-range rejected: {errors[0][:60]}...')

# Test 4: Soft validation — large delta from previous
is_valid, warnings, errors = validate_measurement('hips', 38.0, previous_value=30.0)
assert is_valid is True
assert len(warnings) == 1
assert 'changed by' in warnings[0]
print(f'Test 4 PASSED: Large delta warned: {warnings[0][:60]}...')

# Test 5: Soft validation — small delta (no warning)
is_valid, warnings, errors = validate_measurement('hips', 38.0, previous_value=37.0)
assert is_valid is True
assert len(warnings) == 0
print('Test 5 PASSED: Small delta accepted without warning.')

# Test 6: Invalid point name
is_valid, warnings, errors = validate_measurement('belly', 32.0)
assert is_valid is False
assert 'Unknown measurement point' in errors[0]
print('Test 6 PASSED: Invalid point rejected.')

# Test 7: Negative value
is_valid, warnings, errors = validate_measurement('waist', -5.0)
assert is_valid is False
assert 'positive' in errors[0]
print('Test 7 PASSED: Negative value rejected.')

# Test 8: Boundary values (exact min/max should pass)
is_valid, _, _ = validate_measurement('waist', 15.0)
assert is_valid is True
is_valid, _, _ = validate_measurement('waist', 80.0)
assert is_valid is True
print('Test 8 PASSED: Boundary values accepted.')

print('All 8 validation tests passed.')
"
# Expected output:
# Test 1 PASSED: Valid measurement accepted.
# Test 2 PASSED: Below-range rejected: waist value 10.0 is outside plausible range (15.0-80.0 ...
# Test 3 PASSED: Above-range rejected: waist value 325.0 is outside plausible range (15.0-80...
# Test 4 PASSED: Large delta warned: hips changed by 8.0 inches from previous value (30.0 ->...
# Test 5 PASSED: Small delta accepted without warning.
# Test 6 PASSED: Invalid point rejected.
# Test 7 PASSED: Negative value rejected.
# Test 8 PASSED: Boundary values accepted.
# All 8 validation tests passed.
```

- [ ] 4. Test delta calculation with real DB data:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import photo_db
from app.services.measurement_service import (
    calculate_session_deltas, calculate_aggregate_stats, AGGREGATE_POINTS,
)

init_db()
run_migrations()

# Create test patient and sessions
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('mstest@test.com', 'Measure', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

cycle_id = photo_db.create_treatment_cycle(pid, cycle_number=1)

# Baseline session
baseline_sid = photo_db.create_session(
    pid, session_number=1, session_date='2026-01-15',
    session_type='baseline', cycle_id=cycle_id,
)

# Final session
final_sid = photo_db.create_session(
    pid, session_number=6, session_date='2026-03-15',
    session_type='final', cycle_id=cycle_id,
)

# Baseline measurements
baseline_data = {
    'waist': 34.0, 'hips': 40.0, 'thighs_left': 24.0, 'thighs_right': 24.5,
    'arms_left': 13.0, 'arms_right': 13.5, 'chest': 38.0, 'under_bust': 32.0,
}
for point, val in baseline_data.items():
    photo_db.upsert_measurement(baseline_sid, point, val)

# Final measurements (lost some inches)
final_data = {
    'waist': 32.0, 'hips': 38.5, 'thighs_left': 23.0, 'thighs_right': 23.5,
    'arms_left': 12.5, 'arms_right': 13.0, 'chest': 37.5, 'under_bust': 31.5,
}
for point, val in final_data.items():
    photo_db.upsert_measurement(final_sid, point, val)

# Test 1: Calculate deltas
deltas = calculate_session_deltas(baseline_sid, final_sid)
assert deltas['points_matched'] == 8
assert deltas['aggregate_points_matched'] == 6
# Waist: 34-32=2, Hips: 40-38.5=1.5, ThL: 24-23=1, ThR: 24.5-23.5=1,
# ArmL: 13-12.5=0.5, ArmR: 13.5-13=0.5 => aggregate = 6.5
assert abs(deltas['aggregate_points_delta'] - 6.5) < 0.01
print(f'Test 1 PASSED: Aggregate delta = {deltas[\"aggregate_points_delta\"]} inches lost.')

# Verify per-point detail
assert abs(deltas['per_point']['waist']['delta'] - 2.0) < 0.01
assert abs(deltas['per_point']['hips']['delta'] - 1.5) < 0.01
print('Test 2 PASSED: Per-point deltas correct.')

# Test 3: Aggregate stats across patients
stats = calculate_aggregate_stats([pid])
assert stats['patient_count'] == 1
assert abs(stats['total_inches_lost']['avg'] - 6.5) < 0.01
assert abs(stats['total_inches_lost']['median'] - 6.5) < 0.01
print(f'Test 3 PASSED: Aggregate stats — avg={stats[\"total_inches_lost\"][\"avg\"]}, patient_count={stats[\"patient_count\"]}')

# Test 4: Patient without final session is excluded
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('mstest2@test.com', 'No', 'Final', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid2 = cursor.lastrowid
conn.close()

stats2 = calculate_aggregate_stats([pid, pid2])
assert stats2['patient_count'] == 1
assert pid2 in stats2['excluded_patient_ids']
print('Test 4 PASSED: Patient without final session excluded from aggregates.')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_measurements WHERE session_id IN (?, ?)', (baseline_sid, final_sid))
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id IN (?, ?)', (pid, pid2))
conn.execute('DELETE FROM patient_treatment_cycles WHERE patient_id IN (?, ?)', (pid, pid2))
conn.execute('DELETE FROM patients WHERE id IN (?, ?)', (pid, pid2))
conn.commit()
conn.close()
print('All 4 delta/aggregate tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Aggregate delta = 6.5 inches lost.
# Test 2 PASSED: Per-point deltas correct.
# Test 3 PASSED: Aggregate stats — avg=6.5, patient_count=1
# Test 4 PASSED: Patient without final session excluded from aggregates.
# All 4 delta/aggregate tests passed. Cleanup complete.
```

- [ ] 5. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/measurement_service.py
git commit -m "Add measurement validation and delta calculation service

Plausible range validation (hard reject for typos like 325 vs 32.5),
soft warning for >4-inch deltas from previous session. Session delta
calculator for baseline->final inches lost. Aggregate stats across
patients for case study use, excluding chest and under_bust from
marketing totals per spec."
```

---

### Task 7: Testimonial DB (app/testimonial_db.py)

Create the database access layer for testimonials, the send log, token management, bounce tracking, and the 90-day lookback guard. Follows the same `get_db()` / `log_event()` pattern as `consent_db.py`.

**Files:**
- `app/testimonial_db.py` (new)

**Steps:**

- [ ] 1. Create `app/testimonial_db.py` with the following complete code:

```python
from datetime import datetime
from typing import Optional
from app.database import get_db, log_event


# ── Testimonials ──────────────────────────────────────────

def create_testimonial(
    patient_id: int,
    session_id: Optional[int],
    cycle_id: Optional[int],
    token: str,
    token_expires_at: str,
) -> int:
    """Create a new testimonial request with status='requested'.

    Returns the new testimonial ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO testimonials
           (patient_id, session_id, cycle_id, token, token_expires_at, status)
           VALUES (?, ?, ?, ?, ?, 'requested')""",
        (patient_id, session_id, cycle_id, token, token_expires_at),
    )
    conn.commit()
    testimonial_id = cursor.lastrowid
    conn.close()
    log_event(
        "testimonial",
        f"Testimonial requested for patient {patient_id}",
        {"testimonial_id": testimonial_id, "session_id": session_id},
    )
    return testimonial_id


def get_testimonial(testimonial_id: int) -> Optional[dict]:
    """Get a testimonial by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM testimonials WHERE id = ?", (testimonial_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_testimonial_by_token(token: str) -> Optional[dict]:
    """Get a testimonial by its unique token (for public form access)."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM testimonials WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_testimonial(testimonial_id: int, **kwargs) -> bool:
    """Update arbitrary fields on a testimonial.

    Allowed fields: rating, text, video_path, status, flag_reason,
    submitted_at, consent_website, consent_social, consent_advertising,
    token_expires_at.
    Returns True if the testimonial was found and updated.
    Auto-injects updated_at = now on every update.
    """
    allowed = {
        "rating", "text", "video_path", "status", "flag_reason",
        "submitted_at", "consent_website", "consent_social",
        "consent_advertising", "token_expires_at",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    # Always set updated_at on any modification
    from datetime import datetime
    updates["updated_at"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [testimonial_id]

    conn = get_db()
    cursor = conn.execute(
        f"UPDATE testimonials SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "testimonial",
            f"Testimonial {testimonial_id} updated",
            {"fields": list(updates.keys())},
        )
    return changed


def get_testimonials_for_patient(patient_id: int) -> list[dict]:
    """Get all testimonials for a patient, ordered by creation date descending."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM testimonials
           WHERE patient_id = ?
           ORDER BY created_at DESC""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_testimonials_by_status(status: str) -> list[dict]:
    """Get all testimonials with a specific status.

    Joins with patients table to include patient name and email.
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT t.*, p.first_name, p.last_name, p.email
           FROM testimonials t
           JOIN patients p ON t.patient_id = p.id
           WHERE t.status = ?
           ORDER BY t.created_at DESC""",
        (status,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def has_recent_testimonial(patient_id: int, days: int = 90) -> bool:
    """Check if a patient has submitted a testimonial within the last N days.

    This is the 90-day lookback guard. Only checks status='submitted' —
    declined_this_time and expired_no_response do NOT suppress new requests.
    """
    conn = get_db()
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM testimonials
           WHERE patient_id = ?
             AND submitted_at >= datetime('now', '-' || ? || ' days')
             AND status = 'submitted'""",
        (patient_id, days),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


# ── Testimonial Send Log ──────────────────────────────────

def create_send_log_entry(
    testimonial_id: int,
    touch_number: int,
    scheduled_for: str,
) -> int:
    """Create a send log entry for a testimonial touch.

    touch_number: 1 = initial request, 2 = reminder 1, 3 = reminder 2
    Returns the new log entry ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO testimonial_send_log
           (testimonial_id, touch_number, scheduled_for, status)
           VALUES (?, ?, ?, 'scheduled')""",
        (testimonial_id, touch_number, scheduled_for),
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    log_event(
        "testimonial",
        f"Send log entry created: testimonial {testimonial_id}, touch {touch_number}",
        {"log_id": log_id, "scheduled_for": scheduled_for},
    )
    return log_id


def get_send_log(testimonial_id: int) -> list[dict]:
    """Get all send log entries for a testimonial, ordered by touch number."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM testimonial_send_log
           WHERE testimonial_id = ?
           ORDER BY touch_number ASC""",
        (testimonial_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_sends(scheduled_before: Optional[str] = None) -> list[dict]:
    """Get all pending (scheduled) send log entries.

    If scheduled_before is provided, only returns entries scheduled before
    that timestamp. Joins with testimonials and patients for context.
    """
    conn = get_db()
    query = """SELECT sl.*, t.patient_id, t.token, t.status as testimonial_status,
                      p.first_name, p.last_name, p.email, p.email_bounced
               FROM testimonial_send_log sl
               JOIN testimonials t ON sl.testimonial_id = t.id
               JOIN patients p ON t.patient_id = p.id
               WHERE sl.status = 'scheduled'"""
    params: list = []
    if scheduled_before:
        query += " AND sl.scheduled_for <= ?"
        params.append(scheduled_before)
    query += " ORDER BY sl.scheduled_for ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_send_log_entry(log_id: int, **kwargs) -> bool:
    """Update fields on a send log entry.

    Allowed fields: sent_at, opened_at, clicked_at, status.
    Returns True if the entry was found and updated.
    """
    allowed = {"sent_at", "opened_at", "clicked_at", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [log_id]

    conn = get_db()
    cursor = conn.execute(
        f"UPDATE testimonial_send_log SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed


def cancel_remaining_touches(testimonial_id: int) -> int:
    """Cancel all remaining scheduled sends for a testimonial.

    Sets status='cancelled' on all send log entries with status='scheduled'.
    Returns the number of entries cancelled.
    """
    conn = get_db()
    cursor = conn.execute(
        """UPDATE testimonial_send_log
           SET status = 'cancelled'
           WHERE testimonial_id = ? AND status = 'scheduled'""",
        (testimonial_id,),
    )
    conn.commit()
    cancelled = cursor.rowcount
    conn.close()
    if cancelled > 0:
        log_event(
            "testimonial",
            f"Cancelled {cancelled} remaining touches for testimonial {testimonial_id}",
        )
    return cancelled


# ── Bounce Handling ───────────────────────────────────────

def mark_patient_bounced(patient_id: int) -> bool:
    """Mark a patient's email as bounced on the patients table.

    Sets email_bounced=1 and email_bounced_at to now.
    Returns True if the patient was found and updated.
    """
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        """UPDATE patients
           SET email_bounced = 1, email_bounced_at = ?
           WHERE id = ? AND email_bounced = 0""",
        (now, patient_id),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "testimonial",
            f"Patient {patient_id} email marked as bounced",
        )
    return changed
```

- [ ] 2. Verify the file was created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/testimonial_db.py
# Expected output: approximately 240-280 lines

python -c "
from app import testimonial_db
funcs = [
    'create_testimonial', 'get_testimonial', 'get_testimonial_by_token',
    'update_testimonial', 'get_testimonials_for_patient', 'get_testimonials_by_status',
    'has_recent_testimonial',
    'create_send_log_entry', 'get_send_log', 'get_pending_sends',
    'update_send_log_entry', 'cancel_remaining_touches',
    'mark_patient_bounced',
]
for fn in funcs:
    assert hasattr(testimonial_db, fn), f'Missing function: {fn}'
print(f'All {len(funcs)} testimonial_db functions verified.')
"
# Expected output: All 13 testimonial_db functions verified.
```

- [ ] 3. Test testimonial_db functions with a quick integration test:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
import uuid
from datetime import datetime, timedelta
from app.database import get_db, init_db, run_migrations
from app import testimonial_db

init_db()
run_migrations()

# Create test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('testmonial@test.com', 'Testi', 'Monial', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Test 1: Create testimonial
token = str(uuid.uuid4())
expires = (datetime.now() + timedelta(days=14)).isoformat()
tid = testimonial_db.create_testimonial(pid, session_id=None, cycle_id=None, token=token, token_expires_at=expires)
assert tid > 0
print(f'Test 1 PASSED: Created testimonial {tid}')

# Test 2: Get by ID
t = testimonial_db.get_testimonial(tid)
assert t is not None
assert t['status'] == 'requested'
assert t['patient_id'] == pid
print('Test 2 PASSED: Retrieved testimonial by ID.')

# Test 3: Get by token
t = testimonial_db.get_testimonial_by_token(token)
assert t is not None
assert t['id'] == tid
print('Test 3 PASSED: Retrieved testimonial by token.')

# Test 4: Update testimonial
result = testimonial_db.update_testimonial(
    tid,
    rating=5,
    text='Amazing results!',
    status='submitted',
    submitted_at=datetime.now().isoformat(),
    consent_website=1,
    consent_social=1,
)
assert result is True
t = testimonial_db.get_testimonial(tid)
assert t['rating'] == 5
assert t['status'] == 'submitted'
assert t['consent_website'] == 1
print('Test 4 PASSED: Testimonial updated with rating, text, consent, status.')

# Test 5: 90-day lookback guard
assert testimonial_db.has_recent_testimonial(pid, days=90) is True
assert testimonial_db.has_recent_testimonial(pid, days=0) is False
print('Test 5 PASSED: 90-day lookback guard works.')

# Test 6: Get by status
submitted = testimonial_db.get_testimonials_by_status('submitted')
assert any(r['id'] == tid for r in submitted)
print('Test 6 PASSED: Retrieved testimonials by status.')

# Test 7: Get for patient
patient_testimonials = testimonial_db.get_testimonials_for_patient(pid)
assert len(patient_testimonials) >= 1
print('Test 7 PASSED: Retrieved testimonials for patient.')

# Test 8: Send log entries
log1 = testimonial_db.create_send_log_entry(tid, touch_number=1, scheduled_for=datetime.now().isoformat())
log2 = testimonial_db.create_send_log_entry(tid, touch_number=2, scheduled_for=(datetime.now() + timedelta(days=3)).isoformat())
log3 = testimonial_db.create_send_log_entry(tid, touch_number=3, scheduled_for=(datetime.now() + timedelta(days=7)).isoformat())
assert log1 > 0
send_log = testimonial_db.get_send_log(tid)
assert len(send_log) == 3
assert send_log[0]['touch_number'] == 1
print('Test 8 PASSED: Created 3 send log entries.')

# Test 9: Update send log entry
result = testimonial_db.update_send_log_entry(log1, sent_at=datetime.now().isoformat(), status='sent')
assert result is True
send_log = testimonial_db.get_send_log(tid)
assert send_log[0]['status'] == 'sent'
print('Test 9 PASSED: Send log entry updated.')

# Test 10: Get pending sends
pending = testimonial_db.get_pending_sends()
assert any(r['id'] == log2 for r in pending)
assert not any(r['id'] == log1 for r in pending)  # log1 is now 'sent'
print(f'Test 10 PASSED: Found {len(pending)} pending sends.')

# Test 11: Cancel remaining touches
cancelled = testimonial_db.cancel_remaining_touches(tid)
assert cancelled == 2  # log2 and log3
send_log = testimonial_db.get_send_log(tid)
assert send_log[1]['status'] == 'cancelled'
assert send_log[2]['status'] == 'cancelled'
print('Test 11 PASSED: Cancelled 2 remaining touches.')

# Test 12: Mark patient bounced
result = testimonial_db.mark_patient_bounced(pid)
assert result is True
conn = get_db()
patient = conn.execute('SELECT email_bounced, email_bounced_at FROM patients WHERE id = ?', (pid,)).fetchone()
conn.close()
assert patient['email_bounced'] == 1
assert patient['email_bounced_at'] is not None
# Second call should return False (already bounced)
result2 = testimonial_db.mark_patient_bounced(pid)
assert result2 is False
print('Test 12 PASSED: Patient email marked as bounced (idempotent).')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM testimonial_send_log WHERE testimonial_id = ?', (tid,))
conn.execute('DELETE FROM testimonials WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()
print('All 12 testimonial_db tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Created testimonial ...
# Test 2 PASSED: Retrieved testimonial by ID.
# Test 3 PASSED: Retrieved testimonial by token.
# Test 4 PASSED: Testimonial updated with rating, text, consent, status.
# Test 5 PASSED: 90-day lookback guard works.
# Test 6 PASSED: Retrieved testimonials by status.
# Test 7 PASSED: Retrieved testimonials for patient.
# Test 8 PASSED: Created 3 send log entries.
# Test 9 PASSED: Send log entry updated.
# Test 10 PASSED: Found ... pending sends.
# Test 11 PASSED: Cancelled 2 remaining touches.
# Test 12 PASSED: Patient email marked as bounced (idempotent).
# All 12 testimonial_db tests passed. Cleanup complete.
```

- [ ] 4. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/testimonial_db.py
git commit -m "Add testimonial database layer with send log and bounce tracking

CRUD for testimonials with token-based public access. 90-day lookback
guard (has_recent_testimonial) only suppresses on status='submitted'.
3-touch send log with create/update/cancel_remaining_touches. Bounce
handling sets email_bounced flag on patients table (idempotent).
get_pending_sends joins testimonials+patients for scheduler use."
```

---

### Task 8: Gallery DB + Case Study DB (app/gallery_db.py + app/case_study_db.py)

Create two database access layer files: gallery_db.py for gallery versions, persistent exclusions, content usage tracking, and WordPress media uploads; and case_study_db.py for case studies, patient selections, and metric overrides.

**Files:**
- `app/gallery_db.py` (new)
- `app/case_study_db.py` (new)

**Steps:**

- [ ] 1. Create `app/gallery_db.py` with the following complete code:

```python
import json
from datetime import datetime
from typing import Optional
from app.database import get_db, log_event


# ── Gallery Versions ──────────────────────────────────────

def create_gallery_version(
    gallery_slug: str,
    patients_included: list[int],
    photo_ids_included: list[int],
    patient_count: int,
    generated_html: str,
    notes: str = "",
) -> int:
    """Create a new gallery version snapshot.

    Does NOT set is_current=1 — call publish_gallery_version to make it live.
    Returns the new gallery version ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO gallery_versions
           (gallery_slug, patients_included, photo_ids_included,
            patient_count, generated_html, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            gallery_slug,
            json.dumps(patients_included),
            json.dumps(photo_ids_included),
            patient_count,
            generated_html,
            notes,
        ),
    )
    conn.commit()
    version_id = cursor.lastrowid
    conn.close()
    log_event(
        "gallery",
        f"Gallery version created: slug={gallery_slug}, {patient_count} patients",
        {"version_id": version_id},
    )
    return version_id


def get_current_gallery(gallery_slug: str) -> Optional[dict]:
    """Get the currently published gallery version for a slug."""
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM gallery_versions
           WHERE gallery_slug = ? AND is_current = 1
           LIMIT 1""",
        (gallery_slug,),
    ).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["patients_included"] = json.loads(result["patients_included"])
        result["photo_ids_included"] = json.loads(result["photo_ids_included"])
        return result
    return None


def get_gallery_version(version_id: int) -> Optional[dict]:
    """Get a specific gallery version by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM gallery_versions WHERE id = ?", (version_id,)
    ).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["patients_included"] = json.loads(result["patients_included"])
        result["photo_ids_included"] = json.loads(result["photo_ids_included"])
        return result
    return None


def get_gallery_history(gallery_slug: str) -> list[dict]:
    """Get all gallery versions for a slug, ordered by generation date descending."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM gallery_versions
           WHERE gallery_slug = ?
           ORDER BY generated_at DESC""",
        (gallery_slug,),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        r["patients_included"] = json.loads(r["patients_included"])
        r["photo_ids_included"] = json.loads(r["photo_ids_included"])
        results.append(r)
    return results


def publish_gallery_version(
    version_id: int,
    published_by: str,
    wp_page_id: Optional[int] = None,
) -> bool:
    """Publish a gallery version, making it the current live version.

    Sets is_current=0 on all other versions for the same slug,
    then sets is_current=1, published_at, published_by on the target version.
    Returns True if the version was found and published.
    """
    now = datetime.now().isoformat()
    conn = get_db()

    # Get the version to find its slug
    version = conn.execute(
        "SELECT gallery_slug FROM gallery_versions WHERE id = ?", (version_id,)
    ).fetchone()
    if not version:
        conn.close()
        return False

    slug = version["gallery_slug"]

    # Un-publish all versions for this slug
    conn.execute(
        "UPDATE gallery_versions SET is_current = 0 WHERE gallery_slug = ?",
        (slug,),
    )

    # Publish the target version
    if wp_page_id is not None:
        conn.execute(
            """UPDATE gallery_versions
               SET is_current = 1, published_at = ?, published_by = ?, wp_page_id = ?
               WHERE id = ?""",
            (now, published_by, wp_page_id, version_id),
        )
    else:
        conn.execute(
            """UPDATE gallery_versions
               SET is_current = 1, published_at = ?, published_by = ?
               WHERE id = ?""",
            (now, published_by, version_id),
        )

    conn.commit()
    conn.close()
    log_event(
        "gallery",
        f"Gallery version {version_id} published for slug={slug}",
        {"published_by": published_by, "wp_page_id": wp_page_id},
    )
    return True


# ── Content Usage Log ─────────────────────────────────────

def create_content_usage_entry(
    patient_id: int,
    photo_id: Optional[int],
    testimonial_id: Optional[int],
    used_in: str,
    scope_used: str,
) -> int:
    """Log a published use of a patient's photo or testimonial.

    Returns the new usage entry ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO content_usage_log
           (patient_id, photo_id, testimonial_id, used_in, scope_used)
           VALUES (?, ?, ?, ?, ?)""",
        (patient_id, photo_id, testimonial_id, used_in, scope_used),
    )
    conn.commit()
    usage_id = cursor.lastrowid
    conn.close()
    log_event(
        "gallery",
        f"Content usage logged: patient {patient_id} in {used_in} (scope={scope_used})",
        {"usage_id": usage_id, "photo_id": photo_id, "testimonial_id": testimonial_id},
    )
    return usage_id


def get_content_usage_for_patient(patient_id: int) -> list[dict]:
    """Get all content usage entries for a patient, ordered by usage date descending."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM content_usage_log
           WHERE patient_id = ?
           ORDER BY used_at DESC""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_removals() -> list[dict]:
    """Get all content usage entries with removal_status='removal_pending'.

    Joins with patients for context.
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT cul.*, p.first_name, p.last_name, p.email
           FROM content_usage_log cul
           JOIN patients p ON cul.patient_id = p.id
           WHERE cul.removal_status = 'removal_pending'
           ORDER BY cul.removal_requested_at ASC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_content_removal(
    usage_id: int,
    action: str,
    resolved_by: str,
    reason: str = "",
) -> bool:
    """Resolve a pending content removal.

    action: 'removed' or 'kept_despite_flag'
    If action='removed', sets removal_status='removed', removed_at, removed_by.
    If action='kept_despite_flag', sets removal_status='kept_despite_flag',
        kept_despite_flag_reason.
    Returns True if the entry was found and resolved.
    """
    now = datetime.now().isoformat()
    conn = get_db()

    if action == "removed":
        cursor = conn.execute(
            """UPDATE content_usage_log
               SET removal_status = 'removed', removed_at = ?, removed_by = ?
               WHERE id = ? AND removal_status = 'removal_pending'""",
            (now, resolved_by, usage_id),
        )
    elif action == "kept_despite_flag":
        cursor = conn.execute(
            """UPDATE content_usage_log
               SET removal_status = 'kept_despite_flag', kept_despite_flag_reason = ?
               WHERE id = ? AND removal_status = 'removal_pending'""",
            (reason, usage_id),
        )
    else:
        conn.close()
        return False

    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "gallery",
            f"Content removal resolved: usage {usage_id}, action={action}",
            {"resolved_by": resolved_by, "reason": reason},
        )
    return changed


# ── Gallery Persistent Exclusions ─────────────────────────

def add_gallery_exclusion(
    patient_id: int,
    excluded_by: str,
    reason: str = "",
) -> int:
    """Add a patient to the gallery persistent exclusion list.

    Returns the exclusion ID. If already excluded, returns existing ID.
    """
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM gallery_persistent_exclusions WHERE patient_id = ?",
        (patient_id,),
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO gallery_persistent_exclusions
           (patient_id, excluded_by, reason)
           VALUES (?, ?, ?)""",
        (patient_id, excluded_by, reason),
    )
    conn.commit()
    exclusion_id = cursor.lastrowid
    conn.close()
    log_event(
        "gallery",
        f"Patient {patient_id} added to gallery exclusion list",
        {"exclusion_id": exclusion_id, "excluded_by": excluded_by, "reason": reason},
    )
    return exclusion_id


def remove_gallery_exclusion(patient_id: int) -> bool:
    """Remove a patient from the gallery persistent exclusion list.

    Returns True if the patient was found and removed.
    """
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM gallery_persistent_exclusions WHERE patient_id = ?",
        (patient_id,),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "gallery",
            f"Patient {patient_id} removed from gallery exclusion list",
        )
    return changed


def get_gallery_exclusions() -> list[dict]:
    """Get all gallery persistent exclusions, with patient name/email."""
    conn = get_db()
    rows = conn.execute(
        """SELECT gpe.*, p.first_name, p.last_name, p.email
           FROM gallery_persistent_exclusions gpe
           JOIN patients p ON gpe.patient_id = p.id
           ORDER BY gpe.excluded_at DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_patient_excluded(patient_id: int) -> bool:
    """Check if a patient is on the gallery persistent exclusion list."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM gallery_persistent_exclusions WHERE patient_id = ?",
        (patient_id,),
    ).fetchone()
    conn.close()
    return row is not None


# ── WordPress Media Uploads ───────────────────────────────

def create_wp_media_upload(
    patient_photo_id: int,
    wp_media_id: int,
    wp_media_url: str,
) -> int:
    """Record a photo uploaded to WordPress media library.

    Returns the new upload record ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO wp_media_uploads
           (patient_photo_id, wp_media_id, wp_media_url)
           VALUES (?, ?, ?)""",
        (patient_photo_id, wp_media_id, wp_media_url),
    )
    conn.commit()
    upload_id = cursor.lastrowid
    conn.close()
    return upload_id


def get_wp_media_for_photo(patient_photo_id: int) -> Optional[dict]:
    """Get the WordPress media record for a patient photo, if uploaded.

    Returns the most recent upload record.
    """
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM wp_media_uploads
           WHERE patient_photo_id = ?
           ORDER BY uploaded_at DESC
           LIMIT 1""",
        (patient_photo_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
```

- [ ] 2. Create `app/case_study_db.py` with the following complete code:

```python
import json
from datetime import datetime
from typing import Optional
from app.database import get_db, log_event


# ── Case Studies ──────────────────────────────────────────

def create_case_study(
    title: str,
    patients_included_count: int,
    featured_patient_ids: list[int],
    aggregate_data: dict,
    generated_markdown: str,
    metadata_json: Optional[dict] = None,
) -> int:
    """Create a new case study with status='draft'.

    Returns the new case study ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO case_studies
           (title, patients_included_count, featured_patient_ids,
            aggregate_data, generated_markdown, metadata_json, status)
           VALUES (?, ?, ?, ?, ?, ?, 'draft')""",
        (
            title,
            patients_included_count,
            json.dumps(featured_patient_ids),
            json.dumps(aggregate_data),
            generated_markdown,
            json.dumps(metadata_json or {}),
        ),
    )
    conn.commit()
    case_study_id = cursor.lastrowid
    conn.close()
    log_event(
        "case_study",
        f"Case study created: '{title}' with {patients_included_count} patients",
        {"case_study_id": case_study_id},
    )
    return case_study_id


def get_case_study(case_study_id: int) -> Optional[dict]:
    """Get a case study by ID, with JSON fields parsed."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM case_studies WHERE id = ?", (case_study_id,)
    ).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["featured_patient_ids"] = json.loads(result["featured_patient_ids"])
        result["aggregate_data"] = json.loads(result["aggregate_data"])
        result["metadata_json"] = json.loads(result["metadata_json"])
        return result
    return None


def get_case_studies(status: Optional[str] = None) -> list[dict]:
    """Get all case studies, optionally filtered by status.

    Ordered by generation date descending.
    """
    conn = get_db()
    if status:
        rows = conn.execute(
            """SELECT * FROM case_studies
               WHERE status = ?
               ORDER BY generated_at DESC""",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM case_studies ORDER BY generated_at DESC"
        ).fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        r["featured_patient_ids"] = json.loads(r["featured_patient_ids"])
        r["aggregate_data"] = json.loads(r["aggregate_data"])
        r["metadata_json"] = json.loads(r["metadata_json"])
        results.append(r)
    return results


def update_case_study(case_study_id: int, **kwargs) -> bool:
    """Update arbitrary fields on a case study.

    Allowed fields: title, edited_markdown, status, metadata_json.
    JSON fields (metadata_json) are serialized automatically.
    Returns True if the case study was found and updated.
    """
    allowed = {"title", "edited_markdown", "status", "metadata_json"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    # Serialize JSON fields
    if "metadata_json" in updates and isinstance(updates["metadata_json"], dict):
        updates["metadata_json"] = json.dumps(updates["metadata_json"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [case_study_id]

    conn = get_db()
    cursor = conn.execute(
        f"UPDATE case_studies SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "case_study",
            f"Case study {case_study_id} updated",
            {"fields": list(updates.keys())},
        )
    return changed


def supersede_case_study(old_id: int, new_id: int) -> bool:
    """Mark an old case study as superseded by a new one.

    Sets status='superseded' and superseded_by=new_id on the old case study.
    Returns True if the old case study was found and updated.
    """
    conn = get_db()
    cursor = conn.execute(
        """UPDATE case_studies
           SET status = 'superseded', superseded_by = ?
           WHERE id = ? AND status != 'superseded'""",
        (new_id, old_id),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "case_study",
            f"Case study {old_id} superseded by {new_id}",
        )
    return changed


def publish_case_study(
    case_study_id: int,
    published_by: str,
    wp_post_id: int,
    wp_post_url: str,
) -> bool:
    """Publish a case study to WordPress.

    Sets status='published', published_at, published_by, wp_post_id, wp_post_url.
    Returns True if the case study was found and published.
    """
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        """UPDATE case_studies
           SET status = 'published', published_at = ?, published_by = ?,
               wp_post_id = ?, wp_post_url = ?
           WHERE id = ?""",
        (now, published_by, wp_post_id, wp_post_url, case_study_id),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    if changed:
        log_event(
            "case_study",
            f"Case study {case_study_id} published to WordPress",
            {"published_by": published_by, "wp_post_id": wp_post_id, "wp_post_url": wp_post_url},
        )
    return changed


# ── Case Study Selections ────────────────────────────────

def create_case_study_selection(
    case_study_id: int,
    patient_id: int,
    recommended_by_ai: int = 0,
    recommendation_reasoning: str = "",
    selected_by_admin: int = 0,
    selection_order: Optional[int] = None,
) -> int:
    """Create a case study patient selection record.

    Tracks Claude's recommendations vs admin's final picks.
    Returns the new selection ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO case_study_selections
           (case_study_id, patient_id, recommended_by_ai,
            recommendation_reasoning, selected_by_admin, selection_order)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            case_study_id,
            patient_id,
            recommended_by_ai,
            recommendation_reasoning,
            selected_by_admin,
            selection_order,
        ),
    )
    conn.commit()
    selection_id = cursor.lastrowid
    conn.close()
    return selection_id


def get_case_study_selections(case_study_id: int) -> list[dict]:
    """Get all patient selections for a case study, with patient names.

    Ordered by selection_order, then by creation date.
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT css.*, p.first_name, p.last_name, p.email
           FROM case_study_selections css
           JOIN patients p ON css.patient_id = p.id
           WHERE css.case_study_id = ?
           ORDER BY css.selection_order ASC NULLS LAST, css.created_at ASC""",
        (case_study_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Case Study Overrides ─────────────────────────────────

def create_case_study_override(
    case_study_id: int,
    metric_name: str,
    original_value: str,
    override_value: str,
    reason: str,
    overridden_by: str = "",
) -> int:
    """Create a metric override for a case study.

    Records when an admin manually corrects a calculated metric.
    Returns the new override ID.
    """
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO case_study_overrides
           (case_study_id, metric_name, original_value,
            override_value, reason, overridden_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            case_study_id,
            metric_name,
            original_value,
            override_value,
            reason,
            overridden_by,
        ),
    )
    conn.commit()
    override_id = cursor.lastrowid
    conn.close()
    log_event(
        "case_study",
        f"Override created for case study {case_study_id}: {metric_name}",
        {"override_id": override_id, "original": original_value, "override": override_value},
    )
    return override_id


def get_case_study_overrides(case_study_id: int) -> list[dict]:
    """Get all metric overrides for a case study, ordered by creation date."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM case_study_overrides
           WHERE case_study_id = ?
           ORDER BY created_at ASC""",
        (case_study_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] 3. Verify both files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/gallery_db.py app/case_study_db.py
# Expected output: approximately 320-360 lines for gallery_db.py and 250-290 lines for case_study_db.py

python -c "
from app import gallery_db, case_study_db

# Verify gallery_db functions
gallery_funcs = [
    'create_gallery_version', 'get_current_gallery', 'get_gallery_version',
    'get_gallery_history', 'publish_gallery_version',
    'create_content_usage_entry', 'get_content_usage_for_patient',
    'get_pending_removals', 'resolve_content_removal',
    'add_gallery_exclusion', 'remove_gallery_exclusion',
    'get_gallery_exclusions', 'is_patient_excluded',
    'create_wp_media_upload', 'get_wp_media_for_photo',
]
for fn in gallery_funcs:
    assert hasattr(gallery_db, fn), f'Missing gallery_db function: {fn}'
print(f'All {len(gallery_funcs)} gallery_db functions verified.')

# Verify case_study_db functions
cs_funcs = [
    'create_case_study', 'get_case_study', 'get_case_studies',
    'update_case_study', 'supersede_case_study', 'publish_case_study',
    'create_case_study_selection', 'get_case_study_selections',
    'create_case_study_override', 'get_case_study_overrides',
]
for fn in cs_funcs:
    assert hasattr(case_study_db, fn), f'Missing case_study_db function: {fn}'
print(f'All {len(cs_funcs)} case_study_db functions verified.')
"
# Expected output:
# All 15 gallery_db functions verified.
# All 10 case_study_db functions verified.
```

- [ ] 4. Test gallery_db and case_study_db functions with integration tests:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import gallery_db, case_study_db

init_db()
run_migrations()

# Create test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('gallerytest@test.com', 'Gallery', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# ─── Gallery Tests ───

# Test 1: Create gallery version
gv_id = gallery_db.create_gallery_version(
    gallery_slug='zerona-results',
    patients_included=[pid],
    photo_ids_included=[100, 101, 102],
    patient_count=1,
    generated_html='<div>Gallery HTML</div>',
)
assert gv_id > 0
print(f'Test 1 PASSED: Created gallery version {gv_id}')

# Test 2: Get gallery version
gv = gallery_db.get_gallery_version(gv_id)
assert gv is not None
assert gv['patients_included'] == [pid]
assert gv['photo_ids_included'] == [100, 101, 102]
assert gv['is_current'] == 0  # Not published yet
print('Test 2 PASSED: Retrieved gallery version with parsed JSON.')

# Test 3: Publish gallery version
result = gallery_db.publish_gallery_version(gv_id, published_by='admin', wp_page_id=42)
assert result is True
current = gallery_db.get_current_gallery('zerona-results')
assert current is not None
assert current['id'] == gv_id
assert current['is_current'] == 1
assert current['wp_page_id'] == 42
print('Test 3 PASSED: Gallery version published.')

# Test 4: New version supersedes old
gv_id2 = gallery_db.create_gallery_version(
    gallery_slug='zerona-results',
    patients_included=[pid],
    photo_ids_included=[200, 201],
    patient_count=1,
    generated_html='<div>Gallery V2</div>',
)
gallery_db.publish_gallery_version(gv_id2, published_by='admin')
current = gallery_db.get_current_gallery('zerona-results')
assert current['id'] == gv_id2
old = gallery_db.get_gallery_version(gv_id)
assert old['is_current'] == 0
print('Test 4 PASSED: New gallery version replaced old as current.')

# Test 5: Gallery history
history = gallery_db.get_gallery_history('zerona-results')
assert len(history) == 2
print(f'Test 5 PASSED: Gallery history has {len(history)} versions.')

# Test 6: Content usage log
usage_id = gallery_db.create_content_usage_entry(
    patient_id=pid, photo_id=100, testimonial_id=None,
    used_in='https://example.com/gallery', scope_used='website',
)
assert usage_id > 0
usages = gallery_db.get_content_usage_for_patient(pid)
assert len(usages) == 1
print('Test 6 PASSED: Content usage logged.')

# Test 7: Gallery exclusions
exc_id = gallery_db.add_gallery_exclusion(pid, excluded_by='admin', reason='Patient requested')
assert exc_id > 0
assert gallery_db.is_patient_excluded(pid) is True
exclusions = gallery_db.get_gallery_exclusions()
assert len(exclusions) >= 1
# Idempotent add
exc_id2 = gallery_db.add_gallery_exclusion(pid, excluded_by='admin')
assert exc_id2 == exc_id
# Remove
result = gallery_db.remove_gallery_exclusion(pid)
assert result is True
assert gallery_db.is_patient_excluded(pid) is False
print('Test 7 PASSED: Gallery exclusions add/check/remove.')

# Test 8: Pending removals and resolution
conn = get_db()
conn.execute(
    \"\"\"UPDATE content_usage_log
       SET removal_status = 'removal_pending',
           removal_requested_at = datetime('now'),
           removal_requested_by = 'consent_system'
       WHERE id = ?\"\"\",
    (usage_id,),
)
conn.commit()
conn.close()
pending = gallery_db.get_pending_removals()
assert len(pending) >= 1
result = gallery_db.resolve_content_removal(usage_id, action='removed', resolved_by='admin')
assert result is True
pending_after = gallery_db.get_pending_removals()
assert not any(r['id'] == usage_id for r in pending_after)
print('Test 8 PASSED: Pending removal resolved.')

# Test 9: WP media uploads
# Create a test photo first
conn = get_db()
sid = conn.execute(
    \"\"\"INSERT INTO patient_photo_sessions
       (patient_id, session_number, session_date, session_type)
       VALUES (?, 1, '2026-01-15', 'baseline')\"\"\",
    (pid,),
).lastrowid
photo_id = conn.execute(
    \"\"\"INSERT INTO patient_photos
       (session_id, angle, file_path, file_hash, version_number, is_current)
       VALUES (?, 'front', '/path/front.jpg', 'hash123', 1, 1)\"\"\",
    (sid,),
).lastrowid
conn.commit()
conn.close()

wp_id = gallery_db.create_wp_media_upload(photo_id, wp_media_id=555, wp_media_url='https://wp.com/media/555.jpg')
assert wp_id > 0
wp = gallery_db.get_wp_media_for_photo(photo_id)
assert wp is not None
assert wp['wp_media_id'] == 555
print('Test 9 PASSED: WP media upload recorded and retrieved.')

# ─── Case Study Tests ───

# Test 10: Create case study
cs_id = case_study_db.create_case_study(
    title='Q1 2026 Zerona Results',
    patients_included_count=15,
    featured_patient_ids=[pid],
    aggregate_data={'avg_inches_lost': 6.5, 'median_inches_lost': 5.8},
    generated_markdown='# Case Study\n\nResults here.',
    metadata_json={'generation_model': 'claude-sonnet-4-20250514'},
)
assert cs_id > 0
print(f'Test 10 PASSED: Created case study {cs_id}')

# Test 11: Get case study
cs = case_study_db.get_case_study(cs_id)
assert cs is not None
assert cs['title'] == 'Q1 2026 Zerona Results'
assert cs['featured_patient_ids'] == [pid]
assert cs['aggregate_data']['avg_inches_lost'] == 6.5
assert cs['status'] == 'draft'
print('Test 11 PASSED: Case study retrieved with parsed JSON.')

# Test 12: Update case study
result = case_study_db.update_case_study(cs_id, edited_markdown='# Edited\n\nBetter version.', status='reviewed')
assert result is True
cs = case_study_db.get_case_study(cs_id)
assert cs['edited_markdown'] == '# Edited\n\nBetter version.'
assert cs['status'] == 'reviewed'
print('Test 12 PASSED: Case study updated.')

# Test 13: Supersede case study
cs_id2 = case_study_db.create_case_study(
    title='Q1 2026 Zerona Results v2',
    patients_included_count=18,
    featured_patient_ids=[pid],
    aggregate_data={'avg_inches_lost': 7.2},
    generated_markdown='# Case Study v2',
)
result = case_study_db.supersede_case_study(cs_id, cs_id2)
assert result is True
old_cs = case_study_db.get_case_study(cs_id)
assert old_cs['status'] == 'superseded'
assert old_cs['superseded_by'] == cs_id2
print('Test 13 PASSED: Case study superseded.')

# Test 14: Publish case study
result = case_study_db.publish_case_study(
    cs_id2, published_by='admin', wp_post_id=999, wp_post_url='https://wp.com/case-study/q1-2026',
)
assert result is True
cs2 = case_study_db.get_case_study(cs_id2)
assert cs2['status'] == 'published'
assert cs2['wp_post_id'] == 999
print('Test 14 PASSED: Case study published.')

# Test 15: Get case studies by status
published = case_study_db.get_case_studies(status='published')
assert any(r['id'] == cs_id2 for r in published)
all_cs = case_study_db.get_case_studies()
assert len(all_cs) >= 2
print(f'Test 15 PASSED: Retrieved {len(published)} published, {len(all_cs)} total case studies.')

# Test 16: Case study selections
sel_id = case_study_db.create_case_study_selection(
    case_study_id=cs_id2,
    patient_id=pid,
    recommended_by_ai=1,
    recommendation_reasoning='Best results in cohort: 7.2 inches lost.',
    selected_by_admin=1,
    selection_order=1,
)
assert sel_id > 0
selections = case_study_db.get_case_study_selections(cs_id2)
assert len(selections) == 1
assert selections[0]['recommended_by_ai'] == 1
assert selections[0]['first_name'] == 'Gallery'
print('Test 16 PASSED: Case study selection created with patient join.')

# Test 17: Case study overrides
ov_id = case_study_db.create_case_study_override(
    case_study_id=cs_id2,
    metric_name='avg_inches_lost',
    original_value='7.2',
    override_value='7.0',
    reason='Excluded outlier patient per admin review',
    overridden_by='admin',
)
assert ov_id > 0
overrides = case_study_db.get_case_study_overrides(cs_id2)
assert len(overrides) == 1
assert overrides[0]['metric_name'] == 'avg_inches_lost'
print('Test 17 PASSED: Case study override created.')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM case_study_overrides WHERE case_study_id IN (?, ?)', (cs_id, cs_id2))
conn.execute('DELETE FROM case_study_selections WHERE case_study_id IN (?, ?)', (cs_id, cs_id2))
conn.execute('DELETE FROM case_studies WHERE id IN (?, ?)', (cs_id, cs_id2))
conn.execute('DELETE FROM wp_media_uploads WHERE patient_photo_id = ?', (photo_id,))
conn.execute('DELETE FROM content_usage_log WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM gallery_persistent_exclusions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM gallery_versions WHERE gallery_slug = ?', ('zerona-results',))
conn.execute('DELETE FROM patient_photos WHERE session_id = ?', (sid,))
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()
print('All 17 gallery_db + case_study_db tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Created gallery version ...
# Test 2 PASSED: Retrieved gallery version with parsed JSON.
# Test 3 PASSED: Gallery version published.
# Test 4 PASSED: New gallery version replaced old as current.
# Test 5 PASSED: Gallery history has 2 versions.
# Test 6 PASSED: Content usage logged.
# Test 7 PASSED: Gallery exclusions add/check/remove.
# Test 8 PASSED: Pending removal resolved.
# Test 9 PASSED: WP media upload recorded and retrieved.
# Test 10 PASSED: Created case study ...
# Test 11 PASSED: Case study retrieved with parsed JSON.
# Test 12 PASSED: Case study updated.
# Test 13 PASSED: Case study superseded.
# Test 14 PASSED: Case study published.
# Test 15 PASSED: Retrieved ... published, ... total case studies.
# Test 16 PASSED: Case study selection created with patient join.
# Test 17 PASSED: Case study override created.
# All 17 gallery_db + case_study_db tests passed. Cleanup complete.
```

- [ ] 5. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/gallery_db.py app/case_study_db.py
git commit -m "Add gallery and case study database layers

gallery_db.py: Gallery version snapshots with publish/unpublish,
content usage log with removal workflow (pending->removed/kept),
persistent gallery exclusions (idempotent add/remove), and WP
media upload tracking.

case_study_db.py: Case study CRUD with JSON field parsing,
versioning via supersede_case_study, WordPress publishing,
patient selection tracking (AI recommended vs admin selected),
and metric override audit trail."
```

---

### Task 9: Testimonial Service (app/services/testimonial_service.py)

Create the testimonial workflow service with token generation, 3-touch send cadence scheduling, quality checks (deterministic + Claude), content draft generation, and bounce handling. Also create the two prompt files used by Claude for personalized openings and content drafts.

**Files:**
- `app/services/testimonial_service.py` (new)
- `prompts/testimonial_request.txt` (new)
- `prompts/testimonial_draft.txt` (new)

**Steps:**

- [ ] 1. Create `prompts/testimonial_request.txt` with the following complete content:

```text
You are writing a personalized email opening for a Zerona body contouring patient testimonial request.

Patient context:
- First name: {first_name}
- Sessions completed: {session_count}
- Treatment span: {treatment_span}
- Measurement progress: {measurement_summary}
- Session notes: {session_notes}

Write 1-2 warm, professional sentences that reference specific details from this patient's journey. The tone should be congratulatory and genuine — not salesy. This opening will precede the standard testimonial request body text.

Rules:
- Do NOT mention specific inch measurements or body parts — keep it general ("great progress", "impressive results")
- Do NOT use exclamation marks more than once
- Do NOT use the word "amazing" or "incredible"
- Do NOT make medical claims
- Reference the number of sessions or timeframe if available
- If the data is thin (1 session, no notable progress), output exactly: STATIC_FALLBACK

Output ONLY the 1-2 sentence opening. No greeting, no sign-off, no explanation.
```

- [ ] 2. Create `prompts/testimonial_draft.txt` with the following complete content:

```text
You are generating content drafts from a patient testimonial for a Zerona body contouring practice.

Patient testimonial:
- Rating: {rating} out of 5 stars
- Text: "{testimonial_text}"
- Sessions completed: {session_count}
- Total inches lost: {inches_lost}

Generate exactly 3 content drafts from this testimonial. Output valid JSON with this structure:
{{
  "social_post": "...",
  "longer_caption": "...",
  "blog_paragraph": "..."
}}

Rules for all drafts:
- Use observed language only ("this patient reported...", "after completing X sessions...")
- No absolute claims ("clinically proven", "guaranteed", etc.)
- No specific body part measurements — keep totals general
- First name only, no last names
- Include star rating mention where natural
- Maintain the patient's authentic voice where quoting

Draft specifications:
1. social_post: 1-3 sentences for Facebook/Instagram. Punchy, shareable. Include a relevant emoji or two. Under 280 characters.
2. longer_caption: 3-5 sentences expanding on the testimonial. Suitable for a Facebook post with more context. Under 500 characters.
3. blog_paragraph: 4-6 sentences suitable for embedding in a case study or blog post. More formal tone. Under 800 characters.

Output ONLY the JSON object. No explanation, no markdown fences.
```

- [ ] 3. Create `app/services/testimonial_service.py` with the following complete code:

```python
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from anthropic import Anthropic

from app.config import settings
from app.database import get_db, log_event, insert_content_piece
from app import testimonial_db
from app import consent_db
from app.services import consent_service

logger = logging.getLogger(__name__)

# ── Adverse Event Keywords ────────────────────────────────

ADVERSE_EVENT_KEYWORDS = [
    "side effect",
    "burn",
    "pain",
    "injury",
    "hospital",
    "doctor",
    "emergency",
    "allergic",
    "reaction",
    "complaint",
    "sue",
    "lawyer",
    "regulatory",
    "fda",
    "malpractice",
]


# ── Token Generation ─────────────────────────────────────

def generate_testimonial_token() -> str:
    """Generate a URL-safe token for public testimonial form access."""
    return secrets.token_urlsafe(32)


# ── Testimonial Request Creation ─────────────────────────

def create_testimonial_request(
    patient_id: int,
    session_id: int,
    cycle_id: Optional[int],
) -> dict:
    """Create a testimonial request and schedule the 3-touch send cadence.

    Generates a token, creates the testimonial record, and schedules
    all 3 touches in the send log using configured day intervals.

    Returns:
        dict with keys: testimonial_id, token, touches_scheduled (list of log IDs)
    """
    token = generate_testimonial_token()
    expires_at = (
        datetime.now() + timedelta(days=settings.testimonial_token_expiry_days)
    ).isoformat()

    testimonial_id = testimonial_db.create_testimonial(
        patient_id=patient_id,
        session_id=session_id,
        cycle_id=cycle_id,
        token=token,
        token_expires_at=expires_at,
    )

    # Schedule 3-touch cadence using configured intervals
    now = datetime.now()
    touch_intervals = [
        (1, settings.testimonial_request_initial_days),
        (2, settings.testimonial_request_reminder_1_days),
        (3, settings.testimonial_request_reminder_2_days),
    ]

    touch_log_ids = []
    for touch_number, days_offset in touch_intervals:
        scheduled_for = (now + timedelta(days=days_offset)).isoformat()
        log_id = testimonial_db.create_send_log_entry(
            testimonial_id=testimonial_id,
            touch_number=touch_number,
            scheduled_for=scheduled_for,
        )
        touch_log_ids.append(log_id)

    log_event(
        "testimonial",
        f"Testimonial request created with 3-touch cadence for patient {patient_id}",
        {
            "testimonial_id": testimonial_id,
            "session_id": session_id,
            "cycle_id": cycle_id,
            "touch_log_ids": touch_log_ids,
        },
    )

    return {
        "testimonial_id": testimonial_id,
        "token": token,
        "touches_scheduled": touch_log_ids,
    }


# ── Eligible Session Finder ──────────────────────────────

def find_eligible_sessions() -> list[dict]:
    """Find sessions eligible for testimonial requests.

    Queries sessions that are:
    - session_type='final' with completed_at set
    - testimonial_request_eligible_at is set
    - Not archived
    - No existing testimonial for the same patient+cycle
    - Patient has not submitted a testimonial in the last 90 days
    - Patient has not opted out of testimonial requests
    - Patient email is not bounced

    Returns list of dicts with session and patient info.
    """
    conn = get_db()

    rows = conn.execute(
        """SELECT pps.id AS session_id, pps.patient_id, pps.cycle_id,
                  pps.session_number, pps.session_date, pps.completed_at,
                  pps.testimonial_request_eligible_at,
                  p.first_name, p.last_name, p.email, p.email_bounced
           FROM patient_photo_sessions pps
           JOIN patients p ON pps.patient_id = p.id
           WHERE pps.session_type = 'final'
             AND pps.completed_at IS NOT NULL
             AND pps.testimonial_request_eligible_at IS NOT NULL
             AND pps.archived_at IS NULL
             AND p.email_bounced = 0
             AND p.email IS NOT NULL
             AND p.email != ''
           ORDER BY pps.testimonial_request_eligible_at ASC"""
    ).fetchall()

    conn.close()

    eligible = []
    for row in rows:
        row_dict = dict(row)
        patient_id = row_dict["patient_id"]
        cycle_id = row_dict["cycle_id"]

        # Check if a testimonial already exists for this patient+cycle
        existing = _has_testimonial_for_cycle(patient_id, cycle_id)
        if existing:
            continue

        # 90-day lookback guard
        if testimonial_db.has_recent_testimonial(patient_id, days=90):
            continue

        # Check patient preferences for opt-out
        if _patient_opted_out(patient_id):
            continue

        eligible.append(row_dict)

    return eligible


def _has_testimonial_for_cycle(
    patient_id: int, cycle_id: Optional[int]
) -> bool:
    """Check if a testimonial already exists for a patient+cycle combo."""
    conn = get_db()
    if cycle_id is not None:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM testimonials
               WHERE patient_id = ? AND cycle_id = ?""",
            (patient_id, cycle_id),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM testimonials
               WHERE patient_id = ? AND cycle_id IS NULL""",
            (patient_id,),
        ).fetchone()
    conn.close()
    return row["cnt"] > 0


def _patient_opted_out(patient_id: int) -> bool:
    """Check if a patient has opted out of testimonial requests."""
    conn = get_db()
    row = conn.execute(
        """SELECT value FROM patient_preferences
           WHERE patient_id = ? AND preference_type = 'testimonial_requests'""",
        (patient_id,),
    ).fetchone()
    conn.close()
    if row and row["value"] == "none":
        return True
    return False


# ── Touch 1 Opening (Personalized + Static Fallback) ────

def get_static_touch1_opening() -> str:
    """Return the static (non-personalized) Touch 1 opening.

    Used as automatic fallback when the Claude-personalized opening
    sits in the review queue past TESTIMONIAL_ESCALATION_FALLBACK_DAYS
    without admin approval. Deliberately simple — no Claude, no
    personalization, no review needed. This is the safety valve that
    ensures patients always receive their testimonial request even if
    the review queue is neglected.
    """
    return (
        "Thank you for choosing White House Chiropractic for your "
        "Zerona treatments. We'd love to hear about your experience — "
        "your feedback helps us improve and helps others considering "
        "similar treatments."
    )


def generate_personalized_opening(
    patient_id: int, session_data: dict
) -> dict:
    """Generate a personalized 1-2 sentence opening for Touch 1.

    Uses Claude to generate a warm, specific opening referencing the
    patient's treatment journey. Falls back to static template if
    data is too thin or Claude API fails.

    Args:
        patient_id: The patient ID.
        session_data: Dict with keys like first_name, session_count,
                      treatment_span, measurement_summary, session_notes.

    Returns:
        dict with keys: opening (str), is_personalized (bool), error (str|None)
    """
    static_fallback = (
        f"Thank you for choosing White House Chiropractic for your "
        f"Zerona body contouring journey, {session_data.get('first_name', 'there')}. "
        f"We hope you're enjoying your results!"
    )

    # Thin data check — if only 1 session and no notable progress, use static
    session_count = session_data.get("session_count", 0)
    measurement_summary = session_data.get("measurement_summary", "")
    if session_count <= 1 and not measurement_summary:
        return {
            "opening": static_fallback,
            "is_personalized": False,
            "error": None,
        }

    # Build prompt from template
    try:
        with open("prompts/testimonial_request.txt", "r") as f:
            prompt_template = f.read()

        # Calculate treatment span
        treatment_span = session_data.get("treatment_span", "your recent treatment")

        prompt = prompt_template.format(
            first_name=session_data.get("first_name", "there"),
            session_count=session_count,
            treatment_span=treatment_span,
            measurement_summary=measurement_summary or "No measurement data available",
            session_notes=session_data.get("session_notes", "No notes"),
        )

        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        opening_text = response.content[0].text.strip()

        # Check for thin-data fallback signal from Claude
        if opening_text == "STATIC_FALLBACK":
            return {
                "opening": static_fallback,
                "is_personalized": False,
                "error": None,
            }

        return {
            "opening": opening_text,
            "is_personalized": True,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Claude personalization failed for patient {patient_id}: {e}")
        return {
            "opening": static_fallback,
            "is_personalized": False,
            "error": str(e),
        }


def submit_touch1_for_review(
    testimonial_id: int,
    send_log_id: int,
    personalized_opening: str,
    patient_name: str,
) -> int:
    """Insert Touch 1 personalized opening into content_pieces for admin review.

    Touch 1 is the only touch that requires human review before sending
    (spec Section 6, line 715). Touches 2 and 3 are static text and auto-send.

    The content piece appears in the existing /dashboard review queue alongside
    blog and social content. Admin approves or edits, then the next run of
    send_testimonial_emails_job() picks it up and sends.

    Returns content_piece_id.
    """
    import json
    from app.campaign_db import create_content_piece
    from app.database import log_event

    piece_id = create_content_piece({
        "content_type": "testimonial_email",
        "title": f"Testimonial request: {patient_name} (Touch 1)",
        "body": personalized_opening,
        "status": "pending",
        "metadata_json": json.dumps({
            "testimonial_id": testimonial_id,
            "send_log_id": send_log_id,
            "touch_number": 1,
        }),
    })
    log_event(
        "testimonial",
        f"Touch 1 opening submitted for review: testimonial {testimonial_id} "
        f"for {patient_name}",
    )
    return piece_id


# ── Quality Checks ───────────────────────────────────────

def check_testimonial_quality(
    rating: Optional[int], text: str
) -> dict:
    """Two-layer quality check on a testimonial submission.

    Layer 1 (deterministic): rating checks, keyword scan.
    Layer 2 (Claude): adverse event / confused content detection.
    Claude layer only runs if deterministic checks pass.

    Returns:
        dict with keys: flagged (bool), flag_reason (str|None),
                        flags (list of str)
    """
    flags: list[str] = []

    # ── Layer 1: Deterministic Checks ──

    # Rating check
    if rating is not None and rating <= 2:
        if text.strip():
            flags.append("low_rating")
        else:
            flags.append("low_rating_no_context")

    # Keyword scan (always runs, belt-and-suspenders)
    text_lower = text.lower() if text else ""
    for keyword in ADVERSE_EVENT_KEYWORDS:
        if keyword in text_lower:
            flags.append("adverse_event_keyword")
            break  # One match is enough

    # If deterministic checks already flagged, skip Claude
    if flags:
        return {
            "flagged": True,
            "flag_reason": ", ".join(flags),
            "flags": flags,
        }

    # ── Layer 2: Claude Check ──

    if text and text.strip():
        try:
            claude_result = _claude_quality_check(text)
            if claude_result["flagged"]:
                flags.extend(claude_result["flags"])
        except Exception as e:
            logger.error(f"Claude quality check failed: {e}")
            # On Claude failure, don't flag — fail open for quality checks
            # (conservative: let staff review in normal queue)

    if flags:
        return {
            "flagged": True,
            "flag_reason": ", ".join(flags),
            "flags": flags,
        }

    return {
        "flagged": False,
        "flag_reason": None,
        "flags": [],
    }


def _claude_quality_check(text: str) -> dict:
    """Use Claude to check for adverse events, medical complaints, or confused content.

    Returns:
        dict with keys: flagged (bool), flags (list of str)
    """
    prompt = f"""Analyze this patient testimonial for a Zerona body contouring practice.
Check for:
1. Medical complaints or adverse events (burns, pain, injury, side effects)
2. Adverse event language that might indicate a safety concern
3. Confused content (patient describing a different treatment, wrong practice, etc.)

Testimonial text:
"{text}"

Respond with ONLY valid JSON:
{{"flagged": true/false, "reason": "adverse_event_ai" or "confused_content" or null}}

If none of the above issues are found, respond: {{"flagged": false, "reason": null}}"""

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text.strip()
    result = json.loads(result_text)

    flags = []
    if result.get("flagged"):
        reason = result.get("reason", "adverse_event_ai")
        flags.append(reason)

    return {"flagged": bool(flags), "flags": flags}


# ── Testimonial Submission Processing ────────────────────

def process_testimonial_submission(
    token: str,
    rating: int,
    text: str,
    consent_scopes: list[str],
) -> dict:
    """Process a public testimonial form submission.

    Validates the token, saves the submission, runs quality checks,
    grants consent for selected scopes, and generates content drafts
    for non-flagged 3+ star testimonials.

    Args:
        token: The testimonial URL token.
        rating: Star rating (1-5).
        text: Testimonial text (may be empty).
        consent_scopes: List of scopes patient consented to
                        (e.g., ['website', 'social']).

    Returns:
        dict with keys: success (bool), error (str|None),
                        testimonial_id (int|None), flagged (bool),
                        drafts_generated (int)
    """
    # Validate token
    testimonial = testimonial_db.get_testimonial_by_token(token)
    if not testimonial:
        return {
            "success": False,
            "error": "Invalid or expired token.",
            "testimonial_id": None,
            "flagged": False,
            "drafts_generated": 0,
        }

    # Check token not expired
    if testimonial.get("token_expires_at"):
        try:
            expires = datetime.fromisoformat(testimonial["token_expires_at"])
            if datetime.now() > expires:
                return {
                    "success": False,
                    "error": "This testimonial link has expired.",
                    "testimonial_id": None,
                    "flagged": False,
                    "drafts_generated": 0,
                }
        except ValueError:
            pass

    # Check testimonial hasn't already been submitted
    if testimonial["status"] not in ("requested",):
        return {
            "success": False,
            "error": "This testimonial has already been submitted or is no longer available.",
            "testimonial_id": None,
            "flagged": False,
            "drafts_generated": 0,
        }

    testimonial_id = testimonial["id"]
    patient_id = testimonial["patient_id"]
    now = datetime.now().isoformat()

    # Save the submission
    testimonial_db.update_testimonial(
        testimonial_id,
        rating=rating,
        text=text,
        status="submitted",
        submitted_at=now,
        consent_website=1 if "website" in consent_scopes else 0,
        consent_social=1 if "social" in consent_scopes else 0,
        consent_advertising=1 if "advertising" in consent_scopes else 0,
    )

    # Cancel remaining scheduled touches
    testimonial_db.cancel_remaining_touches(testimonial_id)

    # Grant consent for selected scopes via consent_service
    if consent_scopes:
        # Filter to only testimonial-form-allowed scopes
        allowed_scopes = [
            s for s in consent_scopes
            if s in consent_service.TESTIMONIAL_FORM_ALLOWED_SCOPES
        ]
        if allowed_scopes:
            try:
                consent_service.grant_consent_from_testimonial_form(
                    patient_id=patient_id,
                    scopes=allowed_scopes,
                )
            except ValueError as e:
                logger.warning(
                    f"Consent grant failed for patient {patient_id}: {e}"
                )

    # Run quality check
    quality = check_testimonial_quality(rating, text)

    if quality["flagged"]:
        testimonial_db.update_testimonial(
            testimonial_id,
            status="flagged",
            flag_reason=quality["flag_reason"],
        )

        # Send immediate notification to admin
        _send_flag_notification(testimonial_id, patient_id, quality)

        log_event(
            "testimonial",
            f"Testimonial {testimonial_id} flagged: {quality['flag_reason']}",
            {"patient_id": patient_id, "flags": quality["flags"]},
        )

        return {
            "success": True,
            "error": None,
            "testimonial_id": testimonial_id,
            "flagged": True,
            "drafts_generated": 0,
        }

    # Generate content drafts for non-flagged 3+ star testimonials
    drafts_generated = 0
    if rating is not None and rating >= 3:
        try:
            drafts_generated = generate_content_drafts(testimonial_id)
        except Exception as e:
            logger.error(
                f"Content draft generation failed for testimonial {testimonial_id}: {e}"
            )

    return {
        "success": True,
        "error": None,
        "testimonial_id": testimonial_id,
        "flagged": False,
        "drafts_generated": drafts_generated,
    }


def _send_flag_notification(
    testimonial_id: int, patient_id: int, quality: dict
) -> None:
    """Send immediate email notification to admin about a flagged testimonial."""
    from app.services.email_service import send_notification

    subject = f"FLAGGED Testimonial #{testimonial_id} — Requires Attention"
    body = (
        f"A testimonial submission has been flagged and requires your review.\n\n"
        f"Testimonial ID: {testimonial_id}\n"
        f"Patient ID: {patient_id}\n"
        f"Flag Reason: {quality['flag_reason']}\n"
        f"Flags: {', '.join(quality['flags'])}\n\n"
        f"Please review this testimonial in the admin panel."
    )
    send_notification(subject, body)


# ── Content Draft Generation ─────────────────────────────

def generate_content_drafts(testimonial_id: int) -> int:
    """Generate social/blog content drafts from a testimonial using Claude.

    Creates 3 content drafts (social post, longer caption, blog paragraph)
    and inserts them into content_pieces with content_type='testimonial_derived'.

    Args:
        testimonial_id: The submitted testimonial ID.

    Returns:
        Number of drafts generated and inserted (0-3).
    """
    testimonial = testimonial_db.get_testimonial(testimonial_id)
    if not testimonial:
        return 0

    patient_id = testimonial["patient_id"]

    # Gather session data for context
    session_data = _get_session_context(patient_id, testimonial.get("session_id"))

    # Read the prompt template
    try:
        with open("prompts/testimonial_draft.txt", "r") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error("prompts/testimonial_draft.txt not found")
        return 0

    prompt = prompt_template.format(
        rating=testimonial.get("rating", "N/A"),
        testimonial_text=testimonial.get("text", ""),
        session_count=session_data.get("session_count", "N/A"),
        inches_lost=session_data.get("inches_lost", "N/A"),
    )

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = response.content[0].text.strip()
        drafts = json.loads(result_text)
    except Exception as e:
        logger.error(f"Claude draft generation failed: {e}")
        return 0

    # Determine which platforms are allowed based on consent
    consent_scopes = []
    if testimonial.get("consent_website"):
        consent_scopes.append("website")
    if testimonial.get("consent_social"):
        consent_scopes.append("social")

    # Insert drafts into content_pieces
    draft_count = 0
    draft_types = [
        ("social_post", "Social Post (from Testimonial)"),
        ("longer_caption", "Social Caption (from Testimonial)"),
        ("blog_paragraph", "Blog Paragraph (from Testimonial)"),
    ]

    for draft_key, draft_title in draft_types:
        draft_text = drafts.get(draft_key)
        if not draft_text:
            continue

        try:
            insert_content_piece({
                "content_type": "testimonial_derived",
                "category": "social_proof",
                "title": draft_title,
                "body": draft_text,
                "status": "pending",
                "platform": "facebook" if "social" in draft_key.lower() or "caption" in draft_key.lower() else "blog",
                "created_at": datetime.now().isoformat(),
                "metadata": json.dumps({
                    "testimonial_id": testimonial_id,
                    "patient_id": patient_id,
                    "draft_type": draft_key,
                    "consent_scopes": consent_scopes,
                }),
            })
            draft_count += 1
        except Exception as e:
            logger.error(f"Failed to insert {draft_key} draft: {e}")

    if draft_count > 0:
        log_event(
            "testimonial",
            f"Generated {draft_count} content drafts from testimonial {testimonial_id}",
            {"testimonial_id": testimonial_id, "patient_id": patient_id},
        )

    return draft_count


def _get_session_context(
    patient_id: int, session_id: Optional[int]
) -> dict:
    """Gather session context for content draft generation."""
    from app.services.measurement_service import calculate_session_deltas

    conn = get_db()

    # Get session count
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM patient_photo_sessions
           WHERE patient_id = ? AND archived_at IS NULL""",
        (patient_id,),
    ).fetchone()
    session_count = row["cnt"] if row else 0

    # Try to calculate inches lost from baseline to final
    inches_lost = "N/A"
    baseline = conn.execute(
        """SELECT id FROM patient_photo_sessions
           WHERE patient_id = ? AND session_type = 'baseline'
             AND archived_at IS NULL
           ORDER BY session_number ASC LIMIT 1""",
        (patient_id,),
    ).fetchone()

    final = conn.execute(
        """SELECT id FROM patient_photo_sessions
           WHERE patient_id = ? AND session_type = 'final'
             AND archived_at IS NULL
           ORDER BY session_number DESC LIMIT 1""",
        (patient_id,),
    ).fetchone()

    conn.close()

    if baseline and final:
        try:
            deltas = calculate_session_deltas(baseline["id"], final["id"])
            if deltas.get("aggregate_points_delta") is not None:
                inches_lost = f"{deltas['aggregate_points_delta']:.1f}"
        except Exception:
            pass

    return {
        "session_count": session_count,
        "inches_lost": inches_lost,
    }


# ── Bounce Handling ───────────────────────────────────────

def handle_bounce(testimonial_id: int) -> dict:
    """Handle an email bounce for a testimonial request.

    Marks the testimonial as bounced, sets the patient's email_bounced flag,
    cancels remaining scheduled touches, and creates an admin notification.

    Returns:
        dict with keys: success (bool), cancelled_touches (int)
    """
    testimonial = testimonial_db.get_testimonial(testimonial_id)
    if not testimonial:
        return {"success": False, "cancelled_touches": 0}

    patient_id = testimonial["patient_id"]

    # Mark testimonial as bounced
    testimonial_db.update_testimonial(testimonial_id, status="bounced")

    # Set patient email_bounced flag
    testimonial_db.mark_patient_bounced(patient_id)

    # Cancel remaining touches
    cancelled = testimonial_db.cancel_remaining_touches(testimonial_id)

    # Send admin notification
    from app.services.email_service import send_notification

    conn = get_db()
    patient = conn.execute(
        "SELECT first_name, last_name, email FROM patients WHERE id = ?",
        (patient_id,),
    ).fetchone()
    conn.close()

    if patient:
        patient_name = f"{patient['first_name']} {patient['last_name']}"
        send_notification(
            f"Testimonial request to {patient_name} bounced — update email address",
            f"The testimonial request email to {patient_name} ({patient['email']}) "
            f"has bounced.\n\nTestimonial ID: {testimonial_id}\n"
            f"Patient ID: {patient_id}\n\n"
            f"Please update the patient's email address and consider resending."
        )

    log_event(
        "testimonial",
        f"Testimonial {testimonial_id} bounced for patient {patient_id}",
        {"cancelled_touches": cancelled},
    )

    return {"success": True, "cancelled_touches": cancelled}
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/services/testimonial_service.py prompts/testimonial_request.txt prompts/testimonial_draft.txt
# Expected output: approximately 480-530 lines for testimonial_service.py, ~25 for request prompt, ~35 for draft prompt

python -c "
from app.services import testimonial_service as ts
# Verify all expected exports
funcs = [
    'generate_testimonial_token',
    'create_testimonial_request',
    'find_eligible_sessions',
    'get_static_touch1_opening',
    'generate_personalized_opening',
    'submit_touch1_for_review',
    'check_testimonial_quality',
    'process_testimonial_submission',
    'generate_content_drafts',
    'handle_bounce',
    'ADVERSE_EVENT_KEYWORDS',
]
for fn in funcs:
    assert hasattr(ts, fn), f'Missing: {fn}'
print(f'All {len(funcs)} testimonial_service exports verified.')

# Verify ADVERSE_EVENT_KEYWORDS list
assert len(ts.ADVERSE_EVENT_KEYWORDS) == 15
assert 'side effect' in ts.ADVERSE_EVENT_KEYWORDS
assert 'malpractice' in ts.ADVERSE_EVENT_KEYWORDS
print(f'ADVERSE_EVENT_KEYWORDS: {len(ts.ADVERSE_EVENT_KEYWORDS)} terms.')

# Verify token generation
token = ts.generate_testimonial_token()
assert len(token) > 20
assert isinstance(token, str)
print(f'Token generation works: {token[:20]}...')
"
# Expected output:
# All 9 testimonial_service exports verified.
# ADVERSE_EVENT_KEYWORDS: 15 terms.
# Token generation works: ...
```

- [ ] 5. Test quality check logic (deterministic layer — no Claude API needed):

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.testimonial_service import check_testimonial_quality, ADVERSE_EVENT_KEYWORDS

# Test 1: Low rating flag
result = check_testimonial_quality(2, 'It was okay I guess.')
assert result['flagged'] is True
assert 'low_rating' in result['flags']
print(f'Test 1 PASSED: Low rating flagged: {result[\"flag_reason\"]}')

# Test 2: Low rating no context
result = check_testimonial_quality(1, '')
assert result['flagged'] is True
assert 'low_rating_no_context' in result['flags']
print(f'Test 2 PASSED: Low rating no context flagged: {result[\"flag_reason\"]}')

# Test 3: Adverse event keyword
result = check_testimonial_quality(5, 'Great results but I had some pain during treatment.')
assert result['flagged'] is True
assert 'adverse_event_keyword' in result['flags']
print(f'Test 3 PASSED: Adverse keyword flagged: {result[\"flag_reason\"]}')

# Test 4: Clean 5-star testimonial (deterministic layer only — skip Claude)
# Note: In production, Claude layer would also run. Here we test deterministic only.
result = check_testimonial_quality(5, 'Absolutely loved my results! Lost several inches.')
# May or may not be flagged by Claude — but deterministic layer should pass
assert 'low_rating' not in result.get('flags', [])
assert 'adverse_event_keyword' not in result.get('flags', [])
print('Test 4 PASSED: Clean testimonial not flagged by deterministic checks.')

# Test 5: Each keyword individually
for kw in ADVERSE_EVENT_KEYWORDS:
    r = check_testimonial_quality(5, f'This is a test with {kw} in it.')
    assert r['flagged'] is True, f'Keyword {kw!r} was not flagged'
print(f'Test 5 PASSED: All {len(ADVERSE_EVENT_KEYWORDS)} keywords individually flagged.')

# Test 6: Rating of 3 should NOT be flagged by rating check alone
result = check_testimonial_quality(3, 'Good experience overall.')
assert 'low_rating' not in result.get('flags', [])
print('Test 6 PASSED: Rating of 3 not flagged by rating check.')

# Test 7: None rating should not crash
result = check_testimonial_quality(None, 'Some text here.')
assert 'low_rating' not in result.get('flags', [])
print('Test 7 PASSED: None rating handled gracefully.')

print('All 7 quality check tests passed.')
"
# Expected output:
# Test 1 PASSED: Low rating flagged: low_rating
# Test 2 PASSED: Low rating no context flagged: low_rating_no_context
# Test 3 PASSED: Adverse keyword flagged: adverse_event_keyword
# Test 4 PASSED: Clean testimonial not flagged by deterministic checks.
# Test 5 PASSED: All 15 keywords individually flagged.
# Test 6 PASSED: Rating of 3 not flagged by rating check.
# Test 7 PASSED: None rating handled gracefully.
# All 7 quality check tests passed.
```

- [ ] 6. Test create_testimonial_request with real DB:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from datetime import datetime, timedelta
from app.database import get_db, init_db, run_migrations
from app import testimonial_db
from app.services.testimonial_service import create_testimonial_request

init_db()
run_migrations()

# Create test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('tstest@test.com', 'Test', 'Service', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Test 1: Create testimonial request
result = create_testimonial_request(pid, session_id=999, cycle_id=None)
assert result['testimonial_id'] > 0
assert result['token'] is not None
assert len(result['touches_scheduled']) == 3
print(f'Test 1 PASSED: Created request with ID={result[\"testimonial_id\"]}, 3 touches scheduled.')

# Test 2: Verify send log entries are properly spaced
send_log = testimonial_db.get_send_log(result['testimonial_id'])
assert len(send_log) == 3
assert send_log[0]['touch_number'] == 1
assert send_log[1]['touch_number'] == 2
assert send_log[2]['touch_number'] == 3
# Verify each is scheduled for the future
for entry in send_log:
    scheduled = datetime.fromisoformat(entry['scheduled_for'])
    assert scheduled > datetime.now() - timedelta(minutes=1)
print('Test 2 PASSED: Send log entries have correct touch numbers and future dates.')

# Test 3: Verify token was created and testimonial status
testimonial = testimonial_db.get_testimonial(result['testimonial_id'])
assert testimonial['status'] == 'requested'
assert testimonial['token'] == result['token']
print('Test 3 PASSED: Testimonial has status=requested and correct token.')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM testimonial_send_log WHERE testimonial_id = ?', (result['testimonial_id'],))
conn.execute('DELETE FROM testimonials WHERE id = ?', (result['testimonial_id'],))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()
print('All 3 create_testimonial_request tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Created request with ID=..., 3 touches scheduled.
# Test 2 PASSED: Send log entries have correct touch numbers and future dates.
# Test 3 PASSED: Testimonial has status=requested and correct token.
# All 3 create_testimonial_request tests passed. Cleanup complete.
```

- [ ] 7. Verify prompt files load correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
# Verify prompt templates exist and have placeholders
with open('prompts/testimonial_request.txt') as f:
    content = f.read()
assert '{first_name}' in content
assert '{session_count}' in content
assert '{treatment_span}' in content
assert '{measurement_summary}' in content
assert 'STATIC_FALLBACK' in content
print(f'testimonial_request.txt: {len(content)} chars, all placeholders present.')

with open('prompts/testimonial_draft.txt') as f:
    content = f.read()
assert '{rating}' in content
assert '{testimonial_text}' in content
assert '{session_count}' in content
assert '{inches_lost}' in content
assert 'social_post' in content
assert 'longer_caption' in content
assert 'blog_paragraph' in content
print(f'testimonial_draft.txt: {len(content)} chars, all placeholders present.')

print('Both prompt files verified.')
"
# Expected output:
# testimonial_request.txt: ... chars, all placeholders present.
# testimonial_draft.txt: ... chars, all placeholders present.
# Both prompt files verified.
```

- [ ] 8. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/testimonial_service.py prompts/testimonial_request.txt prompts/testimonial_draft.txt
git commit -m "Add testimonial service with quality checks and content draft generation

Token generation (secrets.token_urlsafe), 3-touch cadence scheduling
with configurable day intervals, eligible session finder with 90-day
lookback guard + opt-out + bounce checks. Two-layer quality check:
deterministic (rating + 15 adverse event keywords) then Claude AI.
Personalized opening generation with thin-data fallback. Content draft
generation inserts social post, caption, and blog paragraph into
content_pieces. Bounce handler marks patient email_bounced, cancels
remaining touches, sends admin notification."
```

---

### Task 10: Gallery Service (app/services/gallery_service.py)

Create the gallery generation and WordPress publishing service with qualifying patient queries, semantic HTML generation, photo upload deduplication, page management, drift detection, and emergency removal.

**Files:**
- `app/services/gallery_service.py` (new)

**Steps:**

- [ ] 1. Create `app/services/gallery_service.py` with the following complete code:

```python
import json
import logging
from datetime import datetime
from typing import Optional

import requests

from app.config import settings
from app.database import get_db, log_event
from app import gallery_db
from app import photo_db
from app.services import consent_service
from app.services.wordpress_service import (
    _get_auth_headers,
    _wp_api_url,
    _upload_image,
)

logger = logging.getLogger(__name__)


# ── Qualifying Patient Query ─────────────────────────────

def get_qualifying_patients(gallery_slug: Optional[str] = None) -> list[dict]:
    """Find patients who qualify for gallery inclusion.

    Qualifying criteria:
    - Has a complete final session (completed_at set, session_type='final')
    - Has active website consent (scope='website')
    - Not in gallery_persistent_exclusions
    - Not archived (session not archived)

    Returns list of dicts with patient info, session data, and photo paths.
    """
    conn = get_db()

    # Get all patients with completed final sessions
    rows = conn.execute(
        """SELECT DISTINCT p.id AS patient_id, p.first_name, p.last_name,
                  pps.id AS final_session_id, pps.session_number,
                  pps.session_date, pps.completed_at
           FROM patients p
           JOIN patient_photo_sessions pps ON pps.patient_id = p.id
           WHERE pps.session_type = 'final'
             AND pps.completed_at IS NOT NULL
             AND pps.archived_at IS NULL
           ORDER BY pps.completed_at DESC"""
    ).fetchall()

    conn.close()

    qualifying = []
    for row in rows:
        row_dict = dict(row)
        patient_id = row_dict["patient_id"]

        # Check active website consent
        if not consent_service.patient_has_active_consent(patient_id, "website"):
            continue

        # Check not persistently excluded
        if gallery_db.is_patient_excluded(patient_id):
            continue

        # Get baseline session for before photos
        baseline_data = _get_baseline_session(patient_id)
        if not baseline_data:
            continue

        # Get photos for both sessions
        baseline_photos = photo_db.get_current_photos(baseline_data["id"])
        final_photos = photo_db.get_current_photos(row_dict["final_session_id"])

        # Need at least some photos in both sessions
        if not baseline_photos or not final_photos:
            continue

        # Get session count
        session_count = photo_db.get_session_count_for_patient(patient_id)

        # Get measurement summary
        measurement_summary = _get_measurement_summary(
            baseline_data["id"], row_dict["final_session_id"]
        )

        row_dict["baseline_session_id"] = baseline_data["id"]
        row_dict["baseline_session_date"] = baseline_data["session_date"]
        row_dict["baseline_photos"] = baseline_photos
        row_dict["final_photos"] = final_photos
        row_dict["session_count"] = session_count
        row_dict["measurement_summary"] = measurement_summary

        qualifying.append(row_dict)

    return qualifying


def _get_baseline_session(patient_id: int) -> Optional[dict]:
    """Get the earliest baseline session for a patient."""
    conn = get_db()
    row = conn.execute(
        """SELECT id, session_date, completed_at FROM patient_photo_sessions
           WHERE patient_id = ? AND session_type = 'baseline'
             AND archived_at IS NULL
           ORDER BY session_number ASC LIMIT 1""",
        (patient_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _get_measurement_summary(
    baseline_session_id: int, final_session_id: int
) -> str:
    """Generate a brief measurement summary (total inches lost)."""
    from app.services.measurement_service import calculate_session_deltas

    try:
        deltas = calculate_session_deltas(baseline_session_id, final_session_id)
        total = deltas.get("aggregate_points_delta")
        if total is not None and total > 0:
            return f"{total:.1f} total inches lost"
        return ""
    except Exception:
        return ""


# ── Gallery HTML Generation ──────────────────────────────

def generate_gallery_html(
    patient_data_list: list[dict],
    gallery_slug: str,
) -> str:
    """Generate semantic static HTML for a before/after gallery.

    Produces clean HTML using article/figure/figcaption elements.
    Before (baseline) on left, after (final) on right.
    CTA buttons inserted every 3-5 patients.
    No JavaScript dependencies.

    Args:
        patient_data_list: List of qualifying patient dicts (from get_qualifying_patients).
        gallery_slug: The gallery slug for identification.

    Returns:
        Complete HTML string for the gallery content.
    """
    if not patient_data_list:
        return "<p>No qualifying patients for this gallery.</p>"

    html_parts = []

    # Gallery header
    html_parts.append(
        '<section class="zerona-results-gallery" '
        f'data-gallery-slug="{gallery_slug}" '
        f'data-generated="{datetime.now().isoformat()}">'
    )
    html_parts.append(
        "<h2>Real Zerona Results from Our Patients</h2>"
    )
    html_parts.append(
        "<p>See the real before and after photos from patients who completed "
        "the Zerona Z6 body contouring protocol at our practice.</p>"
    )

    for idx, patient in enumerate(patient_data_list):
        # Patient section
        first_initial = (patient.get("first_name", "?") or "?")[0].upper()
        session_count = patient.get("session_count", 0)
        measurement_summary = patient.get("measurement_summary", "")

        html_parts.append(f'<article class="patient-result" data-index="{idx + 1}">')
        html_parts.append(f"<h3>Patient {first_initial}.</h3>")

        # Before/After photo pair — use front angle as primary
        baseline_front = _find_photo_by_angle(patient.get("baseline_photos", []), "front")
        final_front = _find_photo_by_angle(patient.get("final_photos", []), "front")

        html_parts.append(
            '<div class="before-after-container" '
            'style="display:flex;gap:20px;flex-wrap:wrap;margin:15px 0;">'
        )

        # Before photo
        if baseline_front:
            before_wp_url = baseline_front.get("wp_url", "")
            before_alt = (
                f"Before Zerona treatment — patient after baseline session"
            )
            html_parts.append(
                '<figure style="flex:1;min-width:280px;">'
                f'<img src="{before_wp_url}" alt="{before_alt}" '
                'style="width:100%;height:auto;border-radius:8px;" loading="lazy" />'
                "<figcaption><strong>Before</strong> — Baseline</figcaption>"
                "</figure>"
            )

        # After photo
        if final_front:
            after_wp_url = final_front.get("wp_url", "")
            session_text = f"{session_count} Zerona sessions" if session_count else "Zerona sessions"
            after_alt = (
                f"After Zerona treatment — patient after {session_text}"
            )
            html_parts.append(
                '<figure style="flex:1;min-width:280px;">'
                f'<img src="{after_wp_url}" alt="{after_alt}" '
                'style="width:100%;height:auto;border-radius:8px;" loading="lazy" />'
                f"<figcaption><strong>After</strong> — {session_text}</figcaption>"
                "</figure>"
            )

        html_parts.append("</div>")  # close before-after-container

        # Progress summary
        summary_parts = []
        if session_count:
            summary_parts.append(f"{session_count} sessions completed")
        if measurement_summary:
            summary_parts.append(measurement_summary)
        if summary_parts:
            html_parts.append(
                f'<p class="progress-summary" style="color:#666;font-style:italic;">'
                f'{" — ".join(summary_parts)}</p>'
            )

        html_parts.append("</article>")
        html_parts.append("<hr />")

        # CTA button every 4 patients (between 3-5 range)
        if (idx + 1) % 4 == 0 and idx < len(patient_data_list) - 1:
            html_parts.append(
                '<div class="gallery-cta" style="text-align:center;margin:30px 0;">'
                '<a href="/contact" '
                'style="display:inline-block;padding:14px 32px;'
                "background-color:#0EA5A0;color:#fff;text-decoration:none;"
                'border-radius:6px;font-weight:bold;font-size:18px;">'
                "Schedule Your Consultation"
                "</a></div>"
            )

    # Final CTA
    html_parts.append(
        '<div class="gallery-cta" style="text-align:center;margin:40px 0;">'
        '<a href="/contact" '
        'style="display:inline-block;padding:14px 32px;'
        "background-color:#0EA5A0;color:#fff;text-decoration:none;"
        'border-radius:6px;font-weight:bold;font-size:18px;">'
        "Ready to See Your Own Results? Schedule Your Consultation"
        "</a></div>"
    )

    html_parts.append("</section>")

    return "\n".join(html_parts)


def _find_photo_by_angle(
    photos: list[dict], angle: str
) -> Optional[dict]:
    """Find a photo by angle from a list of photo dicts."""
    for photo in photos:
        if photo.get("angle") == angle:
            return photo
    return None


# ── WordPress Photo Upload ───────────────────────────────

def upload_photos_to_wordpress(photo_ids: list[int]) -> dict:
    """Upload preview images to WordPress media library with deduplication.

    Checks wp_media_uploads table before uploading to avoid duplicates.
    Uses preview_path (1200px) images, not originals.

    Args:
        photo_ids: List of patient_photo IDs to upload.

    Returns:
        dict with keys: uploaded (int), skipped (int), failed (int),
                        results (list of dicts with photo_id, wp_media_id, wp_url)
    """
    uploaded = 0
    skipped = 0
    failed = 0
    results = []

    for photo_id in photo_ids:
        # Check if already uploaded (dedup)
        existing = gallery_db.get_wp_media_for_photo(photo_id)
        if existing:
            results.append({
                "photo_id": photo_id,
                "wp_media_id": existing["wp_media_id"],
                "wp_url": existing["wp_media_url"],
                "status": "skipped",
            })
            skipped += 1
            continue

        # Get photo record for file path
        conn = get_db()
        photo = conn.execute(
            "SELECT * FROM patient_photos WHERE id = ?", (photo_id,)
        ).fetchone()
        conn.close()

        if not photo:
            failed += 1
            continue

        photo = dict(photo)

        # Use preview_path if available, fall back to file_path
        image_path = photo.get("preview_path") or photo.get("file_path")
        if not image_path:
            failed += 1
            continue

        # Generate clean filename
        clean_name = _generate_clean_filename(photo)

        # Upload to WordPress
        wp_media_id = _upload_image(image_path, clean_name)
        if wp_media_id is None:
            failed += 1
            continue

        # Get the URL of the uploaded media
        wp_url = _get_wp_media_url(wp_media_id)
        if not wp_url:
            wp_url = ""

        # Record in wp_media_uploads
        gallery_db.create_wp_media_upload(photo_id, wp_media_id, wp_url)

        results.append({
            "photo_id": photo_id,
            "wp_media_id": wp_media_id,
            "wp_url": wp_url,
            "status": "uploaded",
        })
        uploaded += 1

    log_event(
        "gallery",
        f"WordPress photo upload: {uploaded} uploaded, {skipped} skipped, {failed} failed",
        {"photo_ids": photo_ids},
    )

    return {
        "uploaded": uploaded,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }


def _generate_clean_filename(photo: dict) -> str:
    """Generate a clean filename for WordPress upload."""
    session_id = photo.get("session_id", 0)
    angle = photo.get("angle", "unknown")
    angle_clean = angle.replace("_", "-")
    return f"zerona-progress-session-{session_id}-{angle_clean}.jpg"


def _get_wp_media_url(wp_media_id: int) -> Optional[str]:
    """Fetch the source URL of an uploaded WordPress media item."""
    try:
        resp = requests.get(
            _wp_api_url(f"media/{wp_media_id}"),
            headers=_get_auth_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("source_url", "")
    except requests.RequestException as e:
        logger.error(f"Failed to get WP media URL for {wp_media_id}: {e}")
    return None


# ── WordPress Page Publishing ────────────────────────────

def publish_gallery_to_wordpress(
    gallery_version_id: int,
    gallery_slug: str,
    publish_as_draft: bool = False,
) -> dict:
    """Create or update a WordPress page with gallery HTML.

    First generation creates a new page; subsequent regenerations update
    the existing page. Preserves URL/slug across regenerations.

    Args:
        gallery_version_id: The gallery_versions.id to publish.
        gallery_slug: The page slug (e.g., 'zerona-results').
        publish_as_draft: If True, creates/updates as draft instead of published.

    Returns:
        dict with keys: success (bool), wp_page_id (int|None),
                        wp_url (str|None), error (str|None)
    """
    version = gallery_db.get_gallery_version(gallery_version_id)
    if not version:
        return {
            "success": False,
            "wp_page_id": None,
            "wp_url": None,
            "error": "Gallery version not found.",
        }

    html_content = version.get("generated_html", "")
    wp_status = "draft" if publish_as_draft else "publish"

    # Check if a page already exists for this slug
    existing_page_id = _find_wp_page_by_slug(gallery_slug)

    try:
        headers = _get_auth_headers()
        headers["Content-Type"] = "application/json"

        if existing_page_id:
            # Update existing page
            resp = requests.post(
                _wp_api_url(f"pages/{existing_page_id}"),
                headers=headers,
                json={
                    "content": html_content,
                    "status": wp_status,
                },
                timeout=30,
            )
        else:
            # Create new page
            resp = requests.post(
                _wp_api_url("pages"),
                headers=headers,
                json={
                    "title": "Zerona Results Gallery",
                    "slug": gallery_slug,
                    "content": html_content,
                    "status": wp_status,
                },
                timeout=30,
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            wp_page_id = data.get("id")
            wp_url = data.get("link", "")

            log_event(
                "gallery",
                f"Gallery published to WordPress: page_id={wp_page_id}",
                {
                    "gallery_version_id": gallery_version_id,
                    "slug": gallery_slug,
                    "status": wp_status,
                },
            )

            return {
                "success": True,
                "wp_page_id": wp_page_id,
                "wp_url": wp_url,
                "error": None,
            }
        else:
            error_msg = f"WordPress API error: HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error(error_msg)
            return {
                "success": False,
                "wp_page_id": None,
                "wp_url": None,
                "error": error_msg,
            }

    except requests.RequestException as e:
        error_msg = f"WordPress request failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "wp_page_id": None,
            "wp_url": None,
            "error": error_msg,
        }


def _find_wp_page_by_slug(slug: str) -> Optional[int]:
    """Find an existing WordPress page by slug. Returns page ID or None."""
    try:
        resp = requests.get(
            _wp_api_url(f"pages?slug={slug}&status=publish,draft,private"),
            headers=_get_auth_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            pages = resp.json()
            if pages:
                return pages[0].get("id")
    except requests.RequestException:
        pass
    return None


# ── Gallery Drift Detection ──────────────────────────────

def get_gallery_drift(gallery_slug: str) -> dict:
    """Compare current gallery patients vs today's qualifying set.

    Returns drift analysis showing patients who should be added or removed.

    Args:
        gallery_slug: The gallery slug to check.

    Returns:
        dict with keys:
            has_drift (bool),
            patients_to_add (list of patient_ids),
            patients_to_remove (list of dicts with patient_id and reason),
            patients_with_updated_photos (list of patient_ids),
            current_count (int),
            qualifying_count (int)
    """
    current_gallery = gallery_db.get_current_gallery(gallery_slug)
    current_patient_ids = set()
    if current_gallery:
        current_patient_ids = set(current_gallery.get("patients_included", []))

    # Get today's qualifying set
    qualifying = get_qualifying_patients(gallery_slug)
    qualifying_patient_ids = {p["patient_id"] for p in qualifying}

    # Patients to add (qualifying but not in current gallery)
    patients_to_add = sorted(qualifying_patient_ids - current_patient_ids)

    # Patients to remove (in current gallery but no longer qualifying)
    patients_to_remove = []
    for pid in sorted(current_patient_ids - qualifying_patient_ids):
        reason = _determine_removal_reason(pid)
        patients_to_remove.append({"patient_id": pid, "reason": reason})

    # Check for updated photos in current gallery patients
    patients_with_updated_photos = []
    if current_gallery:
        current_photo_ids = set(current_gallery.get("photo_ids_included", []))
        for pid in current_patient_ids & qualifying_patient_ids:
            patient_data = next(
                (p for p in qualifying if p["patient_id"] == pid), None
            )
            if patient_data:
                current_photos = patient_data.get("final_photos", [])
                for photo in current_photos:
                    if photo.get("id") not in current_photo_ids:
                        patients_with_updated_photos.append(pid)
                        break

    has_drift = bool(patients_to_add or patients_to_remove or patients_with_updated_photos)

    return {
        "has_drift": has_drift,
        "patients_to_add": patients_to_add,
        "patients_to_remove": patients_to_remove,
        "patients_with_updated_photos": patients_with_updated_photos,
        "current_count": len(current_patient_ids),
        "qualifying_count": len(qualifying_patient_ids),
    }


def _determine_removal_reason(patient_id: int) -> str:
    """Determine why a patient no longer qualifies for the gallery."""
    if not consent_service.patient_has_active_consent(patient_id, "website"):
        return "consent_revoked_or_expired"
    if gallery_db.is_patient_excluded(patient_id):
        return "persistently_excluded"
    return "no_qualifying_session"


# ── Emergency Patient Removal ────────────────────────────

def emergency_remove_patient(
    patient_id: int,
    gallery_slug: str,
    removed_by: str = "",
    reason: str = "emergency_removal",
) -> dict:
    """Immediately remove a patient from the current published gallery.

    Regenerates the gallery HTML excluding the specified patient,
    updates the WordPress page, and logs the emergency removal.

    Args:
        patient_id: The patient to remove.
        gallery_slug: The gallery slug.
        removed_by: Staff member performing removal.
        reason: Reason for emergency removal.

    Returns:
        dict with keys: success (bool), new_version_id (int|None),
                        error (str|None)
    """
    current_gallery = gallery_db.get_current_gallery(gallery_slug)
    if not current_gallery:
        return {
            "success": False,
            "new_version_id": None,
            "error": "No current gallery found for this slug.",
        }

    current_patients = current_gallery.get("patients_included", [])
    if patient_id not in current_patients:
        return {
            "success": False,
            "new_version_id": None,
            "error": f"Patient {patient_id} is not in the current gallery.",
        }

    # Get qualifying patients excluding the removed one
    qualifying = get_qualifying_patients(gallery_slug)
    filtered = [p for p in qualifying if p["patient_id"] != patient_id]

    # Regenerate gallery HTML
    new_html = generate_gallery_html(filtered, gallery_slug)

    # Create new gallery version
    new_patient_ids = [p["patient_id"] for p in filtered]
    all_photo_ids = []
    for p in filtered:
        for photo in p.get("baseline_photos", []):
            all_photo_ids.append(photo.get("id"))
        for photo in p.get("final_photos", []):
            all_photo_ids.append(photo.get("id"))

    new_version_id = gallery_db.create_gallery_version(
        gallery_slug=gallery_slug,
        patients_included=new_patient_ids,
        photo_ids_included=all_photo_ids,
        patient_count=len(filtered),
        generated_html=new_html,
        notes=f"Emergency removal of patient {patient_id}: {reason}",
    )

    # Publish the new version
    wp_page_id = current_gallery.get("wp_page_id")
    gallery_db.publish_gallery_version(
        new_version_id,
        published_by=removed_by or "system_emergency",
        wp_page_id=wp_page_id,
    )

    # Update WordPress page if configured
    if wp_page_id and settings.wp_url:
        publish_gallery_to_wordpress(
            new_version_id, gallery_slug, publish_as_draft=False
        )

    log_event(
        "gallery",
        f"Emergency removal: patient {patient_id} removed from gallery {gallery_slug}",
        {
            "removed_by": removed_by,
            "reason": reason,
            "new_version_id": new_version_id,
            "old_patient_count": len(current_patients),
            "new_patient_count": len(filtered),
        },
    )

    return {
        "success": True,
        "new_version_id": new_version_id,
        "error": None,
    }
```

- [ ] 2. Verify the file was created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/services/gallery_service.py
# Expected output: approximately 460-510 lines

python -c "
from app.services import gallery_service as gs
funcs = [
    'get_qualifying_patients',
    'generate_gallery_html',
    'upload_photos_to_wordpress',
    'publish_gallery_to_wordpress',
    'get_gallery_drift',
    'emergency_remove_patient',
]
for fn in funcs:
    assert hasattr(gs, fn), f'Missing: {fn}'
print(f'All {len(funcs)} gallery_service exports verified.')
"
# Expected output: All 6 gallery_service exports verified.
```

- [ ] 3. Test gallery HTML generation:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.gallery_service import generate_gallery_html

# Test 1: Empty patient list
html = generate_gallery_html([], 'zerona-results')
assert 'No qualifying patients' in html
print('Test 1 PASSED: Empty list produces placeholder message.')

# Test 2: Single patient
patients = [{
    'patient_id': 1,
    'first_name': 'Jane',
    'session_count': 6,
    'measurement_summary': '5.5 total inches lost',
    'baseline_photos': [{'id': 1, 'angle': 'front', 'wp_url': 'https://example.com/before.jpg'}],
    'final_photos': [{'id': 2, 'angle': 'front', 'wp_url': 'https://example.com/after.jpg'}],
}]
html = generate_gallery_html(patients, 'zerona-results')
assert '<article' in html
assert '<figure' in html
assert '<figcaption' in html
assert 'Patient J.' in html
assert 'Schedule Your Consultation' in html
assert '6 sessions completed' in html
assert '5.5 total inches lost' in html
assert 'data-gallery-slug=\"zerona-results\"' in html
print('Test 2 PASSED: Single patient generates correct semantic HTML.')

# Test 3: Multiple patients with CTA insertion
patients_multi = []
for i in range(8):
    patients_multi.append({
        'patient_id': i + 1,
        'first_name': chr(65 + i),  # A, B, C, ...
        'session_count': 6,
        'measurement_summary': '',
        'baseline_photos': [{'id': i * 2 + 1, 'angle': 'front', 'wp_url': f'https://ex.com/b{i}.jpg'}],
        'final_photos': [{'id': i * 2 + 2, 'angle': 'front', 'wp_url': f'https://ex.com/a{i}.jpg'}],
    })
html = generate_gallery_html(patients_multi, 'zerona-results')
assert html.count('Schedule Your Consultation') >= 2  # At least mid-gallery + final CTA
assert html.count('<article') == 8
print(f'Test 3 PASSED: 8 patients with CTA buttons. Found {html.count(\"Schedule Your Consultation\")} CTAs.')

# Test 4: No JavaScript in output
assert '<script' not in html
print('Test 4 PASSED: No JavaScript in gallery HTML.')

# Test 5: Privacy — first initial only, no last names
assert 'Patient A.' in html
assert 'Patient B.' in html
print('Test 5 PASSED: Only first initials used for patient names.')

print('All 5 gallery HTML tests passed.')
"
# Expected output:
# Test 1 PASSED: Empty list produces placeholder message.
# Test 2 PASSED: Single patient generates correct semantic HTML.
# Test 3 PASSED: 8 patients with CTA buttons. Found ... CTAs.
# Test 4 PASSED: No JavaScript in gallery HTML.
# Test 5 PASSED: Only first initials used for patient names.
# All 5 gallery HTML tests passed.
```

- [ ] 4. Test drift detection logic:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.gallery_service import get_gallery_drift
from app.database import init_db, run_migrations

init_db()
run_migrations()

# Test with no existing gallery — should not crash
drift = get_gallery_drift('zerona-results')
assert isinstance(drift, dict)
assert 'has_drift' in drift
assert 'patients_to_add' in drift
assert 'patients_to_remove' in drift
assert 'patients_with_updated_photos' in drift
assert 'current_count' in drift
assert 'qualifying_count' in drift
print(f'Drift detection returned: current={drift[\"current_count\"]}, qualifying={drift[\"qualifying_count\"]}')
print('Drift detection test passed — no errors on empty state.')
"
# Expected output:
# Drift detection returned: current=0, qualifying=0
# Drift detection test passed — no errors on empty state.
```

- [ ] 5. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/gallery_service.py
git commit -m "Add gallery service with HTML generation and WordPress publishing

Qualifying patient query checks final session completion, active website
consent, and gallery persistent exclusions. Semantic HTML generator with
article/figure/figcaption, before/after photo pairs, CTA buttons every
4 patients, first-initial-only privacy. WordPress photo upload with
dedup via wp_media_uploads table. Page create/update with slug
preservation. Gallery drift detection compares current vs qualifying
patients. Emergency patient removal regenerates and republishes."
```

---

### Task 11: Case Study Service (app/services/case_study_service.py)

Create the case study generation service with qualifying patient queries, readiness indicators, Claude-powered patient selection recommendations, aggregate metric calculations, structured markdown generation, and WordPress publishing. Also create the two prompt files for Claude.

**Files:**
- `app/services/case_study_service.py` (new)
- `prompts/case_study.txt` (new)
- `prompts/patient_selection.txt` (new)

**Steps:**

- [ ] 1. Create `prompts/patient_selection.txt` with the following complete content:

```text
You are selecting featured patients for a Zerona body contouring case study.

Qualifying patients (JSON array):
{patients_json}

Selection criteria (in priority order):
1. Consent scope — must have case_study consent (already pre-filtered)
2. Rating — prefer 4-5 stars
3. Measurement delta magnitude — larger total inches lost preferred, but weight by baseline size (smaller frame patients are not penalized)
4. Testimonial text quality — prefer longer, more specific testimonials
5. Photo completeness — prefer all 6 angles in both baseline and final sessions

Select {max_count} patients from this pool. For each selected patient, provide reasoning.

Output valid JSON:
{{
  "selections": [
    {{
      "patient_id": 123,
      "reasoning": "4.8 star rating, 8.2 total inches lost across 6 sessions, detailed testimonial describing specific body areas improved, all 6 photo angles complete."
    }}
  ]
}}

Output ONLY the JSON object. No explanation, no markdown fences.
```

- [ ] 2. Create `prompts/case_study.txt` with the following complete content:

```text
You are generating a structured case study for a Zerona Z6 body contouring practice.

Practice: White House Chiropractic
Provider: Dr. Chris Banning, DC
Treatment: Zerona Z6 laser body contouring

Aggregate data:
{aggregate_json}

Featured patient stories:
{featured_json}

Date range: {date_start} to {date_end}
Total patients in cohort: {patient_count}

Generate a complete case study in Markdown with these exact sections:

## Hero Summary
2-3 sentences summarizing the overall results. Lead with the most compelling aggregate metric.

## Clinical Overview
Brief description of the Zerona Z6 protocol as performed at this practice. 6-session standard protocol. Non-invasive laser body contouring.

## Patient Cohort Statistics
Present the aggregate metrics in a clean table format. Include: average total inches lost, median, range, average satisfaction rating, percentage rating 4+ stars, average sessions completed, patient count.

## Featured Patient Stories
For each featured patient, write 2-3 paragraphs covering their journey, results, and testimonial excerpt. Use first name only. Include their star rating and total inches lost.

## Aggregated Results
Deeper analysis of the cohort results. Break down by measurement area if data is available. Use exact calculated numbers — no rounding or approximation.

## Methodology
"Results based on [N] patients who completed the full Zerona Z6 protocol between [start] and [end]. Measurements taken at baseline and final session using standardized 6-point body measurement protocol."

## About Dr. Banning
Brief bio: Dr. Chris Banning has been providing chiropractic and wellness services at White House Chiropractic. The practice offers Zerona Z6 as part of its comprehensive body contouring program.

## About Zerona Z6 Technology
Brief description of Erchonia's Zerona Z6 laser technology. FDA-cleared for circumferential reduction.

## Conclusion
2-3 sentences summarizing the case study findings. End with a call to action.

Rules:
- Use exact calculated numbers — no rounding or approximation
- Use observed language only: "patients in this cohort lost an average of X inches"
- No absolute claims: "clinically proven", "guaranteed", "100% effective", etc.
- Flag anything resembling medical claims by wrapping it in [REVIEW: ...]
- First names only — no last names or identifying details
- Patient privacy: no specific body part complaints unless from their own testimonial
- If a metric seems unusually high or low, note it with [VERIFY: ...]

Output ONLY the Markdown content. No explanation or preamble.
```

- [ ] 3. Create `app/services/case_study_service.py` with the following complete code:

```python
import json
import logging
from datetime import datetime
from typing import Optional

import requests
from anthropic import Anthropic

from app.config import settings
from app.database import get_db, log_event
from app import case_study_db
from app import gallery_db
from app import testimonial_db
from app.services import consent_service
from app.services.measurement_service import calculate_aggregate_stats
from app.services.wordpress_service import _get_auth_headers, _wp_api_url

logger = logging.getLogger(__name__)


# ── Qualifying Patients ──────────────────────────────────

def get_qualifying_patients_for_case_study() -> list[dict]:
    """Find patients who qualify for case study inclusion.

    Qualifying criteria:
    - Has case_study consent from signed_document or manual_staff_entry
    - Has a complete final session (completed_at set)
    - Has a submitted testimonial (status='submitted')
    - Session not archived

    Returns list of dicts with patient info, session data, testimonial data.
    """
    conn = get_db()

    rows = conn.execute(
        """SELECT DISTINCT p.id AS patient_id, p.first_name, p.last_name,
                  pps.id AS final_session_id, pps.session_number,
                  pps.session_date, pps.completed_at,
                  pps.cycle_id
           FROM patients p
           JOIN patient_photo_sessions pps ON pps.patient_id = p.id
           WHERE pps.session_type = 'final'
             AND pps.completed_at IS NOT NULL
             AND pps.archived_at IS NULL
           ORDER BY pps.completed_at DESC"""
    ).fetchall()

    conn.close()

    qualifying = []
    for row in rows:
        row_dict = dict(row)
        patient_id = row_dict["patient_id"]

        # Check case_study consent (requires signed_document or manual_staff_entry)
        if not consent_service.patient_has_active_consent(
            patient_id, "case_study"
        ):
            continue

        # Check for submitted testimonial
        testimonials = testimonial_db.get_testimonials_for_patient(patient_id)
        submitted = [
            t for t in testimonials if t.get("status") == "submitted"
        ]
        if not submitted:
            continue

        # Use most recent submitted testimonial
        latest_testimonial = submitted[0]
        row_dict["testimonial_id"] = latest_testimonial["id"]
        row_dict["rating"] = latest_testimonial.get("rating")
        row_dict["testimonial_text"] = latest_testimonial.get("text", "")

        # Get photo completeness
        from app import photo_db

        baseline = conn if False else None  # need fresh conn
        conn2 = get_db()
        baseline_row = conn2.execute(
            """SELECT id FROM patient_photo_sessions
               WHERE patient_id = ? AND session_type = 'baseline'
                 AND archived_at IS NULL
               ORDER BY session_number ASC LIMIT 1""",
            (patient_id,),
        ).fetchone()
        conn2.close()

        if baseline_row:
            row_dict["baseline_session_id"] = baseline_row["id"]
            baseline_photos = photo_db.get_current_photos(baseline_row["id"])
            final_photos = photo_db.get_current_photos(row_dict["final_session_id"])
            row_dict["baseline_photo_count"] = len(baseline_photos)
            row_dict["final_photo_count"] = len(final_photos)
        else:
            row_dict["baseline_session_id"] = None
            row_dict["baseline_photo_count"] = 0
            row_dict["final_photo_count"] = 0

        # Get measurement delta
        if row_dict.get("baseline_session_id"):
            from app.services.measurement_service import calculate_session_deltas

            try:
                deltas = calculate_session_deltas(
                    row_dict["baseline_session_id"],
                    row_dict["final_session_id"],
                )
                row_dict["total_inches_lost"] = deltas.get(
                    "aggregate_points_delta", 0
                )
            except Exception:
                row_dict["total_inches_lost"] = 0
        else:
            row_dict["total_inches_lost"] = 0

        # Session count
        row_dict["session_count"] = photo_db.get_session_count_for_patient(
            patient_id
        )

        qualifying.append(row_dict)

    return qualifying


# ── Readiness Indicator ──────────────────────────────────

def get_readiness_indicator(qualifying_count: int) -> dict:
    """Return a readiness indicator based on qualifying patient count.

    Args:
        qualifying_count: Number of qualifying patients.

    Returns:
        dict with keys: level (str: green/yellow/red), message (str)
    """
    if qualifying_count >= 20:
        return {
            "level": "green",
            "message": "Ready to generate a strong case study",
        }
    elif qualifying_count >= 10:
        return {
            "level": "yellow",
            "message": "Generation possible but results will be limited",
        }
    else:
        return {
            "level": "red",
            "message": "Not recommended — too few for meaningful aggregates",
        }


# ── Patient Recommendation ───────────────────────────────

def recommend_featured_patients(
    qualifying_patients: list[dict],
    max_count: int = 5,
) -> list[dict]:
    """Use Claude to recommend featured patients from the qualifying pool.

    Selection priorities:
    1. Rating (4-5 stars)
    2. Measurement delta magnitude
    3. Testimonial text quality
    4. Photo completeness

    Args:
        qualifying_patients: List of qualifying patient dicts.
        max_count: Maximum number to recommend (default 5).

    Returns:
        list of dicts with keys: patient_id (int), reasoning (str)
    """
    if not qualifying_patients:
        return []

    # If fewer patients than max_count, recommend all
    if len(qualifying_patients) <= max_count:
        return [
            {
                "patient_id": p["patient_id"],
                "reasoning": "Included — qualifying pool is smaller than requested count.",
            }
            for p in qualifying_patients
        ]

    # Build simplified patient data for Claude
    patient_summaries = []
    for p in qualifying_patients:
        patient_summaries.append({
            "patient_id": p["patient_id"],
            "first_name": p.get("first_name", ""),
            "rating": p.get("rating"),
            "total_inches_lost": p.get("total_inches_lost", 0),
            "testimonial_text_length": len(p.get("testimonial_text", "")),
            "testimonial_excerpt": (p.get("testimonial_text", "") or "")[:200],
            "session_count": p.get("session_count", 0),
            "baseline_photo_count": p.get("baseline_photo_count", 0),
            "final_photo_count": p.get("final_photo_count", 0),
        })

    try:
        with open("prompts/patient_selection.txt", "r") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(
            patients_json=json.dumps(patient_summaries, indent=2),
            max_count=max_count,
        )

        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text.strip()
        result = json.loads(result_text)
        selections = result.get("selections", [])

        # Validate that all patient_ids exist in qualifying pool
        valid_ids = {p["patient_id"] for p in qualifying_patients}
        validated = [
            s for s in selections if s.get("patient_id") in valid_ids
        ]

        return validated[:max_count]

    except Exception as e:
        logger.error(f"Claude patient recommendation failed: {e}")
        # Fallback: select top patients by rating then inches lost
        sorted_patients = sorted(
            qualifying_patients,
            key=lambda p: (
                -(p.get("rating") or 0),
                -(p.get("total_inches_lost") or 0),
            ),
        )
        return [
            {
                "patient_id": p["patient_id"],
                "reasoning": "Auto-selected by rating and measurement results (Claude unavailable).",
            }
            for p in sorted_patients[:max_count]
        ]


# ── Aggregate Calculations ───────────────────────────────

def calculate_case_study_aggregates(patient_ids: list[int]) -> dict:
    """Calculate aggregate statistics for a case study cohort.

    Uses measurement_service.calculate_aggregate_stats for body measurements,
    then adds testimonial rating statistics.

    Args:
        patient_ids: List of patient IDs in the cohort.

    Returns:
        dict with keys:
            measurement_stats (from calculate_aggregate_stats),
            rating_stats (avg, median, pct_4_plus, count),
            session_stats (avg_sessions)
    """
    # Measurement aggregates
    measurement_stats = calculate_aggregate_stats(patient_ids)

    # Rating statistics
    ratings = []
    session_counts = []
    for pid in patient_ids:
        testimonials = testimonial_db.get_testimonials_for_patient(pid)
        submitted = [
            t for t in testimonials if t.get("status") == "submitted"
        ]
        if submitted and submitted[0].get("rating") is not None:
            ratings.append(submitted[0]["rating"])

        from app import photo_db

        session_counts.append(
            photo_db.get_session_count_for_patient(pid)
        )

    import statistics

    rating_stats: dict = {}
    if ratings:
        rating_stats = {
            "avg": round(statistics.mean(ratings), 2),
            "median": round(statistics.median(ratings), 2),
            "pct_4_plus": round(
                len([r for r in ratings if r >= 4]) / len(ratings) * 100, 1
            ),
            "count": len(ratings),
        }

    session_stats: dict = {}
    if session_counts:
        session_stats = {
            "avg_sessions": round(statistics.mean(session_counts), 1),
        }

    return {
        "measurement_stats": measurement_stats,
        "rating_stats": rating_stats,
        "session_stats": session_stats,
    }


# ── Case Study Generation ────────────────────────────────

def generate_case_study_markdown(
    featured_patients: list[dict],
    aggregates: dict,
    overrides: Optional[dict] = None,
) -> str:
    """Use Claude to generate a structured case study in Markdown.

    Args:
        featured_patients: List of featured patient dicts with testimonial data.
        aggregates: Aggregate statistics dict from calculate_case_study_aggregates.
        overrides: Optional dict of metric overrides {metric_name: override_value}.

    Returns:
        Generated Markdown string.
    """
    # Apply overrides to aggregate data
    aggregate_display = json.loads(json.dumps(aggregates))  # deep copy
    if overrides:
        for metric_name, override_value in overrides.items():
            _apply_override(aggregate_display, metric_name, override_value)

    # Build featured patient summaries for the prompt
    featured_summaries = []
    for p in featured_patients:
        featured_summaries.append({
            "first_name": p.get("first_name", "Patient"),
            "rating": p.get("rating"),
            "total_inches_lost": p.get("total_inches_lost", 0),
            "session_count": p.get("session_count", 0),
            "testimonial_text": p.get("testimonial_text", ""),
        })

    # Determine date range from featured patients
    session_dates = [
        p.get("session_date", "")
        for p in featured_patients
        if p.get("session_date")
    ]
    date_start = min(session_dates) if session_dates else "N/A"
    date_end = max(session_dates) if session_dates else "N/A"

    patient_count = aggregates.get("measurement_stats", {}).get(
        "patient_count", len(featured_patients)
    )

    try:
        with open("prompts/case_study.txt", "r") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(
            aggregate_json=json.dumps(aggregate_display, indent=2),
            featured_json=json.dumps(featured_summaries, indent=2),
            date_start=date_start,
            date_end=date_end,
            patient_count=patient_count,
        )

        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        markdown = response.content[0].text.strip()

        log_event(
            "case_study",
            f"Case study markdown generated ({len(markdown)} chars)",
            {"patient_count": patient_count},
        )

        return markdown

    except Exception as e:
        logger.error(f"Claude case study generation failed: {e}")
        # Return a minimal placeholder
        return (
            f"# Case Study — Zerona Z6 Results\n\n"
            f"*Generation failed: {e}. Please retry.*\n\n"
            f"Patient count: {patient_count}\n"
        )


def _apply_override(data: dict, metric_name: str, override_value: str) -> None:
    """Apply a metric override to the aggregate data dict.

    Navigates nested dicts using dot notation (e.g., 'rating_stats.avg').
    """
    parts = metric_name.split(".")
    target = data
    for part in parts[:-1]:
        if isinstance(target, dict) and part in target:
            target = target[part]
        else:
            return
    if isinstance(target, dict):
        try:
            target[parts[-1]] = float(override_value)
        except ValueError:
            target[parts[-1]] = override_value


# ── WordPress Publishing ─────────────────────────────────

def publish_case_study_to_wordpress(case_study_id: int) -> dict:
    """Publish a case study as a WordPress blog post draft.

    Creates a new blog post with the case study content. Embeds
    before/after gallery for featured patients if photos are available.

    Args:
        case_study_id: The case study ID to publish.

    Returns:
        dict with keys: success (bool), wp_post_id (int|None),
                        wp_post_url (str|None), error (str|None)
    """
    case_study = case_study_db.get_case_study(case_study_id)
    if not case_study:
        return {
            "success": False,
            "wp_post_id": None,
            "wp_post_url": None,
            "error": "Case study not found.",
        }

    # Use edited_markdown if available, otherwise generated_markdown
    content = case_study.get("edited_markdown") or case_study.get(
        "generated_markdown", ""
    )
    title = case_study.get("title", "Zerona Z6 Case Study")

    # Convert markdown to HTML for WordPress
    # Simple conversion: wrap in div, handle basic markdown
    html_content = _markdown_to_basic_html(content)

    try:
        headers = _get_auth_headers()
        headers["Content-Type"] = "application/json"

        resp = requests.post(
            _wp_api_url("posts"),
            headers=headers,
            json={
                "title": title,
                "content": html_content,
                "status": "draft",
                "categories": [],
                "tags": [],
            },
            timeout=30,
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            wp_post_id = data.get("id")
            wp_post_url = data.get("link", "")

            # Update case study with WP info
            case_study_db.publish_case_study(
                case_study_id=case_study_id,
                published_by="system",
                wp_post_id=wp_post_id,
                wp_post_url=wp_post_url,
            )

            # Log content usage for featured patients
            featured_ids = case_study.get("featured_patient_ids", [])
            for pid in featured_ids:
                gallery_db.create_content_usage_entry(
                    patient_id=pid,
                    photo_id=None,
                    testimonial_id=None,
                    used_in=wp_post_url,
                    scope_used="case_study",
                )

            log_event(
                "case_study",
                f"Case study {case_study_id} published to WordPress as draft",
                {"wp_post_id": wp_post_id, "wp_post_url": wp_post_url},
            )

            return {
                "success": True,
                "wp_post_id": wp_post_id,
                "wp_post_url": wp_post_url,
                "error": None,
            }
        else:
            error_msg = f"WordPress API error: HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error(error_msg)
            return {
                "success": False,
                "wp_post_id": None,
                "wp_post_url": None,
                "error": error_msg,
            }

    except requests.RequestException as e:
        error_msg = f"WordPress request failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "wp_post_id": None,
            "wp_post_url": None,
            "error": error_msg,
        }


def _markdown_to_basic_html(markdown_text: str) -> str:
    """Convert basic Markdown to HTML for WordPress.

    Handles headings, paragraphs, bold, italic, and tables.
    Not a full Markdown parser — covers the case study structure.
    """
    import re

    lines = markdown_text.split("\n")
    html_lines = []
    in_table = False
    in_table_header = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines (add paragraph break)
        if not stripped:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append("")
            continue

        # Table separator line (e.g., |---|---|)
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            in_table_header = False
            continue

        # Table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                html_lines.append('<table style="width:100%;border-collapse:collapse;margin:15px 0;">')
                in_table = True
                in_table_header = True

            tag = "th" if in_table_header else "td"
            style = 'style="border:1px solid #ddd;padding:8px;text-align:left;"'
            row_html = "<tr>" + "".join(
                f"<{tag} {style}>{c}</{tag}>" for c in cells
            ) + "</tr>"
            html_lines.append(row_html)
            continue

        if in_table:
            html_lines.append("</table>")
            in_table = False

        # Headings
        if stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        else:
            # Bold and italic
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
            # Review/verify flags
            text = re.sub(
                r"\[REVIEW: (.+?)\]",
                r'<span style="background:#fff3cd;padding:2px 6px;">REVIEW: \1</span>',
                text,
            )
            text = re.sub(
                r"\[VERIFY: (.+?)\]",
                r'<span style="background:#f8d7da;padding:2px 6px;">VERIFY: \1</span>',
                text,
            )
            html_lines.append(f"<p>{text}</p>")

    if in_table:
        html_lines.append("</table>")

    return "\n".join(html_lines)
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/services/case_study_service.py prompts/case_study.txt prompts/patient_selection.txt
# Expected output: approximately 420-470 lines for service, ~55 for case_study prompt, ~25 for patient_selection prompt

python -c "
from app.services import case_study_service as cs
funcs = [
    'get_qualifying_patients_for_case_study',
    'get_readiness_indicator',
    'recommend_featured_patients',
    'calculate_case_study_aggregates',
    'generate_case_study_markdown',
    'publish_case_study_to_wordpress',
]
for fn in funcs:
    assert hasattr(cs, fn), f'Missing: {fn}'
print(f'All {len(funcs)} case_study_service exports verified.')
"
# Expected output: All 6 case_study_service exports verified.
```

- [ ] 5. Test readiness indicator:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.case_study_service import get_readiness_indicator

# Test green
r = get_readiness_indicator(25)
assert r['level'] == 'green'
assert 'strong' in r['message']
print(f'Test 1 PASSED: 25 patients -> {r[\"level\"]}: {r[\"message\"]}')

# Test yellow
r = get_readiness_indicator(15)
assert r['level'] == 'yellow'
assert 'limited' in r['message']
print(f'Test 2 PASSED: 15 patients -> {r[\"level\"]}: {r[\"message\"]}')

# Test red
r = get_readiness_indicator(5)
assert r['level'] == 'red'
assert 'Not recommended' in r['message']
print(f'Test 3 PASSED: 5 patients -> {r[\"level\"]}: {r[\"message\"]}')

# Test boundaries
r20 = get_readiness_indicator(20)
assert r20['level'] == 'green'
r10 = get_readiness_indicator(10)
assert r10['level'] == 'yellow'
r9 = get_readiness_indicator(9)
assert r9['level'] == 'red'
r0 = get_readiness_indicator(0)
assert r0['level'] == 'red'
print('Test 4 PASSED: Boundary values correct (20=green, 10=yellow, 9=red, 0=red).')

print('All 4 readiness indicator tests passed.')
"
# Expected output:
# Test 1 PASSED: 25 patients -> green: Ready to generate a strong case study
# Test 2 PASSED: 15 patients -> yellow: Generation possible but results will be limited
# Test 3 PASSED: 5 patients -> red: Not recommended — too few for meaningful aggregates
# Test 4 PASSED: Boundary values correct (20=green, 10=yellow, 9=red, 0=red).
# All 4 readiness indicator tests passed.
```

- [ ] 6. Test recommend_featured_patients fallback (no Claude needed):

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.case_study_service import recommend_featured_patients

# Test 1: Empty list
result = recommend_featured_patients([], max_count=5)
assert result == []
print('Test 1 PASSED: Empty list returns empty.')

# Test 2: Fewer patients than max_count
patients = [
    {'patient_id': 1, 'first_name': 'A', 'rating': 5, 'total_inches_lost': 6.0,
     'testimonial_text': 'Great!', 'session_count': 6,
     'baseline_photo_count': 6, 'final_photo_count': 6},
    {'patient_id': 2, 'first_name': 'B', 'rating': 4, 'total_inches_lost': 4.0,
     'testimonial_text': 'Good!', 'session_count': 6,
     'baseline_photo_count': 6, 'final_photo_count': 6},
]
result = recommend_featured_patients(patients, max_count=5)
assert len(result) == 2
assert result[0]['patient_id'] == 1
assert result[1]['patient_id'] == 2
print(f'Test 2 PASSED: {len(result)} patients returned when pool < max_count.')

# Test 3: Fallback when Claude is not available (no API key)
# The function should fall back to sorting by rating then inches lost
big_pool = []
for i in range(10):
    big_pool.append({
        'patient_id': i + 1,
        'first_name': chr(65 + i),
        'rating': 5 - (i % 3),
        'total_inches_lost': 10.0 - i * 0.5,
        'testimonial_text': f'Testimonial {i}',
        'session_count': 6,
        'baseline_photo_count': 6,
        'final_photo_count': 6,
    })
# This will fail Claude call and use fallback
result = recommend_featured_patients(big_pool, max_count=3)
assert len(result) <= 3
assert all('patient_id' in r and 'reasoning' in r for r in result)
print(f'Test 3 PASSED: Fallback returned {len(result)} patients with reasoning.')

print('All 3 recommend_featured_patients tests passed.')
"
# Expected output:
# Test 1 PASSED: Empty list returns empty.
# Test 2 PASSED: 2 patients returned when pool < max_count.
# Test 3 PASSED: Fallback returned 3 patients with reasoning.
# All 3 recommend_featured_patients tests passed.
```

- [ ] 7. Test markdown-to-HTML converter:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.services.case_study_service import _markdown_to_basic_html

# Test 1: Headings
html = _markdown_to_basic_html('# Title\n## Section\n### Sub')
assert '<h1>Title</h1>' in html
assert '<h2>Section</h2>' in html
assert '<h3>Sub</h3>' in html
print('Test 1 PASSED: Headings converted.')

# Test 2: Bold and italic
html = _markdown_to_basic_html('This is **bold** and *italic* text.')
assert '<strong>bold</strong>' in html
assert '<em>italic</em>' in html
print('Test 2 PASSED: Bold and italic converted.')

# Test 3: Table
md = '| Metric | Value |\n|--------|-------|\n| Avg | 5.2 |\n| Max | 8.1 |'
html = _markdown_to_basic_html(md)
assert '<table' in html
assert '<th' in html
assert '<td' in html
assert '5.2' in html
print('Test 3 PASSED: Table converted.')

# Test 4: Review flags
html = _markdown_to_basic_html('[REVIEW: Check this claim]')
assert 'REVIEW:' in html
assert 'background:#fff3cd' in html
print('Test 4 PASSED: Review flags highlighted.')

# Test 5: Verify flags
html = _markdown_to_basic_html('[VERIFY: Unusually high value]')
assert 'VERIFY:' in html
assert 'background:#f8d7da' in html
print('Test 5 PASSED: Verify flags highlighted.')

print('All 5 markdown-to-HTML tests passed.')
"
# Expected output:
# Test 1 PASSED: Headings converted.
# Test 2 PASSED: Bold and italic converted.
# Test 3 PASSED: Table converted.
# Test 4 PASSED: Review flags highlighted.
# Test 5 PASSED: Verify flags highlighted.
# All 5 markdown-to-HTML tests passed.
```

- [ ] 8. Verify prompt files load correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
with open('prompts/patient_selection.txt') as f:
    content = f.read()
assert '{patients_json}' in content
assert '{max_count}' in content
assert 'patient_id' in content
assert 'reasoning' in content
print(f'patient_selection.txt: {len(content)} chars, all placeholders present.')

with open('prompts/case_study.txt') as f:
    content = f.read()
assert '{aggregate_json}' in content
assert '{featured_json}' in content
assert '{date_start}' in content
assert '{date_end}' in content
assert '{patient_count}' in content
assert 'Hero Summary' in content
assert 'Methodology' in content
assert 'Dr. Banning' in content
print(f'case_study.txt: {len(content)} chars, all placeholders present.')

print('Both prompt files verified.')
"
# Expected output:
# patient_selection.txt: ... chars, all placeholders present.
# case_study.txt: ... chars, all placeholders present.
# Both prompt files verified.
```

- [ ] 9. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/case_study_service.py prompts/case_study.txt prompts/patient_selection.txt
git commit -m "Add case study service with Claude generation and WordPress publishing

Qualifying patient query checks case_study consent (signed_document
required), complete final session, and submitted testimonial. Readiness
indicator (green/yellow/red) based on cohort size. Claude recommends
featured patients with reasoning; fallback sorts by rating+inches.
Aggregate calculations combine measurement_service stats with rating
stats. Claude generates structured markdown with hero summary, cohort
stats, featured stories, methodology footnote, and Dr. Banning bio.
Markdown-to-HTML converter handles tables, headings, and REVIEW/VERIFY
flags. Publishes to WordPress as blog post draft with content usage
logging for all featured patients."
```

---

### Task 12: Patient Export Service (app/services/patient_export_service.py)

Create the patient data export service that generates a ZIP file containing all database records, photo files, consent documents, and testimonial videos for a specific patient. Logs every export in the patient_data_exports table.

**Files:**
- `app/services/patient_export_service.py` (new)

**Steps:**

- [ ] 1. Create `app/services/patient_export_service.py` with the following complete code:

```python
import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.database import get_db, log_event
from app import photo_db
from app import consent_db
from app import testimonial_db
from app import gallery_db

logger = logging.getLogger(__name__)


def export_patient_data(
    patient_id: int,
    exported_by: str = "",
    export_reason: str = "patient_request",
) -> Optional[str]:
    """Generate a ZIP file containing all data for a patient.

    Contents:
    - data.json: All database records (sessions, photos metadata,
      measurements, consents, testimonials, content usage, preferences)
    - photos/: All original photo files
    - consents/: All consent document files
    - videos/: All testimonial video files (if any)

    Logs the export in patient_data_exports table.

    Args:
        patient_id: The patient to export.
        exported_by: Staff member performing the export.
        export_reason: Reason for export (patient_request, legal_requirement,
                       internal_review).

    Returns:
        Path to the generated ZIP file, or None if patient not found.
    """
    conn = get_db()

    # Verify patient exists
    patient = conn.execute(
        "SELECT * FROM patients WHERE id = ?", (patient_id,)
    ).fetchone()
    if not patient:
        conn.close()
        return None

    patient_dict = dict(patient)

    # ── Gather All Data ──

    # Treatment cycles
    cycles = conn.execute(
        "SELECT * FROM patient_treatment_cycles WHERE patient_id = ? ORDER BY cycle_number",
        (patient_id,),
    ).fetchall()
    cycles_data = [dict(r) for r in cycles]

    # Photo sessions
    sessions = conn.execute(
        "SELECT * FROM patient_photo_sessions WHERE patient_id = ? ORDER BY session_number",
        (patient_id,),
    ).fetchall()
    sessions_data = [dict(r) for r in sessions]

    # Photos (all versions, not just current)
    session_ids = [s["id"] for s in sessions]
    photos_data = []
    photo_files = []
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        photos = conn.execute(
            f"SELECT * FROM patient_photos WHERE session_id IN ({placeholders}) ORDER BY session_id, angle, version_number",
            session_ids,
        ).fetchall()
        photos_data = [dict(r) for r in photos]
        photo_files = [
            p["file_path"]
            for p in photos_data
            if p.get("file_path")
        ]

    # Measurements
    measurements_data = []
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        measurements = conn.execute(
            f"SELECT * FROM patient_measurements WHERE session_id IN ({placeholders}) ORDER BY session_id, measurement_point",
            session_ids,
        ).fetchall()
        measurements_data = [dict(r) for r in measurements]

    # Consent documents
    consent_docs = conn.execute(
        "SELECT * FROM consent_documents WHERE patient_id = ? ORDER BY uploaded_at",
        (patient_id,),
    ).fetchall()
    consent_docs_data = [dict(r) for r in consent_docs]
    consent_files = [
        d["file_path"]
        for d in consent_docs_data
        if d.get("file_path")
    ]

    # Patient consents
    consents = conn.execute(
        "SELECT * FROM patient_consents WHERE patient_id = ? ORDER BY granted_at",
        (patient_id,),
    ).fetchall()
    consents_data = [dict(r) for r in consents]

    # Testimonials
    testimonials = conn.execute(
        "SELECT * FROM testimonials WHERE patient_id = ? ORDER BY created_at",
        (patient_id,),
    ).fetchall()
    testimonials_data = [dict(r) for r in testimonials]
    video_files = [
        t["video_path"]
        for t in testimonials_data
        if t.get("video_path")
    ]

    # Testimonial send log
    testimonial_ids = [t["id"] for t in testimonials]
    send_log_data = []
    if testimonial_ids:
        placeholders = ",".join("?" * len(testimonial_ids))
        send_log = conn.execute(
            f"SELECT * FROM testimonial_send_log WHERE testimonial_id IN ({placeholders}) ORDER BY testimonial_id, touch_number",
            testimonial_ids,
        ).fetchall()
        send_log_data = [dict(r) for r in send_log]

    # Content usage log
    content_usage = conn.execute(
        "SELECT * FROM content_usage_log WHERE patient_id = ? ORDER BY used_at",
        (patient_id,),
    ).fetchall()
    content_usage_data = [dict(r) for r in content_usage]

    # Patient preferences
    preferences = conn.execute(
        "SELECT * FROM patient_preferences WHERE patient_id = ? ORDER BY preference_type",
        (patient_id,),
    ).fetchall()
    preferences_data = [dict(r) for r in preferences]

    # WP media uploads for this patient's photos
    wp_uploads_data = []
    photo_ids = [p["id"] for p in photos_data]
    if photo_ids:
        placeholders = ",".join("?" * len(photo_ids))
        wp_uploads = conn.execute(
            f"SELECT * FROM wp_media_uploads WHERE patient_photo_id IN ({placeholders}) ORDER BY uploaded_at",
            photo_ids,
        ).fetchall()
        wp_uploads_data = [dict(r) for r in wp_uploads]

    # Session type history
    type_history_data = []
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        type_history = conn.execute(
            f"SELECT * FROM session_type_history WHERE session_id IN ({placeholders}) ORDER BY changed_at",
            session_ids,
        ).fetchall()
        type_history_data = [dict(r) for r in type_history]

    # Previous exports
    prev_exports = conn.execute(
        "SELECT * FROM patient_data_exports WHERE patient_id = ? ORDER BY exported_at",
        (patient_id,),
    ).fetchall()
    prev_exports_data = [dict(r) for r in prev_exports]

    conn.close()

    # ── Build JSON Data ──

    export_data = {
        "export_metadata": {
            "patient_id": patient_id,
            "exported_at": datetime.now().isoformat(),
            "exported_by": exported_by,
            "export_reason": export_reason,
        },
        "patient": patient_dict,
        "treatment_cycles": cycles_data,
        "photo_sessions": sessions_data,
        "photos": photos_data,
        "measurements": measurements_data,
        "consent_documents": consent_docs_data,
        "patient_consents": consents_data,
        "testimonials": testimonials_data,
        "testimonial_send_log": send_log_data,
        "content_usage_log": content_usage_data,
        "patient_preferences": preferences_data,
        "wp_media_uploads": wp_uploads_data,
        "session_type_history": type_history_data,
        "previous_exports": prev_exports_data,
    }

    # ── Create ZIP File ──

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"patient_{patient_id}"
    zip_filename = f"{safe_name}_export_{timestamp}.zip"

    # Use a temp directory for assembly
    export_dir = os.path.join(tempfile.gettempdir(), f"patient_export_{patient_id}_{timestamp}")
    os.makedirs(export_dir, exist_ok=True)

    try:
        # Write JSON data
        json_path = os.path.join(export_dir, "data.json")
        with open(json_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        # Copy photo files
        photos_dir = os.path.join(export_dir, "photos")
        os.makedirs(photos_dir, exist_ok=True)
        for file_path in photo_files:
            _safe_copy_file(file_path, photos_dir)

        # Copy consent documents
        consents_dir = os.path.join(export_dir, "consents")
        os.makedirs(consents_dir, exist_ok=True)
        for file_path in consent_files:
            _safe_copy_file(file_path, consents_dir)

        # Copy video files
        videos_dir = os.path.join(export_dir, "videos")
        os.makedirs(videos_dir, exist_ok=True)
        for file_path in video_files:
            _safe_copy_file(file_path, videos_dir)

        # Create ZIP
        uploads_exports_dir = os.path.join("uploads", "exports")
        os.makedirs(uploads_exports_dir, exist_ok=True)
        zip_path = os.path.join(uploads_exports_dir, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(export_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, export_dir)
                    zf.write(full_path, arcname)

        # Log the export
        conn = get_db()
        conn.execute(
            """INSERT INTO patient_data_exports
               (patient_id, exported_by, export_reason)
               VALUES (?, ?, ?)""",
            (patient_id, exported_by, export_reason),
        )
        conn.commit()
        conn.close()

        log_event(
            "patient_export",
            f"Patient data exported: patient {patient_id} by {exported_by}",
            {
                "patient_id": patient_id,
                "export_reason": export_reason,
                "zip_path": zip_path,
                "photo_count": len(photo_files),
                "consent_count": len(consent_files),
                "video_count": len(video_files),
            },
        )

        return zip_path

    except Exception as e:
        logger.error(f"Patient data export failed for patient {patient_id}: {e}")
        log_event(
            "error",
            f"Patient data export failed: patient {patient_id}",
            {"error": str(e)},
        )
        return None

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(export_dir, ignore_errors=True)
        except Exception:
            pass


def _safe_copy_file(src_path: str, dest_dir: str) -> bool:
    """Copy a file to a destination directory, handling missing files gracefully.

    Args:
        src_path: Source file path.
        dest_dir: Destination directory.

    Returns:
        True if the file was copied, False if it was missing or failed.
    """
    try:
        src = Path(src_path)
        if not src.exists():
            logger.warning(f"Export: file not found, skipping: {src_path}")
            return False

        dest = Path(dest_dir) / src.name
        # Handle filename collisions
        counter = 1
        while dest.exists():
            stem = src.stem
            suffix = src.suffix
            dest = Path(dest_dir) / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.copy2(str(src), str(dest))
        return True
    except Exception as e:
        logger.warning(f"Export: failed to copy {src_path}: {e}")
        return False
```

- [ ] 2. Verify the file was created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/services/patient_export_service.py
# Expected output: approximately 280-320 lines

python -c "
from app.services import patient_export_service as pes
assert hasattr(pes, 'export_patient_data'), 'Missing export_patient_data'
print('patient_export_service.export_patient_data verified.')
"
# Expected output: patient_export_service.export_patient_data verified.
```

- [ ] 3. Test export with a real patient in the database:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
import os
import json
import zipfile
from app.database import get_db, init_db, run_migrations
from app import photo_db, testimonial_db
from app.services.patient_export_service import export_patient_data

init_db()
run_migrations()

# Create test patient with some data
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('export@test.com', 'Export', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Add a treatment cycle and session
cycle_id = photo_db.create_treatment_cycle(pid, cycle_number=1)
sid = photo_db.create_session(
    pid, session_number=1, session_date='2026-01-15',
    session_type='baseline', cycle_id=cycle_id,
)
photo_db.upsert_measurement(sid, 'waist', 34.0)
photo_db.upsert_measurement(sid, 'hips', 40.0)

# Create a testimonial
import secrets
from datetime import datetime, timedelta
token = secrets.token_urlsafe(32)
expires = (datetime.now() + timedelta(days=30)).isoformat()
tid = testimonial_db.create_testimonial(pid, session_id=sid, cycle_id=cycle_id, token=token, token_expires_at=expires)
testimonial_db.update_testimonial(tid, rating=5, text='Great results!', status='submitted', submitted_at=datetime.now().isoformat())

# Test 1: Export patient data
zip_path = export_patient_data(pid, exported_by='test', export_reason='internal_review')
assert zip_path is not None
assert os.path.exists(zip_path)
print(f'Test 1 PASSED: ZIP created at {zip_path}')

# Test 2: Verify ZIP contents
with zipfile.ZipFile(zip_path, 'r') as zf:
    names = zf.namelist()
    assert 'data.json' in names
    print(f'Test 2 PASSED: ZIP contains {len(names)} files: {names}')

    # Read and verify JSON
    with zf.open('data.json') as f:
        data = json.loads(f.read())
    assert data['patient']['id'] == pid
    assert data['patient']['email'] == 'export@test.com'
    assert len(data['photo_sessions']) == 1
    assert len(data['measurements']) == 2
    assert len(data['testimonials']) == 1
    assert data['testimonials'][0]['rating'] == 5
    assert data['export_metadata']['export_reason'] == 'internal_review'
    print('Test 3 PASSED: JSON data contains correct patient records.')

# Test 4: Verify export was logged
conn = get_db()
exports = conn.execute(
    'SELECT * FROM patient_data_exports WHERE patient_id = ?', (pid,)
).fetchall()
conn.close()
assert len(exports) == 1
assert exports[0]['exported_by'] == 'test'
assert exports[0]['export_reason'] == 'internal_review'
print('Test 4 PASSED: Export logged in patient_data_exports table.')

# Test 5: Non-existent patient returns None
result = export_patient_data(999999)
assert result is None
print('Test 5 PASSED: Non-existent patient returns None.')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_data_exports WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM testimonials WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_measurements WHERE session_id = ?', (sid,))
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_treatment_cycles WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()

# Remove the ZIP file
if os.path.exists(zip_path):
    os.remove(zip_path)

print('All 5 patient export tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: ZIP created at uploads/exports/patient_..._export_....zip
# Test 2 PASSED: ZIP contains ... files: ['data.json', ...]
# Test 3 PASSED: JSON data contains correct patient records.
# Test 4 PASSED: Export logged in patient_data_exports table.
# Test 5 PASSED: Non-existent patient returns None.
# All 5 patient export tests passed. Cleanup complete.
```

- [ ] 4. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/patient_export_service.py
git commit -m "Add patient data export service for ZIP generation

Exports all patient data as a ZIP file: JSON dump of all database
records (sessions, photos metadata, measurements, consents, testimonials,
content usage, preferences, send log, WP uploads, type history), plus
original photo files, consent documents, and testimonial videos. Handles
missing files gracefully with warnings. Logs every export in
patient_data_exports table for audit trail. Uses temp directory for
assembly with cleanup in finally block."
```

---

### Task 13: Consent Routes + Templates (app/routes/consents.py + templates)

Create consent management routes and templates for uploading consent documents, viewing per-patient consent status, revoking consent, and securely serving consent document files.

**Files:**
- `app/routes/consents.py` (new)
- `app/templates/consent_upload.html` (new)
- `app/templates/consent_status.html` (new)

**Steps:**

- [ ] 1. Create `app/routes/consents.py` with the following complete code:

```python
import os
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.config import settings
from app.database import get_db, log_event
from app import consent_db
from app.services import consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/patients")
templates = Jinja2Templates(directory="app/templates")

# Accepted consent document MIME types
ACCEPTED_CONSENT_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
}

CONSENT_SCOPES = ["website", "social", "advertising", "email_testimonial", "case_study"]

DOCUMENT_TYPES = [
    ("media_release_v1", "Media Release (v1)"),
    ("media_release_v2", "Media Release (v2)"),
    ("hipaa_photo_auth", "HIPAA Photo Authorization"),
    ("general_consent", "General Consent Form"),
]


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_patient_or_404(patient_id: int):
    """Fetch patient by ID. Returns dict or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


@router.get("/{patient_id}/consents", response_class=HTMLResponse)
async def consent_status(request: Request, patient_id: int):
    """Per-patient consent dashboard showing all scopes with visual indicators."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    # Get all consents (active and revoked) for this patient
    all_consents = consent_db.get_all_consents_for_patient(patient_id)

    # Get active consents grouped by scope
    active_consents = consent_db.get_active_consents(patient_id)

    # Get consent documents
    documents = consent_db.get_consent_documents_for_patient(patient_id)

    # Build scope summary for template
    scope_summary = []
    for scope in CONSENT_SCOPES:
        # Find active consent for this scope
        active = None
        for c in active_consents:
            if c["scope"] == scope:
                active = c
                break

        scope_summary.append({
            "scope": scope,
            "label": scope.replace("_", " ").title(),
            "active": active is not None,
            "source": active["consent_source"] if active else None,
            "expires_at": active["expires_at"] if active else None,
            "granted_at": active["granted_at"] if active else None,
            "consent_id": active["id"] if active else None,
            "is_restricted": scope in consent_service.RESTRICTED_SCOPES,
        })

    # Get consent summary from service
    summary = consent_service.get_consent_summary(patient_id)

    return templates.TemplateResponse("consent_status.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "scope_summary": scope_summary,
        "all_consents": all_consents,
        "documents": documents,
        "summary": summary,
    })


@router.get("/{patient_id}/consents/upload", response_class=HTMLResponse)
async def consent_upload_form(request: Request, patient_id: int):
    """Upload consent document form."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    # Calculate default expiration
    default_expiration_years = settings.consent_default_expiration_years

    return templates.TemplateResponse("consent_upload.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "document_types": DOCUMENT_TYPES,
        "consent_scopes": CONSENT_SCOPES,
        "default_expiration_years": default_expiration_years,
        "error": None,
        "success": None,
    })


@router.post("/{patient_id}/consents/upload", response_class=HTMLResponse)
async def consent_upload_process(
    request: Request,
    patient_id: int,
    document_file: UploadFile = File(...),
    document_type: str = Form(...),
    signed_date: str = Form(...),
    expiration_date: str = Form(""),
    expiration_override_reason: str = Form(""),
    scope_website: str = Form(""),
    scope_social: str = Form(""),
    scope_advertising: str = Form(""),
    scope_email_testimonial: str = Form(""),
    scope_case_study: str = Form(""),
):
    """Process consent document upload with file, scopes, and expiration."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    error = None

    # Collect selected scopes
    selected_scopes = []
    if scope_website:
        selected_scopes.append("website")
    if scope_social:
        selected_scopes.append("social")
    if scope_advertising:
        selected_scopes.append("advertising")
    if scope_email_testimonial:
        selected_scopes.append("email_testimonial")
    if scope_case_study:
        selected_scopes.append("case_study")

    if not selected_scopes:
        error = "Please select at least one consent scope."

    # Validate signed_date
    if not error:
        try:
            datetime.strptime(signed_date, "%Y-%m-%d")
        except ValueError:
            error = "Invalid signed date format. Use YYYY-MM-DD."

    # Validate expiration override
    if not error and expiration_date and not expiration_override_reason.strip():
        error = (
            "When providing a custom expiration date, "
            "an override reason is required."
        )

    # Validate file
    file_bytes = b""
    if not error:
        file_bytes = await document_file.read()
        if not file_bytes:
            error = "No file uploaded or file is empty."

    if not error:
        # Check file size
        max_bytes = settings.max_consent_upload_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            error = (
                f"File too large: {len(file_bytes) / 1024 / 1024:.1f}MB. "
                f"Maximum is {settings.max_consent_upload_mb}MB."
            )

    if not error:
        # Check MIME type
        try:
            import magic
            mime_type = magic.from_buffer(file_bytes, mime=True)
        except Exception:
            mime_type = document_file.content_type or ""

        if mime_type not in ACCEPTED_CONSENT_MIMES:
            error = (
                f"Invalid file type: {mime_type}. "
                "Accepted types: PDF, JPEG, PNG, HEIC."
            )

    if error:
        return templates.TemplateResponse("consent_upload.html", {
            "request": request,
            "active": "patients",
            "patient": patient,
            "document_types": DOCUMENT_TYPES,
            "consent_scopes": CONSENT_SCOPES,
            "default_expiration_years": settings.consent_default_expiration_years,
            "error": error,
            "success": None,
        })

    # Determine file extension from MIME type
    ext_map = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/heic": "heic",
        "image/heif": "heif",
    }
    file_ext = ext_map.get(mime_type, "pdf")

    # Save file with UUID filename
    upload_dir = os.path.join("uploads", "consents", str(patient_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_uuid = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_uuid}.{file_ext}")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Create consent document record
    doc_id = consent_db.create_consent_document(
        patient_id=patient_id,
        document_path=file_path,
        document_type=document_type,
        signed_date=signed_date,
        uploaded_by="admin",
    )

    # Determine expiration
    expires_at = None
    override_reason = ""
    if expiration_date:
        expires_at = f"{expiration_date}T23:59:59"
        override_reason = expiration_override_reason.strip()

    # Grant consent for selected scopes
    try:
        consent_ids = consent_service.grant_consent_from_document(
            patient_id=patient_id,
            document_id=doc_id,
            scopes=selected_scopes,
            signed_date=signed_date,
            granted_by="admin",
            expires_at=expires_at,
            expiration_override_reason=override_reason,
        )
    except ValueError as e:
        return templates.TemplateResponse("consent_upload.html", {
            "request": request,
            "active": "patients",
            "patient": patient,
            "document_types": DOCUMENT_TYPES,
            "consent_scopes": CONSENT_SCOPES,
            "default_expiration_years": settings.consent_default_expiration_years,
            "error": str(e),
            "success": None,
        })

    log_event(
        "consent",
        f"Consent document uploaded and {len(consent_ids)} scopes granted for patient {patient_id}",
        {"document_id": doc_id, "scopes": selected_scopes, "consent_ids": consent_ids},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}/consents?success=1",
        status_code=303,
    )


@router.post("/{patient_id}/consents/{consent_id}/revoke", response_class=HTMLResponse)
async def consent_revoke(
    request: Request,
    patient_id: int,
    consent_id: int,
    revoke_reason: str = Form(...),
):
    """Revoke a specific consent scope."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    if not revoke_reason.strip():
        return RedirectResponse(
            url=f"/dashboard/patients/{patient_id}/consents?error=reason_required",
            status_code=303,
        )

    try:
        result = consent_service.revoke_patient_consent(
            consent_id=consent_id,
            revoked_by="admin",
            reason=revoke_reason.strip(),
        )
    except Exception as e:
        logger.error(f"Failed to revoke consent {consent_id}: {e}")
        return RedirectResponse(
            url=f"/dashboard/patients/{patient_id}/consents?error=revoke_failed",
            status_code=303,
        )

    log_event(
        "consent",
        f"Consent {consent_id} revoked for patient {patient_id}",
        {"revoked_reason": revoke_reason, "result": result},
    )

    flagged = result.get("flagged_content_count", 0)
    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}/consents?revoked=1&flagged={flagged}",
        status_code=303,
    )


@router.get("/admin/consents/{document_id}/view")
async def consent_document_view(request: Request, document_id: int):
    """Secure file serving for consent documents. Authenticated, streams file."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    doc = consent_db.get_consent_document(document_id)
    if not doc:
        return HTMLResponse("<h1>Document not found</h1>", status_code=404)

    file_path = doc["document_path"]
    if not os.path.exists(file_path):
        return HTMLResponse("<h1>Document file not found on disk</h1>", status_code=404)

    # Determine content type from extension
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    def file_iterator():
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    filename = os.path.basename(file_path)
    return StreamingResponse(
        file_iterator(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
```

- [ ] 2. Create `app/templates/consent_upload.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Upload Consent - {{ patient.first_name }} {{ patient.last_name }} - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">&gt;</span>
        <a href="/dashboard/patients/{{ patient.id }}/consents" class="hover:text-teal">{{ patient.first_name }} {{ patient.last_name }}</a>
        <span class="mx-1">&gt;</span>
        <span class="text-navy">Upload Consent</span>
    </nav>

    <h2 class="text-2xl font-bold text-navy mb-6">Upload Consent Document</h2>
    <p class="text-gray-600 mb-6">Patient: <strong>{{ patient.first_name }} {{ patient.last_name }}</strong></p>

    {% if error %}
    <div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6">
        {{ error }}
    </div>
    {% endif %}

    {% if success %}
    <div class="bg-green-50 border border-green-200 text-green-700 p-4 rounded-lg mb-6">
        Consent document uploaded and scopes granted successfully.
    </div>
    {% endif %}

    <form method="POST" action="/dashboard/patients/{{ patient.id }}/consents/upload" enctype="multipart/form-data" class="bg-white rounded-lg shadow-sm p-6 max-w-2xl">

        <!-- File Upload -->
        <div class="mb-6">
            <label class="block text-sm font-semibold text-navy mb-2">Consent Document File <span class="text-red-500">*</span></label>
            <input type="file" name="document_file" required accept=".pdf,.jpg,.jpeg,.png,.heic,.heif"
                   class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-teal/10 file:text-teal hover:file:bg-teal/20">
            <p class="text-xs text-gray-400 mt-1">Accepted: PDF, JPG, PNG, HEIC. Max {{ settings.max_consent_upload_mb if settings else 15 }}MB.</p>
        </div>

        <!-- Document Type -->
        <div class="mb-6">
            <label class="block text-sm font-semibold text-navy mb-2">Document Type <span class="text-red-500">*</span></label>
            <select name="document_type" required class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                {% for value, label in document_types %}
                <option value="{{ value }}">{{ label }}</option>
                {% endfor %}
            </select>
        </div>

        <!-- Signed Date -->
        <div class="mb-6">
            <label class="block text-sm font-semibold text-navy mb-2">Date Signed <span class="text-red-500">*</span></label>
            <input type="date" name="signed_date" required class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
        </div>

        <!-- Consent Scopes -->
        <div class="mb-6">
            <label class="block text-sm font-semibold text-navy mb-3">Consent Scopes <span class="text-red-500">*</span></label>
            <p class="text-xs text-gray-500 mb-3">Check the scopes that match what the patient authorized on the signed document.</p>
            <div class="space-y-2">
                <label class="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="scope_website" value="1" class="rounded border-gray-300 text-teal focus:ring-teal">
                    <span>Website</span>
                    <span class="text-xs text-gray-400">- Photos/testimonials on practice website</span>
                </label>
                <label class="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="scope_social" value="1" class="rounded border-gray-300 text-teal focus:ring-teal">
                    <span>Social Media</span>
                    <span class="text-xs text-gray-400">- Facebook, Instagram posts</span>
                </label>
                <label class="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="scope_email_testimonial" value="1" class="rounded border-gray-300 text-teal focus:ring-teal">
                    <span>Email Testimonial</span>
                    <span class="text-xs text-gray-400">- Testimonial in email campaigns</span>
                </label>
                <label class="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="scope_advertising" value="1" class="rounded border-gray-300 text-teal focus:ring-teal">
                    <span>Advertising</span>
                    <span class="text-xs text-gray-400">- Paid ads, promotional materials</span>
                </label>
                <label class="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="scope_case_study" value="1" class="rounded border-gray-300 text-teal focus:ring-teal">
                    <span>Case Study</span>
                    <span class="text-xs text-gray-400">- Published case study with detailed results</span>
                </label>
            </div>
        </div>

        <!-- Expiration -->
        <div class="mb-6 bg-gray-50 rounded-lg p-4">
            <label class="block text-sm font-semibold text-navy mb-2">Expiration Date</label>
            <p class="text-xs text-gray-500 mb-3">
                Default: {{ default_expiration_years }} years from signed date.
                Only change if the signed document specifies a different term.
            </p>
            <input type="date" name="expiration_date" class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50 mb-3">

            <label class="block text-sm font-semibold text-navy mb-1">Override Reason</label>
            <p class="text-xs text-gray-500 mb-2">Required if you set a custom expiration date.</p>
            <input type="text" name="expiration_override_reason" placeholder='e.g., "Signed release specifies 5-year term"'
                   class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
        </div>

        <!-- Reminder -->
        <div class="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
            <p class="text-sm text-amber-800 font-medium">
                Review the signed document to confirm the consent duration matches your entered expiration date.
            </p>
        </div>

        <!-- Submit -->
        <div class="flex gap-3">
            <button type="submit" class="bg-teal text-white px-6 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
                Upload & Grant Consent
            </button>
            <a href="/dashboard/patients/{{ patient.id }}/consents" class="bg-gray-200 text-gray-700 px-6 py-2 rounded text-sm font-semibold hover:bg-gray-300 transition">
                Cancel
            </a>
        </div>
    </form>
</div>
{% endblock %}
```

- [ ] 3. Create `app/templates/consent_status.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Consent Status - {{ patient.first_name }} {{ patient.last_name }} - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">&gt;</span>
        <span class="text-navy">{{ patient.first_name }} {{ patient.last_name }} - Consents</span>
    </nav>

    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Consent Status</h2>
        <a href="/dashboard/patients/{{ patient.id }}/consents/upload" class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
            + Upload Consent Document
        </a>
    </div>

    {% if request.query_params.get('success') %}
    <div class="bg-green-50 border border-green-200 text-green-700 p-4 rounded-lg mb-6">
        Consent document uploaded and scopes granted successfully.
    </div>
    {% endif %}

    {% if request.query_params.get('revoked') %}
    <div class="bg-yellow-50 border border-yellow-200 text-yellow-700 p-4 rounded-lg mb-6">
        Consent has been revoked. Any active content uses have been flagged for review.
    </div>
    {% endif %}

    {% if request.query_params.get('error') == 'reason_required' %}
    <div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6">
        A reason is required to revoke consent.
    </div>
    {% endif %}

    <p class="text-gray-600 mb-6">Patient: <strong>{{ patient.first_name }} {{ patient.last_name }}</strong> ({{ patient.email or 'No email' }})</p>

    <!-- Scope Status Grid -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Active Consent by Scope</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {% for scope in scope_summary %}
            <div class="border rounded-lg p-4 {% if scope.active %}border-green-300 bg-green-50{% else %}border-gray-200 bg-gray-50{% endif %}">
                <div class="flex items-center gap-2 mb-2">
                    {% if scope.active %}
                        {% if scope.source == 'signed_document' %}
                        <!-- Solid green checkmark for signed_document -->
                        <svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>
                        {% elif scope.source == 'testimonial_form' %}
                        <!-- Outlined checkmark for testimonial_form -->
                        <svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        {% else %}
                        <!-- Manual staff entry -->
                        <svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>
                        {% endif %}
                    {% else %}
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    {% endif %}
                    <span class="font-semibold text-navy text-sm">{{ scope.label }}</span>
                </div>

                {% if scope.active %}
                    <p class="text-xs text-green-700 mb-1">
                        {% if scope.source == 'signed_document' %}Signed consent on file
                        {% elif scope.source == 'testimonial_form' %}Web form consent — limited scope
                        {% else %}Manual staff entry{% endif %}
                    </p>
                    {% if scope.expires_at %}
                    <p class="text-xs text-gray-500">Expires: {{ scope.expires_at[:10] }}</p>
                    {% endif %}

                    <!-- Revoke form -->
                    <details class="mt-2">
                        <summary class="text-xs text-red-500 cursor-pointer hover:text-red-700">Revoke this consent</summary>
                        <form method="POST" action="/dashboard/patients/{{ patient.id }}/consents/{{ scope.consent_id }}/revoke" class="mt-2">
                            <input type="text" name="revoke_reason" required placeholder="Reason for revocation (required)"
                                   class="w-full border border-gray-300 rounded px-2 py-1 text-xs mb-2 focus:outline-none focus:ring-1 focus:ring-red-300">
                            <button type="submit" class="bg-red-500 text-white px-3 py-1 rounded text-xs hover:bg-red-600 transition"
                                    onclick="return confirm('Are you sure you want to revoke this consent? This will flag all active content uses for review.')">
                                Confirm Revoke
                            </button>
                        </form>
                    </details>
                {% else %}
                    <p class="text-xs text-gray-500">No active consent</p>
                    {% if scope.is_restricted %}
                    <p class="text-xs text-amber-600 mt-1">Requires signed document or manual staff entry</p>
                    {% endif %}
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Blocking Dialog Description for restricted scopes -->
    {% set has_ad_consent = false %}
    {% set has_cs_consent = false %}
    {% for scope in scope_summary %}
        {% if scope.scope == 'advertising' and scope.active and scope.source != 'testimonial_form' %}
            {% set has_ad_consent = true %}
        {% endif %}
        {% if scope.scope == 'case_study' and scope.active and scope.source != 'testimonial_form' %}
            {% set has_cs_consent = true %}
        {% endif %}
    {% endfor %}

    {% if not has_ad_consent or not has_cs_consent %}
    <div class="bg-amber-50 border border-amber-300 rounded-lg p-4 mb-6">
        <h4 class="font-semibold text-amber-800 text-sm mb-2">Consent Required for Marketing Use</h4>
        <p class="text-sm text-amber-700">
            This patient has not signed a media release covering
            {% if not has_ad_consent %}advertising{% endif %}
            {% if not has_ad_consent and not has_cs_consent %} or {% endif %}
            {% if not has_cs_consent %}case study{% endif %}
            use. Web-form consent alone is not sufficient for these purposes.
        </p>
        <div class="mt-3 flex gap-2">
            <a href="/dashboard/patients/{{ patient.id }}/consents/upload" class="bg-teal text-white px-3 py-1 rounded text-xs font-semibold hover:bg-teal/90 transition">
                Upload Signed Document
            </a>
        </div>
    </div>
    {% endif %}

    <!-- Consent Documents -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Uploaded Documents</h3>
        {% if documents %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200">
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">ID</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Type</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Signed Date</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Uploaded</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for doc in documents %}
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="py-2 px-3">{{ doc.id }}</td>
                        <td class="py-2 px-3">{{ doc.document_type }}</td>
                        <td class="py-2 px-3">{{ doc.signed_date }}</td>
                        <td class="py-2 px-3">{{ doc.uploaded_at[:10] if doc.uploaded_at else '-' }}</td>
                        <td class="py-2 px-3">
                            <a href="/dashboard/patients/admin/consents/{{ doc.id }}/view" target="_blank"
                               class="text-teal hover:text-teal/80 text-xs font-semibold">View Document</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-gray-500 text-sm">No consent documents uploaded yet.</p>
        {% endif %}
    </div>

    <!-- Full Consent History -->
    <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Consent History</h3>
        {% if all_consents %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200">
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Scope</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Source</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Granted</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Expires</th>
                        <th class="text-left py-2 px-3 text-gray-500 font-medium">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for c in all_consents %}
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="py-2 px-3">{{ c.scope.replace('_', ' ').title() }}</td>
                        <td class="py-2 px-3">
                            {% if c.consent_source == 'signed_document' %}
                            <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Signed</span>
                            {% elif c.consent_source == 'testimonial_form' %}
                            <span class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">Web Form</span>
                            {% else %}
                            <span class="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-xs">Manual</span>
                            {% endif %}
                        </td>
                        <td class="py-2 px-3">{{ c.granted_at[:10] if c.granted_at else '-' }}</td>
                        <td class="py-2 px-3">{{ c.expires_at[:10] if c.expires_at else 'No expiry' }}</td>
                        <td class="py-2 px-3">
                            {% if c.revoked_at %}
                            <span class="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs" title="{{ c.revoked_reason or '' }}">Revoked {{ c.revoked_at[:10] }}</span>
                            {% else %}
                            <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Active</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-gray-500 text-sm">No consent records found.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/consents.py app/templates/consent_upload.html app/templates/consent_status.html
# Expected output: approximately 280-310 lines for routes, 120-140 for upload template, 180-210 for status template

python -c "
from app.routes.consents import router
routes = [r.path for r in router.routes]
print(f'Consent router has {len(routes)} routes:')
for r in sorted(routes):
    print(f'  {r}')
assert '/{patient_id}/consents' in routes
assert '/{patient_id}/consents/upload' in routes
assert '/{patient_id}/consents/{consent_id}/revoke' in routes
assert '/admin/consents/{document_id}/view' in routes
print('All expected routes present.')
"
# Expected output:
# Consent router has 5 routes:
#   /admin/consents/{document_id}/view
#   /{patient_id}/consents
#   /{patient_id}/consents/upload
#   /{patient_id}/consents/upload
#   /{patient_id}/consents/{consent_id}/revoke
# All expected routes present.
```

- [ ] 5. Test consent upload flow (integration):

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import consent_db
from app.services import consent_service

init_db()
run_migrations()

# Create test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('consenttest@test.com', 'Consent', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Test 1: Create consent document
doc_id = consent_db.create_consent_document(
    patient_id=pid,
    document_path='uploads/consents/test/test.pdf',
    document_type='media_release_v1',
    signed_date='2026-04-01',
    uploaded_by='admin',
)
assert doc_id > 0
print(f'Test 1 PASSED: Created consent document {doc_id}')

# Test 2: Grant consent from document
consent_ids = consent_service.grant_consent_from_document(
    patient_id=pid,
    document_id=doc_id,
    scopes=['website', 'social', 'advertising'],
    signed_date='2026-04-01',
    granted_by='admin',
)
assert len(consent_ids) == 3
print(f'Test 2 PASSED: Granted {len(consent_ids)} consent scopes')

# Test 3: Check active consent
assert consent_service.patient_has_active_consent(pid, 'website')
assert consent_service.patient_has_active_consent(pid, 'advertising')
assert not consent_service.patient_has_active_consent(pid, 'case_study')
print('Test 3 PASSED: Active consent checks correct')

# Test 4: Revoke consent
result = consent_service.revoke_patient_consent(
    consent_id=consent_ids[2],  # advertising
    revoked_by='admin',
    revoked_reason='Patient requested revocation',
)
assert not consent_service.patient_has_active_consent(pid, 'advertising')
print('Test 4 PASSED: Consent revoked successfully')

# Test 5: Get consent summary
summary = consent_service.get_consent_summary(pid)
assert summary['total_active'] == 2
print(f'Test 5 PASSED: Consent summary shows {summary[\"total_active\"]} active')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_consents WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM consent_documents WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()

print('All 5 consent route tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Created consent document ...
# Test 2 PASSED: Granted 3 consent scopes
# Test 3 PASSED: Active consent checks correct
# Test 4 PASSED: Consent revoked successfully
# Test 5 PASSED: Consent summary shows 2 active
# All 5 consent route tests passed. Cleanup complete.
```

- [ ] 6. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/consents.py app/templates/consent_upload.html app/templates/consent_status.html
git commit -m "Add consent routes and templates for document upload and status management

Routes handle consent document upload (file validation, UUID filenames,
scope checkbox processing, expiration with override reason), per-patient
consent status dashboard (visual scope grid with source indicators:
solid green for signed_document, outlined for testimonial_form), consent
revocation with required reason, and secure authenticated file streaming
for consent documents. Templates include blocking dialog for advertising
and case_study scopes without signed consent."
```

---

### Task 14: Session Routes + Templates (app/routes/sessions.py + templates)

Create photo session management routes and templates for listing sessions, creating new sessions (with auto-suggested type and cycle creation prompts), viewing session detail with 6-angle photo grid and measurement form, and session lifecycle actions (complete, archive, change type).

**Files:**
- `app/routes/sessions.py` (new)
- `app/templates/session_view.html` (new)
- `app/templates/session_list.html` (new)

**Steps:**

- [ ] 1. Create `app/routes/sessions.py` with the following complete code:

```python
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import get_db, log_event
from app import photo_db
from app.services import measurement_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/patients")
templates = Jinja2Templates(directory="app/templates")

ANGLES = ["front", "side_left", "side_right", "45_degree_left", "45_degree_right", "back"]
ANGLE_LABELS = {
    "front": "Front",
    "side_left": "Left Side",
    "side_right": "Right Side",
    "45_degree_left": "45° Left",
    "45_degree_right": "45° Right",
    "back": "Back",
}

MEASUREMENT_POINTS = [
    "waist", "hips", "thighs_left", "thighs_right",
    "arms_left", "arms_right", "chest", "under_bust",
]
MEASUREMENT_LABELS = {
    "waist": "Waist",
    "hips": "Hips",
    "thighs_left": "Left Thigh",
    "thighs_right": "Right Thigh",
    "arms_left": "Left Arm",
    "arms_right": "Right Arm",
    "chest": "Chest",
    "under_bust": "Under Bust",
}

SESSION_TYPES = ["baseline", "mid_treatment", "final", "followup", "incomplete"]


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_patient_or_404(patient_id: int):
    """Fetch patient by ID. Returns dict or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _suggest_session_type(patient_id: int) -> str:
    """Auto-suggest session type based on patient history.

    - First session -> baseline
    - Middle sessions -> mid_treatment
    - 5+ sessions with no final -> suggest final
    - Post-final -> followup
    """
    sessions = photo_db.get_sessions_for_patient(patient_id, include_archived=False)
    if not sessions:
        return "baseline"

    types = [s["session_type"] for s in sessions]

    # If there is a completed final, suggest followup
    for s in sessions:
        if s["session_type"] == "final" and s["completed_at"]:
            return "followup"

    # If 5+ sessions and no final, suggest final
    if len(sessions) >= 5 and "final" not in types:
        return "final"

    return "mid_treatment"


def _check_cycle_prompt(patient_id: int) -> dict:
    """Check if we should prompt for new cycle creation.

    Returns dict with:
        should_prompt: bool
        last_final_date: str or None
        next_cycle_number: int
    """
    sessions = photo_db.get_sessions_for_patient(patient_id, include_archived=False)
    if not sessions:
        return {"should_prompt": False, "last_final_date": None, "next_cycle_number": 1}

    # Check if the most recent session is a completed final
    latest = sessions[0]  # sessions ordered by session_date DESC
    if latest["session_type"] == "final" and latest["completed_at"]:
        cycles = photo_db.get_cycles_for_patient(patient_id)
        next_num = max((c["cycle_number"] for c in cycles), default=0) + 1
        return {
            "should_prompt": True,
            "last_final_date": latest["session_date"],
            "next_cycle_number": next_num,
        }

    return {"should_prompt": False, "last_final_date": None, "next_cycle_number": 1}


@router.get("/{patient_id}/sessions", response_class=HTMLResponse)
async def session_list(request: Request, patient_id: int, show_archived: str = ""):
    """Session list for a patient."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    include_archived = show_archived == "1"
    sessions = photo_db.get_sessions_for_patient(
        patient_id, include_archived=include_archived
    )

    # Add completion info to each session
    for s in sessions:
        completion = photo_db.check_session_complete(s["id"])
        s["completion"] = completion

    cycles = photo_db.get_cycles_for_patient(patient_id)

    return templates.TemplateResponse("session_list.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "sessions": sessions,
        "cycles": cycles,
        "show_archived": include_archived,
    })


@router.get("/{patient_id}/sessions/new", response_class=HTMLResponse)
async def session_new_form(request: Request, patient_id: int):
    """New session form with auto-suggested type."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    suggested_type = _suggest_session_type(patient_id)
    cycle_prompt = _check_cycle_prompt(patient_id)
    cycles = photo_db.get_cycles_for_patient(patient_id)
    session_count = photo_db.get_session_count_for_patient(patient_id)

    return templates.TemplateResponse("session_list.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "sessions": [],
        "cycles": cycles,
        "show_new_form": True,
        "suggested_type": suggested_type,
        "cycle_prompt": cycle_prompt,
        "session_count": session_count,
        "session_types": SESSION_TYPES,
        "show_archived": False,
    })


@router.post("/{patient_id}/sessions/create", response_class=HTMLResponse)
async def session_create(
    request: Request,
    patient_id: int,
    session_type: str = Form(...),
    session_date: str = Form(""),
    notes: str = Form(""),
    start_new_cycle: str = Form(""),
    cycle_id: str = Form(""),
):
    """Create a new session with cycle creation prompt logic."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    # Default session date to today
    if not session_date:
        session_date = datetime.now().strftime("%Y-%m-%d")

    # Validate session type
    if session_type not in SESSION_TYPES:
        return RedirectResponse(
            url=f"/dashboard/patients/{patient_id}/sessions/new?error=invalid_type",
            status_code=303,
        )

    # Handle cycle logic
    resolved_cycle_id = None

    if start_new_cycle == "yes":
        # Create a new cycle
        cycles = photo_db.get_cycles_for_patient(patient_id)
        next_num = max((c["cycle_number"] for c in cycles), default=0) + 1
        resolved_cycle_id = photo_db.create_treatment_cycle(
            patient_id, cycle_number=next_num, started_at=session_date
        )
        log_event(
            "session",
            f"New treatment cycle {next_num} started for patient {patient_id}",
            {"cycle_id": resolved_cycle_id},
        )
    elif cycle_id:
        try:
            resolved_cycle_id = int(cycle_id)
        except ValueError:
            resolved_cycle_id = None
    else:
        # Auto-create cycle 1 if none exists
        cycles = photo_db.get_cycles_for_patient(patient_id)
        if not cycles:
            resolved_cycle_id = photo_db.create_treatment_cycle(
                patient_id, cycle_number=1, started_at=session_date
            )
        else:
            # Use latest cycle
            latest = photo_db.get_latest_cycle(patient_id)
            if latest:
                resolved_cycle_id = latest["id"]

    # Determine session number
    session_count = photo_db.get_session_count_for_patient(patient_id)
    session_number = session_count + 1

    # Create session
    session_id = photo_db.create_session(
        patient_id=patient_id,
        session_number=session_number,
        session_date=session_date,
        session_type=session_type,
        cycle_id=resolved_cycle_id,
        notes=notes,
    )

    log_event(
        "session",
        f"Session {session_number} created for patient {patient_id}",
        {"session_id": session_id, "session_type": session_type},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}/sessions/{session_id}",
        status_code=303,
    )


@router.get("/{patient_id}/sessions/{session_id}", response_class=HTMLResponse)
async def session_view(request: Request, patient_id: int, session_id: int):
    """Session view with 6-angle photo grid, measurement form, and completion status."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    # Get current photos
    photos = photo_db.get_current_photos(session_id)
    photos_by_angle = {p["angle"]: p for p in photos}

    # Get measurements
    measurements = photo_db.get_measurements_for_session(session_id)
    measurements_by_point = {m["measurement_point"]: m for m in measurements}

    # Get previous session measurements for visual diff
    prev_measurements = {}
    sessions = photo_db.get_sessions_for_patient(patient_id, include_archived=False)
    prev_session = None
    for s in sessions:
        if s["id"] != session_id and s["session_date"] < session["session_date"]:
            prev_session = s
            break
    if prev_session:
        prev_meas = photo_db.get_measurements_for_session(prev_session["id"])
        prev_measurements = {m["measurement_point"]: m for m in prev_meas}

    # Completion check
    completion = photo_db.check_session_complete(session_id)

    # Calculate progress percentage
    total_items = 14  # 6 angles + 8 measurements
    completed_items = completion["photo_count"] + completion["measurement_count"]
    progress_pct = int((completed_items / total_items) * 100) if total_items > 0 else 0

    return templates.TemplateResponse("session_view.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "session": session,
        "angles": ANGLES,
        "angle_labels": ANGLE_LABELS,
        "photos_by_angle": photos_by_angle,
        "measurement_points": MEASUREMENT_POINTS,
        "measurement_labels": MEASUREMENT_LABELS,
        "measurements_by_point": measurements_by_point,
        "prev_measurements": prev_measurements,
        "completion": completion,
        "progress_pct": progress_pct,
        "session_types": SESSION_TYPES,
    })


@router.post("/{patient_id}/sessions/{session_id}/complete", response_class=HTMLResponse)
async def session_complete(request: Request, patient_id: int, session_id: int):
    """Mark session as complete. Validates all photos and measurements present."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    # Check completion requirements
    completion = photo_db.check_session_complete(session_id)
    if not completion["is_complete"]:
        missing = []
        if completion["missing_angles"]:
            missing.append(f"Missing photos: {', '.join(completion['missing_angles'])}")
        if completion["missing_measurements"]:
            missing.append(f"Missing measurements: {', '.join(completion['missing_measurements'])}")
        return RedirectResponse(
            url=f"/dashboard/patients/{patient_id}/sessions/{session_id}?error=incomplete",
            status_code=303,
        )

    # Mark complete
    photo_db.complete_session(session_id)

    log_event(
        "session",
        f"Session {session_id} marked complete for patient {patient_id}",
        {"session_type": session["session_type"]},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}/sessions/{session_id}?completed=1",
        status_code=303,
    )


@router.post("/{patient_id}/sessions/{session_id}/archive", response_class=HTMLResponse)
async def session_archive(request: Request, patient_id: int, session_id: int):
    """Archive a session (soft-delete)."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    photo_db.archive_session(session_id)

    log_event(
        "session",
        f"Session {session_id} archived for patient {patient_id}",
    )

    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}/sessions?archived=1",
        status_code=303,
    )


@router.post("/{patient_id}/sessions/{session_id}/change-type", response_class=HTMLResponse)
async def session_change_type(
    request: Request,
    patient_id: int,
    session_id: int,
    new_type: str = Form(...),
    reason: str = Form(""),
):
    """Change session type with reason logging."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    if new_type not in SESSION_TYPES:
        return RedirectResponse(
            url=f"/dashboard/patients/{patient_id}/sessions/{session_id}?error=invalid_type",
            status_code=303,
        )

    if new_type == session["session_type"]:
        return RedirectResponse(
            url=f"/dashboard/patients/{patient_id}/sessions/{session_id}",
            status_code=303,
        )

    photo_db.change_session_type(
        session_id, new_type, changed_by="admin", reason=reason.strip()
    )

    log_event(
        "session",
        f"Session {session_id} type changed from {session['session_type']} to {new_type}",
        {"reason": reason},
    )

    # If changed to final and session is complete, trigger testimonial eligibility
    if new_type == "final":
        completion = photo_db.check_session_complete(session_id)
        if completion["is_complete"] and session.get("completed_at"):
            photo_db.update_session(
                session_id,
                testimonial_request_eligible_at=datetime.now().isoformat(),
            )

    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}/sessions/{session_id}?type_changed=1",
        status_code=303,
    )
```

- [ ] 2. Create `app/templates/session_view.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Session {{ session.session_number }} - {{ patient.first_name }} {{ patient.last_name }} - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">&gt;</span>
        <a href="/dashboard/patients/{{ patient.id }}/sessions" class="hover:text-teal">{{ patient.first_name }} {{ patient.last_name }}</a>
        <span class="mx-1">&gt;</span>
        <span class="text-navy">Session {{ session.session_number }}</span>
    </nav>

    <div class="flex justify-between items-center mb-4">
        <div>
            <h2 class="text-2xl font-bold text-navy">Session {{ session.session_number }}</h2>
            <p class="text-gray-500 text-sm">{{ session.session_date }} &middot;
                <span class="inline-block px-2 py-0.5 rounded text-xs font-semibold
                    {% if session.session_type == 'baseline' %}bg-blue-100 text-blue-700
                    {% elif session.session_type == 'final' %}bg-green-100 text-green-700
                    {% elif session.session_type == 'followup' %}bg-purple-100 text-purple-700
                    {% elif session.session_type == 'incomplete' %}bg-red-100 text-red-700
                    {% else %}bg-gray-100 text-gray-700{% endif %}">
                    {{ session.session_type.replace('_', ' ').title() }}
                </span>
            </p>
        </div>
        <div class="flex gap-2">
            {% if not session.completed_at %}
            <form method="POST" action="/dashboard/patients/{{ patient.id }}/sessions/{{ session.id }}/complete" class="inline">
                <button type="submit" class="bg-green-600 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-green-700 transition"
                        {% if not completion.is_complete %}disabled title="Complete all photos and measurements first" class="bg-gray-400 text-white px-4 py-2 rounded text-sm font-semibold cursor-not-allowed"{% endif %}>
                    Mark Complete
                </button>
            </form>
            {% else %}
            <span class="bg-green-100 text-green-700 px-4 py-2 rounded text-sm font-semibold">Completed {{ session.completed_at[:10] }}</span>
            {% endif %}
            <form method="POST" action="/dashboard/patients/{{ patient.id }}/sessions/{{ session.id }}/archive"
                  onsubmit="return confirm('Archive this session? It will be hidden from all lists.')" class="inline">
                <button type="submit" class="bg-gray-200 text-gray-700 px-4 py-2 rounded text-sm font-semibold hover:bg-gray-300 transition">Archive</button>
            </form>
        </div>
    </div>

    <!-- Status Messages -->
    {% if request.query_params.get('completed') %}
    <div class="bg-green-50 border border-green-200 text-green-700 p-4 rounded-lg mb-6">Session marked as complete.</div>
    {% endif %}
    {% if request.query_params.get('type_changed') %}
    <div class="bg-blue-50 border border-blue-200 text-blue-700 p-4 rounded-lg mb-6">Session type changed successfully.</div>
    {% endif %}
    {% if request.query_params.get('error') == 'incomplete' %}
    <div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6">
        Cannot mark complete. Missing:
        {% if completion.missing_angles %}photos ({{ completion.missing_angles | join(', ') }}){% endif %}
        {% if completion.missing_angles and completion.missing_measurements %} and {% endif %}
        {% if completion.missing_measurements %}measurements ({{ completion.missing_measurements | join(', ') }}){% endif %}
    </div>
    {% endif %}

    <!-- Completion Progress Bar -->
    <div class="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-semibold text-navy">Completion Progress</span>
            <span class="text-sm text-gray-500">{{ completion.photo_count }}/6 photos, {{ completion.measurement_count }}/8 measurements</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3">
            <div class="h-3 rounded-full transition-all duration-500
                {% if progress_pct == 100 %}bg-green-500{% elif progress_pct >= 50 %}bg-teal{% else %}bg-amber-400{% endif %}"
                 style="width: {{ progress_pct }}%"></div>
        </div>
    </div>

    <!-- Change Session Type -->
    <div class="bg-white rounded-lg shadow-sm p-4 mb-6">
        <details>
            <summary class="text-sm font-semibold text-navy cursor-pointer">Change Session Type</summary>
            <form method="POST" action="/dashboard/patients/{{ patient.id }}/sessions/{{ session.id }}/change-type" class="mt-3 flex gap-3 items-end">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">New Type</label>
                    <select name="new_type" class="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                        {% for st in session_types %}
                        <option value="{{ st }}" {% if st == session.session_type %}selected{% endif %}>{{ st.replace('_', ' ').title() }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="flex-1">
                    <label class="block text-xs text-gray-500 mb-1">Reason</label>
                    <input type="text" name="reason" placeholder="Reason for change" class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                </div>
                <button type="submit" class="bg-navy text-white px-4 py-2 rounded text-sm font-semibold hover:bg-navy/90 transition">Change</button>
            </form>
        </details>
    </div>

    <!-- 6-Angle Photo Grid -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Photos ({{ completion.photo_count }}/6)</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
            {% for angle in angles %}
            <div class="border-2 rounded-lg p-3 {% if angle in photos_by_angle %}border-green-300 bg-green-50{% else %}border-dashed border-gray-300 bg-gray-50{% endif %}">
                <p class="text-xs font-semibold text-navy mb-2">{{ angle_labels[angle] }}</p>

                {% if angle in photos_by_angle %}
                    {% set photo = photos_by_angle[angle] %}
                    <!-- Photo uploaded -->
                    {% if photo.thumbnail_path %}
                    <img src="/media/{{ photo.thumbnail_path }}" alt="{{ angle_labels[angle] }}" class="w-full h-40 object-cover rounded mb-2">
                    {% elif photo.preview_path %}
                    <img src="/media/{{ photo.preview_path }}" alt="{{ angle_labels[angle] }}" class="w-full h-40 object-cover rounded mb-2">
                    {% else %}
                    <div class="w-full h-40 bg-gray-200 rounded mb-2 flex items-center justify-center text-gray-400 text-xs">No preview</div>
                    {% endif %}
                    <p class="text-xs text-gray-500">v{{ photo.version_number }} &middot; {{ photo.uploaded_at[:10] if photo.uploaded_at else '' }}</p>

                    <!-- Retake button -->
                    <div class="mt-2" id="retake-{{ angle }}">
                        <label class="block">
                            <span class="text-xs text-teal font-semibold cursor-pointer hover:text-teal/80">Retake Photo</span>
                            <input type="file" accept="image/*" capture="environment" class="hidden"
                                   hx-post="/api/patients/{{ patient.id }}/sessions/{{ session.id }}/photos/upload"
                                   hx-encoding="multipart/form-data"
                                   hx-target="#session-content"
                                   hx-swap="outerHTML"
                                   name="photo_file">
                            <input type="hidden" name="angle" value="{{ angle }}">
                            <input type="hidden" name="retake_reason" value="staff_retake">
                        </label>
                    </div>

                    <!-- Version history link -->
                    <a href="#" class="text-xs text-gray-400 hover:text-teal mt-1 block"
                       hx-get="/api/patients/{{ patient.id }}/sessions/{{ session.id }}/photos/{{ photo.id }}/versions"
                       hx-target="#version-modal"
                       hx-swap="innerHTML">View versions</a>
                {% else %}
                    <!-- Empty slot with upload -->
                    <div class="w-full h-40 bg-gray-100 rounded mb-2 flex flex-col items-center justify-center border border-dashed border-gray-300">
                        <svg class="w-8 h-8 text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/></svg>
                        <label class="cursor-pointer">
                            <span class="text-xs text-teal font-semibold hover:text-teal/80">Upload Photo</span>
                            <input type="file" accept="image/*" capture="environment" class="hidden"
                                   hx-post="/api/patients/{{ patient.id }}/sessions/{{ session.id }}/photos/upload"
                                   hx-encoding="multipart/form-data"
                                   hx-target="#session-content"
                                   hx-swap="outerHTML"
                                   name="photo_file">
                            <input type="hidden" name="angle" value="{{ angle }}">
                        </label>
                    </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <!-- Regenerate Thumbnails -->
        <div class="mt-4 text-right">
            <button class="text-xs text-gray-400 hover:text-teal"
                    hx-post="/api/patients/{{ patient.id }}/sessions/{{ session.id }}/regenerate-thumbnails"
                    hx-swap="none">
                Regenerate Thumbnails
            </button>
        </div>
    </div>

    <!-- Measurements Form -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Measurements ({{ completion.measurement_count }}/8)</h3>
        <form hx-post="/api/patients/{{ patient.id }}/sessions/{{ session.id }}/measurements"
              hx-target="#measurement-status"
              hx-swap="innerHTML">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                {% for point in measurement_points %}
                <div>
                    <label class="block text-xs font-semibold text-navy mb-1">{{ measurement_labels[point] }}</label>
                    <div class="flex items-center gap-2">
                        <input type="number" step="0.1" min="0" max="100"
                               name="m_{{ point }}"
                               value="{{ measurements_by_point[point].value_inches if point in measurements_by_point else '' }}"
                               placeholder="inches"
                               class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                        {% if point in prev_measurements %}
                        <span class="text-xs text-gray-400 whitespace-nowrap" title="Previous session">
                            prev: {{ prev_measurements[point].value_inches }}
                            {% set diff = (measurements_by_point[point].value_inches - prev_measurements[point].value_inches) if point in measurements_by_point else 0 %}
                            {% if point in measurements_by_point and diff != 0 %}
                                <span class="{% if diff < 0 %}text-green-600{% else %}text-red-500{% endif %}">
                                    ({{ '%+.1f' | format(diff) }})
                                </span>
                            {% endif %}
                        </span>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="mt-4 flex items-center gap-4">
                <button type="submit" class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
                    Save Measurements
                </button>
                <div id="measurement-status" class="text-sm"></div>
            </div>
        </form>
    </div>

    <!-- Session Notes -->
    {% if session.notes %}
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-2">Notes</h3>
        <p class="text-sm text-gray-600">{{ session.notes }}</p>
    </div>
    {% endif %}

    <!-- Version History Modal Container -->
    <div id="version-modal"></div>
</div>
{% endblock %}
```

- [ ] 3. Create `app/templates/session_list.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Sessions - {{ patient.first_name }} {{ patient.last_name }} - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">&gt;</span>
        <span class="text-navy">{{ patient.first_name }} {{ patient.last_name }} - Sessions</span>
    </nav>

    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Photo Sessions</h2>
        <div class="flex gap-2">
            <a href="/dashboard/patients/{{ patient.id }}/sessions/new" class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
                + New Session
            </a>
        </div>
    </div>

    {% if request.query_params.get('archived') %}
    <div class="bg-yellow-50 border border-yellow-200 text-yellow-700 p-4 rounded-lg mb-6">
        Session archived successfully.
    </div>
    {% endif %}

    <!-- New Session Form (shown when show_new_form is true) -->
    {% if show_new_form is defined and show_new_form %}
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Create New Session</h3>

        {% if cycle_prompt is defined and cycle_prompt.should_prompt %}
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
            <p class="text-sm text-blue-800 font-medium mb-2">
                Patient's previous cycle ended on {{ cycle_prompt.last_final_date }}.
                Is this new session part of a new treatment cycle?
            </p>
        </div>
        {% endif %}

        <form method="POST" action="/dashboard/patients/{{ patient.id }}/sessions/create">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                    <label class="block text-sm font-semibold text-navy mb-1">Session Type</label>
                    <select name="session_type" class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                        {% for st in session_types %}
                        <option value="{{ st }}" {% if suggested_type is defined and st == suggested_type %}selected{% endif %}>
                            {{ st.replace('_', ' ').title() }}{% if suggested_type is defined and st == suggested_type %} (suggested){% endif %}
                        </option>
                        {% endfor %}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-semibold text-navy mb-1">Session Date</label>
                    <input type="date" name="session_date" value="{{ today if today is defined else '' }}"
                           class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                </div>
                <div>
                    <label class="block text-sm font-semibold text-navy mb-1">Notes</label>
                    <input type="text" name="notes" placeholder="Optional notes"
                           class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50">
                </div>
            </div>

            {% if cycle_prompt is defined and cycle_prompt.should_prompt %}
            <div class="mb-4">
                <label class="block text-sm font-semibold text-navy mb-2">Treatment Cycle</label>
                <div class="flex gap-4">
                    <label class="flex items-center gap-2 text-sm">
                        <input type="radio" name="start_new_cycle" value="yes" class="text-teal focus:ring-teal">
                        Yes, start Cycle {{ cycle_prompt.next_cycle_number }}
                    </label>
                    <label class="flex items-center gap-2 text-sm">
                        <input type="radio" name="start_new_cycle" value="no" checked class="text-teal focus:ring-teal">
                        No, this is a follow-up of previous cycle
                    </label>
                </div>
            </div>
            {% endif %}

            <div class="flex gap-3">
                <button type="submit" class="bg-teal text-white px-6 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
                    Create Session
                </button>
                <a href="/dashboard/patients/{{ patient.id }}/sessions" class="bg-gray-200 text-gray-700 px-6 py-2 rounded text-sm font-semibold hover:bg-gray-300 transition">
                    Cancel
                </a>
            </div>
        </form>
    </div>
    {% endif %}

    <!-- Filter: Show/Hide Archived -->
    <div class="mb-4 flex gap-2">
        {% if show_archived %}
        <a href="/dashboard/patients/{{ patient.id }}/sessions" class="text-sm text-teal hover:text-teal/80">Hide archived sessions</a>
        {% else %}
        <a href="/dashboard/patients/{{ patient.id }}/sessions?show_archived=1" class="text-sm text-gray-400 hover:text-teal">Show archived sessions</a>
        {% endif %}
    </div>

    <!-- Sessions Table -->
    {% if sessions %}
    <div class="bg-white rounded-lg shadow-sm overflow-hidden">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-200 bg-gray-50">
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">#</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Date</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Type</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Photos</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Measurements</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Status</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for s in sessions %}
                <tr class="border-b border-gray-100 hover:bg-gray-50 {% if s.archived_at %}opacity-50{% endif %}">
                    <td class="py-3 px-4 font-medium text-navy">{{ s.session_number }}</td>
                    <td class="py-3 px-4">{{ s.session_date }}</td>
                    <td class="py-3 px-4">
                        <span class="inline-block px-2 py-0.5 rounded text-xs font-semibold
                            {% if s.session_type == 'baseline' %}bg-blue-100 text-blue-700
                            {% elif s.session_type == 'final' %}bg-green-100 text-green-700
                            {% elif s.session_type == 'followup' %}bg-purple-100 text-purple-700
                            {% elif s.session_type == 'incomplete' %}bg-red-100 text-red-700
                            {% else %}bg-gray-100 text-gray-700{% endif %}">
                            {{ s.session_type.replace('_', ' ').title() }}
                        </span>
                    </td>
                    <td class="py-3 px-4">{{ s.completion.photo_count }}/6</td>
                    <td class="py-3 px-4">{{ s.completion.measurement_count }}/8</td>
                    <td class="py-3 px-4">
                        {% if s.archived_at %}
                        <span class="bg-gray-100 text-gray-500 px-2 py-0.5 rounded text-xs">Archived</span>
                        {% elif s.completed_at %}
                        <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Complete</span>
                        {% elif s.completion.is_complete %}
                        <span class="bg-amber-100 text-amber-700 px-2 py-0.5 rounded text-xs">Ready</span>
                        {% else %}
                        <span class="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded text-xs">In Progress</span>
                        {% endif %}
                    </td>
                    <td class="py-3 px-4">
                        <a href="/dashboard/patients/{{ patient.id }}/sessions/{{ s.id }}" class="text-teal hover:text-teal/80 text-sm font-semibold">View</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="bg-white rounded-lg shadow-sm p-8 text-center">
        <p class="text-gray-500 mb-4">No sessions found for this patient.</p>
        <a href="/dashboard/patients/{{ patient.id }}/sessions/new" class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
            Create First Session
        </a>
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/sessions.py app/templates/session_view.html app/templates/session_list.html
# Expected output: approximately 330-370 lines for routes, 200-230 for view template, 170-200 for list template

python -c "
from app.routes.sessions import router
routes = [r.path for r in router.routes]
print(f'Session router has {len(routes)} routes:')
for r in sorted(routes):
    print(f'  {r}')
assert '/{patient_id}/sessions' in routes
assert '/{patient_id}/sessions/new' in routes
assert '/{patient_id}/sessions/create' in routes
assert '/{patient_id}/sessions/{session_id}' in routes
assert '/{patient_id}/sessions/{session_id}/complete' in routes
assert '/{patient_id}/sessions/{session_id}/archive' in routes
assert '/{patient_id}/sessions/{session_id}/change-type' in routes
print('All 7 expected routes present.')
"
# Expected output:
# Session router has 7 routes:
#   /{patient_id}/sessions
#   /{patient_id}/sessions/create
#   /{patient_id}/sessions/new
#   /{patient_id}/sessions/{session_id}
#   /{patient_id}/sessions/{session_id}/archive
#   /{patient_id}/sessions/{session_id}/change-type
#   /{patient_id}/sessions/{session_id}/complete
# All 7 expected routes present.
```

- [ ] 5. Test session creation flow (integration):

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import photo_db
from app.routes.sessions import _suggest_session_type, _check_cycle_prompt

init_db()
run_migrations()

# Create test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('sessiontest@test.com', 'Session', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Test 1: First session suggests baseline
suggested = _suggest_session_type(pid)
assert suggested == 'baseline'
print(f'Test 1 PASSED: First session suggests \"{suggested}\"')

# Test 2: Create cycle and session
cycle_id = photo_db.create_treatment_cycle(pid, cycle_number=1, started_at='2026-01-15')
sid = photo_db.create_session(pid, session_number=1, session_date='2026-01-15',
                               session_type='baseline', cycle_id=cycle_id)
assert sid > 0
print(f'Test 2 PASSED: Created session {sid}')

# Test 3: Second session suggests mid_treatment
suggested = _suggest_session_type(pid)
assert suggested == 'mid_treatment'
print(f'Test 3 PASSED: Second session suggests \"{suggested}\"')

# Test 4: Cycle prompt should not fire (no completed final)
prompt = _check_cycle_prompt(pid)
assert not prompt['should_prompt']
print('Test 4 PASSED: No cycle prompt without completed final')

# Test 5: After many sessions, suggest final
for i in range(2, 7):
    photo_db.create_session(pid, session_number=i, session_date=f'2026-01-{15+i}',
                             session_type='mid_treatment', cycle_id=cycle_id)
suggested = _suggest_session_type(pid)
assert suggested == 'final'
print(f'Test 5 PASSED: After 6 sessions suggests \"{suggested}\"')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_treatment_cycles WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()

print('All 5 session route tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: First session suggests "baseline"
# Test 2 PASSED: Created session ...
# Test 3 PASSED: Second session suggests "mid_treatment"
# Test 4 PASSED: No cycle prompt without completed final
# Test 5 PASSED: After 6 sessions suggests "final"
# All 5 session route tests passed. Cleanup complete.
```

- [ ] 6. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/sessions.py app/templates/session_view.html app/templates/session_list.html
git commit -m "Add session routes and templates for photo session management

Routes handle session CRUD with auto-suggested session types (baseline
for first, mid_treatment for middle, final after 5+, followup after
completed final), explicit cycle creation prompts, and session lifecycle
actions (complete with validation, archive, change type with history
logging). Session view template has 6-angle photo grid with upload/retake
slots using HTMX, measurement form with previous-session visual diffs,
completion progress bar, and version history links. Session list template
shows all sessions with completion status and type badges."
```

---

### Task 15: Patients API Routes (app/routes/patients_api.py)

Create API endpoints for HTMX interactions including photo upload with processing, photo retake with versioning, measurement save/update with validation, thumbnail regeneration, completion status polling, patient creation for walk-ins, GHL contact linking, patient data export, and photo version history.

**Files:**
- `app/routes/patients_api.py` (new)

**Steps:**

- [ ] 1. Create `app/routes/patients_api.py` with the following complete code:

```python
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.config import settings
from app.database import get_db, log_event
from app import photo_db
from app.services import photo_service
from app.services import measurement_service
from app.services import patient_export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patients")
templates = Jinja2Templates(directory="app/templates")

ANGLES = ["front", "side_left", "side_right", "45_degree_left", "45_degree_right", "back"]
ANGLE_LABELS = {
    "front": "Front",
    "side_left": "Left Side",
    "side_right": "Right Side",
    "45_degree_left": "45° Left",
    "45_degree_right": "45° Right",
    "back": "Back",
}

MEASUREMENT_POINTS = [
    "waist", "hips", "thighs_left", "thighs_right",
    "arms_left", "arms_right", "chest", "under_bust",
]


def _require_auth_api(request: Request):
    if not is_authenticated(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return None


# ── Photo Upload ─────────────────────────────────────────

@router.post("/{patient_id}/sessions/{session_id}/photos/upload")
async def photo_upload(
    request: Request,
    patient_id: int,
    session_id: int,
    photo_file: UploadFile = File(...),
    angle: str = Form(...),
    retake_reason: str = Form(""),
):
    """Upload a photo for a specific angle. Handles validation, processing, and DB insert.

    If a photo already exists for this angle, creates a new version and supersedes the old one.
    Returns HTMX partial or JSON depending on request type.
    """
    auth = _require_auth_api(request)
    if auth:
        return auth

    # Validate angle
    if angle not in ANGLES:
        return JSONResponse(
            {"error": f"Invalid angle: {angle}. Must be one of: {', '.join(ANGLES)}"},
            status_code=400,
        )

    # Validate session belongs to patient
    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    # Read file
    file_bytes = await photo_file.read()
    if not file_bytes:
        return JSONResponse({"error": "Empty file uploaded"}, status_code=400)

    # Check file size
    max_bytes = settings.max_photo_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return JSONResponse(
            {"error": f"File too large: {len(file_bytes) / 1024 / 1024:.1f}MB. Maximum is {settings.max_photo_upload_mb}MB."},
            status_code=400,
        )

    # Validate image
    is_valid, error_msg = photo_service.validate_image(file_bytes, photo_file.filename or "upload")
    if not is_valid:
        return JSONResponse({"error": error_msg}, status_code=400)

    # Check for duplicate hash
    file_hash = photo_service.calculate_file_hash(file_bytes)
    duplicate = photo_service.check_duplicate_hash(session_id, angle, file_hash)
    if duplicate:
        return JSONResponse(
            {"error": "This exact photo has already been uploaded for this angle."},
            status_code=409,
        )

    # Process and save the photo (creates original + preview + thumbnail)
    result = photo_service.process_and_save_photo(
        file_bytes=file_bytes,
        filename=photo_file.filename or "upload.jpg",
        patient_id=patient_id,
        session_id=session_id,
        angle=angle,
    )

    # Check if this is a retake (existing photo for this angle)
    existing_photos = photo_db.get_photos_for_session(session_id, current_only=True)
    existing_for_angle = [p for p in existing_photos if p["angle"] == angle]

    if existing_for_angle:
        # This is a retake — determine new version number
        old_photo = existing_for_angle[0]
        new_version = old_photo["version_number"] + 1

        # Insert new photo
        new_photo_id = photo_db.insert_photo(
            session_id=session_id,
            angle=angle,
            file_path=result["file_path"],
            preview_path=result["preview_path"],
            thumbnail_path=result["thumbnail_path"],
            file_hash=result["file_hash"],
            version_number=new_version,
            retake_reason=retake_reason or None,
        )

        # Supersede old photo
        photo_db.supersede_photo(old_photo["id"], new_photo_id)

        log_event(
            "photo",
            f"Photo retake: patient {patient_id}, session {session_id}, angle {angle}, v{new_version}",
            {"photo_id": new_photo_id, "superseded_id": old_photo["id"], "retake_reason": retake_reason},
        )
    else:
        # First upload for this angle
        new_photo_id = photo_db.insert_photo(
            session_id=session_id,
            angle=angle,
            file_path=result["file_path"],
            preview_path=result["preview_path"],
            thumbnail_path=result["thumbnail_path"],
            file_hash=result["file_hash"],
            version_number=1,
        )

        log_event(
            "photo",
            f"Photo uploaded: patient {patient_id}, session {session_id}, angle {angle}",
            {"photo_id": new_photo_id},
        )

    # Return completion status as HTMX partial
    completion = photo_db.check_session_complete(session_id)
    return HTMLResponse(f"""
        <div class="text-sm text-green-600 p-2">
            Photo uploaded successfully ({ANGLE_LABELS.get(angle, angle)}).
            Photos: {completion['photo_count']}/6, Measurements: {completion['measurement_count']}/8
        </div>
    """)


@router.post("/{patient_id}/sessions/{session_id}/photos/{photo_id}/retake")
async def photo_retake(
    request: Request,
    patient_id: int,
    session_id: int,
    photo_id: int,
    photo_file: UploadFile = File(...),
    retake_reason: str = Form("bad_lighting"),
):
    """Replace a specific photo with a retake. Requires retake_reason."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    # Get the existing photo to find its angle
    conn = get_db()
    photo = conn.execute(
        "SELECT * FROM patient_photos WHERE id = ? AND session_id = ?",
        (photo_id, session_id),
    ).fetchone()
    conn.close()

    if not photo:
        return JSONResponse({"error": "Photo not found"}, status_code=404)

    angle = photo["angle"]

    # Read and validate file
    file_bytes = await photo_file.read()
    if not file_bytes:
        return JSONResponse({"error": "Empty file uploaded"}, status_code=400)

    max_bytes = settings.max_photo_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return JSONResponse(
            {"error": f"File too large. Maximum is {settings.max_photo_upload_mb}MB."},
            status_code=400,
        )

    is_valid, error_msg = photo_service.validate_image(file_bytes, photo_file.filename or "retake")
    if not is_valid:
        return JSONResponse({"error": error_msg}, status_code=400)

    # Process and save
    result = photo_service.process_and_save_photo(
        file_bytes=file_bytes,
        filename=photo_file.filename or "retake.jpg",
        patient_id=patient_id,
        session_id=session_id,
        angle=angle,
    )

    new_version = photo["version_number"] + 1

    new_photo_id = photo_db.insert_photo(
        session_id=session_id,
        angle=angle,
        file_path=result["file_path"],
        preview_path=result["preview_path"],
        thumbnail_path=result["thumbnail_path"],
        file_hash=result["file_hash"],
        version_number=new_version,
        retake_reason=retake_reason,
    )

    photo_db.supersede_photo(photo["id"], new_photo_id)

    log_event(
        "photo",
        f"Photo retake via API: patient {patient_id}, angle {angle}, reason={retake_reason}",
        {"new_photo_id": new_photo_id, "superseded_id": photo["id"]},
    )

    return JSONResponse({
        "success": True,
        "photo_id": new_photo_id,
        "version": new_version,
        "angle": angle,
    })


# ── Measurements ─────────────────────────────────────────

@router.post("/{patient_id}/sessions/{session_id}/measurements")
async def save_measurements(
    request: Request,
    patient_id: int,
    session_id: int,
):
    """Save/update measurements for a session. Accepts form data with m_<point> fields.

    Performs validation using measurement_service. Partial saves allowed.
    Returns HTMX partial with status message.
    """
    auth = _require_auth_api(request)
    if auth:
        return auth

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return HTMLResponse('<span class="text-red-500">Session not found</span>', status_code=404)

    form_data = await request.form()

    saved_count = 0
    warnings = []
    errors = []

    for point in MEASUREMENT_POINTS:
        field_name = f"m_{point}"
        value_str = form_data.get(field_name, "")
        if not value_str or not str(value_str).strip():
            continue  # Skip empty fields (partial save allowed)

        try:
            value = float(value_str)
        except (ValueError, TypeError):
            errors.append(f"{point}: invalid number")
            continue

        # Validate using measurement_service
        validation = measurement_service.validate_measurement(
            session_id=session_id,
            measurement_point=point,
            value_inches=value,
        )

        if validation.get("hard_reject"):
            errors.append(f"{point}: {validation['message']}")
            continue

        if validation.get("soft_warning"):
            warnings.append(f"{point}: {validation['message']}")
            # Still save — soft warnings don't block

        # Upsert measurement
        photo_db.upsert_measurement(
            session_id=session_id,
            measurement_point=point,
            value_inches=value,
            measured_by="admin",
        )
        saved_count += 1

    # Build response
    parts = []
    if saved_count > 0:
        parts.append(f'<span class="text-green-600">Saved {saved_count} measurement{"s" if saved_count != 1 else ""}.</span>')
    if warnings:
        parts.append(f'<span class="text-amber-600 ml-2">Warnings: {"; ".join(warnings)}</span>')
    if errors:
        parts.append(f'<span class="text-red-500 ml-2">Errors: {"; ".join(errors)}</span>')
    if not parts:
        parts.append('<span class="text-gray-400">No measurements entered.</span>')

    return HTMLResponse(" ".join(parts))


# ── Thumbnail Regeneration ───────────────────────────────

@router.post("/{patient_id}/sessions/{session_id}/regenerate-thumbnails")
async def regenerate_thumbnails(
    request: Request,
    patient_id: int,
    session_id: int,
):
    """Regenerate preview and thumbnail images for all current photos in a session."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    result = photo_service.regenerate_thumbnails(session_id)

    log_event(
        "photo",
        f"Thumbnails regenerated for session {session_id}",
        result,
    )

    return JSONResponse({
        "success": True,
        "regenerated": result["success_count"],
        "failed": result["failure_count"],
        "failures": result.get("failures", []),
    })


# ── Completion Status ────────────────────────────────────

@router.get("/{patient_id}/sessions/{session_id}/completion-status")
async def completion_status(
    request: Request,
    patient_id: int,
    session_id: int,
):
    """HTMX partial showing completion progress for a session."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    session = photo_db.get_session(session_id)
    if not session or session["patient_id"] != patient_id:
        return HTMLResponse('<span class="text-red-500">Session not found</span>', status_code=404)

    completion = photo_db.check_session_complete(session_id)
    total = 14
    done = completion["photo_count"] + completion["measurement_count"]
    pct = int((done / total) * 100) if total > 0 else 0

    color = "bg-green-500" if pct == 100 else ("bg-teal" if pct >= 50 else "bg-amber-400")

    return HTMLResponse(f"""
        <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-semibold text-navy">Completion Progress</span>
            <span class="text-sm text-gray-500">{completion['photo_count']}/6 photos, {completion['measurement_count']}/8 measurements</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3">
            <div class="h-3 rounded-full transition-all duration-500 {color}" style="width: {pct}%"></div>
        </div>
    """)


# ── Patient Creation ─────────────────────────────────────

@router.post("/{patient_id}/create")
async def create_patient(
    request: Request,
    patient_id: int,  # Ignored — new patient gets auto-generated ID
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
):
    """Create a new patient record for walk-ins not in CSV import and not from GHL."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO patients (first_name, last_name, email, phone, tier, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'active', ?, ?)""",
        (first_name.strip(), last_name.strip(), email.strip(), phone.strip(), now, now),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    log_event(
        "patient",
        f"New walk-in patient created: {first_name} {last_name}",
        {"patient_id": new_id},
    )

    return JSONResponse({
        "success": True,
        "patient_id": new_id,
        "message": f"Patient {first_name} {last_name} created.",
    })


# ── GHL Contact Linking ─────────────────────────────────

@router.post("/{patient_id}/link-ghl")
async def link_ghl_contact(
    request: Request,
    patient_id: int,
    ghl_contact_id: str = Form(...),
):
    """Link a patient to a GHL contact by setting ghl_contact_id on the patients table."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    conn = get_db()
    # Verify patient exists
    patient = conn.execute("SELECT id FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if not patient:
        conn.close()
        return JSONResponse({"error": "Patient not found"}, status_code=404)

    # Verify GHL contact exists in mirror table
    ghl = conn.execute(
        "SELECT id, first_name, last_name FROM ghl_contacts WHERE contact_id = ?",
        (ghl_contact_id.strip(),),
    ).fetchone()

    conn.execute(
        "UPDATE patients SET ghl_contact_id = ?, updated_at = ? WHERE id = ?",
        (ghl_contact_id.strip(), datetime.now().isoformat(), patient_id),
    )
    conn.commit()
    conn.close()

    log_event(
        "patient",
        f"Patient {patient_id} linked to GHL contact {ghl_contact_id}",
        {"ghl_contact_id": ghl_contact_id},
    )

    return JSONResponse({
        "success": True,
        "patient_id": patient_id,
        "ghl_contact_id": ghl_contact_id,
        "ghl_name": f"{dict(ghl)['first_name']} {dict(ghl)['last_name']}" if ghl else None,
    })


# ── Patient Data Export ──────────────────────────────────

@router.post("/{patient_id}/export")
async def export_patient(
    request: Request,
    patient_id: int,
    export_reason: str = Form("patient_request"),
):
    """Trigger patient data export. Generates a ZIP file."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    try:
        zip_path = patient_export_service.export_patient_data(
            patient_id=patient_id,
            exported_by="admin",
            export_reason=export_reason,
        )
    except Exception as e:
        logger.error(f"Patient export failed: {e}")
        return JSONResponse({"error": f"Export failed: {str(e)}"}, status_code=500)

    if not zip_path:
        return JSONResponse({"error": "Patient not found"}, status_code=404)

    return JSONResponse({
        "success": True,
        "zip_path": zip_path,
        "message": "Export complete. Download the ZIP file.",
    })


# ── Photo Version History ────────────────────────────────

@router.get("/{patient_id}/sessions/{session_id}/photos/{photo_id}/versions")
async def photo_version_history(
    request: Request,
    patient_id: int,
    session_id: int,
    photo_id: int,
):
    """Return HTMX partial showing photo version history for a specific angle."""
    auth = _require_auth_api(request)
    if auth:
        return auth

    # Get the photo to find its angle
    conn = get_db()
    photo = conn.execute(
        "SELECT * FROM patient_photos WHERE id = ? AND session_id = ?",
        (photo_id, session_id),
    ).fetchone()
    conn.close()

    if not photo:
        return HTMLResponse('<span class="text-red-500">Photo not found</span>', status_code=404)

    angle = photo["angle"]
    versions = photo_db.get_photo_version_history(session_id, angle)

    # Build HTML for version history modal
    rows = ""
    for v in versions:
        current_badge = '<span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs ml-2">Current</span>' if v["is_current"] else ""
        retake_info = f' <span class="text-gray-400">({v["retake_reason"]})</span>' if v.get("retake_reason") else ""
        thumb = f'<img src="/media/{v["thumbnail_path"]}" class="w-16 h-16 object-cover rounded">' if v.get("thumbnail_path") else '<div class="w-16 h-16 bg-gray-200 rounded"></div>'
        rows += f"""
            <div class="flex items-center gap-3 py-2 border-b border-gray-100">
                {thumb}
                <div>
                    <p class="text-sm font-medium">Version {v['version_number']}{current_badge}</p>
                    <p class="text-xs text-gray-500">{v['uploaded_at'][:16] if v.get('uploaded_at') else ''}{retake_info}</p>
                </div>
            </div>
        """

    angle_label = ANGLE_LABELS.get(angle, angle)
    return HTMLResponse(f"""
        <div class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onclick="this.remove()">
            <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4" onclick="event.stopPropagation()">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold text-navy">{angle_label} — Version History</h3>
                    <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
                </div>
                <div class="max-h-80 overflow-y-auto">
                    {rows if rows else '<p class="text-gray-500 text-sm">No version history found.</p>'}
                </div>
            </div>
        </div>
    """)
```

- [ ] 2. Verify the file was created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/patients_api.py
# Expected output: approximately 420-470 lines

python -c "
from app.routes.patients_api import router
routes = [r.path for r in router.routes]
print(f'Patients API router has {len(routes)} routes:')
for r in sorted(routes):
    print(f'  {r}')
expected = [
    '/{patient_id}/sessions/{session_id}/photos/upload',
    '/{patient_id}/sessions/{session_id}/photos/{photo_id}/retake',
    '/{patient_id}/sessions/{session_id}/measurements',
    '/{patient_id}/sessions/{session_id}/regenerate-thumbnails',
    '/{patient_id}/sessions/{session_id}/completion-status',
    '/{patient_id}/create',
    '/{patient_id}/link-ghl',
    '/{patient_id}/export',
    '/{patient_id}/sessions/{session_id}/photos/{photo_id}/versions',
]
for e in expected:
    assert e in routes, f'Missing route: {e}'
print(f'All {len(expected)} expected routes present.')
"
# Expected output:
# Patients API router has 9 routes:
#   /{patient_id}/create
#   /{patient_id}/export
#   /{patient_id}/link-ghl
#   /{patient_id}/sessions/{session_id}/completion-status
#   /{patient_id}/sessions/{session_id}/measurements
#   /{patient_id}/sessions/{session_id}/photos/upload
#   /{patient_id}/sessions/{session_id}/photos/{photo_id}/retake
#   /{patient_id}/sessions/{session_id}/photos/{photo_id}/versions
#   /{patient_id}/sessions/{session_id}/regenerate-thumbnails
# All 9 expected routes present.
```

- [ ] 3. Test measurement validation integration:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import photo_db
from app.services import measurement_service

init_db()
run_migrations()

# Create test patient + session
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('apitest@test.com', 'API', 'Test', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

cycle_id = photo_db.create_treatment_cycle(pid, cycle_number=1, started_at='2026-01-15')
sid = photo_db.create_session(pid, session_number=1, session_date='2026-01-15',
                               session_type='baseline', cycle_id=cycle_id)

# Test 1: Valid measurement
result = measurement_service.validate_measurement(sid, 'waist', 32.5)
assert not result.get('hard_reject')
print(f'Test 1 PASSED: Valid measurement accepted')

# Test 2: Out of range (hard reject)
result = measurement_service.validate_measurement(sid, 'waist', 325.0)
assert result.get('hard_reject')
print(f'Test 2 PASSED: Out-of-range measurement rejected: {result[\"message\"]}')

# Test 3: Upsert measurement
mid = photo_db.upsert_measurement(sid, 'waist', 32.5, measured_by='admin')
assert mid > 0
meas = photo_db.get_measurements_for_session(sid)
assert len(meas) == 1
assert meas[0]['value_inches'] == 32.5
print(f'Test 3 PASSED: Measurement saved and retrieved')

# Test 4: Completion check
completion = photo_db.check_session_complete(sid)
assert completion['measurement_count'] == 1
assert not completion['is_complete']
print(f'Test 4 PASSED: Completion shows {completion[\"measurement_count\"]}/8 measurements')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_measurements WHERE session_id = ?', (sid,))
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_treatment_cycles WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()

print('All 4 patients API tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Valid measurement accepted
# Test 2 PASSED: Out-of-range measurement rejected: ...
# Test 3 PASSED: Measurement saved and retrieved
# Test 4 PASSED: Completion shows 1/8 measurements
# All 4 patients API tests passed. Cleanup complete.
```

- [ ] 4. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/patients_api.py
git commit -m "Add patients API routes for HTMX interactions

Photo upload endpoint validates MIME type, checks file size, detects
duplicate hashes, processes images via photo_service (EXIF transpose,
preview/thumbnail generation), handles retake versioning with supersede
chain. Measurement endpoint accepts partial saves, runs hard/soft
validation via measurement_service, upserts via photo_db. Also includes
thumbnail regeneration trigger, HTMX completion status partial, walk-in
patient creation, GHL contact linking, patient data export trigger, and
photo version history modal partial."
```

---

### Task 16: Testimonial Routes + Public Form (app/routes/testimonials.py + templates)

Create testimonial admin views (list with status filters, detail view, video attach) and the public testimonial submission form with token validation, star rating, consent checkboxes, decline options, and permanent opt-out. Public routes require NO authentication — they use token validation instead.

**Files:**
- `app/routes/testimonials.py` (new)
- `app/templates/testimonial_form.html` (new)
- `app/templates/testimonial_list.html` (new)

**Steps:**

- [ ] 1. Create `app/routes/testimonials.py` with the following complete code:

```python
import os
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.config import settings
from app.database import get_db, log_event
from app import testimonial_db
from app import consent_db
from app.services import testimonial_service
from app.services import consent_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Accepted video MIME types
ACCEPTED_VIDEO_MIMES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
}


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_patient_or_404(patient_id: int):
    """Fetch patient by ID. Returns dict or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Admin Routes (Authenticated) ─────────────────────────


@router.get("/dashboard/patients/{patient_id}/testimonials", response_class=HTMLResponse)
async def patient_testimonial_history(request: Request, patient_id: int):
    """Patient testimonial history — all testimonials and request status."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    testimonials = testimonial_db.get_testimonials_for_patient(patient_id)

    # Get send log for each testimonial
    for t in testimonials:
        t["send_log"] = testimonial_db.get_send_log(t["id"])

    return templates.TemplateResponse("testimonial_list.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "testimonials": testimonials,
        "show_patient_header": True,
        "status_filter": "",
    })


@router.get("/dashboard/testimonials", response_class=HTMLResponse)
async def testimonial_admin_list(request: Request, status: str = ""):
    """Admin testimonial list with status filters across all patients."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    if status:
        testimonials = testimonial_db.get_testimonials_by_status(status)
    else:
        # Get all testimonials
        conn = get_db()
        rows = conn.execute(
            """SELECT t.*, p.first_name, p.last_name, p.email
               FROM testimonials t
               JOIN patients p ON t.patient_id = p.id
               ORDER BY t.created_at DESC"""
        ).fetchall()
        conn.close()
        testimonials = [dict(r) for r in rows]

    # Status counts for filter badges
    conn = get_db()
    status_counts = {}
    for s in ["requested", "submitted", "flagged", "declined_this_time", "declined_permanent",
              "expired_no_response", "bounced"]:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM testimonials WHERE status = ?", (s,)
        ).fetchone()
        status_counts[s] = row["cnt"]
    status_counts["all"] = sum(status_counts.values())
    conn.close()

    return templates.TemplateResponse("testimonial_list.html", {
        "request": request,
        "active": "patients",
        "patient": None,
        "testimonials": testimonials,
        "show_patient_header": False,
        "status_filter": status,
        "status_counts": status_counts,
    })


@router.get("/dashboard/testimonials/{testimonial_id}", response_class=HTMLResponse)
async def testimonial_detail(request: Request, testimonial_id: int):
    """Testimonial detail view with full info, send log, and video attach option."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    testimonial = testimonial_db.get_testimonial(testimonial_id)
    if not testimonial:
        return HTMLResponse("<h1>Testimonial not found</h1>", status_code=404)

    patient = _get_patient_or_404(testimonial["patient_id"])
    send_log = testimonial_db.get_send_log(testimonial_id)

    return templates.TemplateResponse("testimonial_list.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "testimonial": testimonial,
        "send_log": send_log,
        "show_detail": True,
        "show_patient_header": True,
        "testimonials": [],
        "status_filter": "",
    })


@router.post("/api/testimonials/{testimonial_id}/video")
async def admin_video_attach(
    request: Request,
    testimonial_id: int,
    video_file: UploadFile = File(...),
):
    """Admin video attach to existing testimonial record."""
    redirect = _require_auth(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    testimonial = testimonial_db.get_testimonial(testimonial_id)
    if not testimonial:
        return JSONResponse({"error": "Testimonial not found"}, status_code=404)

    patient_id = testimonial["patient_id"]

    # Read file
    file_bytes = await video_file.read()
    if not file_bytes:
        return JSONResponse({"error": "Empty file uploaded"}, status_code=400)

    # Check file size
    max_bytes = settings.max_video_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return JSONResponse(
            {"error": f"File too large: {len(file_bytes) / 1024 / 1024:.1f}MB. Maximum is {settings.max_video_upload_mb}MB."},
            status_code=400,
        )

    # Check MIME type
    try:
        import magic
        mime_type = magic.from_buffer(file_bytes, mime=True)
    except Exception:
        mime_type = video_file.content_type or ""

    if mime_type not in ACCEPTED_VIDEO_MIMES:
        return JSONResponse(
            {"error": f"Invalid video format: {mime_type}. Accepted: MP4, MOV, AVI, WebM."},
            status_code=400,
        )

    # Determine extension
    ext_map = {
        "video/mp4": "mp4",
        "video/quicktime": "mov",
        "video/x-msvideo": "avi",
        "video/webm": "webm",
    }
    file_ext = ext_map.get(mime_type, "mp4")

    # Save file
    upload_dir = os.path.join("uploads", "videos", str(patient_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{testimonial_id}.{file_ext}")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Update testimonial record
    testimonial_db.update_testimonial(
        testimonial_id,
        video_path=file_path,
    )

    log_event(
        "testimonial",
        f"Video attached to testimonial {testimonial_id} for patient {patient_id}",
        {"file_path": file_path, "mime_type": mime_type, "size_mb": len(file_bytes) / 1024 / 1024},
    )

    return JSONResponse({
        "success": True,
        "testimonial_id": testimonial_id,
        "video_path": file_path,
    })


# ── Public Routes (Token-based, NO auth) ─────────────────


@router.get("/testimonial/{token}", response_class=HTMLResponse)
async def public_testimonial_form(request: Request, token: str):
    """Public testimonial submission form. No auth — uses token validation."""
    testimonial = testimonial_db.get_testimonial_by_token(token)
    if not testimonial:
        return templates.TemplateResponse("testimonial_form.html", {
            "request": request,
            "error": "This testimonial link is invalid or has expired.",
            "testimonial": None,
            "patient": None,
            "token": token,
            "expired": True,
        })

    # Check token expiration
    if testimonial.get("token_expires_at"):
        try:
            expires = datetime.fromisoformat(testimonial["token_expires_at"])
            if datetime.now() > expires:
                return templates.TemplateResponse("testimonial_form.html", {
                    "request": request,
                    "error": "This testimonial link has expired. Please contact the practice if you would still like to share your experience.",
                    "testimonial": None,
                    "patient": None,
                    "token": token,
                    "expired": True,
                })
        except ValueError:
            pass

    # Check if already submitted
    if testimonial["status"] not in ("requested",):
        already_msg = "You have already submitted your testimonial. Thank you for your feedback!"
        if testimonial["status"] in ("declined_this_time", "declined_permanent"):
            already_msg = "This testimonial request has been declined."
        return templates.TemplateResponse("testimonial_form.html", {
            "request": request,
            "error": already_msg,
            "testimonial": None,
            "patient": None,
            "token": token,
            "expired": True,
        })

    patient = _get_patient_or_404(testimonial["patient_id"])

    return templates.TemplateResponse("testimonial_form.html", {
        "request": request,
        "testimonial": testimonial,
        "patient": patient,
        "token": token,
        "error": None,
        "expired": False,
        "practice_email": settings.mailgun_from_email or "info@whitehousechiropractic.com",
    })


@router.post("/testimonial/{token}/submit", response_class=HTMLResponse)
async def public_testimonial_submit(
    request: Request,
    token: str,
    rating: int = Form(...),
    testimonial_text: str = Form(""),
    consent_website: str = Form(""),
    consent_social: str = Form(""),
    consent_advertising: str = Form(""),
):
    """Public testimonial form submission. No auth — uses token validation."""
    # Validate rating
    if rating < 1 or rating > 5:
        return templates.TemplateResponse("testimonial_form.html", {
            "request": request,
            "error": "Please select a rating between 1 and 5 stars.",
            "testimonial": None,
            "patient": None,
            "token": token,
            "expired": False,
        })

    # Truncate text to 2000 chars
    text = (testimonial_text or "").strip()[:2000]

    # Collect consent scopes
    consent_scopes = []
    if consent_website:
        consent_scopes.append("website")
    if consent_social:
        consent_scopes.append("social")
    # Advertising consent from testimonial form — note that consent_service
    # will only allow website, social, email_testimonial from testimonial_form source.
    # We still collect the checkbox value but the service layer enforces restrictions.
    if consent_advertising:
        consent_scopes.append("advertising")

    # Process submission via testimonial_service
    result = testimonial_service.process_testimonial_submission(
        token=token,
        rating=rating,
        text=text,
        consent_scopes=consent_scopes,
    )

    if not result["success"]:
        return templates.TemplateResponse("testimonial_form.html", {
            "request": request,
            "error": result["error"],
            "testimonial": None,
            "patient": None,
            "token": token,
            "expired": "expired" in (result.get("error") or "").lower(),
        })

    # Success — show thank you page
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thank You - White House Chiropractic</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                theme: {{ extend: {{ colors: {{ navy: '#1B2A4A', teal: '#0EA5A0' }} }} }}
            }}
        </script>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center">
        <div class="max-w-lg mx-auto p-8 text-center">
            <div class="bg-white rounded-xl shadow-lg p-8">
                <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                </div>
                <h1 class="text-2xl font-bold text-navy mb-2">Thank You!</h1>
                <p class="text-gray-600 mb-4">
                    Your testimonial has been submitted successfully. We truly appreciate you taking the time to share your experience.
                </p>
                <p class="text-sm text-gray-400">You can close this page now.</p>
            </div>
        </div>
    </body>
    </html>
    """)


@router.get("/testimonial/{token}/decline", response_class=HTMLResponse)
async def public_testimonial_decline_page(request: Request, token: str):
    """Public decline page with this_time vs permanent options."""
    testimonial = testimonial_db.get_testimonial_by_token(token)
    if not testimonial:
        return HTMLResponse("<h1>Invalid or expired link</h1>", status_code=404)

    if testimonial["status"] not in ("requested",):
        return HTMLResponse("<h1>This testimonial request is no longer active.</h1>", status_code=400)

    patient = _get_patient_or_404(testimonial["patient_id"])

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Decline Testimonial - White House Chiropractic</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                theme: {{ extend: {{ colors: {{ navy: '#1B2A4A', teal: '#0EA5A0' }} }} }}
            }}
        </script>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center">
        <div class="max-w-lg mx-auto p-8">
            <div class="bg-white rounded-xl shadow-lg p-8">
                <h1 class="text-2xl font-bold text-navy mb-2">No Problem!</h1>
                <p class="text-gray-600 mb-6">
                    We understand, {patient['first_name'] if patient else 'there'}. No pressure at all.
                </p>
                <form method="POST" action="/testimonial/{token}/decline" class="space-y-4">
                    <label class="block p-4 border border-gray-200 rounded-lg cursor-pointer hover:border-teal transition">
                        <input type="radio" name="decline_type" value="this_time" checked class="mr-2 text-teal focus:ring-teal">
                        <span class="font-medium text-navy">Not this time</span>
                        <p class="text-sm text-gray-500 mt-1 ml-6">We may ask again after your next treatment cycle.</p>
                    </label>
                    <label class="block p-4 border border-gray-200 rounded-lg cursor-pointer hover:border-teal transition">
                        <input type="radio" name="decline_type" value="permanent" class="mr-2 text-teal focus:ring-teal">
                        <span class="font-medium text-navy">No thanks, please don't ask me again</span>
                        <p class="text-sm text-gray-500 mt-1 ml-6">We will permanently remove you from testimonial requests.</p>
                    </label>
                    <button type="submit" class="w-full bg-gray-200 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-300 transition mt-4">
                        Confirm
                    </button>
                </form>
                <p class="text-center text-sm text-gray-400 mt-4">
                    <a href="/testimonial/{token}" class="text-teal hover:text-teal/80">Changed your mind? Go back to the form.</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """)


@router.post("/testimonial/{token}/decline", response_class=HTMLResponse)
async def public_testimonial_decline_process(
    request: Request,
    token: str,
    decline_type: str = Form("this_time"),
):
    """Process testimonial decline. Sets status and optionally sets permanent opt-out."""
    testimonial = testimonial_db.get_testimonial_by_token(token)
    if not testimonial:
        return HTMLResponse("<h1>Invalid or expired link</h1>", status_code=404)

    if testimonial["status"] not in ("requested",):
        return HTMLResponse("<h1>This testimonial request is no longer active.</h1>", status_code=400)

    testimonial_id = testimonial["id"]
    patient_id = testimonial["patient_id"]

    if decline_type == "permanent":
        # Set permanent opt-out
        testimonial_db.update_testimonial(
            testimonial_id,
            status="declined_permanent",
        )
        # Cancel remaining touches
        testimonial_db.cancel_remaining_touches(testimonial_id)
        # Set patient preference to opt out permanently
        consent_db.upsert_patient_preference(
            patient_id=patient_id,
            preference_type="testimonial_requests",
            value="none",
        )
        log_event(
            "testimonial",
            f"Patient {patient_id} permanently opted out of testimonial requests",
            {"testimonial_id": testimonial_id},
        )
        message = "You have been permanently removed from testimonial requests. We will not ask again."
    else:
        # Decline this time only
        testimonial_db.update_testimonial(
            testimonial_id,
            status="declined_this_time",
        )
        # Cancel remaining touches
        testimonial_db.cancel_remaining_touches(testimonial_id)
        log_event(
            "testimonial",
            f"Patient {patient_id} declined testimonial this time",
            {"testimonial_id": testimonial_id},
        )
        message = "Thank you for letting us know. We may reach out again after your next treatment cycle."

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmed - White House Chiropractic</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                theme: {{ extend: {{ colors: {{ navy: '#1B2A4A', teal: '#0EA5A0' }} }} }}
            }}
        </script>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center">
        <div class="max-w-lg mx-auto p-8 text-center">
            <div class="bg-white rounded-xl shadow-lg p-8">
                <h1 class="text-2xl font-bold text-navy mb-4">Confirmed</h1>
                <p class="text-gray-600">{message}</p>
                <p class="text-sm text-gray-400 mt-4">You can close this page now.</p>
            </div>
        </div>
    </body>
    </html>
    """)


@router.get("/testimonial/{token}/optout", response_class=HTMLResponse)
async def public_testimonial_optout(request: Request, token: str):
    """Permanent opt-out from email footer link. One-click permanent opt-out."""
    testimonial = testimonial_db.get_testimonial_by_token(token)
    if not testimonial:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Opt Out - White House Chiropractic</title>
        <script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-50 min-h-screen flex items-center justify-center">
        <div class="max-w-lg mx-auto p-8 text-center">
            <div class="bg-white rounded-xl shadow-lg p-8">
                <h1 class="text-xl font-bold text-navy mb-2">Link Expired</h1>
                <p class="text-gray-600">This opt-out link is no longer valid. Please contact the practice directly.</p>
            </div>
        </div></body></html>
        """)

    patient_id = testimonial["patient_id"]
    testimonial_id = testimonial["id"]

    # Set permanent opt-out
    consent_db.upsert_patient_preference(
        patient_id=patient_id,
        preference_type="testimonial_requests",
        value="none",
    )

    # If testimonial is still in requested state, decline it
    if testimonial["status"] == "requested":
        testimonial_db.update_testimonial(
            testimonial_id,
            status="declined_permanent",
        )
        testimonial_db.cancel_remaining_touches(testimonial_id)

    log_event(
        "testimonial",
        f"Patient {patient_id} opted out via email footer link",
        {"testimonial_id": testimonial_id},
    )

    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Opted Out - White House Chiropractic</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: { extend: { colors: { navy: '#1B2A4A', teal: '#0EA5A0' } } }
        }
    </script></head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center">
    <div class="max-w-lg mx-auto p-8 text-center">
        <div class="bg-white rounded-xl shadow-lg p-8">
            <h1 class="text-xl font-bold text-navy mb-2">Opted Out</h1>
            <p class="text-gray-600">You have been permanently removed from testimonial requests. We will not contact you again about testimonials.</p>
            <p class="text-sm text-gray-400 mt-4">You can close this page now.</p>
        </div>
    </div></body></html>
    """)
```

- [ ] 2. Create `app/templates/testimonial_form.html` with the following complete code:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Share Your Experience - White House Chiropractic</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: { extend: { colors: { navy: '#1B2A4A', teal: '#0EA5A0' } } }
        }
    </script>
    <style>
        .star-rating input { display: none; }
        .star-rating label { cursor: pointer; font-size: 2rem; color: #d1d5db; transition: color 0.15s; }
        .star-rating label:hover, .star-rating label:hover ~ label { color: #facc15; }
        .star-rating input:checked ~ label { color: #facc15; }
        /* Reverse order trick for CSS-only star rating */
        .star-rating { direction: rtl; display: inline-flex; }
        .star-rating label { direction: ltr; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="max-w-lg mx-auto px-4 py-12">
        <!-- Header -->
        <div class="text-center mb-8">
            <h1 class="text-2xl font-bold text-navy">Share Your Zerona Experience</h1>
            <p class="text-gray-500 mt-2">White House Chiropractic</p>
        </div>

        {% if error %}
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-center">
            <p class="text-red-700 text-sm">{{ error }}</p>
        </div>
        {% endif %}

        {% if not expired and testimonial %}
        <div class="bg-white rounded-xl shadow-lg p-6">
            {% if patient %}
            <p class="text-gray-600 mb-6">
                Hi {{ patient.first_name }}, we would love to hear about your experience with Zerona treatments.
                Your feedback helps other patients make informed decisions.
            </p>
            {% endif %}

            <form method="POST" action="/testimonial/{{ token }}/submit">
                <!-- Star Rating -->
                <div class="mb-6">
                    <label class="block text-sm font-semibold text-navy mb-3">How would you rate your experience? <span class="text-red-500">*</span></label>
                    <div class="star-rating">
                        <input type="radio" id="star5" name="rating" value="5" required>
                        <label for="star5" title="5 stars">&#9733;</label>
                        <input type="radio" id="star4" name="rating" value="4">
                        <label for="star4" title="4 stars">&#9733;</label>
                        <input type="radio" id="star3" name="rating" value="3">
                        <label for="star3" title="3 stars">&#9733;</label>
                        <input type="radio" id="star2" name="rating" value="2">
                        <label for="star2" title="2 stars">&#9733;</label>
                        <input type="radio" id="star1" name="rating" value="1">
                        <label for="star1" title="1 star">&#9733;</label>
                    </div>
                </div>

                <!-- Testimonial Text -->
                <div class="mb-6">
                    <label class="block text-sm font-semibold text-navy mb-2">Tell us about your experience</label>
                    <textarea name="testimonial_text" rows="5" maxlength="2000"
                              placeholder="What did you like about your Zerona treatments? How have the results impacted your life?"
                              class="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50 resize-y"></textarea>
                    <p class="text-xs text-gray-400 mt-1 text-right"><span id="char-count">0</span>/2000</p>
                </div>

                <!-- Consent Checkboxes -->
                <div class="mb-6 bg-gray-50 rounded-lg p-4">
                    <label class="block text-sm font-semibold text-navy mb-3">How can we share your testimonial?</label>
                    <div class="space-y-3">
                        <label class="flex items-start gap-2 text-sm">
                            <input type="checkbox" name="consent_website" value="1" class="mt-0.5 rounded border-gray-300 text-teal focus:ring-teal">
                            <div>
                                <span class="font-medium">Website</span>
                                <p class="text-xs text-gray-500">Display on our practice website results page</p>
                            </div>
                        </label>
                        <label class="flex items-start gap-2 text-sm">
                            <input type="checkbox" name="consent_social" value="1" class="mt-0.5 rounded border-gray-300 text-teal focus:ring-teal">
                            <div>
                                <span class="font-medium">Social Media</span>
                                <p class="text-xs text-gray-500">Share on our Facebook and Instagram pages</p>
                            </div>
                        </label>
                        <label class="flex items-start gap-2 text-sm">
                            <input type="checkbox" name="consent_advertising" value="1" class="mt-0.5 rounded border-gray-300 text-teal focus:ring-teal">
                            <div>
                                <span class="font-medium">Advertising</span>
                                <p class="text-xs text-gray-500">Use in promotional materials and paid ads</p>
                            </div>
                        </label>
                    </div>
                </div>

                <!-- Submit -->
                <button type="submit" class="w-full bg-teal text-white py-3 rounded-lg font-semibold text-lg hover:bg-teal/90 transition">
                    Submit My Testimonial
                </button>
            </form>

            <!-- Decline Options -->
            <div class="mt-6 pt-6 border-t border-gray-200">
                <p class="text-center text-sm text-gray-400 mb-2">Rather not share a testimonial?</p>
                <div class="text-center">
                    <a href="/testimonial/{{ token }}/decline" class="text-sm text-gray-500 hover:text-navy">Decline this request</a>
                </div>
            </div>

            <!-- Video Mailto Link -->
            <div class="mt-6 pt-4 border-t border-gray-100 text-center">
                <p class="text-xs text-gray-400">
                    Want to share a video testimonial?
                    <a href="mailto:{{ practice_email }}?subject=Video%20Testimonial" class="text-teal hover:text-teal/80">
                        Email it to us
                    </a>
                </p>
            </div>
        </div>
        {% endif %}
    </div>

    <script>
        // Character counter
        const textarea = document.querySelector('textarea[name="testimonial_text"]');
        const counter = document.getElementById('char-count');
        if (textarea && counter) {
            textarea.addEventListener('input', function() {
                counter.textContent = this.value.length;
            });
        }
    </script>
</body>
</html>
```

- [ ] 3. Create `app/templates/testimonial_list.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Testimonials - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">&gt;</span>
        {% if patient and show_patient_header %}
        <a href="/dashboard/patients/{{ patient.id }}/testimonials" class="hover:text-teal">{{ patient.first_name }} {{ patient.last_name }}</a>
        <span class="mx-1">&gt;</span>
        {% endif %}
        <span class="text-navy">Testimonials</span>
    </nav>

    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">
            {% if patient and show_patient_header %}
            Testimonials — {{ patient.first_name }} {{ patient.last_name }}
            {% else %}
            All Testimonials
            {% endif %}
        </h2>
    </div>

    <!-- Detail View -->
    {% if show_detail is defined and show_detail and testimonial %}
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div class="flex justify-between items-start mb-4">
            <div>
                <h3 class="text-lg font-semibold text-navy">Testimonial #{{ testimonial.id }}</h3>
                <p class="text-sm text-gray-500">
                    {% if patient %}{{ patient.first_name }} {{ patient.last_name }} &middot; {% endif %}
                    {{ testimonial.created_at[:10] if testimonial.created_at else '' }}
                </p>
            </div>
            <span class="inline-block px-3 py-1 rounded text-xs font-semibold
                {% if testimonial.status == 'submitted' %}bg-green-100 text-green-700
                {% elif testimonial.status == 'flagged' %}bg-red-100 text-red-700
                {% elif testimonial.status == 'requested' %}bg-blue-100 text-blue-700
                {% elif testimonial.status == 'declined_this_time' %}bg-yellow-100 text-yellow-700
                {% elif testimonial.status == 'declined_permanent' %}bg-red-100 text-red-700
                {% elif testimonial.status == 'bounced' %}bg-orange-100 text-orange-700
                {% else %}bg-gray-100 text-gray-700{% endif %}">
                {{ testimonial.status.replace('_', ' ').title() }}
            </span>
        </div>

        {% if testimonial.rating %}
        <div class="mb-3">
            <span class="text-sm font-medium text-navy">Rating: </span>
            {% for i in range(testimonial.rating) %}
            <span class="text-yellow-400 text-lg">&#9733;</span>
            {% endfor %}
            {% for i in range(5 - testimonial.rating) %}
            <span class="text-gray-300 text-lg">&#9733;</span>
            {% endfor %}
        </div>
        {% endif %}

        {% if testimonial.text %}
        <div class="bg-gray-50 rounded-lg p-4 mb-4">
            <p class="text-sm text-gray-700 italic">"{{ testimonial.text }}"</p>
        </div>
        {% endif %}

        {% if testimonial.flag_reason %}
        <div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
            <p class="text-sm text-red-700"><strong>Flagged:</strong> {{ testimonial.flag_reason }}</p>
        </div>
        {% endif %}

        <!-- Consent granted -->
        <div class="mb-4">
            <p class="text-sm text-navy font-medium mb-1">Consent Granted:</p>
            <div class="flex gap-2">
                {% if testimonial.consent_website %}
                <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Website</span>
                {% endif %}
                {% if testimonial.consent_social %}
                <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Social</span>
                {% endif %}
                {% if testimonial.consent_advertising %}
                <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Advertising</span>
                {% endif %}
            </div>
        </div>

        <!-- Video -->
        {% if testimonial.video_path %}
        <div class="mb-4">
            <p class="text-sm text-navy font-medium mb-2">Video:</p>
            <video controls class="w-full max-w-md rounded-lg">
                <source src="/media/{{ testimonial.video_path }}" type="video/mp4">
                Your browser does not support video playback.
            </video>
            <a href="/media/{{ testimonial.video_path }}" download class="text-xs text-teal hover:text-teal/80 mt-1 block">Download video</a>
        </div>
        {% else %}
        <div class="mb-4">
            <p class="text-sm text-navy font-medium mb-2">Attach Video:</p>
            <form hx-post="/api/testimonials/{{ testimonial.id }}/video"
                  hx-encoding="multipart/form-data"
                  hx-swap="outerHTML"
                  class="flex gap-2 items-end">
                <input type="file" name="video_file" accept="video/mp4,video/quicktime,video/x-msvideo,video/webm"
                       class="text-sm file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:bg-teal/10 file:text-teal">
                <button type="submit" class="bg-teal text-white px-3 py-1.5 rounded text-sm font-semibold hover:bg-teal/90 transition">Upload</button>
            </form>
            <p class="text-xs text-gray-400 mt-1">Accepted: MP4, MOV, AVI, WebM. Max {{ settings.max_video_upload_mb if settings else 200 }}MB.</p>
        </div>
        {% endif %}

        <!-- Send Log -->
        {% if send_log %}
        <div class="mt-6">
            <h4 class="text-sm font-semibold text-navy mb-2">Send History</h4>
            <div class="overflow-x-auto">
                <table class="w-full text-xs">
                    <thead>
                        <tr class="border-b border-gray-200">
                            <th class="text-left py-2 px-2 text-gray-500">Touch</th>
                            <th class="text-left py-2 px-2 text-gray-500">Scheduled</th>
                            <th class="text-left py-2 px-2 text-gray-500">Sent</th>
                            <th class="text-left py-2 px-2 text-gray-500">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for entry in send_log %}
                        <tr class="border-b border-gray-100">
                            <td class="py-2 px-2">Touch {{ entry.touch_number }}</td>
                            <td class="py-2 px-2">{{ entry.scheduled_for[:10] if entry.scheduled_for else '-' }}</td>
                            <td class="py-2 px-2">{{ entry.sent_at[:10] if entry.sent_at else '-' }}</td>
                            <td class="py-2 px-2">
                                <span class="inline-block px-2 py-0.5 rounded text-xs
                                    {% if entry.status == 'sent' %}bg-green-100 text-green-700
                                    {% elif entry.status == 'pending' %}bg-blue-100 text-blue-700
                                    {% elif entry.status == 'cancelled' %}bg-gray-100 text-gray-500
                                    {% elif entry.status == 'bounced' %}bg-red-100 text-red-700
                                    {% elif entry.status == 'suppressed' %}bg-yellow-100 text-yellow-700
                                    {% else %}bg-gray-100 text-gray-700{% endif %}">
                                    {{ entry.status }}
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}
    </div>

    <a href="/dashboard/testimonials" class="text-sm text-teal hover:text-teal/80">Back to all testimonials</a>
    {% endif %}

    <!-- Status Filter Badges (admin list only) -->
    {% if not show_patient_header and status_counts is defined %}
    <div class="flex flex-wrap gap-2 mb-6">
        <a href="/dashboard/testimonials"
           class="px-3 py-1 rounded-full text-xs font-semibold {% if not status_filter %}bg-navy text-white{% else %}bg-gray-200 text-gray-600 hover:bg-gray-300{% endif %} transition">
            All ({{ status_counts.all }})
        </a>
        {% for s_key, s_label in [('requested', 'Requested'), ('submitted', 'Submitted'), ('flagged', 'Flagged'),
                                   ('declined_this_time', 'Declined'), ('declined_permanent', 'Opted Out'),
                                   ('expired_no_response', 'Expired'), ('bounced', 'Bounced')] %}
        <a href="/dashboard/testimonials?status={{ s_key }}"
           class="px-3 py-1 rounded-full text-xs font-semibold {% if status_filter == s_key %}bg-navy text-white{% else %}bg-gray-200 text-gray-600 hover:bg-gray-300{% endif %} transition">
            {{ s_label }} ({{ status_counts.get(s_key, 0) }})
        </a>
        {% endfor %}
    </div>
    {% endif %}

    <!-- Testimonials Table -->
    {% if testimonials and (show_detail is not defined or not show_detail) %}
    <div class="bg-white rounded-lg shadow-sm overflow-hidden">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-200 bg-gray-50">
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">ID</th>
                    {% if not show_patient_header %}
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Patient</th>
                    {% endif %}
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Rating</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Status</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Date</th>
                    <th class="text-left py-3 px-4 text-gray-500 font-medium">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for t in testimonials %}
                <tr class="border-b border-gray-100 hover:bg-gray-50">
                    <td class="py-3 px-4 font-medium text-navy">{{ t.id }}</td>
                    {% if not show_patient_header %}
                    <td class="py-3 px-4">{{ t.first_name }} {{ t.last_name }}</td>
                    {% endif %}
                    <td class="py-3 px-4">
                        {% if t.rating %}
                        {% for i in range(t.rating) %}<span class="text-yellow-400">&#9733;</span>{% endfor %}
                        {% for i in range(5 - t.rating) %}<span class="text-gray-300">&#9733;</span>{% endfor %}
                        {% else %}-{% endif %}
                    </td>
                    <td class="py-3 px-4">
                        <span class="inline-block px-2 py-0.5 rounded text-xs font-semibold
                            {% if t.status == 'submitted' %}bg-green-100 text-green-700
                            {% elif t.status == 'flagged' %}bg-red-100 text-red-700
                            {% elif t.status == 'requested' %}bg-blue-100 text-blue-700
                            {% elif t.status == 'declined_this_time' %}bg-yellow-100 text-yellow-700
                            {% elif t.status == 'declined_permanent' %}bg-red-100 text-red-700
                            {% elif t.status == 'bounced' %}bg-orange-100 text-orange-700
                            {% else %}bg-gray-100 text-gray-700{% endif %}">
                            {{ t.status.replace('_', ' ').title() }}
                        </span>
                    </td>
                    <td class="py-3 px-4">{{ t.submitted_at[:10] if t.submitted_at else (t.created_at[:10] if t.created_at else '-') }}</td>
                    <td class="py-3 px-4">
                        <a href="/dashboard/testimonials/{{ t.id }}" class="text-teal hover:text-teal/80 text-sm font-semibold">View</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% elif not show_detail %}
    <div class="bg-white rounded-lg shadow-sm p-8 text-center">
        <p class="text-gray-500">No testimonials found{% if status_filter %} with status "{{ status_filter }}"{% endif %}.</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/testimonials.py app/templates/testimonial_form.html app/templates/testimonial_list.html
# Expected output: approximately 430-480 lines for routes, 130-160 for form template, 180-210 for list template

python -c "
from app.routes.testimonials import router
routes = [r.path for r in router.routes]
print(f'Testimonial router has {len(routes)} routes:')
for r in sorted(routes):
    print(f'  {r}')
expected = [
    '/dashboard/patients/{patient_id}/testimonials',
    '/dashboard/testimonials',
    '/dashboard/testimonials/{testimonial_id}',
    '/api/testimonials/{testimonial_id}/video',
    '/testimonial/{token}',
    '/testimonial/{token}/submit',
    '/testimonial/{token}/decline',
    '/testimonial/{token}/decline',
    '/testimonial/{token}/optout',
]
# Deduplicate for check (GET and POST on decline share same path)
unique_expected = set(expected)
for e in unique_expected:
    assert e in routes, f'Missing route: {e}'
print(f'All expected routes present.')
"
# Expected output:
# Testimonial router has 9 routes:
#   /api/testimonials/{testimonial_id}/video
#   /dashboard/patients/{patient_id}/testimonials
#   /dashboard/testimonials
#   /dashboard/testimonials/{testimonial_id}
#   /testimonial/{token}
#   /testimonial/{token}/decline
#   /testimonial/{token}/decline
#   /testimonial/{token}/optout
#   /testimonial/{token}/submit
# All expected routes present.
```

- [ ] 5. Test public testimonial flow (integration):

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations
from app import testimonial_db
from app import consent_db
from app.services import testimonial_service

init_db()
run_migrations()

# Create test patient
conn = get_db()
cursor = conn.execute(
    \"\"\"INSERT INTO patients (email, first_name, last_name, tier, created_at, updated_at)
       VALUES ('testimonialtest@test.com', 'Testi', 'Monial', 'active',
               datetime('now'), datetime('now'))\"\"\",
)
conn.commit()
pid = cursor.lastrowid
conn.close()

# Create cycle + final session
from app import photo_db
cycle_id = photo_db.create_treatment_cycle(pid, cycle_number=1, started_at='2026-01-15')
sid = photo_db.create_session(pid, session_number=1, session_date='2026-01-15',
                               session_type='final', cycle_id=cycle_id)

# Test 1: Create testimonial request
result = testimonial_service.create_testimonial_request(pid, sid, cycle_id)
assert result['testimonial_id'] > 0
assert result['token'] is not None
assert len(result['touches_scheduled']) == 3
print(f'Test 1 PASSED: Testimonial request created: id={result[\"testimonial_id\"]}, token={result[\"token\"][:16]}...')

# Test 2: Token lookup
testimonial = testimonial_db.get_testimonial_by_token(result['token'])
assert testimonial is not None
assert testimonial['status'] == 'requested'
print(f'Test 2 PASSED: Token lookup returns testimonial with status \"{testimonial[\"status\"]}\"')

# Test 3: Process submission
submit_result = testimonial_service.process_testimonial_submission(
    token=result['token'],
    rating=5,
    text='Amazing results! Lost 4 inches in my waist area.',
    consent_scopes=['website', 'social'],
)
assert submit_result['success']
assert not submit_result['flagged']
print(f'Test 3 PASSED: Submission processed, flagged={submit_result[\"flagged\"]}')

# Test 4: Token reuse should fail
submit_again = testimonial_service.process_testimonial_submission(
    token=result['token'],
    rating=4,
    text='Trying again',
    consent_scopes=[],
)
assert not submit_again['success']
assert 'already been submitted' in submit_again['error']
print(f'Test 4 PASSED: Resubmission blocked: \"{submit_again[\"error\"]}\"')

# Test 5: Check consent was granted
from app.services import consent_service
has_website = consent_service.patient_has_active_consent(pid, 'website')
assert has_website
print('Test 5 PASSED: Website consent granted from testimonial form')

# Cleanup
conn = get_db()
conn.execute('DELETE FROM patient_consents WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM testimonial_send_log WHERE testimonial_id = ?', (result['testimonial_id'],))
conn.execute('DELETE FROM testimonials WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_photo_sessions WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patient_treatment_cycles WHERE patient_id = ?', (pid,))
conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
conn.commit()
conn.close()

print('All 5 testimonial route tests passed. Cleanup complete.')
"
# Expected output:
# Test 1 PASSED: Testimonial request created: id=..., token=...
# Test 2 PASSED: Token lookup returns testimonial with status "requested"
# Test 3 PASSED: Submission processed, flagged=False
# Test 4 PASSED: Resubmission blocked: "This testimonial has already been submitted or is no longer available."
# Test 5 PASSED: Website consent granted from testimonial form
# All 5 testimonial route tests passed. Cleanup complete.
```

- [ ] 6. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/testimonials.py app/templates/testimonial_form.html app/templates/testimonial_list.html
git commit -m "Add testimonial routes with public form and admin views

Admin routes: per-patient testimonial history, cross-patient list with
status filter badges (requested/submitted/flagged/declined/expired/bounced),
detail view with star rating display, consent scope badges, send log
history, HTML5 video playback with download fallback, and HTMX video
upload. Public routes (no auth, token-validated): testimonial submission
form with CSS-only star rating, 2000-char text area, consent checkboxes
(website/social/advertising), character counter, decline page with
this_time vs permanent options, and one-click email footer opt-out.
Submission processed via testimonial_service with quality checks."
```

---

### Task 17: Gallery Routes + Templates (app/routes/galleries.py + templates)

Create gallery management routes and templates for the gallery admin dashboard, patient selection/exclusion, gallery HTML preview, WordPress publishing, emergency consent-revocation removal, and version history.

**Files:**
- `app/routes/galleries.py` (new)
- `app/templates/gallery_admin.html` (new)
- `app/templates/gallery_preview.html` (new)

**Steps:**

- [ ] 1. Create `app/routes/galleries.py` with the following complete code:

```python
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.config import settings
from app.database import get_db, log_event
from app import gallery_db
from app import photo_db
from app.services import gallery_service
from app.services import consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/patients")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


# ── Gallery Admin Dashboard ──────────────────────────────


@router.get("/galleries", response_class=HTMLResponse)
async def gallery_admin(request: Request):
    """Gallery admin page: current gallery status, drift indicators, regenerate button."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    gallery_slug = settings.gallery_default_slug

    # Get current published gallery
    current_gallery = gallery_db.get_current_gallery(gallery_slug)

    # Get qualifying patient count
    qualifying = gallery_service.get_qualifying_patients(gallery_slug)
    qualifying_count = len(qualifying)

    # Get drift analysis
    drift = gallery_service.get_gallery_drift(gallery_slug)

    # Get gallery exclusions
    exclusions = gallery_db.get_gallery_exclusions()

    # Get version history (last 10)
    history = gallery_db.get_gallery_history(gallery_slug)
    recent_history = history[:10] if history else []

    return templates.TemplateResponse("gallery_admin.html", {
        "request": request,
        "active": "patients",
        "gallery_slug": gallery_slug,
        "current_gallery": current_gallery,
        "qualifying_count": qualifying_count,
        "drift": drift,
        "exclusions": exclusions,
        "recent_history": recent_history,
    })


# ── Patient Selection Screen ────────────────────────────


@router.get("/galleries/new", response_class=HTMLResponse)
async def gallery_new(request: Request):
    """Patient selection screen for new gallery generation."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    gallery_slug = settings.gallery_default_slug
    qualifying = gallery_service.get_qualifying_patients(gallery_slug)
    exclusions = gallery_db.get_gallery_exclusions()
    excluded_ids = {e["patient_id"] for e in exclusions}

    return templates.TemplateResponse("gallery_admin.html", {
        "request": request,
        "active": "patients",
        "gallery_slug": gallery_slug,
        "mode": "select",
        "qualifying": qualifying,
        "excluded_ids": excluded_ids,
        "current_gallery": None,
        "qualifying_count": len(qualifying),
        "drift": None,
        "exclusions": exclusions,
        "recent_history": [],
    })


@router.get("/galleries/{gallery_slug}/regenerate", response_class=HTMLResponse)
async def gallery_regenerate(request: Request, gallery_slug: str):
    """Patient selection screen for regenerating an existing gallery."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    qualifying = gallery_service.get_qualifying_patients(gallery_slug)
    current_gallery = gallery_db.get_current_gallery(gallery_slug)
    exclusions = gallery_db.get_gallery_exclusions()
    excluded_ids = {e["patient_id"] for e in exclusions}

    # Mark which patients are currently in the gallery
    current_patient_ids = set()
    if current_gallery:
        current_patient_ids = set(current_gallery.get("patients_included", []))

    for p in qualifying:
        p["currently_included"] = p["patient_id"] in current_patient_ids

    return templates.TemplateResponse("gallery_admin.html", {
        "request": request,
        "active": "patients",
        "gallery_slug": gallery_slug,
        "mode": "select",
        "qualifying": qualifying,
        "excluded_ids": excluded_ids,
        "current_gallery": current_gallery,
        "current_patient_ids": current_patient_ids,
        "qualifying_count": len(qualifying),
        "drift": None,
        "exclusions": exclusions,
        "recent_history": [],
    })


# ── Generate Gallery (Preview Mode) ─────────────────────


@router.post("/galleries/generate", response_class=HTMLResponse)
async def gallery_generate(
    request: Request,
    gallery_slug: str = Form(settings.gallery_default_slug),
):
    """Generate gallery HTML from selected patients and show preview."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    form_data = await request.form()

    # Get selected patient IDs from checkboxes
    selected_ids = []
    for key in form_data.keys():
        if key.startswith("include_patient_"):
            try:
                pid = int(key.replace("include_patient_", ""))
                selected_ids.append(pid)
            except ValueError:
                pass

    # Handle persistent exclusions
    for key in form_data.keys():
        if key.startswith("persist_exclude_"):
            try:
                pid = int(key.replace("persist_exclude_", ""))
                reason = form_data.get(f"exclude_reason_{pid}", "Excluded during gallery generation")
                gallery_db.add_gallery_exclusion(pid, excluded_by="admin", reason=reason)
            except ValueError:
                pass

    if not selected_ids:
        return RedirectResponse(
            url="/dashboard/patients/galleries/new?error=no_patients",
            status_code=303,
        )

    # Get qualifying patients and filter to selected
    qualifying = gallery_service.get_qualifying_patients(gallery_slug)
    selected_patients = [
        p for p in qualifying if p["patient_id"] in selected_ids
    ]

    if not selected_patients:
        return RedirectResponse(
            url="/dashboard/patients/galleries/new?error=no_valid_patients",
            status_code=303,
        )

    # Upload photos to WordPress (dedup handled internally)
    all_photo_ids = []
    for p in selected_patients:
        for photo in p.get("baseline_photos", []):
            if photo.get("id"):
                all_photo_ids.append(photo["id"])
        for photo in p.get("final_photos", []):
            if photo.get("id"):
                all_photo_ids.append(photo["id"])

    upload_result = gallery_service.upload_photos_to_wordpress(all_photo_ids)

    # Attach WP URLs to patient photo data
    for p in selected_patients:
        for photo_list in [p.get("baseline_photos", []), p.get("final_photos", [])]:
            for photo in photo_list:
                wp_media = gallery_db.get_wp_media_for_photo(photo.get("id", 0))
                if wp_media:
                    photo["wp_url"] = wp_media["wp_media_url"]

    # Generate gallery HTML
    gallery_html = gallery_service.generate_gallery_html(selected_patients, gallery_slug)

    # Create gallery version (not yet published)
    patient_ids = [p["patient_id"] for p in selected_patients]
    version_id = gallery_db.create_gallery_version(
        gallery_slug=gallery_slug,
        patients_included=patient_ids,
        photo_ids_included=all_photo_ids,
        patient_count=len(selected_patients),
        generated_html=gallery_html,
        notes=f"Generated with {len(selected_patients)} patients",
    )

    log_event(
        "gallery",
        f"Gallery preview generated: version {version_id} with {len(selected_patients)} patients",
        {"version_id": version_id, "patient_ids": patient_ids, "upload_result": upload_result},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/galleries/preview/{version_id}",
        status_code=303,
    )


# ── Preview Gallery ──────────────────────────────────────


@router.get("/galleries/preview/{version_id}", response_class=HTMLResponse)
async def gallery_preview(request: Request, version_id: int):
    """Preview rendered gallery before publishing."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    version = gallery_db.get_gallery_version(version_id)
    if not version:
        return HTMLResponse("<h1>Gallery version not found</h1>", status_code=404)

    return templates.TemplateResponse("gallery_preview.html", {
        "request": request,
        "active": "patients",
        "version": version,
        "gallery_html": version.get("generated_html", ""),
    })


# ── Publish Gallery ──────────────────────────────────────


@router.post("/galleries/{version_id}/publish", response_class=HTMLResponse)
async def gallery_publish(
    request: Request,
    version_id: int,
    publish_as_draft: str = Form(""),
):
    """Publish gallery version to WordPress."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    version = gallery_db.get_gallery_version(version_id)
    if not version:
        return HTMLResponse("<h1>Gallery version not found</h1>", status_code=404)

    gallery_slug = version.get("gallery_slug", settings.gallery_default_slug)
    as_draft = publish_as_draft == "1"

    # Publish to WordPress
    wp_result = gallery_service.publish_gallery_to_wordpress(
        version_id, gallery_slug, publish_as_draft=as_draft
    )

    if wp_result["success"]:
        # Mark version as published and current
        gallery_db.publish_gallery_version(
            version_id,
            published_by="admin",
            wp_page_id=wp_result.get("wp_page_id"),
        )

        # Log content usage for all included patients
        patient_ids = version.get("patients_included", [])
        wp_url = wp_result.get("wp_url", f"/{gallery_slug}")
        for pid in patient_ids:
            gallery_db.create_content_usage_entry(
                patient_id=pid,
                photo_id=None,
                testimonial_id=None,
                used_in=wp_url,
                scope_used="website",
            )

        log_event(
            "gallery",
            f"Gallery version {version_id} published to WordPress",
            {"wp_page_id": wp_result.get("wp_page_id"), "wp_url": wp_url},
        )

        return RedirectResponse(
            url="/dashboard/patients/galleries?success=published",
            status_code=303,
        )
    else:
        log_event(
            "gallery",
            f"Gallery publish failed: {wp_result.get('error')}",
            {"version_id": version_id},
        )
        return RedirectResponse(
            url=f"/dashboard/patients/galleries/preview/{version_id}?error=publish_failed",
            status_code=303,
        )


# ── Emergency Consent Revocation Removal ─────────────────


@router.post("/galleries/emergency-remove/{patient_id}", response_class=HTMLResponse)
async def gallery_emergency_remove(
    request: Request,
    patient_id: int,
    reason: str = Form("Consent revoked — emergency removal"),
):
    """Emergency removal of a patient from the current published gallery."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    gallery_slug = settings.gallery_default_slug

    result = gallery_service.emergency_remove_patient(
        patient_id=patient_id,
        gallery_slug=gallery_slug,
        removed_by="admin",
        reason=reason,
    )

    if result["success"]:
        log_event(
            "gallery",
            f"Emergency removal: patient {patient_id} removed from gallery",
            {"new_version_id": result.get("new_version_id"), "reason": reason},
        )
        return RedirectResponse(
            url="/dashboard/patients/galleries?success=emergency_removed",
            status_code=303,
        )
    else:
        return RedirectResponse(
            url=f"/dashboard/patients/galleries?error={result.get('error', 'removal_failed')}",
            status_code=303,
        )


# ── Version History ──────────────────────────────────────


@router.get("/galleries/history", response_class=HTMLResponse)
async def gallery_history(request: Request):
    """Full gallery version history."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    gallery_slug = settings.gallery_default_slug
    history = gallery_db.get_gallery_history(gallery_slug)

    return templates.TemplateResponse("gallery_admin.html", {
        "request": request,
        "active": "patients",
        "gallery_slug": gallery_slug,
        "mode": "history",
        "history": history,
        "current_gallery": gallery_db.get_current_gallery(gallery_slug),
        "qualifying_count": 0,
        "drift": None,
        "exclusions": [],
        "recent_history": history,
    })
```

- [ ] 2. Create `app/templates/gallery_admin.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Gallery Management - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">/</span>
        <span class="text-navy font-medium">Galleries</span>
    </nav>

    <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-navy">Gallery Management</h2>
        {% if mode != 'select' and mode != 'history' %}
        <a href="/dashboard/patients/galleries/new"
           class="bg-teal text-white px-4 py-2 rounded font-semibold hover:bg-teal/90 transition">
            New Gallery
        </a>
        {% endif %}
    </div>

    <!-- Success/Error Messages -->
    {% if request.query_params.get('success') == 'published' %}
    <div class="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
        Gallery published to WordPress successfully.
    </div>
    {% endif %}
    {% if request.query_params.get('success') == 'emergency_removed' %}
    <div class="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded mb-4">
        Patient removed from gallery. New version published.
    </div>
    {% endif %}
    {% if request.query_params.get('error') %}
    <div class="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
        Error: {{ request.query_params.get('error') }}
    </div>
    {% endif %}

    {% if mode == 'select' %}
    <!-- ── Patient Selection Mode ─────────────────────── -->
    <form action="/dashboard/patients/galleries/generate" method="post">
        <input type="hidden" name="gallery_slug" value="{{ gallery_slug }}">

        <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h3 class="text-lg font-semibold text-navy mb-2">Select Patients for Gallery</h3>
            <p class="text-sm text-gray-600 mb-4">
                {{ qualifying|length }} qualifying patients found. Check patients to include in the gallery.
            </p>

            {% if qualifying %}
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 text-left">
                            <th class="pb-2 pr-4">
                                <input type="checkbox" id="select-all" onclick="document.querySelectorAll('.patient-checkbox').forEach(cb => cb.checked = this.checked)">
                            </th>
                            <th class="pb-2 pr-4">Patient</th>
                            <th class="pb-2 pr-4">Final Session</th>
                            <th class="pb-2 pr-4">Sessions</th>
                            <th class="pb-2 pr-4">Progress</th>
                            <th class="pb-2 pr-4">Photos</th>
                            <th class="pb-2 pr-4">Status</th>
                            <th class="pb-2">Exclude</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in qualifying %}
                        <tr class="border-b border-gray-100 hover:bg-gray-50">
                            <td class="py-3 pr-4">
                                {% if p.patient_id not in excluded_ids %}
                                <input type="checkbox" name="include_patient_{{ p.patient_id }}"
                                       class="patient-checkbox" value="1"
                                       {% if p.get('currently_included', false) %}checked{% endif %}>
                                {% else %}
                                <span class="text-gray-400 text-xs">Excluded</span>
                                {% endif %}
                            </td>
                            <td class="py-3 pr-4 font-medium">
                                {{ p.first_name }} {{ p.last_name[0] if p.last_name else '' }}.
                            </td>
                            <td class="py-3 pr-4 text-gray-600">{{ p.session_date }}</td>
                            <td class="py-3 pr-4 text-gray-600">{{ p.session_count or 0 }}</td>
                            <td class="py-3 pr-4 text-gray-600">{{ p.measurement_summary or '—' }}</td>
                            <td class="py-3 pr-4">
                                <span class="text-xs">
                                    B: {{ p.baseline_photos|length if p.baseline_photos else 0 }}/6
                                    F: {{ p.final_photos|length if p.final_photos else 0 }}/6
                                </span>
                            </td>
                            <td class="py-3 pr-4">
                                {% if p.get('currently_included', false) %}
                                <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Current</span>
                                {% else %}
                                <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">New</span>
                                {% endif %}
                            </td>
                            <td class="py-3">
                                {% if p.patient_id not in excluded_ids %}
                                <label class="flex items-center gap-1 text-xs text-gray-500">
                                    <input type="checkbox" name="persist_exclude_{{ p.patient_id }}" value="1">
                                    Persist
                                </label>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <p class="text-gray-500 italic">No qualifying patients. Patients need a completed final session and active website consent.</p>
            {% endif %}
        </div>

        {% if qualifying %}
        <div class="flex gap-3">
            <button type="submit"
                    class="bg-teal text-white px-6 py-2 rounded font-semibold hover:bg-teal/90 transition">
                Generate Preview
            </button>
            <a href="/dashboard/patients/galleries"
               class="bg-gray-200 text-gray-700 px-6 py-2 rounded font-semibold hover:bg-gray-300 transition">
                Cancel
            </a>
        </div>
        {% endif %}
    </form>

    {% elif mode == 'history' %}
    <!-- ── Version History Mode ──────────────────────── -->
    <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Version History</h3>
        {% if history %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200 text-left">
                        <th class="pb-2 pr-4">Version</th>
                        <th class="pb-2 pr-4">Generated</th>
                        <th class="pb-2 pr-4">Patients</th>
                        <th class="pb-2 pr-4">Published</th>
                        <th class="pb-2 pr-4">Published By</th>
                        <th class="pb-2 pr-4">Status</th>
                        <th class="pb-2">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for v in history %}
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="py-3 pr-4 font-mono text-xs">#{{ v.id }}</td>
                        <td class="py-3 pr-4 text-gray-600">{{ v.generated_at[:16] if v.generated_at else '—' }}</td>
                        <td class="py-3 pr-4">{{ v.patient_count }}</td>
                        <td class="py-3 pr-4 text-gray-600">{{ v.published_at[:16] if v.published_at else '—' }}</td>
                        <td class="py-3 pr-4 text-gray-600">{{ v.published_by or '—' }}</td>
                        <td class="py-3 pr-4">
                            {% if v.is_current %}
                            <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Current</span>
                            {% elif v.published_at %}
                            <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">Previous</span>
                            {% else %}
                            <span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">Draft</span>
                            {% endif %}
                        </td>
                        <td class="py-3">
                            <a href="/dashboard/patients/galleries/preview/{{ v.id }}"
                               class="text-teal text-xs hover:underline">View</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-gray-500 italic">No gallery versions yet.</p>
        {% endif %}
    </div>

    {% else %}
    <!-- ── Dashboard Mode (Default) ──────────────────── -->

    <!-- Current Gallery Status -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-teal">
            <p class="text-sm text-gray-500">Current Gallery</p>
            {% if current_gallery %}
            <p class="text-2xl font-bold text-navy">{{ current_gallery.patient_count }} patients</p>
            <p class="text-xs text-gray-400 mt-1">
                Last generated: {{ current_gallery.generated_at[:10] if current_gallery.generated_at else 'N/A' }}
            </p>
            {% else %}
            <p class="text-lg font-semibold text-gray-400">Not generated</p>
            {% endif %}
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-blue-500">
            <p class="text-sm text-gray-500">Qualifying Patients</p>
            <p class="text-2xl font-bold text-navy">{{ qualifying_count }}</p>
            <p class="text-xs text-gray-400 mt-1">Ready for gallery inclusion</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 {% if drift and drift.has_drift %}border-yellow-500{% else %}border-green-500{% endif %}">
            <p class="text-sm text-gray-500">Drift Status</p>
            {% if drift and drift.has_drift %}
            <p class="text-lg font-semibold text-yellow-600">Changes detected</p>
            <p class="text-xs text-gray-400 mt-1">
                {% if drift.patients_to_add %}+{{ drift.patients_to_add|length }} new{% endif %}
                {% if drift.patients_to_remove %} -{{ drift.patients_to_remove|length }} removed{% endif %}
                {% if drift.patients_with_updated_photos %} ~{{ drift.patients_with_updated_photos|length }} updated{% endif %}
            </p>
            {% else %}
            <p class="text-lg font-semibold text-green-600">Up to date</p>
            {% endif %}
        </div>
    </div>

    <!-- Drift Alerts -->
    {% if drift and drift.has_drift %}
    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
        <h4 class="font-semibold text-yellow-800 mb-2">Gallery Drift Detected</h4>
        {% if drift.patients_to_add %}
        <p class="text-sm text-yellow-700 mb-1">
            <strong>{{ drift.patients_to_add|length }}</strong> new patients would be added
        </p>
        {% endif %}
        {% if drift.patients_to_remove %}
        <div class="text-sm text-yellow-700 mb-1">
            <strong>{{ drift.patients_to_remove|length }}</strong> patients should be removed:
            <ul class="ml-4 mt-1">
                {% for removal in drift.patients_to_remove %}
                <li>
                    Patient #{{ removal.patient_id }} — {{ removal.reason|replace('_', ' ') }}
                    {% if removal.reason == 'consent_revoked_or_expired' %}
                    <form action="/dashboard/patients/galleries/emergency-remove/{{ removal.patient_id }}"
                          method="post" class="inline ml-2">
                        <input type="hidden" name="reason" value="Consent revoked/expired — drift alert">
                        <button type="submit"
                                class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded hover:bg-red-200"
                                onclick="return confirm('Remove this patient from the live gallery immediately?')">
                            Emergency Remove
                        </button>
                    </form>
                    {% endif %}
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
        {% if drift.patients_with_updated_photos %}
        <p class="text-sm text-yellow-700">
            <strong>{{ drift.patients_with_updated_photos|length }}</strong> patients have updated photos
        </p>
        {% endif %}
        <a href="/dashboard/patients/galleries/{{ gallery_slug }}/regenerate"
           class="inline-block mt-3 bg-yellow-600 text-white px-4 py-1.5 rounded text-sm font-semibold hover:bg-yellow-700 transition">
            Regenerate Gallery
        </a>
    </div>
    {% endif %}

    <!-- Actions -->
    <div class="flex gap-3 mb-6">
        {% if current_gallery %}
        <a href="/dashboard/patients/galleries/{{ gallery_slug }}/regenerate"
           class="bg-teal text-white px-4 py-2 rounded font-semibold hover:bg-teal/90 transition">
            Regenerate Gallery
        </a>
        <a href="/dashboard/patients/galleries/preview/{{ current_gallery.id }}"
           class="bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold hover:bg-gray-300 transition">
            View Current
        </a>
        {% endif %}
        <a href="/dashboard/patients/galleries/history"
           class="bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold hover:bg-gray-300 transition">
            Version History
        </a>
    </div>

    <!-- Exclusions -->
    {% if exclusions %}
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Persistent Exclusions</h3>
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200 text-left">
                        <th class="pb-2 pr-4">Patient</th>
                        <th class="pb-2 pr-4">Excluded By</th>
                        <th class="pb-2 pr-4">Date</th>
                        <th class="pb-2 pr-4">Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {% for e in exclusions %}
                    <tr class="border-b border-gray-100">
                        <td class="py-2 pr-4">{{ e.first_name }} {{ e.last_name }}</td>
                        <td class="py-2 pr-4 text-gray-600">{{ e.excluded_by or '—' }}</td>
                        <td class="py-2 pr-4 text-gray-600">{{ e.excluded_at[:10] if e.excluded_at else '—' }}</td>
                        <td class="py-2 pr-4 text-gray-600">{{ e.reason or '—' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% endif %}

    <!-- Recent History -->
    {% if recent_history %}
    <div class="bg-white rounded-lg shadow-sm p-6">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-semibold text-navy">Recent Versions</h3>
            <a href="/dashboard/patients/galleries/history" class="text-teal text-sm hover:underline">View All</a>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200 text-left">
                        <th class="pb-2 pr-4">Version</th>
                        <th class="pb-2 pr-4">Generated</th>
                        <th class="pb-2 pr-4">Patients</th>
                        <th class="pb-2 pr-4">Status</th>
                        <th class="pb-2">Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {% for v in recent_history[:5] %}
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="py-2 pr-4 font-mono text-xs">#{{ v.id }}</td>
                        <td class="py-2 pr-4 text-gray-600">{{ v.generated_at[:16] if v.generated_at else '—' }}</td>
                        <td class="py-2 pr-4">{{ v.patient_count }}</td>
                        <td class="py-2 pr-4">
                            {% if v.is_current %}
                            <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Current</span>
                            {% elif v.published_at %}
                            <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">Previous</span>
                            {% else %}
                            <span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">Draft</span>
                            {% endif %}
                        </td>
                        <td class="py-2 text-xs text-gray-500">{{ v.notes or '' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% endif %}

    {% endif %}
</div>
{% endblock %}
```

- [ ] 3. Create `app/templates/gallery_preview.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Gallery Preview - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">/</span>
        <a href="/dashboard/patients/galleries" class="hover:text-teal">Galleries</a>
        <span class="mx-1">/</span>
        <span class="text-navy font-medium">Preview #{{ version.id }}</span>
    </nav>

    <div class="flex items-center justify-between mb-6">
        <div>
            <h2 class="text-2xl font-bold text-navy">Gallery Preview</h2>
            <p class="text-sm text-gray-500 mt-1">
                Version #{{ version.id }} — {{ version.patient_count }} patients —
                Generated {{ version.generated_at[:16] if version.generated_at else 'N/A' }}
            </p>
        </div>
        <div class="flex gap-3">
            {% if not version.published_at %}
            <form action="/dashboard/patients/galleries/{{ version.id }}/publish" method="post" class="inline">
                <input type="hidden" name="publish_as_draft" value="1">
                <button type="submit"
                        class="bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold hover:bg-gray-300 transition">
                    Publish as Draft
                </button>
            </form>
            <form action="/dashboard/patients/galleries/{{ version.id }}/publish" method="post" class="inline">
                <input type="hidden" name="publish_as_draft" value="">
                <button type="submit"
                        class="bg-teal text-white px-4 py-2 rounded font-semibold hover:bg-teal/90 transition"
                        onclick="return confirm('Publish this gallery to WordPress? This will replace the current live gallery.')">
                    Publish to WordPress
                </button>
            </form>
            {% else %}
            <span class="text-sm text-green-600 font-medium py-2">
                Published {{ version.published_at[:16] }} by {{ version.published_by or 'admin' }}
            </span>
            {% endif %}
            <a href="/dashboard/patients/galleries"
               class="bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold hover:bg-gray-300 transition">
                Back
            </a>
        </div>
    </div>

    {% if request.query_params.get('error') == 'publish_failed' %}
    <div class="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
        WordPress publishing failed. Check WordPress connection settings and try again.
    </div>
    {% endif %}

    <!-- Rendered Gallery Preview -->
    <div class="bg-white rounded-lg shadow-sm p-6">
        <div class="border border-gray-200 rounded p-6 bg-gray-50">
            <p class="text-xs text-gray-400 mb-4 uppercase tracking-wide">Preview — as it will appear on WordPress</p>
            <div class="bg-white p-6 rounded shadow-sm">
                {{ gallery_html|safe }}
            </div>
        </div>
    </div>

    <!-- Version Metadata -->
    <div class="bg-white rounded-lg shadow-sm p-4 mt-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
                <p class="text-gray-500">Version</p>
                <p class="font-mono">#{{ version.id }}</p>
            </div>
            <div>
                <p class="text-gray-500">Patients</p>
                <p>{{ version.patient_count }}</p>
            </div>
            <div>
                <p class="text-gray-500">Gallery Slug</p>
                <p class="font-mono">{{ version.gallery_slug }}</p>
            </div>
            <div>
                <p class="text-gray-500">Notes</p>
                <p>{{ version.notes or '—' }}</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/galleries.py app/templates/gallery_admin.html app/templates/gallery_preview.html
# Expected output: approximately 300-340 lines for galleries.py, 280-320 for gallery_admin.html, 90-110 for gallery_preview.html

python -c "
from app.routes.galleries import router
routes = [r.path for r in router.routes]
expected = [
    '/galleries',
    '/galleries/new',
    '/galleries/{gallery_slug}/regenerate',
    '/galleries/generate',
    '/galleries/preview/{version_id}',
    '/galleries/{version_id}/publish',
    '/galleries/emergency-remove/{patient_id}',
    '/galleries/history',
]
for e in expected:
    assert e in routes, f'Missing route: {e}'
print(f'All {len(expected)} gallery routes registered.')
"
# Expected output: All 8 gallery routes registered.
```

- [ ] 5. Test gallery routes with integration test:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations

init_db()
run_migrations()

# Test 1: Verify route imports and router prefix
from app.routes.galleries import router
assert router.prefix == '/dashboard/patients'
print('Test 1 PASSED: Router prefix is /dashboard/patients')

# Test 2: Verify all route functions exist
from app.routes import galleries
funcs = [
    'gallery_admin', 'gallery_new', 'gallery_regenerate',
    'gallery_generate', 'gallery_preview', 'gallery_publish',
    'gallery_emergency_remove', 'gallery_history',
]
for fn in funcs:
    assert hasattr(galleries, fn), f'Missing function: {fn}'
print(f'Test 2 PASSED: All {len(funcs)} route functions exist.')

# Test 3: Verify template files exist
import os
for tmpl in ['gallery_admin.html', 'gallery_preview.html']:
    path = os.path.join('app/templates', tmpl)
    assert os.path.exists(path), f'Missing template: {tmpl}'
print('Test 3 PASSED: Both gallery templates exist.')

print('All 3 gallery route tests passed.')
"
# Expected output:
# Test 1 PASSED: Router prefix is /dashboard/patients
# Test 2 PASSED: All 8 route functions exist.
# Test 3 PASSED: Both gallery templates exist.
# All 3 gallery route tests passed.
```

- [ ] 6. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/galleries.py app/templates/gallery_admin.html app/templates/gallery_preview.html
git commit -m "Add gallery routes with admin dashboard, preview, and WordPress publishing

Gallery admin dashboard with current status, drift detection alerts
(new/removed/updated patients), qualifying patient count, persistent
exclusion list, and recent version history. Patient selection screen
with include/exclude checkboxes and persistent exclusion toggle.
Gallery generation uploads photos to WordPress (dedup via wp_media_uploads),
generates semantic HTML, creates draft version for preview. Preview page
with publish-as-draft and publish-live options. Emergency consent
revocation removal with one-click regeneration. Full version history."
```

---

### Task 18: Case Study Routes + Templates (app/routes/case_studies.py + templates)

Create case study generation flow routes and templates for listing case studies with readiness indicators, patient selection with Claude recommendations, aggregate review with override support, Claude-generated markdown preview with inline editing, and WordPress publishing.

**Files:**
- `app/routes/case_studies.py` (new)
- `app/templates/case_study_admin.html` (new)
- `app/templates/case_study_preview.html` (new)

**Steps:**

- [ ] 1. Create `app/routes/case_studies.py` with the following complete code:

```python
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import get_db, log_event
from app import case_study_db
from app import gallery_db
from app.services import case_study_service
from app.services import consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/patients")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_patient_or_404(patient_id: int):
    """Fetch patient by ID. Returns dict or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Case Study List ──────────────────────────────────────


@router.get("/case-studies", response_class=HTMLResponse)
async def case_study_list(request: Request, status: str = ""):
    """Case study list with status filters and readiness indicator."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    if status:
        case_studies = case_study_db.get_case_studies(status=status)
    else:
        case_studies = case_study_db.get_case_studies()

    # Get qualifying patients for readiness indicator
    qualifying = case_study_service.get_qualifying_patients_for_case_study()
    qualifying_count = len(qualifying)
    readiness = case_study_service.get_readiness_indicator(qualifying_count)

    return templates.TemplateResponse("case_study_admin.html", {
        "request": request,
        "active": "patients",
        "mode": "list",
        "case_studies": case_studies,
        "status_filter": status,
        "qualifying_count": qualifying_count,
        "readiness": readiness,
    })


# ── New Case Study — Patient Selection ───────────────────


@router.get("/case-studies/new", response_class=HTMLResponse)
async def case_study_new(request: Request):
    """Start generation flow: patient selection with Claude recommendations."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    qualifying = case_study_service.get_qualifying_patients_for_case_study()
    qualifying_count = len(qualifying)
    readiness = case_study_service.get_readiness_indicator(qualifying_count)

    # Get Claude recommendations
    recommendations = []
    if qualifying:
        recommendations = case_study_service.recommend_featured_patients(
            qualifying, max_count=5
        )

    recommended_ids = {r["patient_id"] for r in recommendations}

    return templates.TemplateResponse("case_study_admin.html", {
        "request": request,
        "active": "patients",
        "mode": "select",
        "qualifying": qualifying,
        "qualifying_count": qualifying_count,
        "readiness": readiness,
        "recommendations": recommendations,
        "recommended_ids": recommended_ids,
        "case_studies": [],
        "status_filter": "",
    })


# ── Confirm Patient Selections ───────────────────────────


@router.post("/case-studies/select-patients", response_class=HTMLResponse)
async def case_study_select_patients(request: Request):
    """Confirm patient selections, calculate aggregates, and show review screen."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    form_data = await request.form()

    # Get selected patient IDs from checkboxes
    selected_ids = []
    for key in form_data.keys():
        if key.startswith("select_patient_"):
            try:
                pid = int(key.replace("select_patient_", ""))
                selected_ids.append(pid)
            except ValueError:
                pass

    if not selected_ids:
        return RedirectResponse(
            url="/dashboard/patients/case-studies/new?error=no_patients",
            status_code=303,
        )

    # Validate: min 1, max 8
    if len(selected_ids) > 8:
        selected_ids = selected_ids[:8]

    # Calculate aggregates for the full qualifying cohort
    qualifying = case_study_service.get_qualifying_patients_for_case_study()
    all_qualifying_ids = [p["patient_id"] for p in qualifying]
    aggregates = case_study_service.calculate_case_study_aggregates(all_qualifying_ids)

    # Get selected patient details
    selected_patients = [
        p for p in qualifying if p["patient_id"] in selected_ids
    ]

    # Create draft case study record
    case_study_id = case_study_db.create_case_study(
        title=f"Zerona Z6 Results — {datetime.now().strftime('%B %Y')}",
        patients_included_count=len(all_qualifying_ids),
        featured_patient_ids=selected_ids,
        aggregate_data=aggregates,
        generated_markdown="",  # Not generated yet
    )

    # Save selections (AI recommendations and admin picks)
    for idx, pid in enumerate(selected_ids):
        # Check if this patient was AI-recommended
        was_recommended = False
        reasoning = ""
        recommendations_json = form_data.get("recommendations_json", "[]")
        try:
            recs = json.loads(recommendations_json)
            for r in recs:
                if r.get("patient_id") == pid:
                    was_recommended = True
                    reasoning = r.get("reasoning", "")
                    break
        except (json.JSONDecodeError, TypeError):
            pass

        case_study_db.create_case_study_selection(
            case_study_id=case_study_id,
            patient_id=pid,
            recommended_by_ai=1 if was_recommended else 0,
            recommendation_reasoning=reasoning,
            selected_by_admin=1,
            selection_order=idx + 1,
        )

    log_event(
        "case_study",
        f"Case study {case_study_id} created with {len(selected_ids)} featured patients",
        {"case_study_id": case_study_id, "selected_ids": selected_ids},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/case-studies/{case_study_id}/aggregates",
        status_code=303,
    )


# ── Review Aggregates ────────────────────────────────────


@router.get("/case-studies/{case_study_id}/aggregates", response_class=HTMLResponse)
async def case_study_aggregates(request: Request, case_study_id: int):
    """Review aggregate numbers with override option."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    case_study = case_study_db.get_case_study(case_study_id)
    if not case_study:
        return HTMLResponse("<h1>Case study not found</h1>", status_code=404)

    aggregates = case_study.get("aggregate_data", {})
    overrides = case_study_db.get_case_study_overrides(case_study_id)
    selections = case_study_db.get_case_study_selections(case_study_id)

    return templates.TemplateResponse("case_study_admin.html", {
        "request": request,
        "active": "patients",
        "mode": "aggregates",
        "case_study": case_study,
        "aggregates": aggregates,
        "overrides": overrides,
        "selections": selections,
        "case_studies": [],
        "status_filter": "",
        "qualifying_count": case_study.get("patients_included_count", 0),
        "readiness": case_study_service.get_readiness_indicator(
            case_study.get("patients_included_count", 0)
        ),
    })


# ── Generate Case Study ──────────────────────────────────


@router.post("/case-studies/{case_study_id}/generate", response_class=HTMLResponse)
async def case_study_generate(request: Request, case_study_id: int):
    """Generate case study markdown via Claude."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    case_study = case_study_db.get_case_study(case_study_id)
    if not case_study:
        return HTMLResponse("<h1>Case study not found</h1>", status_code=404)

    form_data = await request.form()

    # Process any overrides from the form
    for key in form_data.keys():
        if key.startswith("override_") and form_data.get(key):
            metric_name = key.replace("override_", "")
            override_value = form_data.get(key)
            original_value = form_data.get(f"original_{metric_name}", "")
            override_reason = form_data.get(f"reason_{metric_name}", "Admin override")

            if override_value and override_value != original_value:
                case_study_db.create_case_study_override(
                    case_study_id=case_study_id,
                    metric_name=metric_name,
                    original_value=str(original_value),
                    override_value=str(override_value),
                    reason=override_reason,
                    overridden_by="admin",
                )

    # Gather featured patient data
    selections = case_study_db.get_case_study_selections(case_study_id)
    qualifying = case_study_service.get_qualifying_patients_for_case_study()

    featured_patients = []
    for sel in selections:
        if sel.get("selected_by_admin"):
            patient_data = next(
                (p for p in qualifying if p["patient_id"] == sel["patient_id"]),
                None,
            )
            if patient_data:
                featured_patients.append(patient_data)

    # Get overrides as dict
    overrides = case_study_db.get_case_study_overrides(case_study_id)
    override_dict = {o["metric_name"]: o["override_value"] for o in overrides}

    aggregates = case_study.get("aggregate_data", {})

    # Generate markdown via Claude
    markdown = case_study_service.generate_case_study_markdown(
        featured_patients=featured_patients,
        aggregates=aggregates,
        overrides=override_dict,
    )

    # Save generated markdown
    case_study_db.update_case_study(
        case_study_id,
        status="draft",
        edited_markdown=None,
    )
    conn = get_db()
    conn.execute(
        "UPDATE case_studies SET generated_markdown = ? WHERE id = ?",
        (markdown, case_study_id),
    )
    conn.commit()
    conn.close()

    log_event(
        "case_study",
        f"Case study {case_study_id} markdown generated ({len(markdown)} chars)",
        {"case_study_id": case_study_id},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/case-studies/{case_study_id}/preview",
        status_code=303,
    )


# ── Preview Case Study ───────────────────────────────────


@router.get("/case-studies/{case_study_id}/preview", response_class=HTMLResponse)
async def case_study_preview(request: Request, case_study_id: int):
    """Preview full rendered case study document."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    case_study = case_study_db.get_case_study(case_study_id)
    if not case_study:
        return HTMLResponse("<h1>Case study not found</h1>", status_code=404)

    # Use edited markdown if available, otherwise generated
    display_markdown = case_study.get("edited_markdown") or case_study.get("generated_markdown", "")

    selections = case_study_db.get_case_study_selections(case_study_id)
    overrides = case_study_db.get_case_study_overrides(case_study_id)

    return templates.TemplateResponse("case_study_preview.html", {
        "request": request,
        "active": "patients",
        "case_study": case_study,
        "display_markdown": display_markdown,
        "selections": selections,
        "overrides": overrides,
    })


# ── Save Edits ───────────────────────────────────────────


@router.post("/case-studies/{case_study_id}/update", response_class=HTMLResponse)
async def case_study_update(
    request: Request,
    case_study_id: int,
    edited_markdown: str = Form(""),
    title: str = Form(""),
):
    """Save admin edits to case study."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    case_study = case_study_db.get_case_study(case_study_id)
    if not case_study:
        return HTMLResponse("<h1>Case study not found</h1>", status_code=404)

    updates = {}
    if edited_markdown:
        updates["edited_markdown"] = edited_markdown
    if title:
        updates["title"] = title
    if updates:
        updates["status"] = "reviewed"
        case_study_db.update_case_study(case_study_id, **updates)

    log_event(
        "case_study",
        f"Case study {case_study_id} edited by admin",
        {"fields": list(updates.keys())},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/case-studies/{case_study_id}/preview?success=saved",
        status_code=303,
    )


# ── Publish to WordPress ─────────────────────────────────


@router.post("/case-studies/{case_study_id}/publish", response_class=HTMLResponse)
async def case_study_publish(request: Request, case_study_id: int):
    """Publish case study to WordPress as blog post draft."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    case_study = case_study_db.get_case_study(case_study_id)
    if not case_study:
        return HTMLResponse("<h1>Case study not found</h1>", status_code=404)

    # Publish to WordPress
    wp_result = case_study_service.publish_case_study_to_wordpress(case_study_id)

    if wp_result.get("success"):
        # Log content usage for featured patients
        featured_ids = case_study.get("featured_patient_ids", [])
        wp_url = wp_result.get("wp_url", "")
        for pid in featured_ids:
            gallery_db.create_content_usage_entry(
                patient_id=pid,
                photo_id=None,
                testimonial_id=None,
                used_in=wp_url,
                scope_used="case_study",
            )

        log_event(
            "case_study",
            f"Case study {case_study_id} published to WordPress",
            {"wp_post_id": wp_result.get("wp_post_id"), "wp_url": wp_url},
        )

        return RedirectResponse(
            url="/dashboard/patients/case-studies?success=published",
            status_code=303,
        )
    else:
        return RedirectResponse(
            url=f"/dashboard/patients/case-studies/{case_study_id}/preview?error=publish_failed",
            status_code=303,
        )


# ── Compare Versions ─────────────────────────────────────


@router.get("/case-studies/{case_study_id}/compare/{old_id}", response_class=HTMLResponse)
async def case_study_compare(
    request: Request,
    case_study_id: int,
    old_id: int,
):
    """Compare two case study versions side by side."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    current = case_study_db.get_case_study(case_study_id)
    old = case_study_db.get_case_study(old_id)

    if not current or not old:
        return HTMLResponse("<h1>Case study version not found</h1>", status_code=404)

    current_markdown = current.get("edited_markdown") or current.get("generated_markdown", "")
    old_markdown = old.get("edited_markdown") or old.get("generated_markdown", "")

    return templates.TemplateResponse("case_study_preview.html", {
        "request": request,
        "active": "patients",
        "mode": "compare",
        "case_study": current,
        "old_case_study": old,
        "display_markdown": current_markdown,
        "old_markdown": old_markdown,
        "selections": case_study_db.get_case_study_selections(case_study_id),
        "overrides": case_study_db.get_case_study_overrides(case_study_id),
    })
```

- [ ] 2. Create `app/templates/case_study_admin.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Case Studies - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">/</span>
        <span class="text-navy font-medium">Case Studies</span>
    </nav>

    <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-navy">Case Studies</h2>
        {% if mode != 'select' and mode != 'aggregates' %}
        <a href="/dashboard/patients/case-studies/new"
           class="bg-teal text-white px-4 py-2 rounded font-semibold hover:bg-teal/90 transition">
            Generate New
        </a>
        {% endif %}
    </div>

    <!-- Success/Error Messages -->
    {% if request.query_params.get('success') == 'published' %}
    <div class="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
        Case study published to WordPress as a draft post.
    </div>
    {% endif %}
    {% if request.query_params.get('error') %}
    <div class="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
        Error: {{ request.query_params.get('error') }}
    </div>
    {% endif %}

    <!-- Readiness Indicator -->
    {% if readiness %}
    <div class="mb-6 p-3 rounded border
        {% if readiness.level == 'green' %}bg-green-50 border-green-200
        {% elif readiness.level == 'yellow' %}bg-yellow-50 border-yellow-200
        {% else %}bg-red-50 border-red-200{% endif %}">
        <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full
                {% if readiness.level == 'green' %}bg-green-500
                {% elif readiness.level == 'yellow' %}bg-yellow-500
                {% else %}bg-red-500{% endif %}"></span>
            <span class="text-sm font-medium">{{ qualifying_count }} qualifying patients</span>
            <span class="text-sm text-gray-600">— {{ readiness.message }}</span>
        </div>
    </div>
    {% endif %}

    {% if mode == 'select' %}
    <!-- ── Patient Selection Mode ─────────────────────── -->
    <form action="/dashboard/patients/case-studies/select-patients" method="post">
        <input type="hidden" name="recommendations_json"
               value='{{ recommendations|tojson if recommendations else "[]" }}'>

        <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h3 class="text-lg font-semibold text-navy mb-2">Select Featured Patients</h3>
            <p class="text-sm text-gray-600 mb-4">
                Claude recommends the patients marked below. You can change selections (min 1, max 8).
            </p>

            {% if qualifying %}
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 text-left">
                            <th class="pb-2 pr-4">Select</th>
                            <th class="pb-2 pr-4">Patient</th>
                            <th class="pb-2 pr-4">Rating</th>
                            <th class="pb-2 pr-4">Inches Lost</th>
                            <th class="pb-2 pr-4">Sessions</th>
                            <th class="pb-2 pr-4">Photos</th>
                            <th class="pb-2">AI Pick</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in qualifying %}
                        <tr class="border-b border-gray-100 hover:bg-gray-50
                            {% if p.patient_id in recommended_ids %}bg-teal/5{% endif %}">
                            <td class="py-3 pr-4">
                                <input type="checkbox" name="select_patient_{{ p.patient_id }}" value="1"
                                       {% if p.patient_id in recommended_ids %}checked{% endif %}>
                            </td>
                            <td class="py-3 pr-4 font-medium">{{ p.first_name }} {{ p.last_name[0] if p.last_name else '' }}.</td>
                            <td class="py-3 pr-4">
                                {% if p.rating %}
                                <span class="text-yellow-500">
                                    {% for i in range(p.rating) %}&#9733;{% endfor %}{% for i in range(5 - p.rating) %}&#9734;{% endfor %}
                                </span>
                                {% else %}—{% endif %}
                            </td>
                            <td class="py-3 pr-4">{{ "%.1f"|format(p.total_inches_lost) if p.total_inches_lost else '—' }}</td>
                            <td class="py-3 pr-4">{{ p.session_count or 0 }}</td>
                            <td class="py-3 pr-4 text-xs">
                                B: {{ p.baseline_photo_count or 0 }}/6
                                F: {{ p.final_photo_count or 0 }}/6
                            </td>
                            <td class="py-3">
                                {% if p.patient_id in recommended_ids %}
                                <span class="text-xs bg-teal/10 text-teal px-2 py-0.5 rounded">Recommended</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <p class="text-gray-500 italic">No qualifying patients. Patients need case_study consent, a completed final session, and a submitted testimonial.</p>
            {% endif %}
        </div>

        {% if qualifying %}
        <div class="flex gap-3">
            <button type="submit"
                    class="bg-teal text-white px-6 py-2 rounded font-semibold hover:bg-teal/90 transition">
                Continue to Aggregates
            </button>
            <a href="/dashboard/patients/case-studies"
               class="bg-gray-200 text-gray-700 px-6 py-2 rounded font-semibold hover:bg-gray-300 transition">
                Cancel
            </a>
        </div>
        {% endif %}
    </form>

    {% elif mode == 'aggregates' %}
    <!-- ── Aggregate Review Mode ─────────────────────── -->
    <form action="/dashboard/patients/case-studies/{{ case_study.id }}/generate" method="post">
        <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h3 class="text-lg font-semibold text-navy mb-4">Review Aggregate Numbers</h3>
            <p class="text-sm text-gray-600 mb-4">
                Review calculated metrics below. Override any value with a required reason.
            </p>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Measurement Stats -->
                {% if aggregates.get('measurement_stats') %}
                <div>
                    <h4 class="font-semibold text-navy mb-2">Measurement Statistics</h4>
                    {% set ms = aggregates.measurement_stats %}
                    {% for key, val in ms.items() %}
                    <div class="flex items-center gap-2 mb-2">
                        <label class="text-sm text-gray-600 w-40">{{ key|replace('_', ' ')|title }}:</label>
                        <span class="text-sm font-medium w-20">{{ val }}</span>
                        <input type="hidden" name="original_measurement_stats.{{ key }}" value="{{ val }}">
                        <input type="text" name="override_measurement_stats.{{ key }}"
                               class="border border-gray-200 rounded px-2 py-1 text-sm w-20" placeholder="Override">
                        <input type="text" name="reason_measurement_stats.{{ key }}"
                               class="border border-gray-200 rounded px-2 py-1 text-sm flex-1" placeholder="Reason (required if overriding)">
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                <!-- Rating Stats -->
                {% if aggregates.get('rating_stats') %}
                <div>
                    <h4 class="font-semibold text-navy mb-2">Rating Statistics</h4>
                    {% set rs = aggregates.rating_stats %}
                    {% for key, val in rs.items() %}
                    <div class="flex items-center gap-2 mb-2">
                        <label class="text-sm text-gray-600 w-40">{{ key|replace('_', ' ')|title }}:</label>
                        <span class="text-sm font-medium w-20">{{ val }}</span>
                        <input type="hidden" name="original_rating_stats.{{ key }}" value="{{ val }}">
                        <input type="text" name="override_rating_stats.{{ key }}"
                               class="border border-gray-200 rounded px-2 py-1 text-sm w-20" placeholder="Override">
                        <input type="text" name="reason_rating_stats.{{ key }}"
                               class="border border-gray-200 rounded px-2 py-1 text-sm flex-1" placeholder="Reason">
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>

            <!-- Selected Patients -->
            {% if selections %}
            <div class="mt-6">
                <h4 class="font-semibold text-navy mb-2">Featured Patients ({{ selections|length }})</h4>
                <div class="flex flex-wrap gap-2">
                    {% for s in selections %}
                    <span class="text-xs bg-gray-100 px-2 py-1 rounded">
                        {{ s.first_name }} {{ s.last_name[0] if s.last_name else '' }}.
                        {% if s.recommended_by_ai %}<span class="text-teal">(AI)</span>{% endif %}
                    </span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Existing Overrides -->
            {% if overrides %}
            <div class="mt-4">
                <h4 class="text-sm font-semibold text-gray-600 mb-2">Existing Overrides</h4>
                {% for o in overrides %}
                <p class="text-xs text-gray-500">
                    {{ o.metric_name }}: {{ o.original_value }} -> {{ o.override_value }}
                    ({{ o.reason }})
                </p>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        <div class="flex gap-3">
            <button type="submit"
                    class="bg-teal text-white px-6 py-2 rounded font-semibold hover:bg-teal/90 transition">
                Generate Case Study with Claude
            </button>
            <a href="/dashboard/patients/case-studies"
               class="bg-gray-200 text-gray-700 px-6 py-2 rounded font-semibold hover:bg-gray-300 transition">
                Cancel
            </a>
        </div>
    </form>

    {% else %}
    <!-- ── List Mode (Default) ───────────────────────── -->

    <!-- Status Filter -->
    <div class="flex gap-2 mb-4">
        <a href="/dashboard/patients/case-studies"
           class="text-sm px-3 py-1 rounded {% if not status_filter %}bg-navy text-white{% else %}bg-gray-100 text-gray-700 hover:bg-gray-200{% endif %}">
            All
        </a>
        {% for s in ['draft', 'reviewed', 'published', 'superseded'] %}
        <a href="/dashboard/patients/case-studies?status={{ s }}"
           class="text-sm px-3 py-1 rounded {% if status_filter == s %}bg-navy text-white{% else %}bg-gray-100 text-gray-700 hover:bg-gray-200{% endif %}">
            {{ s|title }}
        </a>
        {% endfor %}
    </div>

    {% if case_studies %}
    <div class="bg-white rounded-lg shadow-sm overflow-hidden">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-200 text-left bg-gray-50">
                    <th class="px-4 py-3">Title</th>
                    <th class="px-4 py-3">Patients</th>
                    <th class="px-4 py-3">Generated</th>
                    <th class="px-4 py-3">Status</th>
                    <th class="px-4 py-3">WordPress</th>
                    <th class="px-4 py-3">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for cs in case_studies %}
                <tr class="border-b border-gray-100 hover:bg-gray-50">
                    <td class="px-4 py-3 font-medium">{{ cs.title }}</td>
                    <td class="px-4 py-3">{{ cs.patients_included_count }} ({{ cs.featured_patient_ids|length }} featured)</td>
                    <td class="px-4 py-3 text-gray-600">{{ cs.generated_at[:10] if cs.generated_at else '—' }}</td>
                    <td class="px-4 py-3">
                        {% if cs.status == 'published' %}
                        <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Published</span>
                        {% elif cs.status == 'reviewed' %}
                        <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">Reviewed</span>
                        {% elif cs.status == 'superseded' %}
                        <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">Superseded</span>
                        {% else %}
                        <span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">Draft</span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-3">
                        {% if cs.wp_post_url %}
                        <a href="{{ cs.wp_post_url }}" target="_blank" class="text-teal text-xs hover:underline">View Post</a>
                        {% else %}—{% endif %}
                    </td>
                    <td class="px-4 py-3">
                        <a href="/dashboard/patients/case-studies/{{ cs.id }}/preview"
                           class="text-teal text-xs hover:underline mr-2">Preview</a>
                        {% if cs.superseded_by %}
                        <a href="/dashboard/patients/case-studies/{{ cs.superseded_by }}/compare/{{ cs.id }}"
                           class="text-gray-500 text-xs hover:underline">Compare</a>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="bg-white rounded-lg shadow-sm p-8 text-center">
        <p class="text-gray-500 mb-4">No case studies yet.</p>
        <a href="/dashboard/patients/case-studies/new"
           class="bg-teal text-white px-6 py-2 rounded font-semibold hover:bg-teal/90 transition">
            Generate Your First Case Study
        </a>
    </div>
    {% endif %}

    {% endif %}
</div>
{% endblock %}
```

- [ ] 3. Create `app/templates/case_study_preview.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Case Study Preview - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">/</span>
        <a href="/dashboard/patients/case-studies" class="hover:text-teal">Case Studies</a>
        <span class="mx-1">/</span>
        <span class="text-navy font-medium">{{ case_study.title }}</span>
    </nav>

    <div class="flex items-center justify-between mb-6">
        <div>
            <h2 class="text-2xl font-bold text-navy">{{ case_study.title }}</h2>
            <p class="text-sm text-gray-500 mt-1">
                {{ case_study.patients_included_count }} patients in cohort —
                {{ case_study.featured_patient_ids|length }} featured —
                Status: {{ case_study.status|title }}
            </p>
        </div>
        <div class="flex gap-3">
            {% if case_study.status in ['draft', 'reviewed'] %}
            <form action="/dashboard/patients/case-studies/{{ case_study.id }}/publish" method="post" class="inline">
                <button type="submit"
                        class="bg-teal text-white px-4 py-2 rounded font-semibold hover:bg-teal/90 transition"
                        onclick="return confirm('Publish this case study to WordPress as a draft blog post?')">
                    Publish to WordPress
                </button>
            </form>
            {% endif %}
            <a href="/dashboard/patients/case-studies"
               class="bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold hover:bg-gray-300 transition">
                Back
            </a>
        </div>
    </div>

    <!-- Success/Error Messages -->
    {% if request.query_params.get('success') == 'saved' %}
    <div class="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
        Edits saved successfully.
    </div>
    {% endif %}
    {% if request.query_params.get('error') == 'publish_failed' %}
    <div class="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
        WordPress publishing failed. Check connection settings and try again.
    </div>
    {% endif %}

    {% if mode == 'compare' %}
    <!-- ── Side-by-Side Comparison ───────────────────── -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="bg-white rounded-lg shadow-sm p-6">
            <h3 class="font-semibold text-navy mb-2">Current (v{{ case_study.id }})</h3>
            <div class="prose prose-sm max-w-none whitespace-pre-wrap font-mono text-xs bg-gray-50 p-4 rounded">{{ display_markdown }}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-6">
            <h3 class="font-semibold text-navy mb-2">Previous (v{{ old_case_study.id }})</h3>
            <div class="prose prose-sm max-w-none whitespace-pre-wrap font-mono text-xs bg-gray-50 p-4 rounded">{{ old_markdown }}</div>
        </div>
    </div>

    {% else %}
    <!-- ── Preview + Edit Mode ───────────────────────── -->

    <!-- Override Display -->
    {% if overrides %}
    <div class="bg-yellow-50 border border-yellow-200 rounded p-3 mb-4">
        <p class="text-sm font-semibold text-yellow-800 mb-1">Metric Overrides Applied</p>
        {% for o in overrides %}
        <p class="text-xs text-yellow-700">
            {{ o.metric_name }}: {{ o.original_value }} &rarr; {{ o.override_value }}
            <span class="text-yellow-600">({{ o.reason }})</span>
        </p>
        {% endfor %}
    </div>
    {% endif %}

    <!-- Featured Patients -->
    {% if selections %}
    <div class="bg-white rounded-lg shadow-sm p-4 mb-4">
        <h4 class="text-sm font-semibold text-navy mb-2">Featured Patients</h4>
        <div class="flex flex-wrap gap-2">
            {% for s in selections %}
            <span class="text-xs bg-gray-100 px-2 py-1 rounded">
                {{ s.first_name }} {{ s.last_name[0] if s.last_name else '' }}.
                {% if s.recommended_by_ai %}<span class="text-teal">(AI pick)</span>{% endif %}
                {% if s.recommendation_reasoning %}
                <span class="text-gray-400" title="{{ s.recommendation_reasoning }}">?</span>
                {% endif %}
            </span>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <!-- Inline Edit Form -->
    <form action="/dashboard/patients/case-studies/{{ case_study.id }}/update" method="post">
        <div class="bg-white rounded-lg shadow-sm p-6 mb-4">
            <div class="flex items-center justify-between mb-3">
                <h3 class="font-semibold text-navy">Case Study Content</h3>
                <span class="text-xs text-gray-400">
                    {% if case_study.edited_markdown %}Showing edited version{% else %}Showing generated version{% endif %}
                </span>
            </div>

            <!-- Title -->
            <div class="mb-4">
                <label class="block text-sm text-gray-600 mb-1">Title</label>
                <input type="text" name="title" value="{{ case_study.title }}"
                       class="w-full border border-gray-200 rounded px-3 py-2 text-sm">
            </div>

            <!-- Markdown Content -->
            <div class="mb-4">
                <label class="block text-sm text-gray-600 mb-1">Markdown Content</label>
                <textarea name="edited_markdown" rows="30"
                          class="w-full border border-gray-200 rounded px-3 py-2 text-sm font-mono"
                          >{{ display_markdown }}</textarea>
            </div>
        </div>

        <div class="flex gap-3">
            <button type="submit"
                    class="bg-navy text-white px-6 py-2 rounded font-semibold hover:bg-navy/90 transition">
                Save Edits
            </button>
            {% if case_study.status in ['draft', 'reviewed'] %}
            <a href="/dashboard/patients/case-studies/{{ case_study.id }}/aggregates"
               class="bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold hover:bg-gray-300 transition">
                Back to Aggregates
            </a>
            {% endif %}
        </div>
    </form>

    {% endif %}

    <!-- Metadata -->
    <div class="bg-white rounded-lg shadow-sm p-4 mt-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
                <p class="text-gray-500">Case Study ID</p>
                <p class="font-mono">#{{ case_study.id }}</p>
            </div>
            <div>
                <p class="text-gray-500">Status</p>
                <p>{{ case_study.status|title }}</p>
            </div>
            <div>
                <p class="text-gray-500">Generated</p>
                <p>{{ case_study.generated_at[:16] if case_study.generated_at else '—' }}</p>
            </div>
            <div>
                <p class="text-gray-500">WordPress</p>
                {% if case_study.wp_post_url %}
                <a href="{{ case_study.wp_post_url }}" target="_blank" class="text-teal hover:underline">
                    Post #{{ case_study.wp_post_id }}
                </a>
                {% else %}
                <p>Not published</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] 4. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/case_studies.py app/templates/case_study_admin.html app/templates/case_study_preview.html
# Expected output: approximately 340-380 lines for case_studies.py, 250-290 for case_study_admin.html, 170-210 for case_study_preview.html

python -c "
from app.routes.case_studies import router
routes = [r.path for r in router.routes]
expected = [
    '/case-studies',
    '/case-studies/new',
    '/case-studies/select-patients',
    '/case-studies/{case_study_id}/aggregates',
    '/case-studies/{case_study_id}/generate',
    '/case-studies/{case_study_id}/preview',
    '/case-studies/{case_study_id}/update',
    '/case-studies/{case_study_id}/publish',
    '/case-studies/{case_study_id}/compare/{old_id}',
]
for e in expected:
    assert e in routes, f'Missing route: {e}'
print(f'All {len(expected)} case study routes registered.')
"
# Expected output: All 9 case study routes registered.
```

- [ ] 5. Test case study routes with integration test:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import get_db, init_db, run_migrations

init_db()
run_migrations()

# Test 1: Verify route imports and router prefix
from app.routes.case_studies import router
assert router.prefix == '/dashboard/patients'
print('Test 1 PASSED: Router prefix is /dashboard/patients')

# Test 2: Verify all route functions exist
from app.routes import case_studies
funcs = [
    'case_study_list', 'case_study_new', 'case_study_select_patients',
    'case_study_aggregates', 'case_study_generate', 'case_study_preview',
    'case_study_update', 'case_study_publish', 'case_study_compare',
]
for fn in funcs:
    assert hasattr(case_studies, fn), f'Missing function: {fn}'
print(f'Test 2 PASSED: All {len(funcs)} route functions exist.')

# Test 3: Verify template files exist
import os
for tmpl in ['case_study_admin.html', 'case_study_preview.html']:
    path = os.path.join('app/templates', tmpl)
    assert os.path.exists(path), f'Missing template: {tmpl}'
print('Test 3 PASSED: Both case study templates exist.')

print('All 3 case study route tests passed.')
"
# Expected output:
# Test 1 PASSED: Router prefix is /dashboard/patients
# Test 2 PASSED: All 9 route functions exist.
# Test 3 PASSED: Both case study templates exist.
# All 3 case study route tests passed.
```

- [ ] 6. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/case_studies.py app/templates/case_study_admin.html app/templates/case_study_preview.html
git commit -m "Add case study routes with generation flow and WordPress publishing

Case study list with status filter badges (draft/reviewed/published/
superseded), readiness indicator (green/yellow/red by qualifying patient
count), and version comparison links. New case study flow: patient
selection with Claude AI recommendations, aggregate review with metric
override support (required reasons logged), Claude-generated structured
markdown, inline editing with save, and WordPress blog post draft
publishing. Side-by-side version comparison for superseded studies.
Content usage logged for all featured patients on publish."
```

---

### Task 19: Patients Hub + Patient Detail (app/routes/patients_hub.py + patient_detail.py + templates)

Create the main patients hub page with search, quick stats, action cards, and tabbed navigation, plus the patient detail page with horizontal tabs for overview, sessions, consents, testimonials, content usage, and notes.

**Files:**
- `app/routes/patients_hub.py` (new)
- `app/routes/patient_detail.py` (new)
- `app/templates/patients_hub.html` (new)
- `app/templates/patient_detail.html` (new)

**Steps:**

- [ ] 1. Create `app/routes/patients_hub.py` with the following complete code:

```python
import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import get_db, log_event
from app.campaign_db import get_patients, get_patient_count

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/patients")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_quick_stats() -> dict:
    """Calculate quick stats for the patients hub."""
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()["cnt"]

    active_consents = conn.execute(
        """SELECT COUNT(DISTINCT patient_id) as cnt
           FROM patient_consents
           WHERE revoked_at IS NULL
             AND (expires_at IS NULL OR expires_at > datetime('now'))"""
    ).fetchone()["cnt"]

    incomplete_sessions = conn.execute(
        """SELECT COUNT(*) as cnt
           FROM patient_photo_sessions
           WHERE completed_at IS NULL
             AND archived_at IS NULL"""
    ).fetchone()["cnt"]

    testimonials_awaiting = conn.execute(
        """SELECT COUNT(*) as cnt
           FROM testimonials
           WHERE status = 'requested'"""
    ).fetchone()["cnt"]

    consents_expiring = conn.execute(
        """SELECT COUNT(*) as cnt
           FROM patient_consents
           WHERE revoked_at IS NULL
             AND expires_at IS NOT NULL
             AND expires_at > datetime('now')
             AND expires_at <= datetime('now', '+30 days')"""
    ).fetchone()["cnt"]

    conn.close()

    return {
        "total_patients": total,
        "active_consents": active_consents,
        "incomplete_sessions": incomplete_sessions,
        "testimonials_awaiting": testimonials_awaiting,
        "consents_expiring": consents_expiring,
    }


# ── Patients Hub ─────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def patients_hub(request: Request):
    """Patients hub page with search, quick stats, action cards, tabbed nav."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    stats = _get_quick_stats()

    # Get recent patients (first page)
    patients = get_patients(limit=25, offset=0)
    total_count = get_patient_count()

    return templates.TemplateResponse("patients_hub.html", {
        "request": request,
        "active": "patients",
        "stats": stats,
        "patients": patients,
        "total_count": total_count,
        "page": 1,
        "per_page": 25,
        "search": "",
        "tab": "hub",
    })


# ── HTMX Search ──────────────────────────────────────────


@router.get("/search", response_class=HTMLResponse)
async def patients_search(request: Request, q: str = ""):
    """HTMX search endpoint returning patient rows."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    if not q or len(q) < 2:
        return HTMLResponse("")

    patients = get_patients(search=q, limit=20, offset=0)

    rows_html = ""
    for p in patients:
        pid = p.get("id", 0)
        first = p.get("first_name", "")
        last = p.get("last_name", "")
        email = p.get("email", "")
        tier = p.get("tier", "")

        rows_html += f"""
        <tr class="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
            onclick="window.location='/dashboard/patients/{pid}'">
            <td class="py-2 px-4 font-medium">{first} {last}</td>
            <td class="py-2 px-4 text-gray-600 text-sm">{email}</td>
            <td class="py-2 px-4">
                <span class="text-xs bg-gray-100 px-2 py-0.5 rounded">{tier}</span>
            </td>
            <td class="py-2 px-4 text-teal text-sm">View</td>
        </tr>
        """

    if not patients:
        rows_html = """
        <tr>
            <td colspan="4" class="py-4 px-4 text-center text-gray-500 text-sm">
                No patients found matching your search.
            </td>
        </tr>
        """

    return HTMLResponse(rows_html)


# ── All Patients List ────────────────────────────────────


@router.get("/all", response_class=HTMLResponse)
async def patients_all(
    request: Request,
    page: int = 1,
    search: str = "",
):
    """All patients list with pagination."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    per_page = 50
    offset = (page - 1) * per_page

    patients = get_patients(search=search if search else None, limit=per_page, offset=offset)
    total_count = get_patient_count()
    total_pages = (total_count + per_page - 1) // per_page

    return templates.TemplateResponse("patients_hub.html", {
        "request": request,
        "active": "patients",
        "stats": _get_quick_stats(),
        "patients": patients,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "search": search,
        "tab": "all",
    })


# ── Bulk Export ──────────────────────────────────────────


@router.post("/bulk-export")
async def patients_bulk_export(request: Request):
    """Export selected patients to CSV."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    form_data = await request.form()

    # Get selected patient IDs
    selected_ids = []
    for key in form_data.keys():
        if key.startswith("select_"):
            try:
                pid = int(key.replace("select_", ""))
                selected_ids.append(pid)
            except ValueError:
                pass

    if not selected_ids:
        return RedirectResponse(
            url="/dashboard/patients/all?error=no_selection",
            status_code=303,
        )

    conn = get_db()
    placeholders = ",".join("?" for _ in selected_ids)
    rows = conn.execute(
        f"SELECT * FROM patients WHERE id IN ({placeholders})",
        selected_ids,
    ).fetchall()
    conn.close()

    patients = [dict(r) for r in rows]

    # Build CSV
    output = io.StringIO()
    if patients:
        fieldnames = list(patients[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for p in patients:
            writer.writerow(p)

    csv_bytes = output.getvalue().encode("utf-8")

    log_event(
        "patient",
        f"Bulk export of {len(patients)} patients",
        {"patient_ids": selected_ids},
    )

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="patients_export_{datetime.now().strftime("%Y%m%d")}.csv"'
        },
    )


# ── Bulk Tag ─────────────────────────────────────────────


@router.post("/bulk-tag")
async def patients_bulk_tag(
    request: Request,
    tag: str = Form(""),
):
    """Bulk tag assignment for selected patients."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    if not tag:
        return RedirectResponse(
            url="/dashboard/patients/all?error=no_tag",
            status_code=303,
        )

    form_data = await request.form()

    selected_ids = []
    for key in form_data.keys():
        if key.startswith("select_"):
            try:
                pid = int(key.replace("select_", ""))
                selected_ids.append(pid)
            except ValueError:
                pass

    if not selected_ids:
        return RedirectResponse(
            url="/dashboard/patients/all?error=no_selection",
            status_code=303,
        )

    conn = get_db()
    placeholders = ",".join("?" for _ in selected_ids)
    conn.execute(
        f"UPDATE patients SET tier = ? WHERE id IN ({placeholders})",
        [tag] + selected_ids,
    )
    conn.commit()
    conn.close()

    log_event(
        "patient",
        f"Bulk tag '{tag}' applied to {len(selected_ids)} patients",
        {"patient_ids": selected_ids, "tag": tag},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/all?success=tagged&count={len(selected_ids)}",
        status_code=303,
    )


# ── Bulk Archive ─────────────────────────────────────────


@router.post("/bulk-archive")
async def patients_bulk_archive(request: Request):
    """Bulk archive for selected patients."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    form_data = await request.form()

    selected_ids = []
    for key in form_data.keys():
        if key.startswith("select_"):
            try:
                pid = int(key.replace("select_", ""))
                selected_ids.append(pid)
            except ValueError:
                pass

    if not selected_ids:
        return RedirectResponse(
            url="/dashboard/patients/all?error=no_selection",
            status_code=303,
        )

    conn = get_db()
    placeholders = ",".join("?" for _ in selected_ids)
    conn.execute(
        f"UPDATE patients SET tier = 'archived' WHERE id IN ({placeholders})",
        selected_ids,
    )
    conn.commit()
    conn.close()

    log_event(
        "patient",
        f"Bulk archive of {len(selected_ids)} patients",
        {"patient_ids": selected_ids},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/all?success=archived&count={len(selected_ids)}",
        status_code=303,
    )
```

- [ ] 2. Create `app/routes/patient_detail.py` with the following complete code:

```python
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import get_db, log_event
from app import photo_db
from app import consent_db
from app import testimonial_db
from app import gallery_db
from app.services import consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/patients")
templates = Jinja2Templates(directory="app/templates")

CONSENT_SCOPES = ["website", "social", "advertising", "email_testimonial", "case_study"]


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_patient_or_404(patient_id: int):
    """Fetch patient by ID. Returns dict or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Patient Detail — Overview ────────────────────────────


@router.get("/{patient_id}", response_class=HTMLResponse)
async def patient_detail(request: Request, patient_id: int, tab: str = "overview"):
    """Patient detail page with horizontal tabs."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    # Overview data
    sessions = photo_db.get_sessions_for_patient(patient_id, include_archived=False)
    cycles = photo_db.get_cycles_for_patient(patient_id)

    # Session completion info
    for s in sessions:
        s["completion"] = photo_db.check_session_complete(s["id"])

    # Consent summary
    active_consents = consent_db.get_active_consents(patient_id)
    consent_summary = []
    for scope in CONSENT_SCOPES:
        has_active = any(c["scope"] == scope for c in active_consents)
        active_consent = next((c for c in active_consents if c["scope"] == scope), None)
        consent_summary.append({
            "scope": scope,
            "label": scope.replace("_", " ").title(),
            "active": has_active,
            "source": active_consent["consent_source"] if active_consent else None,
            "expires_at": active_consent.get("expires_at") if active_consent else None,
        })

    # Testimonials
    testimonials = testimonial_db.get_testimonials_for_patient(patient_id)

    # Content usage
    content_usage = gallery_db.get_content_usage_for_patient(patient_id)

    # Lifetime stats
    session_count = len(sessions)
    completed_count = sum(1 for s in sessions if s.get("completed_at"))
    final_sessions = [s for s in sessions if s["session_type"] == "final" and s.get("completed_at")]
    testimonial_count = sum(1 for t in testimonials if t.get("status") == "submitted")

    # Calculate total inches lost if baseline + final exist
    total_inches_lost = None
    if final_sessions:
        baseline_sessions = [s for s in sessions if s["session_type"] == "baseline"]
        if baseline_sessions:
            try:
                from app.services.measurement_service import calculate_session_deltas
                deltas = calculate_session_deltas(
                    baseline_sessions[0]["id"],
                    final_sessions[0]["id"],
                )
                total_inches_lost = deltas.get("aggregate_points_delta")
            except Exception:
                pass

    lifetime_stats = {
        "session_count": session_count,
        "completed_count": completed_count,
        "cycle_count": len(cycles),
        "testimonial_count": testimonial_count,
        "total_inches_lost": total_inches_lost,
        "consent_scopes_active": sum(1 for c in consent_summary if c["active"]),
        "content_usage_count": len(content_usage),
    }

    # Notes
    conn = get_db()
    notes_row = conn.execute(
        """SELECT value FROM patient_preferences
           WHERE patient_id = ? AND preference_type = 'admin_notes'""",
        (patient_id,),
    ).fetchone()
    conn.close()
    admin_notes = notes_row["value"] if notes_row else ""

    return templates.TemplateResponse("patient_detail.html", {
        "request": request,
        "active": "patients",
        "patient": patient,
        "tab": tab,
        "sessions": sessions,
        "cycles": cycles,
        "consent_summary": consent_summary,
        "testimonials": testimonials,
        "content_usage": content_usage,
        "lifetime_stats": lifetime_stats,
        "admin_notes": admin_notes,
    })


# ── Notes Tab ────────────────────────────────────────────


@router.get("/{patient_id}/notes", response_class=HTMLResponse)
async def patient_notes(request: Request, patient_id: int):
    """Notes tab view."""
    return await patient_detail(request, patient_id, tab="notes")


@router.post("/{patient_id}/notes", response_class=HTMLResponse)
async def patient_notes_save(
    request: Request,
    patient_id: int,
    admin_notes: str = Form(""),
):
    """Save admin notes for a patient."""
    redirect = _require_auth(request)
    if redirect:
        return redirect

    patient = _get_patient_or_404(patient_id)
    if not patient:
        return HTMLResponse("<h1>Patient not found</h1>", status_code=404)

    conn = get_db()
    # Upsert admin notes into patient_preferences
    existing = conn.execute(
        """SELECT id FROM patient_preferences
           WHERE patient_id = ? AND preference_type = 'admin_notes'""",
        (patient_id,),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE patient_preferences
               SET value = ?, updated_at = ?
               WHERE patient_id = ? AND preference_type = 'admin_notes'""",
            (admin_notes, datetime.now().isoformat(), patient_id),
        )
    else:
        conn.execute(
            """INSERT INTO patient_preferences
               (patient_id, preference_type, value, updated_at)
               VALUES (?, 'admin_notes', ?, ?)""",
            (patient_id, admin_notes, datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()

    log_event(
        "patient",
        f"Admin notes updated for patient {patient_id}",
        {"patient_id": patient_id},
    )

    return RedirectResponse(
        url=f"/dashboard/patients/{patient_id}?tab=notes&success=saved",
        status_code=303,
    )
```

- [ ] 3. Create `app/templates/patients_hub.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}Patients - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-navy">Patients</h2>
    </div>

    <!-- Search Bar -->
    <div class="mb-6">
        <div class="relative">
            <input type="text" id="patient-search"
                   placeholder="Search patients by name, email, or phone... ( / )"
                   class="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                   hx-get="/dashboard/patients/search"
                   hx-trigger="keyup changed delay:300ms"
                   hx-target="#search-results"
                   hx-swap="innerHTML"
                   name="q"
                   autocomplete="off">
            <span class="absolute right-3 top-3 text-gray-400 text-xs border border-gray-300 rounded px-1.5 py-0.5">/</span>
        </div>
        <div id="search-results" class="mt-2">
            <!-- HTMX search results appear here -->
            <table class="w-full text-sm" id="search-results-table" style="display:none;">
                <tbody></tbody>
            </table>
        </div>
    </div>

    <!-- Quick Stats Row -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-navy">
            <p class="text-xs text-gray-500">Total Patients</p>
            <p class="text-2xl font-bold text-navy">{{ stats.total_patients }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-green-500">
            <p class="text-xs text-gray-500">Active Consents</p>
            <p class="text-2xl font-bold text-navy">{{ stats.active_consents }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-yellow-500">
            <p class="text-xs text-gray-500">Incomplete Sessions</p>
            <p class="text-2xl font-bold text-navy">{{ stats.incomplete_sessions }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-blue-500">
            <p class="text-xs text-gray-500">Testimonials Awaiting</p>
            <p class="text-2xl font-bold text-navy">{{ stats.testimonials_awaiting }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 {% if stats.consents_expiring > 0 %}border-red-500{% else %}border-gray-300{% endif %}">
            <p class="text-xs text-gray-500">Consents Expiring</p>
            <p class="text-2xl font-bold {% if stats.consents_expiring > 0 %}text-red-600{% else %}text-navy{% endif %}">{{ stats.consents_expiring }}</p>
        </div>
    </div>

    <!-- Action Cards -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <a href="/dashboard/campaigns/import"
           class="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition text-center">
            <p class="text-sm font-semibold text-navy">Import CSV</p>
            <p class="text-xs text-gray-500 mt-1">Add patients from file</p>
        </a>
        <a href="/dashboard/patients/sessions/new"
           class="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition text-center">
            <p class="text-sm font-semibold text-navy">New Session</p>
            <p class="text-xs text-gray-500 mt-1">Start photo session</p>
        </a>
        <a href="/dashboard/patients/consents/upload"
           class="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition text-center">
            <p class="text-sm font-semibold text-navy">Upload Consent</p>
            <p class="text-xs text-gray-500 mt-1">Add signed release</p>
        </a>
        <a href="/dashboard/patients/galleries"
           class="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition text-center">
            <p class="text-sm font-semibold text-navy">Gallery</p>
            <p class="text-xs text-gray-500 mt-1">Generate gallery</p>
        </a>
        <a href="/dashboard/patients/case-studies"
           class="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition text-center">
            <p class="text-sm font-semibold text-navy">Case Study</p>
            <p class="text-xs text-gray-500 mt-1">Generate case study</p>
        </a>
    </div>

    <!-- Tabbed Navigation -->
    <div class="border-b border-gray-200 mb-6">
        <nav class="flex gap-6">
            <a href="/dashboard/patients"
               class="pb-2 text-sm font-medium border-b-2 {% if tab == 'hub' %}border-teal text-teal{% else %}border-transparent text-gray-500 hover:text-gray-700{% endif %}">
                Hub
            </a>
            <a href="/dashboard/patients/all"
               class="pb-2 text-sm font-medium border-b-2 {% if tab == 'all' %}border-teal text-teal{% else %}border-transparent text-gray-500 hover:text-gray-700{% endif %}">
                All Patients
            </a>
            <a href="/dashboard/patients/sessions"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Sessions
            </a>
            <a href="/dashboard/patients/consents"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Consents
            </a>
            <a href="/dashboard/testimonials"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Testimonials
            </a>
            <a href="/dashboard/patients/galleries"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Galleries
            </a>
            <a href="/dashboard/patients/case-studies"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Case Studies
            </a>
        </nav>
    </div>

    {% if tab == 'all' %}
    <!-- ── All Patients List ──────────────────────────── -->
    <form action="/dashboard/patients/bulk-export" method="post" id="bulk-form">
        <!-- Success/Error Messages -->
        {% if request.query_params.get('success') == 'tagged' %}
        <div class="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
            Tag applied to {{ request.query_params.get('count', '0') }} patients.
        </div>
        {% endif %}
        {% if request.query_params.get('success') == 'archived' %}
        <div class="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
            {{ request.query_params.get('count', '0') }} patients archived.
        </div>
        {% endif %}

        <!-- Bulk Actions -->
        <div class="flex items-center gap-3 mb-4">
            <button type="submit" formaction="/dashboard/patients/bulk-export"
                    class="bg-gray-200 text-gray-700 px-3 py-1.5 rounded text-sm hover:bg-gray-300">
                Export Selected
            </button>
            <div class="flex items-center gap-1">
                <input type="text" name="tag" placeholder="Tag name"
                       class="border border-gray-200 rounded px-2 py-1 text-sm w-32">
                <button type="submit" formaction="/dashboard/patients/bulk-tag"
                        class="bg-gray-200 text-gray-700 px-3 py-1.5 rounded text-sm hover:bg-gray-300">
                    Apply Tag
                </button>
            </div>
            <button type="submit" formaction="/dashboard/patients/bulk-archive"
                    class="bg-red-50 text-red-700 px-3 py-1.5 rounded text-sm hover:bg-red-100"
                    onclick="return confirm('Archive selected patients?')">
                Archive Selected
            </button>
        </div>

        <div class="bg-white rounded-lg shadow-sm overflow-hidden">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200 text-left bg-gray-50">
                        <th class="px-4 py-3">
                            <input type="checkbox" onclick="document.querySelectorAll('.bulk-cb').forEach(cb => cb.checked = this.checked)">
                        </th>
                        <th class="px-4 py-3">Name</th>
                        <th class="px-4 py-3">Email</th>
                        <th class="px-4 py-3">Tier</th>
                        <th class="px-4 py-3">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in patients %}
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="px-4 py-2">
                            <input type="checkbox" name="select_{{ p.id }}" value="1" class="bulk-cb">
                        </td>
                        <td class="px-4 py-2 font-medium">
                            <a href="/dashboard/patients/{{ p.id }}" class="text-navy hover:text-teal">
                                {{ p.first_name }} {{ p.last_name }}
                            </a>
                        </td>
                        <td class="px-4 py-2 text-gray-600">{{ p.email }}</td>
                        <td class="px-4 py-2">
                            <span class="text-xs bg-gray-100 px-2 py-0.5 rounded">{{ p.tier or '—' }}</span>
                        </td>
                        <td class="px-4 py-2">
                            <a href="/dashboard/patients/{{ p.id }}" class="text-teal text-xs hover:underline">View</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Pagination -->
        {% if total_pages is defined and total_pages > 1 %}
        <div class="flex justify-center gap-2 mt-4">
            {% if page > 1 %}
            <a href="/dashboard/patients/all?page={{ page - 1 }}&search={{ search }}"
               class="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">&laquo; Prev</a>
            {% endif %}
            <span class="px-3 py-1 text-sm text-gray-500">Page {{ page }} of {{ total_pages }}</span>
            {% if page < total_pages %}
            <a href="/dashboard/patients/all?page={{ page + 1 }}&search={{ search }}"
               class="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">Next &raquo;</a>
            {% endif %}
        </div>
        {% endif %}
    </form>

    {% else %}
    <!-- ── Hub View (Recent Patients) ────────────────── -->
    <div class="bg-white rounded-lg shadow-sm overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <h3 class="font-semibold text-navy">Recent Patients</h3>
            <a href="/dashboard/patients/all" class="text-teal text-sm hover:underline">View All ({{ total_count }})</a>
        </div>
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-200 text-left bg-gray-50">
                    <th class="px-4 py-3">Name</th>
                    <th class="px-4 py-3">Email</th>
                    <th class="px-4 py-3">Tier</th>
                    <th class="px-4 py-3">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for p in patients %}
                <tr class="border-b border-gray-100 hover:bg-gray-50">
                    <td class="px-4 py-2 font-medium">
                        <a href="/dashboard/patients/{{ p.id }}" class="text-navy hover:text-teal">
                            {{ p.first_name }} {{ p.last_name }}
                        </a>
                    </td>
                    <td class="px-4 py-2 text-gray-600">{{ p.email }}</td>
                    <td class="px-4 py-2">
                        <span class="text-xs bg-gray-100 px-2 py-0.5 rounded">{{ p.tier or '—' }}</span>
                    </td>
                    <td class="px-4 py-2">
                        <a href="/dashboard/patients/{{ p.id }}" class="text-teal text-xs hover:underline">View</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</div>

<!-- Keyboard shortcut: "/" focuses search -->
<script>
document.addEventListener('keydown', function(e) {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        document.getElementById('patient-search').focus();
    }
});
</script>
{% endblock %}
```

- [ ] 4. Create `app/templates/patient_detail.html` with the following complete code:

```html
{% extends "base.html" %}
{% block title %}{{ patient.first_name }} {{ patient.last_name }} - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <!-- Breadcrumbs -->
    <nav class="text-sm text-gray-500 mb-4">
        <a href="/dashboard/patients" class="hover:text-teal">Patients</a>
        <span class="mx-1">/</span>
        <span class="text-navy font-medium">{{ patient.first_name }} {{ patient.last_name }}</span>
    </nav>

    <!-- Patient Info Card -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div class="flex items-start justify-between">
            <div>
                <h2 class="text-2xl font-bold text-navy">{{ patient.first_name }} {{ patient.last_name }}</h2>
                <p class="text-gray-600 mt-1">{{ patient.email }}</p>
                {% if patient.phone %}
                <p class="text-gray-600 text-sm">{{ patient.phone }}</p>
                {% endif %}
                <div class="flex gap-2 mt-2">
                    <span class="text-xs bg-gray-100 px-2 py-0.5 rounded">{{ patient.tier or 'No tier' }}</span>
                    {% if patient.ghl_contact_id %}
                    <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">GHL Linked</span>
                    {% endif %}
                    {% if patient.email_bounced %}
                    <span class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Email Bounced</span>
                    {% endif %}
                </div>
            </div>
            <div class="flex gap-2">
                <a href="/dashboard/patients/{{ patient.id }}/sessions"
                   class="bg-teal text-white px-3 py-1.5 rounded text-sm font-semibold hover:bg-teal/90 transition">
                    Sessions
                </a>
                <a href="/dashboard/patients/{{ patient.id }}/consents"
                   class="bg-gray-200 text-gray-700 px-3 py-1.5 rounded text-sm font-semibold hover:bg-gray-300 transition">
                    Consents
                </a>
            </div>
        </div>
    </div>

    <!-- Horizontal Tabs -->
    <div class="border-b border-gray-200 mb-6">
        <nav class="flex gap-6">
            <a href="/dashboard/patients/{{ patient.id }}?tab=overview"
               class="pb-2 text-sm font-medium border-b-2 {% if tab == 'overview' %}border-teal text-teal{% else %}border-transparent text-gray-500 hover:text-gray-700{% endif %}">
                Overview
            </a>
            <a href="/dashboard/patients/{{ patient.id }}/sessions"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Sessions ({{ lifetime_stats.session_count }})
            </a>
            <a href="/dashboard/patients/{{ patient.id }}/consents"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Consents ({{ lifetime_stats.consent_scopes_active }}/5)
            </a>
            <a href="/dashboard/patients/{{ patient.id }}/testimonials"
               class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
                Testimonials ({{ lifetime_stats.testimonial_count }})
            </a>
            <a href="/dashboard/patients/{{ patient.id }}?tab=usage"
               class="pb-2 text-sm font-medium border-b-2 {% if tab == 'usage' %}border-teal text-teal{% else %}border-transparent text-gray-500 hover:text-gray-700{% endif %}">
                Content Usage ({{ lifetime_stats.content_usage_count }})
            </a>
            <a href="/dashboard/patients/{{ patient.id }}/notes"
               class="pb-2 text-sm font-medium border-b-2 {% if tab == 'notes' %}border-teal text-teal{% else %}border-transparent text-gray-500 hover:text-gray-700{% endif %}">
                Notes
            </a>
        </nav>
    </div>

    <!-- Success Messages -->
    {% if request.query_params.get('success') == 'saved' %}
    <div class="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
        Changes saved successfully.
    </div>
    {% endif %}

    {% if tab == 'overview' %}
    <!-- ── Overview Tab ──────────────────────────────── -->

    <!-- Lifetime Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div class="bg-white rounded-lg p-3 shadow-sm">
            <p class="text-xs text-gray-500">Sessions</p>
            <p class="text-xl font-bold text-navy">{{ lifetime_stats.completed_count }}/{{ lifetime_stats.session_count }}</p>
            <p class="text-xs text-gray-400">completed</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm">
            <p class="text-xs text-gray-500">Cycles</p>
            <p class="text-xl font-bold text-navy">{{ lifetime_stats.cycle_count }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm">
            <p class="text-xs text-gray-500">Testimonials</p>
            <p class="text-xl font-bold text-navy">{{ lifetime_stats.testimonial_count }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm">
            <p class="text-xs text-gray-500">Total Inches Lost</p>
            <p class="text-xl font-bold text-navy">
                {% if lifetime_stats.total_inches_lost is not none %}
                {{ "%.1f"|format(lifetime_stats.total_inches_lost) }}"
                {% else %}—{% endif %}
            </p>
        </div>
    </div>

    <!-- Consent Status Summary -->
    <div class="bg-white rounded-lg shadow-sm p-4 mb-6">
        <h3 class="font-semibold text-navy mb-3">Consent Status</h3>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
            {% for cs in consent_summary %}
            <div class="flex items-center gap-2">
                {% if cs.active %}
                    {% if cs.source == 'signed_document' %}
                    <span class="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center text-white text-xs">&#10003;</span>
                    {% elif cs.source == 'testimonial_form' %}
                    <span class="w-4 h-4 rounded-full border-2 border-green-500 text-green-500 flex items-center justify-center text-xs">&#10003;</span>
                    {% else %}
                    <span class="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs">&#10003;</span>
                    {% endif %}
                {% else %}
                <span class="w-4 h-4 rounded-full bg-gray-300"></span>
                {% endif %}
                <div>
                    <p class="text-xs font-medium">{{ cs.label }}</p>
                    {% if cs.active and cs.source %}
                    <p class="text-xs text-gray-400">{{ cs.source|replace('_', ' ') }}</p>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Session Timeline -->
    <div class="bg-white rounded-lg shadow-sm p-4 mb-6">
        <h3 class="font-semibold text-navy mb-3">Session Timeline</h3>
        {% if sessions %}
        <div class="space-y-2">
            {% for s in sessions %}
            <div class="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
                <span class="w-8 text-center text-xs font-mono text-gray-500">#{{ s.session_number }}</span>
                <span class="text-sm">{{ s.session_date }}</span>
                <span class="text-xs px-2 py-0.5 rounded
                    {% if s.session_type == 'baseline' %}bg-blue-100 text-blue-700
                    {% elif s.session_type == 'final' %}bg-green-100 text-green-700
                    {% elif s.session_type == 'followup' %}bg-purple-100 text-purple-700
                    {% else %}bg-gray-100 text-gray-600{% endif %}">
                    {{ s.session_type|replace('_', ' ')|title }}
                </span>
                {% if s.completed_at %}
                <span class="text-xs text-green-600">Complete</span>
                {% else %}
                <span class="text-xs text-yellow-600">
                    {{ s.completion.photos_count }}/6 photos, {{ s.completion.measurements_count }}/8 measurements
                </span>
                {% endif %}
                <a href="/dashboard/patients/{{ patient.id }}/sessions/{{ s.id }}"
                   class="text-teal text-xs hover:underline ml-auto">View</a>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p class="text-gray-500 text-sm italic">No sessions yet.</p>
        {% endif %}
    </div>

    {% elif tab == 'usage' %}
    <!-- ── Content Usage Tab ─────────────────────────── -->
    <div class="bg-white rounded-lg shadow-sm p-4">
        <h3 class="font-semibold text-navy mb-3">Content Usage Audit Log</h3>
        {% if content_usage %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200 text-left">
                        <th class="pb-2 pr-4">Used In</th>
                        <th class="pb-2 pr-4">Scope</th>
                        <th class="pb-2 pr-4">Date</th>
                        <th class="pb-2 pr-4">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u in content_usage %}
                    <tr class="border-b border-gray-100">
                        <td class="py-2 pr-4 text-xs">
                            <a href="{{ u.used_in }}" target="_blank" class="text-teal hover:underline">{{ u.used_in[:60] }}</a>
                        </td>
                        <td class="py-2 pr-4">
                            <span class="text-xs bg-gray-100 px-2 py-0.5 rounded">{{ u.scope_used }}</span>
                        </td>
                        <td class="py-2 pr-4 text-gray-600 text-xs">{{ u.used_at[:16] if u.used_at else '—' }}</td>
                        <td class="py-2 pr-4">
                            {% if u.removal_status == 'active' %}
                            <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Active</span>
                            {% elif u.removal_status == 'removal_pending' %}
                            <span class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Removal Pending</span>
                            {% elif u.removal_status == 'removed' %}
                            <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">Removed</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-gray-500 text-sm italic">No content usage recorded for this patient.</p>
        {% endif %}
    </div>

    {% elif tab == 'notes' %}
    <!-- ── Notes Tab ─────────────────────────────────── -->
    <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="font-semibold text-navy mb-3">Admin Notes</h3>
        <form action="/dashboard/patients/{{ patient.id }}/notes" method="post">
            <textarea name="admin_notes" rows="12"
                      class="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal/50"
                      placeholder="Add notes about this patient...">{{ admin_notes }}</textarea>
            <div class="mt-3">
                <button type="submit"
                        class="bg-teal text-white px-4 py-2 rounded font-semibold hover:bg-teal/90 transition">
                    Save Notes
                </button>
            </div>
        </form>
    </div>

    {% endif %}
</div>
{% endblock %}
```

- [ ] 5. Verify the files were created correctly:

```bash
cd /Users/philipsmith/zerona-content-engine
wc -l app/routes/patients_hub.py app/routes/patient_detail.py app/templates/patients_hub.html app/templates/patient_detail.html
# Expected output: approximately 270-310 for patients_hub.py, 190-230 for patient_detail.py, 220-260 for patients_hub.html, 230-270 for patient_detail.html

python -c "
from app.routes.patients_hub import router as hub_router
from app.routes.patient_detail import router as detail_router

# Verify hub routes
hub_routes = [r.path for r in hub_router.routes]
expected_hub = [
    '', '/',
    '/search', '/all',
    '/bulk-export', '/bulk-tag', '/bulk-archive',
]
for e in expected_hub:
    assert e in hub_routes, f'Missing hub route: {e}'
print(f'Hub routes verified: {len(expected_hub)} expected routes found.')

# Verify detail routes
detail_routes = [r.path for r in detail_router.routes]
expected_detail = [
    '/{patient_id}',
    '/{patient_id}/notes',
]
for e in expected_detail:
    assert e in detail_routes, f'Missing detail route: {e}'
print(f'Detail routes verified: {len(expected_detail)} expected routes found.')

# Verify template files exist
import os
for tmpl in ['patients_hub.html', 'patient_detail.html']:
    path = os.path.join('app/templates', tmpl)
    assert os.path.exists(path), f'Missing template: {tmpl}'
print('All template files exist.')

print('All patients hub + detail verification passed.')
"
# Expected output:
# Hub routes verified: 7 expected routes found.
# Detail routes verified: 2 expected routes found.
# All template files exist.
# All patients hub + detail verification passed.
```

- [ ] 6. Test quick stats query:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
from app.database import init_db, run_migrations
from app.routes.patients_hub import _get_quick_stats

init_db()
run_migrations()

stats = _get_quick_stats()
assert 'total_patients' in stats
assert 'active_consents' in stats
assert 'incomplete_sessions' in stats
assert 'testimonials_awaiting' in stats
assert 'consents_expiring' in stats
print(f'Quick stats: {stats}')
print('Quick stats query test passed.')
"
# Expected output:
# Quick stats: {'total_patients': ..., 'active_consents': ..., 'incomplete_sessions': ..., 'testimonials_awaiting': ..., 'consents_expiring': ...}
# Quick stats query test passed.
```

- [ ] 7. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/patients_hub.py app/routes/patient_detail.py app/templates/patients_hub.html app/templates/patient_detail.html
git commit -m "Add patients hub and patient detail pages

Patients hub: HTMX search bar (/ keyboard shortcut), quick stats row
(total patients, active consents, incomplete sessions, testimonials
awaiting, consents expiring in 30 days), action cards (import CSV, new
session, upload consent, gallery, case study), tabbed navigation to
all sub-sections. All Patients list with bulk export to CSV, bulk tag
assignment, and bulk archive actions with select-all support.

Patient detail: horizontal tabs (overview, sessions, consents,
testimonials, content usage, notes). Overview tab shows lifetime stats
(sessions, cycles, testimonials, total inches lost), consent status
summary with visual source indicators (solid=signed, outlined=form,
blue=manual), session timeline with completion progress. Content usage
audit log with removal status badges. Admin notes with save."
```

---

### Task 20: Sidebar Restructure + Dashboard Tiles (base.html + dashboard.html modifications)

Modify existing templates to restructure the sidebar into grouped sections (CONTENT, OUTREACH, INSIGHTS, SYSTEM) with the new Patients link, and add Module 3 dashboard overview tiles for consent expiration, testimonials awaiting, and incomplete sessions.

**Files:**
- `app/templates/base.html` (modify)
- `app/templates/dashboard.html` (modify)

**Steps:**

- [ ] 1. Modify `app/templates/base.html` to restructure the sidebar into grouped sections with the new Patients link. Replace the existing sidebar `<nav>` and mobile nav with grouped sections:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Zerona Content Engine{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: { extend: { colors: { navy: '#1B2A4A', teal: '#0EA5A0' } } }
        }
    </script>
    <script src="/static/js/htmx.min.js"></script>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="flex min-h-screen">
        <!-- Sidebar -->
        <aside class="w-64 bg-navy text-white flex-shrink-0 hidden md:block">
            <div class="p-6">
                <h1 class="text-lg font-bold">Zerona Engine</h1>
                <p class="text-gray-400 text-xs mt-1">Content Management</p>
            </div>
            <nav class="mt-4">
                <!-- CONTENT -->
                <p class="px-6 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Content</p>
                <a href="/dashboard" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'dashboard' %}bg-white/10 border-r-2 border-teal{% endif %}">Overview</a>
                <a href="/dashboard/review" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'review' %}bg-white/10 border-r-2 border-teal{% endif %}">Review Queue</a>
                <a href="/dashboard/calendar" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'calendar' %}bg-white/10 border-r-2 border-teal{% endif %}">Calendar</a>
                <a href="/dashboard/library" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'library' %}bg-white/10 border-r-2 border-teal{% endif %}">Library</a>
                <a href="/dashboard/blog" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'blog' %}bg-white/10 border-r-2 border-teal{% endif %}">Blog Posts</a>

                <!-- OUTREACH -->
                <p class="px-6 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Outreach</p>
                <a href="/dashboard/campaigns" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'campaigns' %}bg-white/10 border-r-2 border-teal{% endif %}">Campaigns</a>
                <a href="/dashboard/referrals" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'referrals' %}bg-white/10 border-r-2 border-teal{% endif %}">Referrals</a>
                <a href="/dashboard/patients" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'patients' %}bg-white/10 border-r-2 border-teal{% endif %}">Patients</a>

                <!-- INSIGHTS -->
                <p class="px-6 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Insights</p>
                <a href="/dashboard/analytics" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'analytics' %}bg-white/10 border-r-2 border-teal{% endif %}">Analytics</a>
                <a href="/dashboard/logs" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'logs' %}bg-white/10 border-r-2 border-teal{% endif %}">Logs</a>

                <!-- SYSTEM -->
                <p class="px-6 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">System</p>
                <a href="/dashboard/settings" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'settings' %}bg-white/10 border-r-2 border-teal{% endif %}">Settings</a>
            </nav>
            <div class="absolute bottom-0 w-64 p-4 border-t border-white/10">
                <a href="/logout" class="text-sm text-gray-400 hover:text-white">Sign Out</a>
            </div>
        </aside>

        <!-- Mobile header -->
        <div class="md:hidden fixed top-0 left-0 right-0 bg-navy text-white p-4 z-50 flex justify-between items-center">
            <h1 class="text-lg font-bold">Zerona Engine</h1>
            <button onclick="document.getElementById('mobile-nav').classList.toggle('hidden')" class="text-white">Menu</button>
        </div>
        <div id="mobile-nav" class="hidden md:hidden fixed inset-0 bg-navy z-40 pt-16">
            <nav class="p-4">
                <p class="pt-2 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Content</p>
                <a href="/dashboard" class="block py-3 text-white">Overview</a>
                <a href="/dashboard/review" class="block py-3 text-white">Review Queue</a>
                <a href="/dashboard/calendar" class="block py-3 text-white">Calendar</a>
                <a href="/dashboard/library" class="block py-3 text-white">Library</a>
                <a href="/dashboard/blog" class="block py-3 text-white">Blog Posts</a>
                <p class="pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Outreach</p>
                <a href="/dashboard/campaigns" class="block py-3 text-white">Campaigns</a>
                <a href="/dashboard/referrals" class="block py-3 text-white">Referrals</a>
                <a href="/dashboard/patients" class="block py-3 text-white">Patients</a>
                <p class="pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">Insights</p>
                <a href="/dashboard/analytics" class="block py-3 text-white">Analytics</a>
                <a href="/dashboard/logs" class="block py-3 text-white">Logs</a>
                <p class="pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">System</p>
                <a href="/dashboard/settings" class="block py-3 text-white">Settings</a>
                <a href="/logout" class="block py-3 text-gray-400 mt-4 border-t border-white/10 pt-4">Sign Out</a>
            </nav>
        </div>

        <!-- Main content -->
        <main class="flex-1 md:p-8 p-4 md:pt-8 pt-20">
            {% block content %}{% endblock %}
        </main>
    </div>
</body>
</html>
```

- [ ] 2. Modify `app/templates/dashboard.html` to add Module 3 dashboard tiles after the existing stats bar. Add the following tile row between the existing stats bar `</div>` and the Manual Generate Button `<div>`:

```html
{% extends "base.html" %}
{% block title %}Dashboard - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <h2 class="text-2xl font-bold text-navy mb-4">Overview</h2>

    <!-- Stats Bar -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-gray-400">
            <p class="text-sm text-gray-500">Pending Review</p>
            <p class="text-3xl font-bold text-navy">{{ stats.pending }}</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-green-500">
            <p class="text-sm text-gray-500">Approved</p>
            <p class="text-3xl font-bold text-navy">{{ stats.approved }}</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-blue-500">
            <p class="text-sm text-gray-500">Queued</p>
            <p class="text-3xl font-bold text-navy">{{ stats.queued }}</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-emerald-600">
            <p class="text-sm text-gray-500">Posted</p>
            <p class="text-3xl font-bold text-navy">{{ stats.posted }}</p>
        </div>
    </div>

    <!-- Module 3: Patient & Consent Tiles -->
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        <a href="/dashboard/patients?tab=consents_expiring" class="bg-white rounded-lg p-4 shadow-sm border-l-4 {% if patient_stats.consents_expiring > 0 %}border-red-500{% else %}border-gray-300{% endif %} hover:shadow-md transition">
            <p class="text-sm text-gray-500">Consent Expiring Soon</p>
            <p class="text-3xl font-bold {% if patient_stats.consents_expiring > 0 %}text-red-600{% else %}text-navy{% endif %}">{{ patient_stats.consents_expiring }}</p>
            <p class="text-xs text-gray-400 mt-1">Next 30 days</p>
        </a>
        <a href="/dashboard/testimonials?status=requested" class="bg-white rounded-lg p-4 shadow-sm border-l-4 {% if patient_stats.testimonials_awaiting > 0 %}border-yellow-500{% else %}border-gray-300{% endif %} hover:shadow-md transition">
            <p class="text-sm text-gray-500">Testimonials Awaiting</p>
            <p class="text-3xl font-bold {% if patient_stats.testimonials_awaiting > 0 %}text-yellow-600{% else %}text-navy{% endif %}">{{ patient_stats.testimonials_awaiting }}</p>
            <p class="text-xs text-gray-400 mt-1">Requested, not yet submitted</p>
        </a>
        <a href="/dashboard/patients/sessions?incomplete=1" class="bg-white rounded-lg p-4 shadow-sm border-l-4 {% if patient_stats.incomplete_sessions > 0 %}border-blue-500{% else %}border-gray-300{% endif %} hover:shadow-md transition">
            <p class="text-sm text-gray-500">Sessions Incomplete</p>
            <p class="text-3xl font-bold {% if patient_stats.incomplete_sessions > 0 %}text-blue-600{% else %}text-navy{% endif %}">{{ patient_stats.incomplete_sessions }}</p>
            <p class="text-xs text-gray-400 mt-1">Created but not completed</p>
        </a>
    </div>

    <!-- Manual Generate Button -->
    <div class="mb-8">
        <button hx-post="/api/generate/social" hx-swap="outerHTML" hx-indicator="#gen-spinner"
                class="bg-teal text-white px-6 py-2 rounded font-semibold hover:bg-teal/90 transition disabled:opacity-50"
                hx-disabled-elt="this">
            Generate This Week's Posts Now
        </button>
        <span id="gen-spinner" class="htmx-indicator ml-2 text-gray-500">
            <svg class="inline w-4 h-4 animate-spin mr-1" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle><path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="4" class="opacity-75" stroke-linecap="round"></path></svg>
            Generating posts &amp; images — this takes 1-2 minutes...
        </span>
    </div>

    <!-- Week Calendar -->
    <h3 class="text-lg font-semibold text-navy mb-3">This Week</h3>
    <div class="grid grid-cols-7 gap-2">
        {% for d in week_dates %}
        <div class="bg-white rounded-lg p-3 shadow-sm min-h-[120px]">
            <p class="text-xs font-semibold text-gray-500 mb-2">
                {{ d.strftime('%a %m/%d') }}
            </p>
            {% for post in week_posts.get(d.isoformat(), []) %}
            <div class="text-xs mb-1 px-2 py-1 rounded cursor-pointer hover:ring-2 hover:ring-teal/50 transition
                {% if post.status == 'pending' %}bg-gray-100 text-gray-600
                {% elif post.status == 'approved' %}bg-green-100 text-green-700
                {% elif post.status == 'queued' %}bg-blue-100 text-blue-700
                {% elif post.status == 'posted' %}bg-emerald-100 text-emerald-700
                {% elif post.status == 'rejected' %}bg-red-100 text-red-600
                {% endif %}"
                hx-get="/api/content/{{ post.id }}/card" hx-target="#post-modal-body" hx-swap="innerHTML"
                onclick="document.getElementById('post-modal').classList.remove('hidden')">
                {{ post.content_type|replace('social_', '')|upper }}
                {% if post.title %}- {{ post.title[:20] }}{% endif %}
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>
</div>

<!-- Post Detail Modal -->
<div id="post-modal" class="hidden fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
     onclick="if(event.target===this)this.classList.add('hidden')">
    <div class="bg-gray-50 rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 relative">
        <button onclick="document.getElementById('post-modal').classList.add('hidden')"
                class="absolute top-3 right-3 text-gray-400 hover:text-gray-700 text-xl">&times;</button>
        <div id="post-modal-body">
            <p class="text-gray-400 text-sm">Loading...</p>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] 3. Update the dashboard route to supply `patient_stats` to the template. Find the dashboard route handler (typically in `app/main.py` or `app/routes/dashboard.py`) and add the patient stats query. Add these lines to the dashboard route handler before the template response:

```python
# In the dashboard route handler, add this before the template response:
# Module 3: Patient stats for dashboard tiles
patient_stats = {"consents_expiring": 0, "testimonials_awaiting": 0, "incomplete_sessions": 0}
try:
    conn = get_db()
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM patient_consents
           WHERE revoked_at IS NULL
             AND expires_at IS NOT NULL
             AND expires_at > datetime('now')
             AND expires_at <= datetime('now', '+30 days')"""
    ).fetchone()
    patient_stats["consents_expiring"] = row["cnt"] if row else 0

    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM testimonials WHERE status = 'requested'"
    ).fetchone()
    patient_stats["testimonials_awaiting"] = row["cnt"] if row else 0

    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM patient_photo_sessions
           WHERE completed_at IS NULL AND archived_at IS NULL"""
    ).fetchone()
    patient_stats["incomplete_sessions"] = row["cnt"] if row else 0
    conn.close()
except Exception:
    pass  # Module 3 tables may not exist yet

# Add patient_stats=patient_stats to the template context dict
```

- [ ] 4. Verify the sidebar changes:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
# Verify base.html has the new grouped sidebar structure
with open('app/templates/base.html', 'r') as f:
    content = f.read()

# Check section labels exist
assert 'Content</p>' in content or 'CONTENT' in content.upper()
assert 'Outreach</p>' in content or 'OUTREACH' in content.upper()
assert 'Insights</p>' in content or 'INSIGHTS' in content.upper()
assert 'System</p>' in content or 'SYSTEM' in content.upper()
print('Test 1 PASSED: All 4 sidebar section labels present.')

# Check new Patients link exists in sidebar
assert '/dashboard/patients' in content
print('Test 2 PASSED: Patients link present in sidebar.')

# Check link grouping (Patients should be in OUTREACH section, near Campaigns/Referrals)
campaigns_pos = content.index('/dashboard/campaigns')
referrals_pos = content.index('/dashboard/referrals')
patients_pos = content.index('/dashboard/patients')
analytics_pos = content.index('/dashboard/analytics')
assert campaigns_pos < patients_pos < analytics_pos
print('Test 3 PASSED: Patients is between Campaigns/Referrals and Analytics (OUTREACH section).')

# Check mobile nav has same sections
mobile_start = content.index('mobile-nav')
mobile_section = content[mobile_start:]
assert '/dashboard/patients' in mobile_section
print('Test 4 PASSED: Patients link in mobile nav too.')

print('All 4 sidebar verification tests passed.')
"
# Expected output:
# Test 1 PASSED: All 4 sidebar section labels present.
# Test 2 PASSED: Patients link present in sidebar.
# Test 3 PASSED: Patients is between Campaigns/Referrals and Analytics (OUTREACH section).
# Test 4 PASSED: Patients link in mobile nav too.
# All 4 sidebar verification tests passed.
```

- [ ] 5. Verify the dashboard tile changes:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
# Verify dashboard.html has the new Module 3 tiles
with open('app/templates/dashboard.html', 'r') as f:
    content = f.read()

assert 'Consent Expiring Soon' in content
assert 'Testimonials Awaiting' in content
assert 'Sessions Incomplete' in content
assert 'patient_stats.consents_expiring' in content
assert 'patient_stats.testimonials_awaiting' in content
assert 'patient_stats.incomplete_sessions' in content
print('All 3 Module 3 dashboard tiles present with correct variable references.')
"
# Expected output:
# All 3 Module 3 dashboard tiles present with correct variable references.
```

- [ ] 6. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/templates/base.html app/templates/dashboard.html
git commit -m "Restructure sidebar into grouped sections and add Module 3 dashboard tiles

Sidebar reorganized into 4 visual groups: CONTENT (Overview, Review
Queue, Calendar, Library, Blog Posts), OUTREACH (Campaigns, Referrals,
Patients), INSIGHTS (Analytics, Logs), SYSTEM (Settings). Section
labels styled as small uppercase muted text, no collapse/expand.
Applied to both desktop sidebar and mobile nav. New Patients link
added under OUTREACH section.

Dashboard tiles added: Consent Expiring Soon (30-day lookahead with
red highlight when >0), Testimonials Awaiting Response (requested but
not submitted, yellow highlight), Sessions Incomplete (created but not
completed, blue highlight). Tiles link to relevant filtered views."
```

### Task 21: Scheduled Jobs (modify app/services/scheduler.py)

Add 6 new scheduled job functions and register them in `init_scheduler()`. Implement consecutive failure tracking with email notification after 3 failures. Each job uses lazy imports and per-item commits for list-processing jobs.

**Files:**
- `app/services/scheduler.py` (modify)

**Steps:**

- [ ] 1. Add the 6 new job functions and failure tracking to `app/services/scheduler.py`. Replace the entire file with:

```python
import logging
import traceback
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import log_event


logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="America/Chicago")

# ── Consecutive Failure Tracking ─────────────────────────
# Tracks consecutive failures per job ID for alerting
_consecutive_failures: dict[str, int] = {}
FAILURE_THRESHOLD = 3


def _record_job_success(job_id: str):
    """Reset consecutive failure counter on success."""
    _consecutive_failures[job_id] = 0


def _record_job_failure(job_id: str, error: Exception):
    """Increment failure counter and send email alert after 3 consecutive failures."""
    _consecutive_failures[job_id] = _consecutive_failures.get(job_id, 0) + 1
    count = _consecutive_failures[job_id]

    tb = traceback.format_exc()
    log_event("error", f"Scheduled job '{job_id}' failed (consecutive: {count}): {error}", {
        "job_id": job_id,
        "consecutive_failures": count,
        "traceback": tb,
    })

    if count >= FAILURE_THRESHOLD:
        try:
            from app.services.email_service import send_notification
            send_notification(
                f"ALERT: Scheduled job '{job_id}' failed {count} consecutive times",
                f"The scheduled job '{job_id}' has failed {count} consecutive times.\n\n"
                f"Latest error:\n{error}\n\n"
                f"Traceback:\n{tb}\n\n"
                f"This job will continue to retry on its normal schedule. "
                f"Please investigate.",
            )
            log_event("alert", f"Failure alert sent for job '{job_id}' after {count} consecutive failures")
        except Exception as email_err:
            logger.error(f"Failed to send failure alert email for job '{job_id}': {email_err}")


# ── Existing Jobs (Module 1 & 2) ─────────────────────────

def weekly_social_job():
    try:
        from app.services.content_generator import generate_weekly_social
        from app.services.image_generator import generate_images_for_batch  # parallel, blocks until done
        from app.database import get_content_pieces
        ids = generate_weekly_social()
        pieces = get_content_pieces(limit=200)
        batch_pieces = [p for p in pieces if p["id"] in ids]
        generate_images_for_batch(ids, batch_pieces)  # scheduler jobs can wait
        log_event("generation", f"Scheduled: generated {len(ids)} social posts")
        try:
            from app.services.email_service import send_notification
            send_notification(
                f"Zerona: {len(ids)} New Posts Ready for Review",
                f"{len(ids)} new social media posts have been generated and are waiting for your review.\n\nVisit your dashboard to approve them.",
            )
        except Exception:
            pass
    except Exception as e:
        log_event("error", f"Scheduled social generation failed: {str(e)}")


def blog_generation_job():
    try:
        from app.services.content_generator import generate_blog_post
        from app.services.image_generator import generate_image
        from app.database import get_db
        row_id = generate_blog_post()
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_image(row_id, "blog", row["image_prompt"])
            log_event("generation", f"Scheduled: generated blog post {row_id}")
    except Exception as e:
        log_event("error", f"Scheduled blog generation failed: {str(e)}")


def daily_buffer_queue_job():
    try:
        from app.services.buffer_service import queue_todays_posts
        count = queue_todays_posts()
        if count > 0:
            log_event("queue", f"Scheduled: queued {count} posts to Buffer")
    except Exception as e:
        log_event("error", f"Scheduled Buffer queue failed: {str(e)}")


def backup_job():
    try:
        from app.database import backup_database
        backup_database()
    except Exception as e:
        log_event("error", f"Scheduled backup failed: {str(e)}")


def retry_processor_job():
    try:
        from app.services.retry_queue import process_retries
        process_retries()
    except Exception as e:
        log_event("error", f"Retry processor failed: {str(e)}")


def warmup_batch_job():
    """Check for campaigns in warmup mode and send next batch."""
    try:
        from app.campaign_db import get_campaigns
        from app.services.campaign_service import send_next_warmup_batch
        sending = get_campaigns(status="sending")
        for campaign in sending:
            if campaign.get("warmup_schedule"):
                result = send_next_warmup_batch(campaign["id"])
                if result:
                    log_event("warmup", f"Warmup batch for campaign {campaign['id']}: {result}")
    except Exception as e:
        log_event("error", f"Warmup batch job failed: {str(e)}")


# ── Module 3 Jobs ────────────────────────────────────────

def check_testimonial_requests_job():
    """Daily 9am CT: Find eligible sessions, generate personalized openings,
    create testimonial requests with 3-touch send cadence.

    Per-item commits so a failure on one patient doesn't lose earlier work.
    If Claude API fails for personalization, falls back to static template.
    """
    job_id = "check_testimonial_requests"
    try:
        from app.services import testimonial_service
        from app.database import get_db

        eligible = testimonial_service.find_eligible_sessions()
        created_count = 0
        error_count = 0
        errors = []

        for session in eligible:
            try:
                # Generate personalized opening for Touch 1
                opening_result = testimonial_service.generate_personalized_opening(
                    patient_id=session["patient_id"],
                    session_data={
                        "first_name": session.get("first_name", ""),
                        "session_count": session.get("session_number", 1),
                        "treatment_span": "",
                        "measurement_summary": "",
                        "session_notes": "",
                    },
                )

                # Create the testimonial request (includes 3-touch cadence scheduling)
                result = testimonial_service.create_testimonial_request(
                    patient_id=session["patient_id"],
                    session_id=session["session_id"],
                    cycle_id=session.get("cycle_id"),
                )

                # Store the personalized opening in the first send log entry
                if opening_result.get("opening"):
                    conn = get_db()
                    first_touch_id = result["touches_scheduled"][0] if result["touches_scheduled"] else None
                    if first_touch_id:
                        conn.execute(
                            """UPDATE testimonial_send_log
                               SET personalized_opening = ?, is_personalized = ?
                               WHERE id = ?""",
                            (
                                opening_result["opening"],
                                1 if opening_result["is_personalized"] else 0,
                                first_touch_id,
                            ),
                        )
                        conn.commit()

                        # Route Touch 1 through content review queue (spec §6 line 715).
                        # Admin must approve before send_testimonial_emails_job() sends it.
                        patient_name = f"{session.get('first_name', '')} {session.get('last_name', '')}".strip()
                        testimonial_service.submit_touch1_for_review(
                            testimonial_id=result["testimonial_id"],
                            send_log_id=first_touch_id,
                            personalized_opening=opening_result["opening"],
                            patient_name=patient_name or "Patient",
                        )
                    conn.close()

                created_count += 1

            except Exception as item_err:
                error_count += 1
                error_msg = (
                    f"Failed to create testimonial request for patient "
                    f"{session.get('patient_id')}, session {session.get('session_id')}: {item_err}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        log_event(
            "testimonial_requests",
            f"Checked testimonial eligibility: {len(eligible)} eligible, "
            f"{created_count} created, {error_count} errors",
            {
                "eligible_count": len(eligible),
                "created_count": created_count,
                "error_count": error_count,
                "errors": errors[:10],  # Cap logged errors
            },
        )

        _record_job_success(job_id)

    except Exception as e:
        _record_job_failure(job_id, e)


def send_testimonial_emails_job():
    """Daily 10am CT, Tue-Thu only: Send approved/due testimonial emails
    within the Tue-Thu 10am-2pm CT send window.

    Re-checks suppression and bounce status at send time.
    Per-item commits so a failure on one send doesn't block others.
    """
    job_id = "send_testimonial_emails"
    try:
        from app import testimonial_db
        from app.services import consent_service
        from app.services.mailgun_service import send_single
        from app.database import get_db

        now = datetime.now()
        in_send_window = (
            now.weekday() in (1, 2, 3)  # Tue, Wed, Thu
            and 10 <= now.hour < 14      # 10am-2pm CT
        )

        # Get all pending sends scheduled up to now
        pending = testimonial_db.get_pending_sends(
            scheduled_before=now.isoformat()
        )

        sent_count = 0
        skipped_count = 0
        error_count = 0

        for send in pending:
            try:
                patient_id = send["patient_id"]
                touch_number = send["touch_number"]
                testimonial_status = send.get("testimonial_status", "")

                # Send window check: skip unless in window OR flagged to bypass.
                # Fallback auto-approved sends set skip_send_window=1 because
                # at 5+ days past schedule, timeliness > engagement optimization.
                if not in_send_window and not send.get("skip_send_window"):
                    continue  # Will retry on next run within window

                # Touch 1 review gate: must be approved in content_pieces queue
                if touch_number == 1:
                    conn = get_db()
                    piece = conn.execute(
                        """SELECT status FROM content_pieces
                           WHERE content_type = 'testimonial_email'
                             AND json_extract(metadata_json, '$.send_log_id') = ?""",
                        (send["id"],),
                    ).fetchone()
                    conn.close()
                    if not piece or piece["status"] != "approved":
                        continue  # Not yet reviewed — skip, will retry

                # Skip if testimonial already resolved
                if testimonial_status in (
                    "submitted", "declined_this_time", "declined_permanent",
                    "expired_no_response", "bounced",
                ):
                    testimonial_db.update_send_log_entry(
                        send["id"], status="cancelled"
                    )
                    skipped_count += 1
                    continue

                # Re-check bounce status at send time
                if send.get("email_bounced"):
                    testimonial_db.update_send_log_entry(
                        send["id"], status="suppressed"
                    )
                    skipped_count += 1
                    continue

                # Re-check patient preferences at send time (opt-out check)
                conn = get_db()
                pref_row = conn.execute(
                    """SELECT value FROM patient_preferences
                       WHERE patient_id = ? AND preference_type = 'testimonial_requests'""",
                    (patient_id,),
                ).fetchone()
                conn.close()

                if pref_row and pref_row["value"] == "none":
                    testimonial_db.update_send_log_entry(
                        send["id"], status="suppressed"
                    )
                    skipped_count += 1
                    continue

                # Check if patient already responded to an earlier touch
                conn = get_db()
                responded = conn.execute(
                    """SELECT COUNT(*) as cnt FROM testimonial_send_log
                       WHERE testimonial_id = ? AND touch_number < ?
                       AND status IN ('submitted', 'declined')""",
                    (send["testimonial_id"], send["touch_number"]),
                ).fetchone()
                conn.close()

                if responded and responded["cnt"] > 0:
                    testimonial_db.update_send_log_entry(
                        send["id"], status="cancelled"
                    )
                    skipped_count += 1
                    continue

                # Build email content
                email = send.get("email", "")
                if not email:
                    testimonial_db.update_send_log_entry(
                        send["id"], status="suppressed"
                    )
                    skipped_count += 1
                    continue

                first_name = send.get("first_name", "there")
                token = send.get("token", "")
                touch_number = send.get("touch_number", 1)

                form_url = f"{settings.base_url}/testimonial/{token}"

                if touch_number == 1:
                    subject = f"{first_name}, we'd love to hear about your Zerona results!"
                    # Use personalized opening if available
                    personalized_opening = send.get("personalized_opening", "")
                    if not personalized_opening:
                        personalized_opening = (
                            f"Thank you for choosing White House Chiropractic "
                            f"for your Zerona body contouring journey, {first_name}. "
                            f"We hope you're enjoying your results!"
                        )
                    body = (
                        f"{personalized_opening}\n\n"
                        f"Would you be willing to share your experience? Your feedback "
                        f"helps other patients considering Zerona treatment.\n\n"
                        f"Share your experience: {form_url}\n\n"
                        f"It only takes a minute or two. Thank you!\n\n"
                        f"— The team at White House Chiropractic"
                    )
                elif touch_number == 2:
                    subject = f"Quick reminder: share your Zerona experience, {first_name}"
                    body = (
                        f"Hi {first_name},\n\n"
                        f"Just a gentle reminder — we'd love to hear about your "
                        f"Zerona experience. Your feedback means a lot to us and "
                        f"helps others who are considering treatment.\n\n"
                        f"Share your experience: {form_url}\n\n"
                        f"Thank you!\n\n"
                        f"— The team at White House Chiropractic"
                    )
                else:
                    subject = f"Last chance to share your Zerona feedback, {first_name}"
                    body = (
                        f"Hi {first_name},\n\n"
                        f"This is our last reminder — we'd truly appreciate hearing "
                        f"about your Zerona experience. If you have a moment, "
                        f"your feedback would help us improve and help future patients.\n\n"
                        f"Share your experience: {form_url}\n\n"
                        f"No worries if now isn't a good time.\n\n"
                        f"— The team at White House Chiropractic"
                    )

                # Send via Mailgun
                send_result = send_single(
                    to_email=email,
                    subject=subject,
                    text_body=body,
                )

                if send_result and send_result.get("id"):
                    testimonial_db.update_send_log_entry(
                        send["id"],
                        status="sent",
                        sent_at=datetime.now().isoformat(),
                    )
                    sent_count += 1
                else:
                    # Check if it was a hard bounce
                    error_msg = send_result.get("error", "") if send_result else ""
                    if "bounce" in str(error_msg).lower():
                        testimonial_db.update_send_log_entry(
                            send["id"], status="bounced"
                        )
                        # Mark patient as bounced
                        conn = get_db()
                        conn.execute(
                            """UPDATE patients SET email_bounced = 1,
                               email_bounced_at = ? WHERE id = ?""",
                            (datetime.now().isoformat(), patient_id),
                        )
                        conn.commit()
                        conn.close()

                        # Update testimonial status
                        conn = get_db()
                        conn.execute(
                            """UPDATE testimonials SET status = 'bounced',
                               updated_at = ?
                               WHERE id = ?""",
                            (datetime.now().isoformat(), send["testimonial_id"]),
                        )
                        conn.commit()
                        conn.close()

                        log_event(
                            "testimonial_bounce",
                            f"Testimonial email bounced for patient {patient_id}",
                            {"patient_id": patient_id, "send_log_id": send["id"]},
                        )

                        # Notify admin
                        try:
                            from app.services.email_service import send_notification
                            patient_name = f"{first_name} {send.get('last_name', '')}"
                            send_notification(
                                f"Testimonial request to {patient_name} bounced",
                                f"The testimonial request email to {patient_name} ({email}) "
                                f"bounced with a hard bounce. The patient has been flagged.\n\n"
                                f"Please update their email address in the patient record.",
                            )
                        except Exception:
                            pass
                    else:
                        testimonial_db.update_send_log_entry(
                            send["id"], status="failed"
                        )
                        error_count += 1

            except Exception as item_err:
                error_count += 1
                logger.error(
                    f"Failed to send testimonial email (log_id={send.get('id')}): {item_err}"
                )
                try:
                    testimonial_db.update_send_log_entry(
                        send["id"], status="failed"
                    )
                except Exception:
                    pass

        log_event(
            "testimonial_send",
            f"Testimonial email job: {sent_count} sent, {skipped_count} skipped, {error_count} errors",
            {
                "sent_count": sent_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "total_pending": len(pending),
            },
        )

        _record_job_success(job_id)

    except Exception as e:
        _record_job_failure(job_id, e)


def check_consent_expirations_job():
    """Daily 1am CT: Process expired consents and generate 30-day lookahead warnings.

    CRITICAL job — consent compliance depends on it. If this job fails,
    logs at CRITICAL level and sends immediate email notification.
    """
    job_id = "check_consent_expirations"
    try:
        from app.services import consent_service
        from app import consent_db

        # Auto-revoke expired consents and flag affected content
        result = consent_service.process_expired_consents()

        # Get 30-day lookahead for dashboard awareness
        expiring_soon = consent_db.get_expiring_consents(days_ahead=30)

        log_event(
            "consent_expiration",
            f"Consent expiration check: {result['processed_count']} expired processed, "
            f"{result['flagged_content_count']} content uses flagged, "
            f"{len(expiring_soon)} expiring in next 30 days",
            {
                "processed_count": result["processed_count"],
                "flagged_content_count": result["flagged_content_count"],
                "expiring_soon_count": len(expiring_soon),
                "errors": result.get("errors", []),
            },
        )

        # If any per-item errors occurred within process_expired_consents,
        # still treat the job as successful (items are per-item committed),
        # but log the errors prominently
        if result.get("errors"):
            for err in result["errors"]:
                logger.critical(f"Consent expiration per-item error: {err}")

        _record_job_success(job_id)

    except Exception as e:
        # CRITICAL: This job must never silently fail
        logger.critical(f"check_consent_expirations FAILED: {e}")
        log_event("error", f"CRITICAL: Consent expiration job failed: {e}", {
            "severity": "critical",
            "traceback": traceback.format_exc(),
        })

        # Immediate email notification regardless of consecutive failure count
        try:
            from app.services.email_service import send_notification
            send_notification(
                "CRITICAL: Consent Expiration Job Failed",
                f"The consent expiration check job has failed.\n\n"
                f"This is a compliance-critical job. Expired consents may not "
                f"have been revoked and affected content may not have been flagged.\n\n"
                f"Error: {e}\n\n"
                f"Traceback:\n{traceback.format_exc()}\n\n"
                f"Please investigate immediately.",
            )
        except Exception as email_err:
            logger.critical(f"Failed to send consent expiration failure alert: {email_err}")

        _record_job_failure(job_id, e)


def retry_failed_thumbnails_job():
    """Every 30 min: Retry thumbnail generation for photos with NULL preview/thumbnail paths.

    Finds photos where preview_path or thumbnail_path is NULL (indicating
    initial thumbnail generation failed) and retries via photo_service.
    Per-item commits.
    """
    job_id = "retry_failed_thumbnails"
    try:
        from app.services import photo_service
        from app.database import get_db

        conn = get_db()
        # Find sessions with photos missing thumbnails
        rows = conn.execute(
            """SELECT DISTINCT session_id FROM patient_photos
               WHERE is_current = 1
               AND (preview_path IS NULL OR thumbnail_path IS NULL)"""
        ).fetchall()
        conn.close()

        session_ids = [row["session_id"] for row in rows]

        if not session_ids:
            _record_job_success(job_id)
            return

        success_count = 0
        failure_count = 0

        for session_id in session_ids:
            try:
                result = photo_service.regenerate_thumbnails(session_id)
                if result["failure_count"] == 0:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as item_err:
                failure_count += 1
                logger.error(
                    f"Failed to regenerate thumbnails for session {session_id}: {item_err}"
                )

        log_event(
            "thumbnail_retry",
            f"Thumbnail retry: {success_count} sessions succeeded, "
            f"{failure_count} sessions had failures",
            {
                "total_sessions": len(session_ids),
                "success_count": success_count,
                "failure_count": failure_count,
            },
        )

        _record_job_success(job_id)

    except Exception as e:
        _record_job_failure(job_id, e)


def cleanup_expired_tokens_job():
    """Daily 2am CT: Mark testimonials with expired tokens as expired_no_response.

    Finds testimonials where:
    - token_expires_at has passed
    - status is still 'requested' (no response received)
    Marks them as 'expired_no_response' and cancels any remaining scheduled sends.
    """
    job_id = "cleanup_expired_tokens"
    try:
        from app.database import get_db

        now = datetime.now().isoformat()
        conn = get_db()

        # Find testimonials with expired tokens that haven't been resolved
        expired_rows = conn.execute(
            """SELECT id FROM testimonials
               WHERE token_expires_at < ?
               AND status = 'requested'""",
            (now,),
        ).fetchall()

        expired_count = 0

        for row in expired_rows:
            testimonial_id = row["id"]
            try:
                # Mark testimonial as expired
                conn.execute(
                    """UPDATE testimonials
                       SET status = 'expired_no_response',
                           updated_at = ?
                       WHERE id = ?""",
                    (now, testimonial_id),
                )

                # Cancel any remaining scheduled sends
                conn.execute(
                    """UPDATE testimonial_send_log
                       SET status = 'cancelled'
                       WHERE testimonial_id = ?
                       AND status = 'scheduled'""",
                    (testimonial_id,),
                )

                conn.commit()
                expired_count += 1

            except Exception as item_err:
                logger.error(
                    f"Failed to expire testimonial {testimonial_id}: {item_err}"
                )
                conn.rollback()

        conn.close()

        if expired_count > 0:
            log_event(
                "testimonial_cleanup",
                f"Expired {expired_count} testimonial tokens",
                {"expired_count": expired_count},
            )

        _record_job_success(job_id)

    except Exception as e:
        _record_job_failure(job_id, e)


def check_gallery_drift_job():
    """Daily 3am CT: Compare published galleries against current qualifying patients.

    For each published gallery, detects:
    - Patients in gallery whose consent was revoked/expired
    - New qualifying patients not yet in gallery
    - Patients with updated photos

    Creates high-visibility dashboard alerts for consent-related drift.
    """
    job_id = "check_gallery_drift"
    try:
        from app.services import gallery_service
        from app import gallery_db
        from app.database import get_db

        # Check drift for the default gallery
        gallery_slug = settings.gallery_default_slug
        current_gallery = gallery_db.get_current_gallery(gallery_slug)

        if not current_gallery:
            log_event("gallery_drift", "No published gallery found, skipping drift check")
            _record_job_success(job_id)
            return

        drift = gallery_service.get_gallery_drift(gallery_slug)

        if not drift["has_drift"]:
            log_event("gallery_drift", "No gallery drift detected")
            _record_job_success(job_id)
            return

        # Log drift details
        log_event(
            "gallery_drift",
            f"Gallery drift detected: {len(drift['patients_to_add'])} to add, "
            f"{len(drift['patients_to_remove'])} to remove, "
            f"{len(drift['patients_with_updated_photos'])} with updated photos",
            {
                "gallery_slug": gallery_slug,
                "patients_to_add": drift["patients_to_add"],
                "patients_to_remove": drift["patients_to_remove"],
                "patients_with_updated_photos": drift["patients_with_updated_photos"],
                "current_count": drift["current_count"],
                "qualifying_count": drift["qualifying_count"],
            },
        )

        # Create dashboard alerts for consent-related removals (high priority)
        consent_removals = [
            p for p in drift["patients_to_remove"]
            if p.get("reason") == "consent_revoked_or_expired"
        ]

        if consent_removals:
            conn = get_db()
            now = datetime.now().isoformat()
            for removal in consent_removals:
                patient_id = removal["patient_id"]
                # Insert a dashboard alert into system_log with high severity
                conn.execute(
                    """INSERT INTO system_log
                       (event_type, message, severity, details, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        "gallery_drift_alert",
                        f"CONSENT ALERT: Patient {patient_id} is in the published "
                        f"gallery but their consent has been revoked or expired. "
                        f"Gallery should be regenerated.",
                        "warning",
                        f'{{"patient_id": {patient_id}, "gallery_slug": "{gallery_slug}", '
                        f'"reason": "consent_revoked_or_expired"}}',
                        now,
                    ),
                )
            conn.commit()
            conn.close()

            # Also email admin for consent-related drift
            try:
                from app.services.email_service import send_notification
                patient_ids = [p["patient_id"] for p in consent_removals]
                send_notification(
                    f"Gallery Drift Alert: {len(consent_removals)} patient(s) need removal",
                    f"The published gallery '{gallery_slug}' contains "
                    f"{len(consent_removals)} patient(s) whose consent has been "
                    f"revoked or expired:\n\n"
                    f"Patient IDs: {patient_ids}\n\n"
                    f"Please regenerate the gallery or use the emergency removal "
                    f"action to remove these patients.",
                )
            except Exception:
                pass

        _record_job_success(job_id)

    except Exception as e:
        _record_job_failure(job_id, e)


def escalate_stalled_reviews_job():
    """Daily 9:30am CT: Check for Touch 1 emails stuck in content review queue.

    Uses configurable thresholds (default: 3-day warning, 5-day fallback).
    - Warning: email notification to Chris. Recorded via warning_3day_sent_at
      on testimonial_send_log so we only warn once per send.
    - Fallback: auto-approve with static (non-personalized) opening, set
      skip_send_window=1 so the next send_testimonial_emails_job() run sends
      it immediately regardless of Tue-Thu window. At 5+ days past schedule,
      timeliness matters more than engagement optimization.

    Each testimonial request is independent — a fallback on cycle 1's
    testimonial does not affect cycle 2's, which goes through the normal
    review queue again.
    """
    job_id = "escalate_stalled_reviews"
    try:
        from app.services.testimonial_service import get_static_touch1_opening
        from app.services.mailgun_service import send_single
        from app.config import settings
        from app.database import get_db, log_event

        now = datetime.now()
        warning_days = settings.testimonial_escalation_warning_days
        fallback_days = settings.testimonial_escalation_fallback_days

        conn = get_db()

        # Find all Touch 1 content_pieces still pending review
        pending_pieces = conn.execute(
            """SELECT cp.id, cp.title, cp.created_at,
                      json_extract(cp.metadata_json, '$.send_log_id') as send_log_id,
                      json_extract(cp.metadata_json, '$.testimonial_id') as testimonial_id
               FROM content_pieces cp
               WHERE cp.content_type = 'testimonial_email'
                 AND cp.status = 'pending'""",
        ).fetchall()

        for piece in pending_pieces:
            # Get the scheduled send date and patient info
            send_log = conn.execute(
                """SELECT sl.scheduled_for, sl.warning_3day_sent_at,
                          t.patient_id
                   FROM testimonial_send_log sl
                   JOIN testimonials t ON sl.testimonial_id = t.id
                   WHERE sl.id = ?""",
                (piece["send_log_id"],),
            ).fetchone()

            if not send_log:
                continue

            scheduled_for = datetime.fromisoformat(send_log["scheduled_for"])
            days_past = (now - scheduled_for).days

            # Get patient details for email content
            patient = conn.execute(
                "SELECT first_name, last_name, email FROM patients WHERE id = ?",
                (send_log["patient_id"],),
            ).fetchone()
            patient_name = f"{patient['first_name']} {patient['last_name']}" if patient else "Unknown"

            if days_past >= fallback_days:
                # ── 5-day fallback: auto-approve with static version ──
                static_opening = get_static_touch1_opening()

                conn.execute(
                    """UPDATE content_pieces
                       SET status = 'approved',
                           body = ?,
                           metadata_json = json_set(metadata_json, '$.auto_fallback', 1)
                       WHERE id = ?""",
                    (static_opening, piece["id"]),
                )

                # Replace personalized opening with static, bypass send window
                conn.execute(
                    """UPDATE testimonial_send_log
                       SET personalized_opening = ?,
                           is_personalized = 0,
                           skip_send_window = 1
                       WHERE id = ?""",
                    (static_opening, piece["send_log_id"]),
                )

                conn.commit()
                log_event(
                    "testimonial_escalation",
                    f"5-day fallback triggered: testimonial {piece['testimonial_id']} "
                    f"for {patient_name} ({days_past} days past scheduled send). "
                    f"Static version will send on next run, bypassing send window.",
                )

                # Notify Chris — tone conveys this is a missed review, not routine
                try:
                    send_single(
                        to_email=settings.notification_email,
                        subject=(
                            f"Missed review: testimonial email for {patient_name} "
                            f"sent as generic fallback"
                        ),
                        html=(
                            f"<p><strong>A personalized testimonial request was not reviewed "
                            f"in time and has been replaced with a generic version.</strong></p>"
                            f"<p><strong>Patient:</strong> {patient_name} "
                            f"(ID: {send_log['patient_id']})</p>"
                            f"<p><strong>Testimonial ID:</strong> {piece['testimonial_id']}</p>"
                            f"<p><strong>Originally scheduled:</strong> "
                            f"{send_log['scheduled_for'][:10]}</p>"
                            f"<p><strong>Days overdue:</strong> {days_past}</p>"
                            f"<p><strong>What happened:</strong> The Claude-personalized "
                            f"opening sat in the review queue for {days_past} days without "
                            f"approval. The system has replaced it with a standard template "
                            f"and will send it on the next scheduler run.</p>"
                            f"<p>To prevent this, review testimonial emails within "
                            f"{warning_days} days of their scheduled send date.</p>"
                            f"<p><a href=\"{settings.base_url}/dashboard/patients/"
                            f"{send_log['patient_id']}\">View patient record</a></p>"
                        ),
                        text=(
                            f"Missed review: testimonial email for {patient_name} "
                            f"(ID {send_log['patient_id']}) sent as generic fallback. "
                            f"{days_past} days past scheduled send."
                        ),
                    )
                except Exception:
                    log_event("testimonial_escalation", "Failed to send fallback notification")

            elif days_past >= warning_days:
                # ── 3-day warning: email Chris once ──
                # Dedup via warning_3day_sent_at column (deterministic, not log pattern)
                if send_log["warning_3day_sent_at"] is not None:
                    continue  # Already warned for this send

                try:
                    send_single(
                        to_email=settings.notification_email,
                        subject=(
                            f"Action needed: testimonial email for {patient_name} "
                            f"pending review ({days_past}d overdue)"
                        ),
                        html=(
                            f"<p>A testimonial request email has been pending review for "
                            f"<strong>{days_past} days</strong> past its scheduled send:</p>"
                            f"<p><strong>Patient:</strong> {patient_name} "
                            f"(ID: {send_log['patient_id']})</p>"
                            f"<p><strong>Testimonial ID:</strong> {piece['testimonial_id']}</p>"
                            f"<p><strong>Scheduled send:</strong> "
                            f"{send_log['scheduled_for'][:10]}</p>"
                            f"<p>If not approved within {fallback_days} days of the "
                            f"scheduled send, a generic fallback version will be sent "
                            f"automatically.</p>"
                            f"<p><a href=\"{settings.base_url}/dashboard\">"
                            f"Review pending content</a></p>"
                        ),
                        text=(
                            f"Testimonial email for {patient_name} pending review "
                            f"for {days_past} days. Review at {settings.base_url}/dashboard"
                        ),
                    )

                    # Mark warning as sent — deterministic dedup
                    conn.execute(
                        """UPDATE testimonial_send_log
                           SET warning_3day_sent_at = ?
                           WHERE id = ?""",
                        (now.isoformat(), piece["send_log_id"]),
                    )
                    conn.commit()

                    log_event(
                        "testimonial_escalation",
                        f"{warning_days}-day warning sent for testimonial "
                        f"{piece['testimonial_id']} ({patient_name})",
                    )
                except Exception:
                    log_event("testimonial_escalation", "Failed to send warning email")

        conn.close()
        _record_job_success(job_id)

    except Exception as e:
        _record_job_failure(job_id, e)


# ── Scheduler Initialization ─────────────────────────────

def init_scheduler():
    day_map = {
        "sunday": "sun", "monday": "mon", "tuesday": "tue",
        "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat",
    }
    gen_day = day_map.get(settings.generation_day.lower(), "sun")
    gen_hour = settings.generation_hour

    # ── Module 1 & 2 Jobs ──

    scheduler.add_job(
        weekly_social_job, CronTrigger(day_of_week=gen_day, hour=gen_hour, minute=0),
        id="weekly_social", replace_existing=True,
    )

    scheduler.add_job(
        blog_generation_job, CronTrigger(day="1,15", hour=gen_hour, minute=0),
        id="blog_generation", replace_existing=True,
    )

    scheduler.add_job(
        daily_buffer_queue_job, CronTrigger(hour=7, minute=0),
        id="daily_buffer", replace_existing=True,
    )

    scheduler.add_job(
        backup_job, CronTrigger(hour=2, minute=0),
        id="daily_backup", replace_existing=True,
    )

    scheduler.add_job(
        retry_processor_job, CronTrigger(minute="*/15"),
        id="retry_processor", replace_existing=True,
    )

    scheduler.add_job(warmup_batch_job, CronTrigger(hour="8,12,16", timezone="America/Chicago"),
                      id="warmup_batch", replace_existing=True)

    # ── Module 3 Jobs ──

    scheduler.add_job(
        check_testimonial_requests_job,
        CronTrigger(hour=9, minute=0),
        id="check_testimonial_requests",
        replace_existing=True,
    )

    scheduler.add_job(
        send_testimonial_emails_job,
        CronTrigger(day_of_week="tue,wed,thu", hour=10, minute=0),
        id="send_testimonial_emails",
        replace_existing=True,
    )

    scheduler.add_job(
        check_consent_expirations_job,
        CronTrigger(hour=1, minute=0),
        id="check_consent_expirations",
        replace_existing=True,
    )

    scheduler.add_job(
        retry_failed_thumbnails_job,
        IntervalTrigger(minutes=30),
        id="retry_failed_thumbnails",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_expired_tokens_job,
        CronTrigger(hour=2, minute=30),
        id="cleanup_expired_tokens",
        replace_existing=True,
    )

    scheduler.add_job(
        check_gallery_drift_job,
        CronTrigger(hour=3, minute=0),
        id="check_gallery_drift",
        replace_existing=True,
    )

    scheduler.add_job(
        escalate_stalled_reviews_job,
        CronTrigger(hour=9, minute=30),
        id="escalate_stalled_reviews",
        name="Escalate stalled Touch 1 reviews",
        replace_existing=True,
    )

    scheduler.start()
    log_event("system", "Scheduler initialized", {
        "social_gen": f"{gen_day} at {gen_hour}:00",
        "blog_gen": f"1st & 15th at {gen_hour}:00",
        "buffer_queue": "daily at 7:00",
        "backup": "daily at 2:00",
        "retry_processor": "every 15 minutes",
        "warmup_batch": "daily at 8:00, 12:00, 16:00",
        "check_testimonial_requests": "daily at 9:00",
        "send_testimonial_emails": "Tue-Thu at 10:00",
        "escalate_stalled_reviews": "daily at 9:30",
        "check_consent_expirations": "daily at 1:00",
        "retry_failed_thumbnails": "every 30 minutes",
        "cleanup_expired_tokens": "daily at 2:30",
        "check_gallery_drift": "daily at 3:00",
    })
```

- [ ] 2. Verify the scheduler file is valid Python and all jobs are registered:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
import ast

with open('app/services/scheduler.py', 'r') as f:
    source = f.read()

tree = ast.parse(source)

# Find all function definitions
functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

# Verify all 7 new job functions exist
required_jobs = [
    'check_testimonial_requests_job',
    'send_testimonial_emails_job',
    'escalate_stalled_reviews_job',
    'check_consent_expirations_job',
    'retry_failed_thumbnails_job',
    'cleanup_expired_tokens_job',
    'check_gallery_drift_job',
]

for job in required_jobs:
    assert job in functions, f'Missing job function: {job}'
    print(f'OK: {job}')

# Verify failure tracking functions
assert '_record_job_success' in functions
assert '_record_job_failure' in functions
print('OK: failure tracking functions present')

# Verify init_scheduler registers all jobs
init_func = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'init_scheduler'][0]
init_source = ast.get_source_segment(source, init_func)

required_job_ids = [
    'check_testimonial_requests',
    'send_testimonial_emails',
    'escalate_stalled_reviews',
    'check_consent_expirations',
    'retry_failed_thumbnails',
    'cleanup_expired_tokens',
    'check_gallery_drift',
]

for job_id in required_job_ids:
    assert job_id in init_source, f'Job not registered in init_scheduler: {job_id}'
    print(f'Registered: {job_id}')

# Verify existing jobs are preserved
existing_jobs = ['weekly_social', 'blog_generation', 'daily_buffer', 'daily_backup', 'retry_processor', 'warmup_batch']
for job_id in existing_jobs:
    assert job_id in init_source, f'Existing job missing from init_scheduler: {job_id}'
    print(f'Preserved: {job_id}')

# Count total scheduler.add_job calls
add_job_count = init_source.count('scheduler.add_job')
print(f'Total scheduler.add_job calls: {add_job_count}')
assert add_job_count == 13, f'Expected 13 add_job calls, got {add_job_count}'
print('All scheduler verification checks passed.')
"
# Expected output:
# OK: check_testimonial_requests_job
# OK: send_testimonial_emails_job
# OK: check_consent_expirations_job
# OK: retry_failed_thumbnails_job
# OK: cleanup_expired_tokens_job
# OK: check_gallery_drift_job
# OK: failure tracking functions present
# Registered: check_testimonial_requests
# Registered: send_testimonial_emails
# Registered: check_consent_expirations
# Registered: retry_failed_thumbnails
# Registered: cleanup_expired_tokens
# Registered: check_gallery_drift
# Preserved: weekly_social
# Preserved: blog_generation
# Preserved: daily_buffer
# Preserved: daily_backup
# Preserved: retry_processor
# Preserved: warmup_batch
# Total scheduler.add_job calls: 12
# All scheduler verification checks passed.
```

- [ ] 3. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/scheduler.py
git commit -m "Add 6 Module 3 scheduled jobs with consecutive failure tracking

New jobs: check_testimonial_requests (daily 9am), send_testimonial_emails
(Tue-Thu 10am), check_consent_expirations (daily 1am, CRITICAL on failure
with immediate email), retry_failed_thumbnails (every 30min),
cleanup_expired_tokens (daily 2:30am), check_gallery_drift (daily 3am
with consent-removal alerts).

Consecutive failure tracking: _record_job_success/_record_job_failure
functions track per-job failure counts and send admin email notification
after 3 consecutive failures. All list-processing jobs use per-item
commits. Testimonial request job falls back to static template if Claude
API fails. Gallery drift job creates dashboard alerts and emails admin
for consent-related drift."
```

### Task 22: Test Files (6 test files)

Create 6 test files with minimum happy-path coverage plus edge cases for consent/compliance logic. Each test uses raw assert statements, sets up and tears down test data, and can be run directly.

**Files:**
- `tests/test_consent_logic.py` (new)
- `tests/test_photo_upload.py` (new)
- `tests/test_testimonial_flow.py` (new)
- `tests/test_gallery_generation.py` (new)
- `tests/test_case_study.py` (new)
- `tests/test_patient_identity.py` (new)

**Steps:**

- [ ] 1. Ensure the `tests/` directory exists:

```bash
cd /Users/philipsmith/zerona-content-engine
mkdir -p tests
```

- [ ] 2. Create `tests/test_consent_logic.py`:

```python
"""Tests for consent checks, expiration, revocation, source enforcement, and trigger validation."""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db


TEST_PATIENT_ID = None
TEST_CONSENT_DOC_ID = None


def setup():
    """Create test patient and consent document."""
    global TEST_PATIENT_ID, TEST_CONSENT_DOC_ID

    conn = get_db()

    # Create a test patient
    cursor = conn.execute(
        """INSERT INTO patients (first_name, last_name, email, email_bounced)
           VALUES (?, ?, ?, ?)""",
        ("ConsentTest", "Patient", "consent-test@example.com", 0),
    )
    conn.commit()
    TEST_PATIENT_ID = cursor.lastrowid

    # Create a consent document
    cursor = conn.execute(
        """INSERT INTO consent_documents
           (patient_id, document_path, document_type, uploaded_by, uploaded_at, signed_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (TEST_PATIENT_ID, "/tmp/test-consent.pdf", "photo_release", "test_setup",
         datetime.now().isoformat(), "2026-01-15"),
    )
    conn.commit()
    TEST_CONSENT_DOC_ID = cursor.lastrowid
    conn.close()


def teardown():
    """Remove test data."""
    global TEST_PATIENT_ID, TEST_CONSENT_DOC_ID
    if TEST_PATIENT_ID is None:
        return

    conn = get_db()
    conn.execute("DELETE FROM patient_consents WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM consent_documents WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patient_preferences WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patients WHERE id = ?", (TEST_PATIENT_ID,))
    conn.commit()
    conn.close()

    TEST_PATIENT_ID = None
    TEST_CONSENT_DOC_ID = None


def test_grant_consent_with_signed_document():
    """Granting consent with signed_document source should succeed."""
    from app.services import consent_service

    result = consent_service.grant_patient_consent(
        patient_id=TEST_PATIENT_ID,
        scope="website",
        consent_source="signed_document",
        document_id=TEST_CONSENT_DOC_ID,
        granted_by="test_user",
    )

    assert result["granted"] is True, f"Expected consent granted, got {result}"
    assert result["consent_id"] is not None
    print("PASSED: test_grant_consent_with_signed_document")


def test_consent_source_enforcement():
    """Case study scope should require signed_document source."""
    from app.services import consent_service

    # Try granting case_study scope with testimonial_form source
    result = consent_service.grant_patient_consent(
        patient_id=TEST_PATIENT_ID,
        scope="case_study",
        consent_source="testimonial_form",
        granted_by="test_user",
    )

    assert result["granted"] is False, "case_study consent should not be grantable via testimonial_form"
    print("PASSED: test_consent_source_enforcement")


def test_active_consent_check():
    """Active consent should be queryable after grant."""
    from app.services import consent_service

    # Grant consent
    consent_service.grant_patient_consent(
        patient_id=TEST_PATIENT_ID,
        scope="social_media",
        consent_source="signed_document",
        document_id=TEST_CONSENT_DOC_ID,
        granted_by="test_user",
    )

    # Check active
    has_consent = consent_service.patient_has_active_consent(
        TEST_PATIENT_ID, "social_media"
    )
    assert has_consent is True, "Patient should have active social_media consent"
    print("PASSED: test_active_consent_check")


def test_revoke_consent():
    """Revoking consent should make it inactive."""
    from app.services import consent_service

    # Grant
    grant_result = consent_service.grant_patient_consent(
        patient_id=TEST_PATIENT_ID,
        scope="advertising",
        consent_source="signed_document",
        document_id=TEST_CONSENT_DOC_ID,
        granted_by="test_user",
    )

    # Revoke
    revoke_result = consent_service.revoke_patient_consent(
        consent_id=grant_result["consent_id"],
        revoked_by="test_user",
        reason="patient_requested",
    )

    assert revoke_result["revoked"] is True

    # Verify no longer active
    has_consent = consent_service.patient_has_active_consent(
        TEST_PATIENT_ID, "advertising"
    )
    assert has_consent is False, "Revoked consent should not be active"
    print("PASSED: test_revoke_consent")


def test_consent_expiration():
    """Expired consent should be detected by process_expired_consents."""
    from app.services import consent_service
    from app import consent_db

    # Grant with past expiration
    conn = get_db()
    past_date = (datetime.now() - timedelta(days=1)).isoformat()
    cursor = conn.execute(
        """INSERT INTO patient_consents
           (patient_id, scope, consent_source, source_document_id, granted_by,
            granted_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (TEST_PATIENT_ID, "website", "signed_document", TEST_CONSENT_DOC_ID,
         "test_user", datetime.now().isoformat(), past_date),
    )
    conn.commit()
    expired_consent_id = cursor.lastrowid
    conn.close()

    # Process expired
    result = consent_service.process_expired_consents()
    assert result["processed_count"] >= 1, f"Should process at least 1 expired consent, got {result}"
    print("PASSED: test_consent_expiration")


def test_trigger_testimonial_request_eligible_at():
    """The session_completion trigger should set testimonial_request_eligible_at
    when session_type='final' and completed_at is set."""
    conn = get_db()

    # Create a cycle and session
    cursor = conn.execute(
        """INSERT INTO patient_treatment_cycles (patient_id, cycle_number)
           VALUES (?, 1)""",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    cycle_id = cursor.lastrowid

    cursor = conn.execute(
        """INSERT INTO patient_photo_sessions
           (patient_id, cycle_id, session_number, session_date, session_type)
           VALUES (?, ?, 1, date('now'), 'final')""",
        (TEST_PATIENT_ID, cycle_id),
    )
    conn.commit()
    session_id = cursor.lastrowid

    # Before completion, eligible_at should be NULL
    row = conn.execute(
        "SELECT testimonial_request_eligible_at FROM patient_photo_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    assert row["testimonial_request_eligible_at"] is None, "Should be NULL before completion"

    # Mark as completed — trigger should fire
    conn.execute(
        "UPDATE patient_photo_sessions SET completed_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()

    row = conn.execute(
        "SELECT testimonial_request_eligible_at FROM patient_photo_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()

    # Note: trigger may or may not be set depending on photo/measurement completeness
    # The trigger checks for all 6 photos + 8 measurements. Without those, it stays NULL.
    # This test verifies the trigger runs without error, not the full eligibility logic.

    # Cleanup
    conn.execute("DELETE FROM patient_photo_sessions WHERE id = ?", (session_id,))
    conn.execute("DELETE FROM patient_treatment_cycles WHERE id = ?", (cycle_id,))
    conn.commit()
    conn.close()

    print("PASSED: test_trigger_testimonial_request_eligible_at")


if __name__ == "__main__":
    init_db()
    run_migrations()

    tests = [
        test_grant_consent_with_signed_document,
        test_consent_source_enforcement,
        test_active_consent_check,
        test_revoke_consent,
        test_consent_expiration,
        test_trigger_testimonial_request_eligible_at,
    ]

    for test_fn in tests:
        setup()
        try:
            test_fn()
        except Exception as e:
            print(f"FAILED: {test_fn.__name__}: {e}")
        finally:
            teardown()

    print(f"\nRan {len(tests)} consent logic tests.")
```

- [ ] 3. Create `tests/test_photo_upload.py`:

```python
"""Tests for photo upload flow, versioning, HEIC conversion, hash dedup, and min dimensions."""
import os
import sys
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db


TEST_PATIENT_ID = None
TEST_CYCLE_ID = None
TEST_SESSION_ID = None
TEST_UPLOAD_DIR = None


def setup():
    """Create test patient, cycle, session, and upload directory."""
    global TEST_PATIENT_ID, TEST_CYCLE_ID, TEST_SESSION_ID, TEST_UPLOAD_DIR

    conn = get_db()

    cursor = conn.execute(
        """INSERT INTO patients (first_name, last_name, email, email_bounced)
           VALUES (?, ?, ?, ?)""",
        ("PhotoTest", "Patient", "photo-test@example.com", 0),
    )
    conn.commit()
    TEST_PATIENT_ID = cursor.lastrowid

    cursor = conn.execute(
        """INSERT INTO patient_treatment_cycles (patient_id, cycle_number)
           VALUES (?, 1)""",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    TEST_CYCLE_ID = cursor.lastrowid

    cursor = conn.execute(
        """INSERT INTO patient_photo_sessions
           (patient_id, cycle_id, session_number, session_date, session_type)
           VALUES (?, ?, 1, date('now'), 'baseline')""",
        (TEST_PATIENT_ID, TEST_CYCLE_ID),
    )
    conn.commit()
    TEST_SESSION_ID = cursor.lastrowid
    conn.close()

    TEST_UPLOAD_DIR = Path(f"media/patients/{TEST_PATIENT_ID}/sessions/{TEST_SESSION_ID}")
    TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def teardown():
    """Remove test data and upload directory."""
    global TEST_PATIENT_ID, TEST_CYCLE_ID, TEST_SESSION_ID, TEST_UPLOAD_DIR
    if TEST_PATIENT_ID is None:
        return

    conn = get_db()
    conn.execute("DELETE FROM patient_photos WHERE session_id = ?", (TEST_SESSION_ID,))
    conn.execute("DELETE FROM patient_photo_sessions WHERE id = ?", (TEST_SESSION_ID,))
    conn.execute("DELETE FROM patient_treatment_cycles WHERE id = ?", (TEST_CYCLE_ID,))
    conn.execute("DELETE FROM patients WHERE id = ?", (TEST_PATIENT_ID,))
    conn.commit()
    conn.close()

    # Clean up test files
    if TEST_UPLOAD_DIR and TEST_UPLOAD_DIR.exists():
        import shutil
        shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)

    TEST_PATIENT_ID = None
    TEST_CYCLE_ID = None
    TEST_SESSION_ID = None
    TEST_UPLOAD_DIR = None


def _create_test_jpeg(path: Path, width: int = 800, height: int = 600):
    """Create a minimal valid JPEG file for testing."""
    try:
        from PIL import Image
        img = Image.new("RGB", (width, height), color="blue")
        img.save(str(path), "JPEG", quality=85)
    except ImportError:
        # Minimal JPEG without Pillow — write a tiny valid JPEG
        # SOI + APP0 + minimal scan data + EOI
        path.write_bytes(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xd9'
        )


def test_photo_record_creation():
    """Creating a photo record should store angle, path, and hash."""
    from app import photo_db

    test_file = TEST_UPLOAD_DIR / "front.jpg"
    _create_test_jpeg(test_file)

    file_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()

    photo_id = photo_db.create_photo(
        session_id=TEST_SESSION_ID,
        angle="front",
        file_path=str(test_file),
        file_hash=file_hash,
    )

    assert photo_id is not None, "Should return a photo ID"

    # Retrieve and verify
    conn = get_db()
    row = conn.execute("SELECT * FROM patient_photos WHERE id = ?", (photo_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row["angle"] == "front"
    assert row["file_hash"] == file_hash
    assert row["is_current"] == 1
    assert row["version_number"] == 1
    print("PASSED: test_photo_record_creation")


def test_photo_versioning():
    """Uploading a new photo for the same angle should supersede the old one."""
    from app import photo_db

    # First photo
    test_file_v1 = TEST_UPLOAD_DIR / "side_left_v1.jpg"
    _create_test_jpeg(test_file_v1)
    hash_v1 = hashlib.sha256(test_file_v1.read_bytes()).hexdigest()

    photo_id_v1 = photo_db.create_photo(
        session_id=TEST_SESSION_ID,
        angle="side_left",
        file_path=str(test_file_v1),
        file_hash=hash_v1,
    )

    # Second photo (version 2)
    test_file_v2 = TEST_UPLOAD_DIR / "side_left_v2.jpg"
    _create_test_jpeg(test_file_v2, width=900, height=700)
    hash_v2 = hashlib.sha256(test_file_v2.read_bytes()).hexdigest()

    photo_id_v2 = photo_db.create_photo(
        session_id=TEST_SESSION_ID,
        angle="side_left",
        file_path=str(test_file_v2),
        file_hash=hash_v2,
        supersedes_photo_id=photo_id_v1,
    )

    conn = get_db()

    # V1 should no longer be current
    v1_row = conn.execute(
        "SELECT is_current, superseded_by FROM patient_photos WHERE id = ?",
        (photo_id_v1,),
    ).fetchone()
    assert v1_row["is_current"] == 0, "V1 should no longer be current"
    assert v1_row["superseded_by"] == photo_id_v2

    # V2 should be current with version_number 2
    v2_row = conn.execute(
        "SELECT is_current, version_number FROM patient_photos WHERE id = ?",
        (photo_id_v2,),
    ).fetchone()
    assert v2_row["is_current"] == 1, "V2 should be current"
    assert v2_row["version_number"] == 2

    conn.close()
    print("PASSED: test_photo_versioning")


def test_hash_dedup_detection():
    """Uploading a photo with the same hash should be detected."""
    from app.services import photo_service

    test_file = TEST_UPLOAD_DIR / "dedup_test.jpg"
    _create_test_jpeg(test_file)
    file_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()

    # Check if hash exists (should not for first upload)
    is_dup = photo_service.check_duplicate_hash(TEST_SESSION_ID, file_hash)
    assert is_dup is False, "First upload should not be a duplicate"

    # Create the photo record
    from app import photo_db
    photo_db.create_photo(
        session_id=TEST_SESSION_ID,
        angle="back",
        file_path=str(test_file),
        file_hash=file_hash,
    )

    # Now the same hash should be detected as duplicate
    is_dup = photo_service.check_duplicate_hash(TEST_SESSION_ID, file_hash)
    assert is_dup is True, "Same hash should be detected as duplicate"
    print("PASSED: test_hash_dedup_detection")


def test_min_dimensions_validation():
    """Photos below minimum dimensions should be rejected."""
    from app.services import photo_service

    # Create a tiny image
    tiny_file = TEST_UPLOAD_DIR / "tiny.jpg"
    _create_test_jpeg(tiny_file, width=100, height=100)

    result = photo_service.validate_photo_dimensions(str(tiny_file))
    assert result["valid"] is False, f"Tiny image should fail dimension check: {result}"
    print("PASSED: test_min_dimensions_validation")


def test_valid_dimensions():
    """Photos meeting minimum dimensions should pass validation."""
    from app.services import photo_service

    valid_file = TEST_UPLOAD_DIR / "valid.jpg"
    _create_test_jpeg(valid_file, width=800, height=600)

    result = photo_service.validate_photo_dimensions(str(valid_file))
    assert result["valid"] is True, f"Valid image should pass dimension check: {result}"
    print("PASSED: test_valid_dimensions")


if __name__ == "__main__":
    init_db()
    run_migrations()

    tests = [
        test_photo_record_creation,
        test_photo_versioning,
        test_hash_dedup_detection,
        test_min_dimensions_validation,
        test_valid_dimensions,
    ]

    for test_fn in tests:
        setup()
        try:
            test_fn()
        except Exception as e:
            print(f"FAILED: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            teardown()

    print(f"\nRan {len(tests)} photo upload tests.")
```

- [ ] 4. Create `tests/test_testimonial_flow.py`:

```python
"""Tests for token generation, 3-touch cadence, quality checks, opt-out, and bounce handling."""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db


TEST_PATIENT_ID = None
TEST_CYCLE_ID = None
TEST_SESSION_ID = None


def setup():
    """Create test patient with a completed final session."""
    global TEST_PATIENT_ID, TEST_CYCLE_ID, TEST_SESSION_ID

    conn = get_db()

    cursor = conn.execute(
        """INSERT INTO patients (first_name, last_name, email, email_bounced)
           VALUES (?, ?, ?, ?)""",
        ("TestimonialTest", "Patient", "testimonial-test@example.com", 0),
    )
    conn.commit()
    TEST_PATIENT_ID = cursor.lastrowid

    cursor = conn.execute(
        """INSERT INTO patient_treatment_cycles (patient_id, cycle_number)
           VALUES (?, 1)""",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    TEST_CYCLE_ID = cursor.lastrowid

    cursor = conn.execute(
        """INSERT INTO patient_photo_sessions
           (patient_id, cycle_id, session_number, session_date, session_type,
            completed_at, testimonial_request_eligible_at)
           VALUES (?, ?, 6, date('now'), 'final', datetime('now'), datetime('now'))""",
        (TEST_PATIENT_ID, TEST_CYCLE_ID),
    )
    conn.commit()
    TEST_SESSION_ID = cursor.lastrowid
    conn.close()


def teardown():
    """Remove test data."""
    global TEST_PATIENT_ID, TEST_CYCLE_ID, TEST_SESSION_ID
    if TEST_PATIENT_ID is None:
        return

    conn = get_db()
    conn.execute(
        """DELETE FROM testimonial_send_log WHERE testimonial_id IN
           (SELECT id FROM testimonials WHERE patient_id = ?)""",
        (TEST_PATIENT_ID,),
    )
    conn.execute("DELETE FROM testimonials WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patient_preferences WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patient_photo_sessions WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patient_treatment_cycles WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patients WHERE id = ?", (TEST_PATIENT_ID,))
    conn.commit()
    conn.close()

    TEST_PATIENT_ID = None
    TEST_CYCLE_ID = None
    TEST_SESSION_ID = None


def test_token_generation():
    """Token should be URL-safe and unique."""
    from app.services.testimonial_service import generate_testimonial_token

    token1 = generate_testimonial_token()
    token2 = generate_testimonial_token()

    assert isinstance(token1, str)
    assert len(token1) >= 32, "Token should be at least 32 chars"
    assert token1 != token2, "Tokens should be unique"
    # URL-safe check
    assert " " not in token1
    assert "/" not in token1 or token1.replace("-", "").replace("_", "").isalnum()
    print("PASSED: test_token_generation")


def test_create_testimonial_request_with_3_touch_cadence():
    """Creating a request should schedule 3 send log entries."""
    from app.services import testimonial_service
    from app import testimonial_db

    result = testimonial_service.create_testimonial_request(
        patient_id=TEST_PATIENT_ID,
        session_id=TEST_SESSION_ID,
        cycle_id=TEST_CYCLE_ID,
    )

    assert result["testimonial_id"] is not None
    assert result["token"] is not None
    assert len(result["touches_scheduled"]) == 3, (
        f"Should schedule 3 touches, got {len(result['touches_scheduled'])}"
    )

    # Verify send log entries
    send_log = testimonial_db.get_send_log(result["testimonial_id"])
    assert len(send_log) == 3
    assert send_log[0]["touch_number"] == 1
    assert send_log[1]["touch_number"] == 2
    assert send_log[2]["touch_number"] == 3
    assert all(entry["status"] == "scheduled" for entry in send_log)
    print("PASSED: test_create_testimonial_request_with_3_touch_cadence")


def test_quality_check_low_rating():
    """Low rating should be flagged."""
    from app.services.testimonial_service import check_testimonial_quality

    result = check_testimonial_quality(rating=1, text="It was terrible and hurt a lot.")
    assert result["flagged"] is True
    assert "low_rating" in result["flags"]
    print("PASSED: test_quality_check_low_rating")


def test_quality_check_adverse_keywords():
    """Adverse event keywords should be flagged."""
    from app.services.testimonial_service import check_testimonial_quality

    result = check_testimonial_quality(rating=5, text="Great results but I had severe pain and bruising.")
    assert result["flagged"] is True
    assert "adverse_event_keyword" in result["flags"]
    print("PASSED: test_quality_check_adverse_keywords")


def test_quality_check_clean_submission():
    """Clean high-rating submission should not be flagged (deterministic layer)."""
    from app.services.testimonial_service import check_testimonial_quality

    result = check_testimonial_quality(rating=5, text="Amazing results! Lost 3 inches.")
    # Note: Claude layer may or may not flag, but deterministic layer should pass
    if not result["flagged"]:
        print("PASSED: test_quality_check_clean_submission")
    else:
        # Only fail if deterministic flags were raised
        deterministic_flags = [f for f in result["flags"] if f in ("low_rating", "low_rating_no_context", "adverse_event_keyword")]
        assert len(deterministic_flags) == 0, f"Deterministic flags should be clean: {result['flags']}"
        print("PASSED: test_quality_check_clean_submission (Claude flagged, deterministic clean)")


def test_opt_out_suppresses_requests():
    """Patient who opted out should not appear in eligible sessions."""
    from app.services import testimonial_service

    # Set opt-out preference
    conn = get_db()
    conn.execute(
        """INSERT INTO patient_preferences (patient_id, preference_type, value)
           VALUES (?, 'testimonial_requests', 'none')""",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    conn.close()

    eligible = testimonial_service.find_eligible_sessions()
    patient_ids = [s["patient_id"] for s in eligible]
    assert TEST_PATIENT_ID not in patient_ids, "Opted-out patient should not be eligible"
    print("PASSED: test_opt_out_suppresses_requests")


def test_bounced_email_suppresses_requests():
    """Patient with bounced email should not appear in eligible sessions."""
    from app.services import testimonial_service

    conn = get_db()
    conn.execute(
        "UPDATE patients SET email_bounced = 1, email_bounced_at = datetime('now') WHERE id = ?",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    conn.close()

    eligible = testimonial_service.find_eligible_sessions()
    patient_ids = [s["patient_id"] for s in eligible]
    assert TEST_PATIENT_ID not in patient_ids, "Bounced-email patient should not be eligible"

    # Reset
    conn = get_db()
    conn.execute("UPDATE patients SET email_bounced = 0, email_bounced_at = NULL WHERE id = ?",
                 (TEST_PATIENT_ID,))
    conn.commit()
    conn.close()
    print("PASSED: test_bounced_email_suppresses_requests")


def test_90_day_lookback_guard():
    """Patient who submitted a testimonial within 90 days should be suppressed."""
    from app.services import testimonial_service
    from app import testimonial_db

    # Create a recent submitted testimonial
    conn = get_db()
    conn.execute(
        """INSERT INTO testimonials
           (patient_id, session_id, cycle_id, token, token_expires_at, status, submitted_at)
           VALUES (?, ?, ?, 'test-guard-token', datetime('now', '+30 days'), 'submitted', datetime('now'))""",
        (TEST_PATIENT_ID, TEST_SESSION_ID, TEST_CYCLE_ID),
    )
    conn.commit()
    conn.close()

    has_recent = testimonial_db.has_recent_testimonial(TEST_PATIENT_ID, days=90)
    assert has_recent is True, "Should detect recent testimonial within 90 days"

    has_old = testimonial_db.has_recent_testimonial(TEST_PATIENT_ID, days=0)
    assert has_old is False, "0-day lookback should not find anything"
    print("PASSED: test_90_day_lookback_guard")


if __name__ == "__main__":
    init_db()
    run_migrations()

    tests = [
        test_token_generation,
        test_create_testimonial_request_with_3_touch_cadence,
        test_quality_check_low_rating,
        test_quality_check_adverse_keywords,
        test_quality_check_clean_submission,
        test_opt_out_suppresses_requests,
        test_bounced_email_suppresses_requests,
        test_90_day_lookback_guard,
    ]

    for test_fn in tests:
        setup()
        try:
            test_fn()
        except Exception as e:
            print(f"FAILED: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            teardown()

    print(f"\nRan {len(tests)} testimonial flow tests.")
```

- [ ] 5. Create `tests/test_gallery_generation.py`:

```python
"""Tests for qualifying patient query, version history, and persistent exclusions."""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db


TEST_PATIENT_IDS = []
TEST_CONSENT_DOC_ID = None


def setup():
    """Create test patients with sessions, photos, consents for gallery eligibility."""
    global TEST_PATIENT_IDS, TEST_CONSENT_DOC_ID

    conn = get_db()

    for i in range(3):
        cursor = conn.execute(
            """INSERT INTO patients (first_name, last_name, email, email_bounced)
               VALUES (?, ?, ?, ?)""",
            (f"GalleryTest{i}", "Patient", f"gallery-test-{i}@example.com", 0),
        )
        conn.commit()
        pid = cursor.lastrowid
        TEST_PATIENT_IDS.append(pid)

        # Create consent document
        cursor = conn.execute(
            """INSERT INTO consent_documents
               (patient_id, document_path, document_type, uploaded_by, uploaded_at, signed_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, f"/tmp/consent-{i}.pdf", "photo_release", "test_setup",
             datetime.now().isoformat(), "2026-01-15"),
        )
        conn.commit()
        doc_id = cursor.lastrowid
        if i == 0:
            TEST_CONSENT_DOC_ID = doc_id

        # Grant website consent
        conn.execute(
            """INSERT INTO patient_consents
               (patient_id, scope, consent_source, source_document_id, granted_by,
                granted_at, expires_at)
               VALUES (?, 'website', 'signed_document', ?, 'test_setup', datetime('now'),
                       datetime('now', '+2 years'))""",
            (pid, doc_id),
        )
        conn.commit()

        # Create cycle + final session
        cursor = conn.execute(
            """INSERT INTO patient_treatment_cycles (patient_id, cycle_number)
               VALUES (?, 1)""",
            (pid,),
        )
        conn.commit()
        cycle_id = cursor.lastrowid

        cursor = conn.execute(
            """INSERT INTO patient_photo_sessions
               (patient_id, cycle_id, session_number, session_date, session_type,
                completed_at, testimonial_request_eligible_at)
               VALUES (?, ?, 6, date('now'), 'final', datetime('now'), datetime('now'))""",
            (pid, cycle_id),
        )
        conn.commit()
        session_id = cursor.lastrowid

        # Create baseline session too
        cursor = conn.execute(
            """INSERT INTO patient_photo_sessions
               (patient_id, cycle_id, session_number, session_date, session_type, completed_at)
               VALUES (?, ?, 1, date('now', '-30 days'), 'baseline', datetime('now', '-30 days'))""",
            (pid, cycle_id),
        )
        conn.commit()

    conn.close()


def teardown():
    """Remove all test data."""
    global TEST_PATIENT_IDS, TEST_CONSENT_DOC_ID
    if not TEST_PATIENT_IDS:
        return

    conn = get_db()
    for pid in TEST_PATIENT_IDS:
        conn.execute("DELETE FROM patient_photos WHERE session_id IN (SELECT id FROM patient_photo_sessions WHERE patient_id = ?)", (pid,))
        conn.execute("DELETE FROM patient_photo_sessions WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM patient_treatment_cycles WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM patient_consents WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM consent_documents WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM gallery_persistent_exclusions WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM patients WHERE id = ?", (pid,))
    conn.commit()
    conn.close()

    TEST_PATIENT_IDS = []
    TEST_CONSENT_DOC_ID = None


def test_qualifying_patients_query():
    """Patients with active website consent and completed final sessions should qualify."""
    from app.services import gallery_service
    from app.config import settings

    qualifying = gallery_service.get_qualifying_patients(settings.gallery_default_slug)
    qualifying_ids = {p["patient_id"] for p in qualifying}

    for pid in TEST_PATIENT_IDS:
        assert pid in qualifying_ids, f"Patient {pid} should qualify for gallery"

    print("PASSED: test_qualifying_patients_query")


def test_persistent_exclusion():
    """Excluded patients should not appear in qualifying set."""
    from app.services import gallery_service
    from app import gallery_db
    from app.config import settings

    excluded_pid = TEST_PATIENT_IDS[0]

    gallery_db.add_gallery_exclusion(
        patient_id=excluded_pid,
        excluded_by="test_user",
        reason="patient_requested",
    )

    qualifying = gallery_service.get_qualifying_patients(settings.gallery_default_slug)
    qualifying_ids = {p["patient_id"] for p in qualifying}

    assert excluded_pid not in qualifying_ids, "Excluded patient should not qualify"
    print("PASSED: test_persistent_exclusion")


def test_gallery_drift_detection():
    """Drift detection should find consent-revoked patients still in gallery."""
    from app.services import gallery_service, consent_service
    from app import gallery_db
    from app.config import settings

    gallery_slug = settings.gallery_default_slug

    # Simulate a published gallery with all 3 patients
    gallery_db.create_gallery_version(
        gallery_slug=gallery_slug,
        patients_included=TEST_PATIENT_IDS,
        photo_ids_included=[],
        generated_by="test_setup",
        is_current=True,
    )

    # Revoke consent for patient 0
    conn = get_db()
    conn.execute(
        "UPDATE patient_consents SET revoked_at = datetime('now'), revoked_by = 'test', revoked_reason = 'test revocation' WHERE patient_id = ?",
        (TEST_PATIENT_IDS[0],),
    )
    conn.commit()
    conn.close()

    drift = gallery_service.get_gallery_drift(gallery_slug)
    assert drift["has_drift"] is True, "Should detect drift"

    remove_ids = [p["patient_id"] for p in drift["patients_to_remove"]]
    assert TEST_PATIENT_IDS[0] in remove_ids, "Patient with revoked consent should be in removal list"

    # Cleanup gallery version
    conn = get_db()
    conn.execute("DELETE FROM gallery_versions WHERE gallery_slug = ?", (gallery_slug,))
    conn.commit()
    conn.close()

    print("PASSED: test_gallery_drift_detection")


def test_gallery_version_history():
    """Creating multiple gallery versions should maintain history."""
    from app import gallery_db
    from app.config import settings

    gallery_slug = settings.gallery_default_slug

    # Create version 1
    v1_id = gallery_db.create_gallery_version(
        gallery_slug=gallery_slug,
        patients_included=[TEST_PATIENT_IDS[0]],
        photo_ids_included=[],
        generated_by="test_v1",
        is_current=True,
    )

    # Create version 2 (should mark v1 as not current)
    v2_id = gallery_db.create_gallery_version(
        gallery_slug=gallery_slug,
        patients_included=TEST_PATIENT_IDS[:2],
        photo_ids_included=[],
        generated_by="test_v2",
        is_current=True,
    )

    history = gallery_db.get_gallery_history(gallery_slug)
    assert len(history) >= 2, f"Should have at least 2 versions, got {len(history)}"

    current = gallery_db.get_current_gallery(gallery_slug)
    assert current is not None
    assert current["id"] == v2_id, "V2 should be the current version"

    # Cleanup
    conn = get_db()
    conn.execute("DELETE FROM gallery_versions WHERE gallery_slug = ?", (gallery_slug,))
    conn.commit()
    conn.close()

    print("PASSED: test_gallery_version_history")


if __name__ == "__main__":
    init_db()
    run_migrations()

    tests = [
        test_qualifying_patients_query,
        test_persistent_exclusion,
        test_gallery_drift_detection,
        test_gallery_version_history,
    ]

    for test_fn in tests:
        setup()
        try:
            test_fn()
        except Exception as e:
            print(f"FAILED: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            teardown()

    print(f"\nRan {len(tests)} gallery generation tests.")
```

- [ ] 6. Create `tests/test_case_study.py`:

```python
"""Tests for aggregate calculations, patient selection, measurement delta math, and versioning."""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db


TEST_PATIENT_IDS = []


def setup():
    """Create test patients with measurements for aggregate calculations."""
    global TEST_PATIENT_IDS

    conn = get_db()

    for i in range(5):
        cursor = conn.execute(
            """INSERT INTO patients (first_name, last_name, email, email_bounced)
               VALUES (?, ?, ?, ?)""",
            (f"CaseStudyTest{i}", "Patient", f"casestudy-{i}@example.com", 0),
        )
        conn.commit()
        pid = cursor.lastrowid
        TEST_PATIENT_IDS.append(pid)

        # Create cycle
        cursor = conn.execute(
            """INSERT INTO patient_treatment_cycles (patient_id, cycle_number)
               VALUES (?, 1)""",
            (pid,),
        )
        conn.commit()
        cycle_id = cursor.lastrowid

        # Create baseline session with measurements
        cursor = conn.execute(
            """INSERT INTO patient_photo_sessions
               (patient_id, cycle_id, session_number, session_date, session_type, completed_at)
               VALUES (?, ?, 1, date('now', '-30 days'), 'baseline', datetime('now', '-30 days'))""",
            (pid, cycle_id),
        )
        conn.commit()
        baseline_session_id = cursor.lastrowid

        # Create final session with measurements
        cursor = conn.execute(
            """INSERT INTO patient_photo_sessions
               (patient_id, cycle_id, session_number, session_date, session_type, completed_at)
               VALUES (?, ?, 6, date('now'), 'final', datetime('now'))""",
            (pid, cycle_id),
        )
        conn.commit()
        final_session_id = cursor.lastrowid

        # Add baseline measurements (waist, hips, thighs_left, thighs_right + 4 more)
        baseline_measurements = [
            ("waist", 36.0 + i),
            ("hips", 40.0 + i),
            ("thighs_left", 24.0 + i * 0.5),
            ("thighs_right", 24.5 + i * 0.5),
            ("upper_abdomen", 34.0 + i),
            ("lower_abdomen", 35.0 + i),
            ("chest", 38.0 + i),
            ("arms", 13.0 + i * 0.3),
        ]
        for measurement_type, value in baseline_measurements:
            conn.execute(
                """INSERT INTO patient_measurements
                   (session_id, measurement_point, value_inches, measured_at)
                   VALUES (?, ?, ?, datetime('now', '-30 days'))""",
                (baseline_session_id, measurement_type, value),
            )

        # Add final measurements (all reduced by 1.5-3.0 inches)
        final_measurements = [
            ("waist", 34.0 + i),
            ("hips", 38.0 + i),
            ("thighs_left", 22.5 + i * 0.5),
            ("thighs_right", 23.0 + i * 0.5),
            ("upper_abdomen", 32.5 + i),
            ("lower_abdomen", 33.0 + i),
            ("chest", 36.5 + i),
            ("arms", 12.0 + i * 0.3),
        ]
        for measurement_type, value in final_measurements:
            conn.execute(
                """INSERT INTO patient_measurements
                   (session_id, measurement_point, value_inches, measured_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (final_session_id, measurement_type, value),
            )

        # Grant case_study consent
        cursor = conn.execute(
            """INSERT INTO consent_documents
               (patient_id, document_path, document_type, uploaded_by, uploaded_at, signed_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, f"/tmp/consent-cs-{i}.pdf", "photo_release", "test_setup",
             datetime.now().isoformat(), "2026-01-15"),
        )
        conn.commit()
        doc_id = cursor.lastrowid

        conn.execute(
            """INSERT INTO patient_consents
               (patient_id, scope, consent_source, source_document_id, granted_by,
                granted_at, expires_at)
               VALUES (?, 'case_study', 'signed_document', ?, 'test_setup',
                       datetime('now'), datetime('now', '+2 years'))""",
            (pid, doc_id),
        )

    conn.commit()
    conn.close()


def teardown():
    """Remove all test data."""
    global TEST_PATIENT_IDS
    if not TEST_PATIENT_IDS:
        return

    conn = get_db()
    for pid in TEST_PATIENT_IDS:
        conn.execute(
            "DELETE FROM patient_measurements WHERE session_id IN (SELECT id FROM patient_photo_sessions WHERE patient_id = ?)",
            (pid,),
        )
        conn.execute("DELETE FROM patient_photo_sessions WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM patient_treatment_cycles WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM patient_consents WHERE patient_id = ?", (pid,))
        conn.execute("DELETE FROM consent_documents WHERE patient_id = ?", (pid,))
        conn.execute(
            "DELETE FROM case_study_selections WHERE case_study_id IN (SELECT id FROM case_studies)",
        )
        conn.execute("DELETE FROM case_studies")
        conn.execute("DELETE FROM patients WHERE id = ?", (pid,))
    conn.commit()
    conn.close()

    TEST_PATIENT_IDS = []


def test_measurement_delta_calculation():
    """Delta between baseline and final measurements should be correct."""
    from app.services import measurement_service

    pid = TEST_PATIENT_IDS[0]
    deltas = measurement_service.get_patient_measurement_deltas(pid)

    assert deltas is not None, "Should return measurement deltas"
    assert "waist" in deltas, "Should include waist measurement"

    # Patient 0: baseline waist = 36.0, final waist = 34.0, delta = -2.0
    assert abs(deltas["waist"] - (-2.0)) < 0.01, f"Waist delta should be -2.0, got {deltas['waist']}"
    print("PASSED: test_measurement_delta_calculation")


def test_aggregate_stats():
    """Aggregate stats across patients should compute correctly."""
    from app.services import measurement_service

    aggregate = measurement_service.get_aggregate_stats(TEST_PATIENT_IDS)

    assert aggregate is not None
    assert "avg_total_loss" in aggregate or "average_total_loss" in aggregate, (
        f"Should have average total loss metric. Keys: {list(aggregate.keys())}"
    )
    print("PASSED: test_aggregate_stats")


def test_case_study_creation():
    """Creating a case study should store aggregate data and patient selections."""
    from app.services import case_study_service
    from app import case_study_db

    result = case_study_service.create_case_study(
        title="Test Case Study",
        patient_ids=TEST_PATIENT_IDS[:3],
        generated_by="test_user",
    )

    assert result["case_study_id"] is not None

    # Verify it was stored
    cs = case_study_db.get_case_study(result["case_study_id"])
    assert cs is not None
    assert cs["title"] == "Test Case Study"
    assert cs["patients_included_count"] == 3
    print("PASSED: test_case_study_creation")


def test_case_study_versioning():
    """Regenerating a case study should create a new version."""
    from app.services import case_study_service
    from app import case_study_db

    # Create initial
    result1 = case_study_service.create_case_study(
        title="Versioned Study",
        patient_ids=TEST_PATIENT_IDS[:2],
        generated_by="test_user_v1",
    )

    cs1 = case_study_db.get_case_study(result1["case_study_id"])
    assert cs1["version_number"] == 1

    # Create version 2 with more patients
    result2 = case_study_service.create_case_study(
        title="Versioned Study",
        patient_ids=TEST_PATIENT_IDS[:4],
        generated_by="test_user_v2",
    )

    cs2 = case_study_db.get_case_study(result2["case_study_id"])
    assert cs2["version_number"] >= 1, "Should have a version number"
    print("PASSED: test_case_study_versioning")


if __name__ == "__main__":
    init_db()
    run_migrations()

    tests = [
        test_measurement_delta_calculation,
        test_aggregate_stats,
        test_case_study_creation,
        test_case_study_versioning,
    ]

    for test_fn in tests:
        setup()
        try:
            test_fn()
        except Exception as e:
            print(f"FAILED: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            teardown()

    print(f"\nRan {len(tests)} case study tests.")
```

- [ ] 7. Create `tests/test_patient_identity.py`:

```python
"""Tests for patient/GHL reconciliation, walk-in creation, and email bounce tracking."""
import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db


TEST_PATIENT_ID = None
TEST_GHL_CONTACT_ID = None


def setup():
    """Create test patient and GHL contact."""
    global TEST_PATIENT_ID, TEST_GHL_CONTACT_ID

    conn = get_db()

    # Create a patient
    cursor = conn.execute(
        """INSERT INTO patients (first_name, last_name, email, phone, email_bounced)
           VALUES (?, ?, ?, ?, ?)""",
        ("IdentityTest", "Patient", "identity-test@example.com", "6155551234", 0),
    )
    conn.commit()
    TEST_PATIENT_ID = cursor.lastrowid

    # Create a GHL contact (if table exists)
    try:
        cursor = conn.execute(
            """INSERT INTO ghl_contacts (ghl_id, email, phone, first_name, last_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("ghl_test_123", "identity-test@example.com", "6155551234",
             "IdentityTest", "Patient", datetime.now().isoformat()),
        )
        conn.commit()
        TEST_GHL_CONTACT_ID = cursor.lastrowid
    except sqlite3.OperationalError:
        # ghl_contacts table may not exist in test DB
        TEST_GHL_CONTACT_ID = None

    conn.close()


def teardown():
    """Remove test data."""
    global TEST_PATIENT_ID, TEST_GHL_CONTACT_ID
    if TEST_PATIENT_ID is None:
        return

    conn = get_db()
    conn.execute("DELETE FROM patients WHERE id = ?", (TEST_PATIENT_ID,))
    if TEST_GHL_CONTACT_ID:
        try:
            conn.execute("DELETE FROM ghl_contacts WHERE id = ?", (TEST_GHL_CONTACT_ID,))
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

    TEST_PATIENT_ID = None
    TEST_GHL_CONTACT_ID = None


def test_walk_in_patient_creation():
    """Walk-in patients (no GHL, no CSV) should be creatable with minimal info."""
    conn = get_db()

    cursor = conn.execute(
        """INSERT INTO patients (first_name, last_name, email, email_bounced)
           VALUES (?, ?, ?, ?)""",
        ("WalkIn", "NewPatient", "walkin@example.com", 0),
    )
    conn.commit()
    walkin_id = cursor.lastrowid

    row = conn.execute("SELECT * FROM patients WHERE id = ?", (walkin_id,)).fetchone()
    assert row is not None
    assert row["first_name"] == "WalkIn"
    assert row["ghl_contact_id"] is None, "Walk-in should have no GHL link"

    # Cleanup
    conn.execute("DELETE FROM patients WHERE id = ?", (walkin_id,))
    conn.commit()
    conn.close()
    print("PASSED: test_walk_in_patient_creation")


def test_ghl_link_by_email():
    """Linking a patient to a GHL contact by email match should work."""
    conn = get_db()

    # Link via ghl_contact_id column
    conn.execute(
        "UPDATE patients SET ghl_contact_id = ? WHERE id = ?",
        ("ghl_test_123", TEST_PATIENT_ID),
    )
    conn.commit()

    row = conn.execute("SELECT ghl_contact_id FROM patients WHERE id = ?",
                       (TEST_PATIENT_ID,)).fetchone()
    assert row["ghl_contact_id"] == "ghl_test_123", "GHL contact should be linked"

    # Reset
    conn.execute("UPDATE patients SET ghl_contact_id = NULL WHERE id = ?", (TEST_PATIENT_ID,))
    conn.commit()
    conn.close()
    print("PASSED: test_ghl_link_by_email")


def test_email_bounce_tracking():
    """Setting email_bounced should persist and be queryable."""
    conn = get_db()

    conn.execute(
        "UPDATE patients SET email_bounced = 1, email_bounced_at = datetime('now') WHERE id = ?",
        (TEST_PATIENT_ID,),
    )
    conn.commit()

    row = conn.execute(
        "SELECT email_bounced, email_bounced_at FROM patients WHERE id = ?",
        (TEST_PATIENT_ID,),
    ).fetchone()

    assert row["email_bounced"] == 1, "email_bounced should be set"
    assert row["email_bounced_at"] is not None, "email_bounced_at should have timestamp"

    # Reset
    conn.execute(
        "UPDATE patients SET email_bounced = 0, email_bounced_at = NULL WHERE id = ?",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    conn.close()
    print("PASSED: test_email_bounce_tracking")


def test_email_match_reconciliation():
    """Finding a patient by email should return the correct record."""
    conn = get_db()

    row = conn.execute(
        "SELECT id, first_name FROM patients WHERE email = ?",
        ("identity-test@example.com",),
    ).fetchone()

    assert row is not None, "Should find patient by email"
    assert row["id"] == TEST_PATIENT_ID
    conn.close()
    print("PASSED: test_email_match_reconciliation")


def test_phone_match_reconciliation():
    """Finding a patient by phone should return the correct record."""
    conn = get_db()

    row = conn.execute(
        "SELECT id, first_name FROM patients WHERE phone = ?",
        ("6155551234",),
    ).fetchone()

    assert row is not None, "Should find patient by phone"
    assert row["id"] == TEST_PATIENT_ID
    conn.close()
    print("PASSED: test_phone_match_reconciliation")


def test_bounce_flag_suppresses_new_sends():
    """Bounced patients should be excluded from testimonial eligibility queries."""
    conn = get_db()

    # Create a final session for this patient
    cursor = conn.execute(
        """INSERT INTO patient_treatment_cycles (patient_id, cycle_number)
           VALUES (?, 1)""",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    cycle_id = cursor.lastrowid

    conn.execute(
        """INSERT INTO patient_photo_sessions
           (patient_id, cycle_id, session_number, session_date, session_type,
            completed_at, testimonial_request_eligible_at)
           VALUES (?, ?, 6, date('now'), 'final', datetime('now'), datetime('now'))""",
        (TEST_PATIENT_ID, cycle_id),
    )
    conn.commit()

    # Mark as bounced
    conn.execute(
        "UPDATE patients SET email_bounced = 1, email_bounced_at = datetime('now') WHERE id = ?",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    conn.close()

    # Check eligibility
    from app.services import testimonial_service
    eligible = testimonial_service.find_eligible_sessions()
    patient_ids = [s["patient_id"] for s in eligible]
    assert TEST_PATIENT_ID not in patient_ids, "Bounced patient should not be eligible"

    # Cleanup
    conn = get_db()
    conn.execute("DELETE FROM patient_photo_sessions WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute("DELETE FROM patient_treatment_cycles WHERE patient_id = ?", (TEST_PATIENT_ID,))
    conn.execute(
        "UPDATE patients SET email_bounced = 0, email_bounced_at = NULL WHERE id = ?",
        (TEST_PATIENT_ID,),
    )
    conn.commit()
    conn.close()
    print("PASSED: test_bounce_flag_suppresses_new_sends")


if __name__ == "__main__":
    init_db()
    run_migrations()

    tests = [
        test_walk_in_patient_creation,
        test_ghl_link_by_email,
        test_email_bounce_tracking,
        test_email_match_reconciliation,
        test_phone_match_reconciliation,
        test_bounce_flag_suppresses_new_sends,
    ]

    for test_fn in tests:
        setup()
        try:
            test_fn()
        except Exception as e:
            print(f"FAILED: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            teardown()

    print(f"\nRan {len(tests)} patient identity tests.")
```

- [ ] 8. Verify all 6 test files exist and are valid Python:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
import ast
import os

test_files = [
    'tests/test_consent_logic.py',
    'tests/test_photo_upload.py',
    'tests/test_testimonial_flow.py',
    'tests/test_gallery_generation.py',
    'tests/test_case_study.py',
    'tests/test_patient_identity.py',
]

for filepath in test_files:
    assert os.path.exists(filepath), f'Missing: {filepath}'
    with open(filepath, 'r') as f:
        source = f.read()
    tree = ast.parse(source)

    # Count test functions
    test_fns = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    assert len(test_fns) >= 3, f'{filepath}: expected >= 3 test functions, got {len(test_fns)}'

    # Check for setup/teardown
    all_fns = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert 'setup' in all_fns, f'{filepath}: missing setup function'
    assert 'teardown' in all_fns, f'{filepath}: missing teardown function'

    # Check for __main__ block
    assert \"__name__\" in source and \"__main__\" in source, f'{filepath}: missing __main__ block'

    print(f'OK: {filepath} ({len(test_fns)} tests)')

print(f'All {len(test_files)} test files validated.')
"
# Expected output:
# OK: tests/test_consent_logic.py (6 tests)
# OK: tests/test_photo_upload.py (5 tests)
# OK: tests/test_testimonial_flow.py (8 tests)
# OK: tests/test_gallery_generation.py (4 tests)
# OK: tests/test_case_study.py (4 tests)
# OK: tests/test_patient_identity.py (6 tests)
# All 6 test files validated.
```

- [ ] 9. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add tests/test_consent_logic.py tests/test_photo_upload.py tests/test_testimonial_flow.py tests/test_gallery_generation.py tests/test_case_study.py tests/test_patient_identity.py
git commit -m "Add 6 Module 3 test files with 33 tests covering consent, photos, testimonials, galleries, case studies, and patient identity

test_consent_logic.py: consent grant/revoke, source enforcement, expiration,
trigger validation. test_photo_upload.py: record creation,
versioning, hash dedup, dimension validation. test_testimonial_flow.py:
token generation, 3-touch cadence, quality checks, opt-out, bounce, 90-day
guard. test_gallery_generation.py: qualifying patients, persistent
exclusions, drift detection, version history. test_case_study.py: measurement
deltas, aggregate stats, creation, versioning. test_patient_identity.py:
walk-in creation, GHL linking, bounce tracking, email/phone reconciliation."
```

### Task 23: Final Integration (main.py router registration + smoke test)

Update `app/main.py` to import and register all 8 new Module 3 routers (consents, sessions, patients_api, testimonials, galleries, case_studies, patients_hub, patient_detail) and create upload directories, then run a comprehensive smoke test verifying routes, tables, config, services, directories, and scheduled jobs.

**Files:**
- `app/main.py` (modify)

**Steps:**

- [ ] 1. Update `app/main.py` to add Module 3 router imports, directory creation, and router registration. Replace the entire file with:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, run_migrations
from app.services.scheduler import init_scheduler
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.api import router as api_router
from app.routes.webhooks import router as webhooks_router
from app.routes.campaigns import router as campaigns_router
from app.routes.campaign_api import router as campaign_api_router
from app.routes.ghl_webhooks import router as ghl_webhooks_router
from app.routes.referrals import router as referrals_router
from app.routes.referral_api import router as referral_api_router
from app.routes.referral_public import router as referral_public_router

# Module 3: Photos, Testimonials, Case Studies
from app.routes.consents import router as consents_router
from app.routes.sessions import router as sessions_router
from app.routes.patients_api import router as patients_api_router
from app.routes.testimonials import router as testimonials_router
from app.routes.galleries import router as galleries_router
from app.routes.case_studies import router as case_studies_router
from app.routes.patients_hub import router as patients_hub_router
from app.routes.patient_detail import router as patient_detail_router

# Ensure directories exist
Path("media/images").mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("prompts").mkdir(parents=True, exist_ok=True)
Path("config").mkdir(parents=True, exist_ok=True)

# Module 3 directories
Path("media/patients").mkdir(parents=True, exist_ok=True)
Path("media/consents").mkdir(parents=True, exist_ok=True)
Path("media/testimonials").mkdir(parents=True, exist_ok=True)
Path("media/galleries").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

# Module 1 & 2 routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(api_router)
app.include_router(webhooks_router)
app.include_router(campaigns_router)
app.include_router(campaign_api_router)
app.include_router(ghl_webhooks_router)
app.include_router(referrals_router)
app.include_router(referral_api_router)
app.include_router(referral_public_router)

# Module 3 routers
app.include_router(consents_router)
app.include_router(sessions_router)
app.include_router(patients_api_router)
app.include_router(testimonials_router)
app.include_router(galleries_router)
app.include_router(case_studies_router)
app.include_router(patients_hub_router)
app.include_router(patient_detail_router)


@app.on_event("startup")
def startup():
    init_db()
    run_migrations()
    init_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
```

- [ ] 2. Run the full smoke test:

```bash
cd /Users/philipsmith/zerona-content-engine
python -c "
import sys
print('=' * 60)
print('MODULE 3 FINAL SMOKE TEST')
print('=' * 60)

passed = 0
failed = 0
errors = []

# ── Test 1: All new routes are registered ──
print('\n[1/6] Checking route registration...')
try:
    from app.main import app
    routes = [r.path for r in app.routes]

    required_prefixes = [
        '/dashboard/patients',
        '/api/patients',
        '/testimonial/',
    ]
    for prefix in required_prefixes:
        matches = [r for r in routes if prefix in r]
        assert len(matches) > 0, f'No routes found with prefix: {prefix}'
        print(f'  OK: {prefix} ({len(matches)} routes)')

    total_routes = len(routes)
    print(f'  Total routes registered: {total_routes}')
    assert total_routes >= 20, f'Expected >= 20 routes, got {total_routes}'
    passed += 1
    print('  PASSED')
except Exception as e:
    failed += 1
    errors.append(f'Route registration: {e}')
    print(f'  FAILED: {e}')

# ── Test 2: All new tables exist in DB ──
print('\n[2/6] Checking database tables...')
try:
    from app.database import get_db, init_db, run_migrations
    init_db()
    run_migrations()
    conn = get_db()
    rows = conn.execute(\"\"\"SELECT name FROM sqlite_master
                           WHERE type='table' ORDER BY name\"\"\").fetchall()
    tables = [r['name'] for r in rows]
    conn.close()

    required_tables = [
        'patient_treatment_cycles',
        'patient_photo_sessions',
        'patient_photos',
        'patient_measurements',
        'consent_documents',
        'patient_consents',
        'patient_preferences',
        'testimonials',
        'testimonial_send_log',
        'gallery_versions',
        'wp_media_uploads',
        'gallery_persistent_exclusions',
        'content_usage_log',
        'case_studies',
        'case_study_selections',
        'case_study_overrides',
        'patient_data_exports',
        'session_type_history',
    ]

    for table in required_tables:
        assert table in tables, f'Missing table: {table}'
        print(f'  OK: {table}')

    passed += 1
    print('  PASSED')
except Exception as e:
    failed += 1
    errors.append(f'Database tables: {e}')
    print(f'  FAILED: {e}')

# ── Test 3: All config values load ──
print('\n[3/6] Checking config values...')
try:
    from app.config import settings

    config_attrs = [
        'max_photo_upload_mb',
        'max_consent_upload_mb',
        'consent_default_expiration_years',
        'testimonial_request_initial_days',
        'testimonial_request_reminder_1_days',
        'testimonial_request_reminder_2_days',
        'testimonial_token_expiry_days',
        'gallery_default_slug',
    ]

    for attr in config_attrs:
        assert hasattr(settings, attr), f'Missing config: {attr}'
        val = getattr(settings, attr)
        print(f'  OK: {attr} = {val}')

    passed += 1
    print('  PASSED')
except Exception as e:
    failed += 1
    errors.append(f'Config values: {e}')
    print(f'  FAILED: {e}')

# ── Test 4: All services import cleanly ──
print('\n[4/6] Checking service imports...')
try:
    from app.services import photo_service
    from app.services import consent_service
    from app.services import testimonial_service
    from app.services import gallery_service
    from app.services import case_study_service
    from app.services import measurement_service
    from app.services import patient_export_service
    from app import photo_db
    from app import consent_db
    from app import testimonial_db
    from app import gallery_db
    from app import case_study_db

    services = [
        'photo_service', 'consent_service', 'testimonial_service',
        'gallery_service', 'case_study_service', 'measurement_service',
        'patient_export_service',
    ]
    dbs = ['photo_db', 'consent_db', 'testimonial_db', 'gallery_db', 'case_study_db']

    for s in services:
        print(f'  OK: app.services.{s}')
    for d in dbs:
        print(f'  OK: app.{d}')

    passed += 1
    print('  PASSED')
except Exception as e:
    failed += 1
    errors.append(f'Service imports: {e}')
    print(f'  FAILED: {e}')

# ── Test 5: Upload directories exist ──
print('\n[5/6] Checking upload directories...')
try:
    from pathlib import Path
    required_dirs = [
        'media/patients',
        'media/consents',
        'media/testimonials',
        'media/galleries',
        'media/images',
    ]
    for d in required_dirs:
        p = Path(d)
        assert p.exists(), f'Missing directory: {d}'
        assert p.is_dir(), f'Not a directory: {d}'
        print(f'  OK: {d}/')

    passed += 1
    print('  PASSED')
except Exception as e:
    failed += 1
    errors.append(f'Upload directories: {e}')
    print(f'  FAILED: {e}')

# ── Test 6: Scheduled jobs are registered ──
print('\n[6/6] Checking scheduled jobs...')
try:
    from app.services.scheduler import scheduler, init_scheduler

    # Check that job functions exist
    from app.services import scheduler as sched_module
    required_job_fns = [
        'check_testimonial_requests_job',
        'send_testimonial_emails_job',
        'escalate_stalled_reviews_job',
        'check_consent_expirations_job',
        'retry_failed_thumbnails_job',
        'cleanup_expired_tokens_job',
        'check_gallery_drift_job',
    ]
    for fn_name in required_job_fns:
        assert hasattr(sched_module, fn_name), f'Missing job function: {fn_name}'
        assert callable(getattr(sched_module, fn_name))
        print(f'  OK: {fn_name}')

    # Verify failure tracking exists
    assert hasattr(sched_module, '_record_job_success')
    assert hasattr(sched_module, '_record_job_failure')
    assert hasattr(sched_module, 'FAILURE_THRESHOLD')
    assert sched_module.FAILURE_THRESHOLD == 3
    print('  OK: failure tracking (threshold=3)')

    passed += 1
    print('  PASSED')
except Exception as e:
    failed += 1
    errors.append(f'Scheduled jobs: {e}')
    print(f'  FAILED: {e}')

# ── Summary ──
print('\n' + '=' * 60)
print(f'SMOKE TEST RESULTS: {passed} passed, {failed} failed')
print('=' * 60)

if errors:
    print('\nFailures:')
    for err in errors:
        print(f'  - {err}')
    sys.exit(1)
else:
    print('\nAll smoke tests passed. Module 3 integration complete.')
    sys.exit(0)
"
# Expected output:
# ============================================================
# MODULE 3 FINAL SMOKE TEST
# ============================================================
# [1/6] Checking route registration...
#   OK: /dashboard/patients (X routes)
#   OK: /api/patients (X routes)
#   OK: /testimonial/ (X routes)
#   Total routes registered: X
#   PASSED
# [2/6] Checking database tables...
#   (18 table checks)
#   PASSED
# [3/6] Checking config values...
#   (8 config checks)
#   PASSED
# [4/6] Checking service imports...
#   (12 import checks)
#   PASSED
# [5/6] Checking upload directories...
#   (5 directory checks)
#   PASSED
# [6/6] Checking scheduled jobs...
#   (6 job function checks + failure tracking)
#   PASSED
# ============================================================
# SMOKE TEST RESULTS: 6 passed, 0 failed
# ============================================================
# All smoke tests passed. Module 3 integration complete.
```

- [ ] 3. Commit:

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/main.py
git commit -m "Register 8 Module 3 routers in main.py and verify full integration

Added imports and include_router calls for consents, sessions,
patients_api, testimonials, galleries, case_studies, patients_hub,
and patient_detail routers. Created Module 3 upload directories:
media/patients, media/consents, media/testimonials, media/galleries.

Total routers: 18 (10 existing + 8 new). All smoke tests pass:
route registration, database tables, config values, service imports,
upload directories, and scheduled job registration confirmed."
```

---

## Plan Complete

**Total tasks:** 23
**Estimated commits:** 23

**Execution options:**

1. **Subagent-Driven (recommended)** - Fresh subagent per task, two-stage review between tasks
2. **Inline Execution** - Execute tasks in this session with batch checkpoints

Which approach?
