-- Guild Configuration
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id BIGINT PRIMARY KEY,
    ticket_category_id BIGINT,
    transcript_channel_id BIGINT,
    log_channel_id BIGINT, -- General fallback
    mod_log_channel_id BIGINT,
    message_log_channel_id BIGINT,
    member_log_channel_id BIGINT,
    voice_log_channel_id BIGINT,
    log_message_edits BOOLEAN DEFAULT TRUE,
    log_message_deletions BOOLEAN DEFAULT TRUE,
    log_member_joins BOOLEAN DEFAULT TRUE,
    log_member_leaves BOOLEAN DEFAULT TRUE,
    log_voice_updates BOOLEAN DEFAULT TRUE,
    mod_role_id BIGINT,
    admin_role_id BIGINT
);

-- Ticket Categories / Reasons
CREATE TABLE IF NOT EXISTS ticket_reasons (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    label VARCHAR(100) NOT NULL,
    category_id BIGINT NOT NULL, 
    description TEXT,
    emoji VARCHAR(50), -- Kept column for compatibility but won't use emojis in UI
    required_roles BIGINT[] 
);

-- Tickets
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT UNIQUE NOT NULL,
    owner_id BIGINT NOT NULL,
    reason_id INTEGER REFERENCES ticket_reasons(id),
    status VARCHAR(20) DEFAULT 'open', 
    claimed_by BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    transcript_url TEXT,
    transcript_text TEXT
);

-- Punishments
CREATE TABLE IF NOT EXISTS punishments (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    type VARCHAR(20) NOT NULL, 
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP, 
    active BOOLEAN DEFAULT TRUE
);

-- Automod Rules
CREATE TABLE IF NOT EXISTS automod_rules (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    rule_type VARCHAR(50) NOT NULL, 
    pattern TEXT NOT NULL,
    punishment_type VARCHAR(20) NOT NULL, 
    enabled BOOLEAN DEFAULT TRUE,
    exempt_roles BIGINT[],
    exempt_channels BIGINT[]
);

-- Snippets
CREATE TABLE IF NOT EXISTS snippets (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    content_json JSONB NOT NULL,
    created_by BIGINT
);

-- General Server Logs
CREATE TABLE IF NOT EXISTS server_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT,
    action_type VARCHAR(50) NOT NULL, -- message_delete, member_join, etc.
    target_id BIGINT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Automod Word Filters
CREATE TABLE IF NOT EXISTS word_filters (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    phrase TEXT NOT NULL,
    UNIQUE(guild_id, phrase)
);
