-- GHL Events (webhook log + idempotency)
CREATE TABLE IF NOT EXISTS ghl_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ghl_event_id TEXT UNIQUE,
    event_type TEXT NOT NULL,
    location_id TEXT,
    contact_id TEXT,
    payload TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ghl_events_type ON ghl_events(event_type);
CREATE INDEX IF NOT EXISTS idx_ghl_events_contact ON ghl_events(contact_id);
CREATE INDEX IF NOT EXISTS idx_ghl_events_created ON ghl_events(created_at);

-- GHL Contact Mirror (read-only sync)
CREATE TABLE IF NOT EXISTS ghl_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ghl_contact_id TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    pipeline_stage TEXT DEFAULT '',
    source TEXT DEFAULT '',
    utm_source TEXT DEFAULT '',
    utm_medium TEXT DEFAULT '',
    utm_campaign TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ghl_contacts_email ON ghl_contacts(email);
CREATE INDEX IF NOT EXISTS idx_ghl_contacts_ghl_id ON ghl_contacts(ghl_contact_id);

-- Referral Codes (one per patient)
CREATE TABLE IF NOT EXISTS referral_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    code TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);
CREATE INDEX IF NOT EXISTS idx_referral_codes_patient ON referral_codes(patient_id);

-- Referrals
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_patient_id INTEGER NOT NULL REFERENCES patients(id),
    referee_ghl_contact_id TEXT,
    referee_email TEXT DEFAULT '',
    referee_name TEXT DEFAULT '',
    referral_code TEXT NOT NULL,
    source TEXT DEFAULT 'utm',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    qualified_at TIMESTAMP,
    paid_at TIMESTAMP,
    reward_notified_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_patient_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referee ON referrals(referee_ghl_contact_id);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status);
CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(referral_code);

-- Patient Credits
CREATE TABLE IF NOT EXISTS patient_credits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER UNIQUE NOT NULL REFERENCES patients(id),
    balance_cents INTEGER DEFAULT 0,
    lifetime_earned_cents INTEGER DEFAULT 0,
    lifetime_redeemed_cents INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patient_credit_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    amount_cents INTEGER NOT NULL,
    type TEXT NOT NULL,
    reference TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_credit_tx_patient ON patient_credit_transactions(patient_id);

-- Reward Notifications (review queue)
CREATE TABLE IF NOT EXISTS reward_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    referral_id INTEGER REFERENCES referrals(id),
    reward_tier TEXT NOT NULL,
    reward_description TEXT NOT NULL,
    channel TEXT DEFAULT 'email',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    ghl_push_result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    pushed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reward_notif_status ON reward_notifications(status);
CREATE INDEX IF NOT EXISTS idx_reward_notif_patient ON reward_notifications(patient_id);
