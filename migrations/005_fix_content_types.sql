-- Fix truncated content_type values from early content generation
UPDATE content_pieces SET content_type = 'social_fb' WHERE content_type = 'social_fa';
UPDATE content_pieces SET content_type = 'social_ig' WHERE content_type = 'social_in';
