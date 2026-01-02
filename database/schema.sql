-- =============================================================================
-- DOPPELGANGER TRACKER - Database Schema
-- =============================================================================
-- PostgreSQL 16+
-- Run with: psql -U doppelganger -d doppelganger -f schema.sql
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- SOURCES TABLE
-- =============================================================================
-- Stores information about content sources (Telegram, media, etc.)

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identification
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    platform VARCHAR(100),
    
    -- Metadata
    url TEXT,
    telegram_channel_id BIGINT,
    language VARCHAR(10),
    
    -- Classification
    is_doppelganger BOOLEAN DEFAULT FALSE,
    is_amplifier BOOLEAN DEFAULT FALSE,
    is_factchecker BOOLEAN DEFAULT FALSE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    first_seen_at TIMESTAMP WITH TIME ZONE,
    last_collected_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_source_type CHECK (
        source_type IN ('telegram', 'domain', 'media', 'factcheck', 'social')
    )
);

-- Indexes for sources
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_language ON sources(language);
CREATE INDEX IF NOT EXISTS idx_sources_telegram_id ON sources(telegram_channel_id);
CREATE INDEX IF NOT EXISTS idx_sources_doppelganger ON sources(is_doppelganger) 
    WHERE is_doppelganger = TRUE;

-- =============================================================================
-- CONTENT TABLE
-- =============================================================================
-- Stores collected content (articles, posts, messages)

CREATE TABLE IF NOT EXISTS content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Source reference
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    
    -- Identification
    external_id VARCHAR(255),
    content_type VARCHAR(50) NOT NULL,
    
    -- Content
    title TEXT,
    text_content TEXT NOT NULL,
    text_hash VARCHAR(64) NOT NULL,
    
    -- Media
    has_media BOOLEAN DEFAULT FALSE,
    media_urls TEXT[],
    media_types VARCHAR(50)[],
    
    -- Metadata
    url TEXT,
    author VARCHAR(255),
    author_id VARCHAR(255),
    language VARCHAR(10),
    
    -- Engagement
    views_count INTEGER,
    shares_count INTEGER,
    comments_count INTEGER,
    reactions_count INTEGER,
    
    -- Timestamps
    published_at TIMESTAMP WITH TIME ZONE,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Analysis status
    is_analyzed BOOLEAN DEFAULT FALSE,
    analysis_version INTEGER DEFAULT 0,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_content_type CHECK (
        content_type IN ('article', 'post', 'message', 'forward', 'comment')
    )
);

-- Indexes for content
CREATE INDEX IF NOT EXISTS idx_content_hash ON content(text_hash);
CREATE INDEX IF NOT EXISTS idx_content_source ON content(source_id);
CREATE INDEX IF NOT EXISTS idx_content_published ON content(published_at);
CREATE INDEX IF NOT EXISTS idx_content_type ON content(content_type);
CREATE INDEX IF NOT EXISTS idx_content_language ON content(language);
CREATE INDEX IF NOT EXISTS idx_content_analyzed ON content(is_analyzed);
CREATE INDEX IF NOT EXISTS idx_content_text_trgm ON content 
    USING gin(text_content gin_trgm_ops);

-- =============================================================================
-- PROPAGATION TABLE
-- =============================================================================
-- Links between related content items

CREATE TABLE IF NOT EXISTS propagation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Content references
    source_content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    target_content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    
    -- Classification
    propagation_type VARCHAR(50) NOT NULL,
    
    -- Analysis
    similarity_score FLOAT,
    mutation_detected BOOLEAN DEFAULT FALSE,
    mutation_type VARCHAR(50),
    mutation_description TEXT,
    
    -- Timing
    time_delta_seconds INTEGER,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_propagation_type CHECK (
        propagation_type IN ('forward', 'quote', 'repost', 'mention', 'link', 'similar')
    ),
    CONSTRAINT uq_propagation_link UNIQUE (source_content_id, target_content_id)
);

-- Indexes for propagation
CREATE INDEX IF NOT EXISTS idx_propagation_source ON propagation(source_content_id);
CREATE INDEX IF NOT EXISTS idx_propagation_target ON propagation(target_content_id);
CREATE INDEX IF NOT EXISTS idx_propagation_type ON propagation(propagation_type);

-- =============================================================================
-- NLP ANALYSIS TABLE
-- =============================================================================
-- NLP processing results

CREATE TABLE IF NOT EXISTS nlp_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID UNIQUE NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    
    -- Sentiment
    sentiment_score FLOAT,
    sentiment_label VARCHAR(20),
    sentiment_confidence FLOAT,
    
    -- Entities (JSONB for flexibility)
    entities JSONB,
    
    -- Keywords and topics
    keywords TEXT[],
    topics TEXT[],
    
    -- Embeddings
    embedding FLOAT[],
    
    -- Propaganda classification
    is_propaganda BOOLEAN,
    propaganda_confidence FLOAT,
    propaganda_techniques TEXT[],
    
    -- Language detection
    detected_language VARCHAR(10),
    language_confidence FLOAT,
    
    -- Metadata
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_version VARCHAR(50)
);

-- Indexes for nlp_analysis
CREATE INDEX IF NOT EXISTS idx_nlp_content ON nlp_analysis(content_id);
CREATE INDEX IF NOT EXISTS idx_nlp_propaganda ON nlp_analysis(is_propaganda);
CREATE INDEX IF NOT EXISTS idx_nlp_sentiment ON nlp_analysis(sentiment_label);

-- =============================================================================
-- COGNITIVE MARKERS TABLE
-- =============================================================================
-- Detected manipulation markers

CREATE TABLE IF NOT EXISTS cognitive_markers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    
    -- Marker identification
    marker_type VARCHAR(100) NOT NULL,
    marker_category VARCHAR(100) NOT NULL,
    
    -- Scoring
    confidence FLOAT NOT NULL,
    severity VARCHAR(20),
    
    -- Evidence
    evidence_text TEXT,
    evidence_start INTEGER,
    evidence_end INTEGER,
    
    -- Context
    context_notes TEXT,
    
    -- Metadata
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    detector_version VARCHAR(50)
);

-- Indexes for cognitive_markers
CREATE INDEX IF NOT EXISTS idx_markers_content ON cognitive_markers(content_id);
CREATE INDEX IF NOT EXISTS idx_markers_type ON cognitive_markers(marker_type);
CREATE INDEX IF NOT EXISTS idx_markers_category ON cognitive_markers(marker_category);
CREATE INDEX IF NOT EXISTS idx_markers_severity ON cognitive_markers(severity);

-- =============================================================================
-- FACTCHECKS TABLE
-- =============================================================================
-- Fact-checking records

CREATE TABLE IF NOT EXISTS factchecks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID REFERENCES content(id) ON DELETE SET NULL,
    
    -- Claim
    claim_text TEXT NOT NULL,
    
    -- Verdict
    verdict VARCHAR(50) NOT NULL,
    verdict_details TEXT,
    
    -- Source
    factcheck_source VARCHAR(255),
    factcheck_url TEXT,
    factcheck_date TIMESTAMP WITH TIME ZONE,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for factchecks
CREATE INDEX IF NOT EXISTS idx_factchecks_content ON factchecks(content_id);
CREATE INDEX IF NOT EXISTS idx_factchecks_verdict ON factchecks(verdict);

-- =============================================================================
-- DOMAINS TABLE
-- =============================================================================
-- Tracked domains for typosquatting

CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Domain info
    domain VARCHAR(255) NOT NULL UNIQUE,
    tld VARCHAR(20),
    
    -- Typosquatting
    impersonates VARCHAR(255),
    similarity_score FLOAT,
    typosquat_type VARCHAR(50),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    first_seen_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    
    -- Technical
    ip_addresses VARCHAR(45)[],
    hosting_provider VARCHAR(255),
    ssl_issuer VARCHAR(255),
    
    -- Classification
    is_confirmed_doppelganger BOOLEAN DEFAULT FALSE,
    attribution_source VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for domains
CREATE INDEX IF NOT EXISTS idx_domains_impersonates ON domains(impersonates);
CREATE INDEX IF NOT EXISTS idx_domains_doppelganger ON domains(is_confirmed_doppelganger)
    WHERE is_confirmed_doppelganger = TRUE;

-- =============================================================================
-- NARRATIVES TABLE
-- =============================================================================
-- Tracked narrative themes

CREATE TABLE IF NOT EXISTS narratives (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identification
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    
    -- Classification
    category VARCHAR(100),
    subcategory VARCHAR(100),
    
    -- Tracking
    first_seen_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    content_count INTEGER DEFAULT 0,
    
    -- Keywords
    keywords TEXT[],
    example_claims TEXT[],
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- CONTENT_NARRATIVES TABLE
-- =============================================================================
-- Many-to-many relationship between content and narratives

CREATE TABLE IF NOT EXISTS content_narratives (
    content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    narrative_id UUID NOT NULL REFERENCES narratives(id) ON DELETE CASCADE,
    confidence FLOAT,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (content_id, narrative_id)
);

-- =============================================================================
-- COLLECTION_RUNS TABLE
-- =============================================================================
-- Logging for collection runs

CREATE TABLE IF NOT EXISTS collection_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Run info
    collector_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    
    -- Results
    status VARCHAR(20) DEFAULT 'running',
    items_collected INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    
    -- Details
    error_messages TEXT[],
    metadata JSONB
);

-- Indexes for collection_runs
CREATE INDEX IF NOT EXISTS idx_runs_type ON collection_runs(collector_type);
CREATE INDEX IF NOT EXISTS idx_runs_status ON collection_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON collection_runs(started_at);

-- =============================================================================
-- SEED DATA - Doppelganger Domains
-- =============================================================================
-- Insert known Doppelganger domains from public attributions

INSERT INTO domains (domain, tld, impersonates, typosquat_type, is_confirmed_doppelganger, attribution_source)
VALUES 
    ('reuters.cfd', '.cfd', 'reuters.com', 'tld_swap', TRUE, 'DOJ Indictment 2024'),
    ('lemonde.ltd', '.ltd', 'lemonde.fr', 'tld_swap', TRUE, 'DOJ Indictment 2024'),
    ('spiegel.ltd', '.ltd', 'spiegel.de', 'tld_swap', TRUE, 'DOJ Indictment 2024'),
    ('bild.ltd', '.ltd', 'bild.de', 'tld_swap', TRUE, 'EU DisinfoLab'),
    ('faz.ltd', '.ltd', 'faz.net', 'tld_swap', TRUE, 'EU DisinfoLab'),
    ('guardian.ltd', '.ltd', 'theguardian.com', 'tld_swap', TRUE, 'Graphika'),
    ('washingtonpost.ltd', '.ltd', 'washingtonpost.com', 'tld_swap', TRUE, 'DOJ Indictment 2024'),
    ('foxnews.ltd', '.ltd', 'foxnews.com', 'tld_swap', TRUE, 'NewsGuard')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- SEED DATA - Narratives
-- =============================================================================
-- Insert tracked narrative themes

INSERT INTO narratives (name, description, category, keywords)
VALUES 
    ('Ukraine Corruption', 'Narrative portraying Ukraine as corrupt', 'anti_ukraine', 
     ARRAY['corruption', 'zelensky', 'oligarch', 'nazi']),
    ('NATO Expansion', 'Narrative about NATO aggression/expansion', 'anti_nato',
     ARRAY['nato', 'expansion', 'encirclement', 'provocation']),
    ('EU Energy Crisis', 'Narrative about European energy crisis', 'anti_eu',
     ARRAY['energy', 'sanctions', 'gas', 'winter']),
    ('Western Weapons Failure', 'Narrative about Western weapons failing', 'pro_russia',
     ARRAY['weapons', 'failure', 'destroyed', 'ineffective']),
    ('Peace Sabotage', 'Narrative about West sabotaging peace', 'peace_sabotage',
     ARRAY['peace', 'negotiations', 'sabotage', 'refuse'])
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- TRIGGERS
-- =============================================================================
-- Auto-update timestamps

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at
DO $$ 
BEGIN
    -- Sources
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'sources_updated_at') THEN
        CREATE TRIGGER sources_updated_at BEFORE UPDATE ON sources
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    
    -- Content
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'content_updated_at') THEN
        CREATE TRIGGER content_updated_at BEFORE UPDATE ON content
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    
    -- Domains
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'domains_updated_at') THEN
        CREATE TRIGGER domains_updated_at BEFORE UPDATE ON domains
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    
    -- Narratives
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'narratives_updated_at') THEN
        CREATE TRIGGER narratives_updated_at BEFORE UPDATE ON narratives
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

-- =============================================================================
-- VIEWS
-- =============================================================================
-- Useful views for analysis

CREATE OR REPLACE VIEW v_content_summary AS
SELECT 
    c.id,
    c.title,
    c.content_type,
    c.language,
    c.published_at,
    s.name AS source_name,
    s.source_type,
    s.is_doppelganger,
    n.sentiment_label,
    n.is_propaganda,
    (SELECT COUNT(*) FROM cognitive_markers cm WHERE cm.content_id = c.id) AS marker_count
FROM content c
LEFT JOIN sources s ON c.source_id = s.id
LEFT JOIN nlp_analysis n ON n.content_id = c.id;

-- =============================================================================
-- COMPLETION
-- =============================================================================
-- Verify schema creation

DO $$
BEGIN
    RAISE NOTICE 'Schema creation completed successfully!';
END $$;
