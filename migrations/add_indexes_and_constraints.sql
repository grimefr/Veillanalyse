-- =============================================================================
-- Doppelganger Tracker - Database Migration
-- =============================================================================
-- Add missing indexes and constraints for performance and data integrity
-- Date: 2026-01-02
-- Version: 2.0
-- =============================================================================

BEGIN;

-- =============================================================================
-- CONTENT TABLE - Add Indexes
-- =============================================================================

-- Individual column indexes
CREATE INDEX IF NOT EXISTS ix_content_source_id ON content(source_id);
CREATE INDEX IF NOT EXISTS ix_content_collected_at ON content(collected_at);
CREATE INDEX IF NOT EXISTS ix_content_published_at ON content(published_at);
CREATE INDEX IF NOT EXISTS ix_content_language ON content(language);
CREATE INDEX IF NOT EXISTS ix_content_is_analyzed ON content(is_analyzed);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS ix_content_source_collected
    ON content(source_id, collected_at);

CREATE INDEX IF NOT EXISTS ix_content_source_published
    ON content(source_id, published_at);

CREATE INDEX IF NOT EXISTS ix_content_analyzed_version
    ON content(is_analyzed, analysis_version);

-- Partial index for unanalyzed content (PostgreSQL specific)
CREATE INDEX IF NOT EXISTS ix_content_unanalyzed
    ON content(id, collected_at)
    WHERE is_analyzed = FALSE;

-- =============================================================================
-- PROPAGATION TABLE - Add Indexes
-- =============================================================================

-- Individual indexes
CREATE INDEX IF NOT EXISTS idx_propagation_created ON propagation(created_at);

-- Composite indexes with sorted columns
CREATE INDEX IF NOT EXISTS idx_propagation_source_similarity
    ON propagation(source_content_id, similarity_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_propagation_target_similarity
    ON propagation(target_content_id, similarity_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_propagation_source_created
    ON propagation(source_content_id, created_at);

-- =============================================================================
-- NLP_ANALYSIS TABLE - Add Indexes and Constraints
-- =============================================================================

-- Individual indexes
CREATE INDEX IF NOT EXISTS idx_nlp_analyzed_at ON nlp_analysis(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_nlp_language ON nlp_analysis(detected_language);

-- Composite indexes
CREATE INDEX IF NOT EXISTS idx_nlp_propaganda_analyzed
    ON nlp_analysis(is_propaganda, analyzed_at);

CREATE INDEX IF NOT EXISTS idx_nlp_propaganda_confidence
    ON nlp_analysis(is_propaganda, propaganda_confidence DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_nlp_sentiment_analyzed
    ON nlp_analysis(sentiment_label, analyzed_at);

-- Check constraints for data validation
ALTER TABLE nlp_analysis
    ADD CONSTRAINT IF NOT EXISTS ck_nlp_sentiment_range
    CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0);

ALTER TABLE nlp_analysis
    ADD CONSTRAINT IF NOT EXISTS ck_nlp_sentiment_conf_range
    CHECK (sentiment_confidence >= 0.0 AND sentiment_confidence <= 1.0);

ALTER TABLE nlp_analysis
    ADD CONSTRAINT IF NOT EXISTS ck_nlp_propaganda_conf_range
    CHECK (propaganda_confidence >= 0.0 AND propaganda_confidence <= 1.0);

ALTER TABLE nlp_analysis
    ADD CONSTRAINT IF NOT EXISTS ck_nlp_language_conf_range
    CHECK (language_confidence >= 0.0 AND language_confidence <= 1.0);

-- =============================================================================
-- PROPAGATION TABLE - Add Constraint
-- =============================================================================

ALTER TABLE propagation
    ADD CONSTRAINT IF NOT EXISTS ck_propagation_similarity_range
    CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0);

-- =============================================================================
-- Analyze tables to update statistics for query planner
-- =============================================================================

ANALYZE content;
ANALYZE propagation;
ANALYZE nlp_analysis;

COMMIT;

-- =============================================================================
-- Verification Queries
-- =============================================================================

-- Check created indexes
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN ('content', 'propagation', 'nlp_analysis')
ORDER BY tablename, indexname;

-- Check created constraints
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    conrelid::regclass AS table_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid::regclass::text IN ('content', 'propagation', 'nlp_analysis')
    AND contype = 'c'  -- Check constraints
ORDER BY table_name, constraint_name;

-- =============================================================================
-- Performance Impact Notes
-- =============================================================================

-- Expected improvements:
-- 1. Content queries filtering by source + time range: 10-100x faster
-- 2. Propagation similarity queries: 5-20x faster
-- 3. NLP propaganda filtering: 3-10x faster
-- 4. Data integrity: Invalid data rejected by constraints
-- 5. Query planner: Better execution plans with updated statistics

-- Disk space impact:
-- Indexes will consume approximately 10-30% of table size
-- For 1M rows in content: ~500MB-1.5GB additional storage

-- Write performance impact:
-- INSERT/UPDATE operations: ~5-15% slower due to index maintenance
-- This is acceptable trade-off for read-heavy workload

-- =============================================================================
-- Rollback Script (if needed)
-- =============================================================================

-- DROP INDEX IF EXISTS ix_content_source_id;
-- DROP INDEX IF EXISTS ix_content_collected_at;
-- ... (all other indexes)
-- ALTER TABLE nlp_analysis DROP CONSTRAINT IF EXISTS ck_nlp_sentiment_range;
-- ... (all other constraints)
