CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    segment_type TEXT NOT NULL DEFAULT 'tier',
    criteria TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    segment_id INTEGER REFERENCES segments(id),
    subject TEXT DEFAULT '',
    body_html TEXT DEFAULT '',
    body_text TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    from_name TEXT DEFAULT '',
    template_key TEXT,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'draft',
    total_recipients INTEGER DEFAULT 0,
    warmup_schedule TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    mailgun_message_id TEXT,
    status TEXT DEFAULT 'queued',
    sent_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_campaign_sends_campaign ON campaign_sends(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_sends_status ON campaign_sends(status);
