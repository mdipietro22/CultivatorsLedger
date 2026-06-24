-- CULTIVATION TELEMETRY ENGINE - FULL SOURCE OF TRUTH BLUEPRINT
-- Target Platform: PostgreSQL (Compatible with local PGMQ extensions)

DROP TABLE IF EXISTS climate_logs CASCADE;
DROP TABLE IF EXISTS irrigation_events CASCADE;
DROP TABLE IF EXISTS batch_harvests CASCADE;
DROP TABLE IF EXISTS import_history CASCADE;
DROP TABLE IF EXISTS system_settings CASCADE;

-- 1. SYSTEM SETTINGS (The RPG Control Center)
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Cultivation Preferences
    default_leaf_offset_c NUMERIC(3,2) DEFAULT 2.00,
    current_growth_stage VARCHAR(20) DEFAULT 'vegetative' CHECK (current_growth_stage IN ('seedling', 'vegetative', 'flowering')),
    preferred_temp_unit VARCHAR(1) DEFAULT 'C' CHECK (preferred_temp_unit IN ('C', 'F')),
    
    -- Feature RPG Toggles (UI reads these to render/hide specific data fields dynamically)
    show_ec_column BOOLEAN DEFAULT TRUE,
    show_yield_column BOOLEAN DEFAULT TRUE,
    show_notes_column BOOLEAN DEFAULT TRUE,
    show_zone_analytics BOOLEAN DEFAULT TRUE,
    show_vpd_warnings BOOLEAN DEFAULT TRUE,
    
    -- Infrastructure Toggles
    enable_cloud_backup BOOLEAN DEFAULT FALSE,
    is_manual_only_mode BOOLEAN DEFAULT FALSE
);

-- Initialize the master setting row immediately
INSERT INTO system_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- 2. IMPORT & TRANSACTION LOGS (The Safety-Net Rollback Ledger)
CREATE TABLE import_history (
    id SERIAL PRIMARY KEY,
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    filename VARCHAR(255) NOT NULL,
    rows_imported INTEGER NOT NULL,
    import_status VARCHAR(20) DEFAULT 'completed' CHECK (import_status IN ('completed', 'rolled_back')),
    rollback_at TIMESTAMPTZ
);

-- 3. CLIMATE TELEMETRY LOGS (Multi-Room, Multi-Zone Atmospheric Vault)
CREATE TABLE climate_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    room_id VARCHAR(50) NOT NULL,
    zone_id VARCHAR(50) DEFAULT 'Main',
    sensor_mac VARCHAR(17) DEFAULT NULL 
        CHECK (sensor_mac ~ '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$' OR sensor_mac IS NULL), -- ✅ Fixed
    air_temp_c NUMERIC(4,2) NOT NULL,
    relative_humidity NUMERIC(5,2) NOT NULL,
    leaf_offset_c NUMERIC(3,2) DEFAULT 2.00,
    calculated_vpd_kpa NUMERIC(4,2) CHECK (calculated_vpd_kpa >= 0), -- ✅ Fixed
    import_id INTEGER REFERENCES import_history(id) ON DELETE CASCADE,
    is_manual_entry BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_climate_room_time ON climate_logs(room_id, timestamp);
CREATE INDEX idx_climate_timestamp ON climate_logs(timestamp);

-- 4. ROOT-ZONE SUBSTRATE LOGS (The Crop Steering Analytics Core)
CREATE TABLE irrigation_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    room_id VARCHAR(50) NOT NULL,
    zone_id VARCHAR(50) NOT NULL,
    sensor_mac VARCHAR(17) DEFAULT NULL 
        CHECK (sensor_mac ~ '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$' OR sensor_mac IS NULL), -- ✅ Fixed
    moisture_percentage NUMERIC(5,2) NOT NULL,
    ec_level NUMERIC(3,1) CHECK (ec_level >= 0 AND ec_level <= 10.0), -- ✅ Fixed
    import_id INTEGER REFERENCES import_history(id) ON DELETE CASCADE,
    is_manual_entry BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_irrigation_room_time ON irrigation_events(room_id, timestamp);

-- 5. BATCH CYCLE JOURNAL (The Pure Performance Ledger)
CREATE TABLE batch_harvests (
    id SERIAL PRIMARY KEY,
    strain_name VARCHAR(100) NOT NULL,
    room_id VARCHAR(50),
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    flower_flip_date DATE DEFAULT NULL,
    harvest_date DATE DEFAULT NULL,
    total_dry_yield_g NUMERIC(8,2) DEFAULT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);