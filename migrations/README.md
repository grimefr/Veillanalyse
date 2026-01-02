# 🔄 Database Migrations

This directory contains SQL migration scripts for the Doppelganger Tracker database.

---

## 📋 Migration Scripts

### `add_indexes_and_constraints.sql`
**Version**: 2.0
**Date**: 2026-01-02
**Purpose**: Add performance indexes and data integrity constraints

**Changes**:
- ✅ 9 new indexes on `content` table
- ✅ 5 new indexes on `propagation` table
- ✅ 6 new indexes on `nlp_analysis` table
- ✅ 5 check constraints for data validation

**Performance Impact**:
- Read queries: 5-100x faster (depending on query)
- Write operations: ~10% slower (acceptable trade-off)
- Disk space: +10-30% for indexes

---

## 🚀 How to Apply Migrations

### Option 1: Docker (Recommended)

```bash
# Apply migration via Docker
docker compose exec postgres psql -U doppelganger -d doppelganger -f /docker-entrypoint-initdb.d/add_indexes_and_constraints.sql

# OR copy and execute
docker cp migrations/add_indexes_and_constraints.sql doppelganger-db:/tmp/
docker compose exec postgres psql -U doppelganger -d doppelganger -f /tmp/add_indexes_and_constraints.sql
```

### Option 2: Direct PostgreSQL Connection

```bash
# Using psql
psql -h localhost -U doppelganger -d doppelganger -f migrations/add_indexes_and_constraints.sql

# Using environment variable
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U doppelganger -d doppelganger \
    -f migrations/add_indexes_and_constraints.sql
```

### Option 3: Python Script

```python
from database import get_engine
from pathlib import Path

engine = get_engine()
migration_sql = Path("migrations/add_indexes_and_constraints.sql").read_text()

with engine.connect() as conn:
    conn.execute(text(migration_sql))
    conn.commit()

print("Migration applied successfully!")
```

---

## ✅ Verification

### Check Indexes Created

```sql
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN ('content', 'propagation', 'nlp_analysis')
ORDER BY tablename, indexname;
```

### Check Constraints Created

```sql
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    conrelid::regclass AS table_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid::regclass::text IN ('content', 'propagation', 'nlp_analysis')
    AND contype = 'c'
ORDER BY table_name, constraint_name;
```

### Check Index Usage

```sql
-- After running queries for a while, check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,          -- Number of times index was used
    idx_tup_read,      -- Tuples read
    idx_tup_fetch      -- Tuples fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND tablename IN ('content', 'propagation', 'nlp_analysis')
ORDER BY idx_scan DESC;
```

---

## 🔙 Rollback (if needed)

If migration causes issues, rollback with:

```sql
BEGIN;

-- Drop all new indexes
DROP INDEX IF EXISTS ix_content_source_id;
DROP INDEX IF EXISTS ix_content_collected_at;
DROP INDEX IF EXISTS ix_content_published_at;
DROP INDEX IF EXISTS ix_content_language;
DROP INDEX IF EXISTS ix_content_is_analyzed;
DROP INDEX IF EXISTS ix_content_source_collected;
DROP INDEX IF EXISTS ix_content_source_published;
DROP INDEX IF EXISTS ix_content_analyzed_version;
DROP INDEX IF EXISTS ix_content_unanalyzed;

DROP INDEX IF EXISTS idx_propagation_created;
DROP INDEX IF EXISTS idx_propagation_source_similarity;
DROP INDEX IF EXISTS idx_propagation_target_similarity;
DROP INDEX IF EXISTS idx_propagation_source_created;

DROP INDEX IF EXISTS idx_nlp_analyzed_at;
DROP INDEX IF EXISTS idx_nlp_language;
DROP INDEX IF EXISTS idx_nlp_propaganda_analyzed;
DROP INDEX IF EXISTS idx_nlp_propaganda_confidence;
DROP INDEX IF EXISTS idx_nlp_sentiment_analyzed;

-- Drop constraints
ALTER TABLE nlp_analysis DROP CONSTRAINT IF EXISTS ck_nlp_sentiment_range;
ALTER TABLE nlp_analysis DROP CONSTRAINT IF EXISTS ck_nlp_sentiment_conf_range;
ALTER TABLE nlp_analysis DROP CONSTRAINT IF EXISTS ck_nlp_propaganda_conf_range;
ALTER TABLE nlp_analysis DROP CONSTRAINT IF EXISTS ck_nlp_language_conf_range;
ALTER TABLE propagation DROP CONSTRAINT IF EXISTS ck_propagation_similarity_range;

COMMIT;
```

---

## 📊 Performance Testing

### Before Migration

```sql
-- Test query performance BEFORE applying migration
EXPLAIN ANALYZE
SELECT c.*
FROM content c
WHERE c.source_id = '123e4567-e89b-12d3-a456-426614174000'
    AND c.collected_at >= NOW() - INTERVAL '7 days'
ORDER BY c.collected_at DESC
LIMIT 100;
```

### After Migration

```sql
-- Same query AFTER migration should show index usage
EXPLAIN ANALYZE
SELECT c.*
FROM content c
WHERE c.source_id = '123e4567-e89b-12d3-a456-426614174000'
    AND c.collected_at >= NOW() - INTERVAL '7 days'
ORDER BY c.collected_at DESC
LIMIT 100;

-- Look for "Index Scan using ix_content_source_collected"
-- instead of "Seq Scan on content"
```

---

## 🎯 Best Practices

### Before Migration
1. ✅ Backup database: `pg_dump -U doppelganger doppelganger > backup.sql`
2. ✅ Test on staging environment first
3. ✅ Monitor disk space (indexes need ~20% additional space)
4. ✅ Schedule during low-traffic period

### During Migration
1. ✅ Run inside transaction (already done in script)
2. ✅ Monitor query duration (`CREATE INDEX` can take time on large tables)
3. ✅ Check for locks: `SELECT * FROM pg_locks WHERE NOT granted;`

### After Migration
1. ✅ Run `ANALYZE` to update statistics (already done in script)
2. ✅ Monitor query performance with `EXPLAIN ANALYZE`
3. ✅ Check index usage after 24-48 hours
4. ✅ Monitor disk usage

---

## 📝 Migration Log

Keep track of applied migrations:

```sql
-- Create migrations tracking table (optional)
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    description TEXT
);

-- Record migration
INSERT INTO schema_migrations (version, description)
VALUES ('2.0_add_indexes', 'Add performance indexes and data constraints');
```

---

## 🆘 Troubleshooting

### Issue: Migration times out

**Solution**: Create indexes concurrently (no table lock)

```sql
-- Instead of CREATE INDEX, use:
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_content_source_id
    ON content(source_id);
```

**Note**: Cannot use `CONCURRENTLY` inside a transaction

### Issue: Out of disk space

**Solution**: Drop least-used indexes

```sql
-- Find unused indexes
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Drop if confirmed unused after 1+ week
DROP INDEX idx_name;
```

### Issue: Constraint violation on existing data

**Solution**: Fix data before applying constraint

```sql
-- Find invalid data
SELECT * FROM nlp_analysis
WHERE sentiment_score NOT BETWEEN -1.0 AND 1.0;

-- Fix data
UPDATE nlp_analysis
SET sentiment_score = GREATEST(-1.0, LEAST(1.0, sentiment_score));

-- Then apply constraint
```

---

## 📚 References

- [PostgreSQL Indexes](https://www.postgresql.org/docs/current/indexes.html)
- [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [Index Maintenance](https://www.postgresql.org/docs/current/sql-reindex.html)
- [Query Performance](https://www.postgresql.org/docs/current/using-explain.html)

---

**Last Updated**: 2026-01-02
**Version**: 2.0
