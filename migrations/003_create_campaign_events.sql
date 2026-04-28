CREATE TABLE IF NOT EXISTS campaign_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER REFERENCES campaigns(id),
    recipient_email TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,
    mailgun_message_id TEXT,
    timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_campaign_events_campaign ON campaign_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_events_email ON campaign_events(recipient_email);
CREATE INDEX IF NOT EXISTS idx_campaign_events_type ON campaign_events(event_type);
CREATE INDEX IF NOT EXISTS idx_campaign_events_message ON campaign_events(mailgun_message_id);
