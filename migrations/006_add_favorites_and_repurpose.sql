-- Feature: Favorites + Repurpose tracking
ALTER TABLE content_pieces ADD COLUMN is_favorite INTEGER DEFAULT 0;
ALTER TABLE content_pieces ADD COLUMN repurposed_from INTEGER REFERENCES content_pieces(id);

CREATE INDEX IF NOT EXISTS idx_content_pieces_is_favorite ON content_pieces(is_favorite);
