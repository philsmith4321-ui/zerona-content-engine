-- Feature: Favorites + Repurpose tracking
-- Columns are added idempotently via init_db(), so this migration
-- just creates the index if missing.
CREATE INDEX IF NOT EXISTS idx_content_pieces_is_favorite ON content_pieces(is_favorite);
