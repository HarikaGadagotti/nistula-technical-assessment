-- =============================================================================
-- Nistula Unified Messaging Platform — PostgreSQL Schema
-- schema.sql
--
-- Design goals:
--   1. One canonical guest record regardless of how many channels they use.
--   2. All messages in a single table (inbox) — avoids fan-out queries.
--   3. Every AI draft is auditable: we store what the AI said, what the
--      agent changed (if anything), what was actually sent, and why.
--   4. Conversations are first-class entities linking guests ↔ reservations.
--   5. Confidence scores and query types are indexed for analytics queries
--      (e.g. "how often does the AI get complaints right?").
-- =============================================================================

-- ---------------------------------------------------------------------------
-- EXTENSION
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- trigram indexes for name search


-- ---------------------------------------------------------------------------
-- PROPERTIES
-- A reference table for the villas / properties managed by Nistula.
-- ---------------------------------------------------------------------------
CREATE TABLE properties (
    property_id     TEXT        PRIMARY KEY,                   -- e.g. 'villa-b1'
    name            TEXT        NOT NULL,
    location        TEXT        NOT NULL,
    max_guests      SMALLINT    NOT NULL CHECK (max_guests > 0),
    base_rate_inr   NUMERIC(10,2) NOT NULL,
    extra_guest_rate_inr NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------
-- GUESTS
-- One record per unique guest, merged across all channels.
--
-- Design decision: We use a canonical guest record rather than per-channel
-- records because the same person may contact Nistula via WhatsApp today and
-- Booking.com tomorrow.  The channel_identifiers JSONB column stores all
-- known channel-specific IDs (e.g. {"whatsapp": "+919876543210",
-- "airbnb": "guest_abc123"}) allowing reverse lookup.
--
-- Unique constraint on normalised_phone and email prevents duplicates while
-- allowing guests who only have one identifier.
-- ---------------------------------------------------------------------------
CREATE TABLE guests (
    guest_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name           TEXT        NOT NULL,
    email               TEXT        UNIQUE,
    phone_normalised    TEXT        UNIQUE,                    -- E.164 format
    channel_identifiers JSONB       NOT NULL DEFAULT '{}',     -- {source: id}
    preferred_channel   TEXT,                                  -- whatsapp | email | etc.
    vip_flag            BOOLEAN     NOT NULL DEFAULT FALSE,
    total_stays         SMALLINT    NOT NULL DEFAULT 0,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigram index for fuzzy name search (e.g. "Rahul Sharm" → "Rahul Sharma")
CREATE INDEX idx_guests_name_trgm ON guests USING gin (full_name gin_trgm_ops);
CREATE INDEX idx_guests_channel_ids ON guests USING gin (channel_identifiers);


-- ---------------------------------------------------------------------------
-- RESERVATIONS
-- Booking records.  A guest can have many reservations; a property can have
-- many reservations.  Conversations and messages link to reservations.
-- ---------------------------------------------------------------------------
CREATE TABLE reservations (
    reservation_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref     TEXT        NOT NULL UNIQUE,               -- e.g. NIS-2024-0891
    guest_id        UUID        NOT NULL REFERENCES guests(guest_id) ON DELETE RESTRICT,
    property_id     TEXT        NOT NULL REFERENCES properties(property_id),
    check_in        DATE        NOT NULL,
    check_out       DATE        NOT NULL,
    num_guests      SMALLINT    NOT NULL CHECK (num_guests > 0),
    total_amount_inr NUMERIC(12,2),
    status          TEXT        NOT NULL DEFAULT 'confirmed'
                    CHECK (status IN ('enquiry','confirmed','checked_in','checked_out','cancelled')),
    source_channel  TEXT        NOT NULL,                      -- booking_com | airbnb | direct
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT check_dates CHECK (check_out > check_in)
);

CREATE INDEX idx_reservations_guest ON reservations(guest_id);
CREATE INDEX idx_reservations_property ON reservations(property_id);
CREATE INDEX idx_reservations_checkin ON reservations(check_in);


-- ---------------------------------------------------------------------------
-- CONVERSATIONS
-- A conversation groups a thread of messages between a guest and Nistula
-- on a specific channel.  One guest may have multiple concurrent conversations
-- (e.g. one on WhatsApp for pre-stay, one on Booking.com for a complaint).
-- ---------------------------------------------------------------------------
CREATE TABLE conversations (
    conversation_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID        NOT NULL REFERENCES guests(guest_id),
    reservation_id  UUID        REFERENCES reservations(reservation_id),  -- nullable pre-booking
    property_id     TEXT        REFERENCES properties(property_id),
    channel         TEXT        NOT NULL
                    CHECK (channel IN ('whatsapp','booking_com','airbnb','instagram','direct')),
    status          TEXT        NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','resolved','escalated')),
    subject         TEXT,                                      -- auto-set from first message
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    assigned_agent  TEXT,                                      -- agent username / ID
    escalation_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_guest ON conversations(guest_id);
CREATE INDEX idx_conversations_reservation ON conversations(reservation_id);
CREATE INDEX idx_conversations_status ON conversations(status);


-- ---------------------------------------------------------------------------
-- MESSAGES
-- Every inbound and outbound message.  This is the single source of truth
-- for the full message history across all channels.
--
-- Key audit columns:
--   ai_drafted_text    — raw text produced by Claude
--   agent_edited_text  — text after human edits (NULL = not edited)
--   sent_text          — what was actually delivered to the guest
--   send_status        — auto_sent | agent_sent | escalated | failed
--   ai_query_type      — classifier output
--   ai_confidence      — our confidence score (0–1)
--
-- Design decision (hardest):
--   We store three versions of outbound text (ai_drafted, agent_edited,
--   sent_text) rather than overwriting.  This is verbosity but it enables:
--     (a) training data: compare AI draft vs human correction over time
--     (b) audit trail: legal / dispute resolution
--     (c) quality analytics: how often do agents edit AI drafts?
--   The cost is storage (TEXT columns are cheap) and slightly more complex
--   INSERT logic — worth it.
-- ---------------------------------------------------------------------------
CREATE TABLE messages (
    message_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID        NOT NULL REFERENCES conversations(conversation_id),
    guest_id            UUID        NOT NULL REFERENCES guests(guest_id),
    direction           TEXT        NOT NULL CHECK (direction IN ('inbound','outbound')),
    channel             TEXT        NOT NULL,
    raw_payload         JSONB,                                  -- original webhook JSON
    message_text        TEXT        NOT NULL,                   -- normalised inbound text
    received_at         TIMESTAMPTZ,                            -- inbound only
    sent_at             TIMESTAMPTZ,                            -- outbound only

    -- AI processing columns (populated for inbound messages)
    ai_query_type       TEXT        CHECK (ai_query_type IN (
                            'pre_sales_availability','pre_sales_pricing',
                            'post_sales_checkin','special_request',
                            'complaint','general_enquiry'
                        )),
    ai_confidence       NUMERIC(4,3) CHECK (ai_confidence BETWEEN 0 AND 1),
    ai_drafted_text     TEXT,                                   -- Claude's raw draft
    ai_model_used       TEXT,                                   -- model string

    -- Human intervention columns (populated for outbound messages)
    agent_edited_text   TEXT,                                   -- NULL if not edited
    agent_id            TEXT,                                   -- who edited / approved
    sent_text           TEXT,                                   -- final delivered text
    send_status         TEXT        CHECK (send_status IN (
                            'auto_sent','agent_sent','escalated','failed','pending'
                        )),

    booking_ref         TEXT,                                   -- denormalised for quick lookup
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_guest ON messages(guest_id);
CREATE INDEX idx_messages_query_type ON messages(ai_query_type);
CREATE INDEX idx_messages_send_status ON messages(send_status);
CREATE INDEX idx_messages_received_at ON messages(received_at DESC);

-- Partial index for analytics: AI drafts by confidence band
CREATE INDEX idx_messages_low_confidence ON messages(ai_confidence)
    WHERE ai_confidence IS NOT NULL AND ai_confidence < 0.60;


-- ---------------------------------------------------------------------------
-- AI_AUDIT_LOG
-- Immutable append-only log of every Claude API call.
-- Useful for cost tracking, latency monitoring, and debugging.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_audit_log (
    log_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID        REFERENCES messages(message_id),
    model           TEXT        NOT NULL,
    prompt_tokens   INT,
    completion_tokens INT,
    latency_ms      INT,
    confidence      NUMERIC(4,3),
    query_type      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_audit_created ON ai_audit_log(created_at DESC);


-- ---------------------------------------------------------------------------
-- PROPERTY_ISSUE_LOG
-- Tracks recurring operational issues per property.
-- This table powers the pattern detection in the thinking.md escalation
-- design — if the same issue occurs 3+ times, it triggers a maintenance flag.
-- ---------------------------------------------------------------------------
CREATE TABLE property_issue_log (
    issue_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id     TEXT        NOT NULL REFERENCES properties(property_id),
    issue_category  TEXT        NOT NULL,                       -- 'hot_water' | 'ac' | 'wifi'
    reported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_id      UUID        REFERENCES messages(message_id),
    resolution_notes TEXT,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT
);

CREATE INDEX idx_issue_log_property_category
    ON property_issue_log(property_id, issue_category, reported_at DESC);


-- ---------------------------------------------------------------------------
-- VIEW: conversation_summary
-- Convenient view for the agent dashboard — one row per conversation with
-- the most recent message preview.
-- ---------------------------------------------------------------------------
CREATE VIEW conversation_summary AS
SELECT
    c.conversation_id,
    c.status,
    c.channel,
    g.full_name          AS guest_name,
    g.phone_normalised,
    r.booking_ref,
    c.property_id,
    latest.message_text  AS last_message,
    latest.ai_confidence AS last_confidence,
    latest.ai_query_type AS last_query_type,
    latest.send_status,
    c.opened_at,
    c.assigned_agent
FROM conversations c
JOIN guests g ON g.guest_id = c.guest_id
LEFT JOIN reservations r ON r.reservation_id = c.reservation_id
LEFT JOIN LATERAL (
    SELECT message_text, ai_confidence, ai_query_type, send_status
    FROM messages
    WHERE conversation_id = c.conversation_id
    ORDER BY created_at DESC
    LIMIT 1
) latest ON TRUE;