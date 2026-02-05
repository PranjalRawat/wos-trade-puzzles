-- Discord Puzzle Trading Bot - Database Schema
-- SQLite schema with easy migration path to Postgres

-- Users table: Maps Discord users to internal IDs
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL UNIQUE,
    discord_username TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_discord_id ON users(discord_id);

-- Inventory table: Tracks piece ownership
-- CRITICAL: (user_id, scene, slot_index) must be unique
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    scene TEXT NOT NULL,
    slot_index INTEGER NOT NULL,
    stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    duplicates INTEGER NOT NULL DEFAULT 0 CHECK (duplicates >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, scene, slot_index)
);

CREATE INDEX IF NOT EXISTS idx_inventory_user_scene ON inventory(user_id, scene);
CREATE INDEX IF NOT EXISTS idx_inventory_scene_slot ON inventory(scene, slot_index);

-- Scan history: Audit trail of all image scans
CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    image_hash TEXT NOT NULL,
    image_filename TEXT,
    scene TEXT,
    pieces_found INTEGER DEFAULT 0,
    pieces_added INTEGER DEFAULT 0,
    pieces_updated INTEGER DEFAULT 0,
    conflicts_found INTEGER DEFAULT 0,
    scan_status TEXT NOT NULL, -- 'success', 'partial', 'failed', 'skipped'
    error_message TEXT,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scan_history_user ON scan_history(user_id);
CREATE INDEX IF NOT EXISTS idx_scan_history_hash ON scan_history(image_hash);

-- Image hashes: Deduplication tracking
-- Prevents processing the same image multiple times
CREATE TABLE IF NOT EXISTS image_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL UNIQUE,
    first_seen_by INTEGER NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    times_attempted INTEGER DEFAULT 1,
    FOREIGN KEY (first_seen_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_image_hashes_hash ON image_hashes(hash);

-- Scan details: Tracks exactly what each scan did
-- Required for /unscan rollback functionality
CREATE TABLE IF NOT EXISTS scan_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    scene TEXT NOT NULL,
    slot_index INTEGER NOT NULL,
    added_duplicates INTEGER DEFAULT 0,
    FOREIGN KEY (scan_id) REFERENCES scan_history(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scan_details_scan ON scan_details(scan_id);
