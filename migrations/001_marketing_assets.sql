CREATE TABLE IF NOT EXISTS marketing_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,          -- 'image', 'pdf', 'video', 'html', 'document'
    source_url TEXT NOT NULL,
    local_path TEXT,
    thumbnail_url TEXT,
    file_size INTEGER,
    downloaded INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_marketing_assets_category ON marketing_assets(category);
CREATE INDEX IF NOT EXISTS idx_marketing_assets_type ON marketing_assets(asset_type);
