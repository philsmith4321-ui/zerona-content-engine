CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    last_visit_date DATE,
    gender TEXT DEFAULT '',
    age INTEGER,
    tags TEXT DEFAULT '[]',
    tier TEXT DEFAULT 'lapsed',
    email_status TEXT DEFAULT 'valid',
    mailgun_unsubscribed_at TIMESTAMP,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patients_email ON patients(email);
CREATE INDEX IF NOT EXISTS idx_patients_tier ON patients(tier);
CREATE INDEX IF NOT EXISTS idx_patients_email_status ON patients(email_status);

CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    column_mapping TEXT,
    total_rows INTEGER DEFAULT 0,
    imported INTEGER DEFAULT 0,
    duplicates_skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
