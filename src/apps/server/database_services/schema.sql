-- Schema for Meridian

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    photo_filename TEXT,
    family_circle_id TEXT,
    phone TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS family_circles (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS family_memberships (
    user_id TEXT NOT NULL,
    family_circle_id TEXT NOT NULL,
    PRIMARY KEY (user_id, family_circle_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS family_permissions (
    user_id TEXT NOT NULL,
    family_circle_id TEXT NOT NULL,
    permission TEXT NOT NULL,
    PRIMARY KEY (user_id, family_circle_id, permission),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    family_circle_id TEXT NOT NULL,
    display_name TEXT,
    phone TEXT,
    email TEXT,
    birthday TEXT,
    relationship TEXT,
    emergency_priority TEXT,
    photo_filename TEXT,
    notes TEXT,
    linked_user_id TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS medication_time_templates (
    name TEXT PRIMARY KEY,
    time TEXT
);

INSERT OR IGNORE INTO medication_time_templates (name, time) VALUES
    ('Morning', '08:00:00'),
    ('Noon', '12:00:00'),
    ('Afternoon', '14:00:00'),
    ('Evening', '18:00:00'),
    ('Bedtime', '21:00:00'),
    ('prn', NULL);

CREATE TABLE IF NOT EXISTS medication_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    name TEXT NOT NULL,
    time TEXT,
    UNIQUE (family_circle_id, name),
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    care_recipient_user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    fda_rxcui TEXT,
    notes TEXT,
    max_daily INTEGER,
    last_taken TEXT,
    taken_today TEXT,
    FOREIGN KEY (care_recipient_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS medication_to_time (
    medication_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (medication_id, group_id),
    FOREIGN KEY (medication_id) REFERENCES medications(id),
    FOREIGN KEY (group_id) REFERENCES medication_times(id)
);

CREATE TABLE IF NOT EXISTS allergies (
    care_recipient_user_id TEXT NOT NULL,
    allergen TEXT NOT NULL,
    PRIMARY KEY (care_recipient_user_id, allergen),
    FOREIGN KEY (care_recipient_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    care_recipient_user_id TEXT NOT NULL,
    condition_name TEXT,
    diagnosis_date TEXT,
    notes TEXT,
    FOREIGN KEY (care_recipient_user_id) REFERENCES users(id),
    UNIQUE (care_recipient_user_id, condition_name)
);

CREATE TABLE IF NOT EXISTS care_recipients (
    family_circle_id TEXT PRIMARY KEY,
    care_recipient_user_id TEXT NOT NULL,
    name TEXT,
    dob TEXT,
    photo_path TEXT,
    medical_dnr INTEGER DEFAULT 0,
    dnr_document_path TEXT,
    notes TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id),
    FOREIGN KEY (care_recipient_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ice_contact_roles (
    family_circle_id TEXT NOT NULL,
    role TEXT NOT NULL,
    contact_id TEXT NOT NULL,
    PRIMARY KEY (family_circle_id, role),
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id),
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS ice_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL UNIQUE,
    profile_name TEXT,
    profile_dob TEXT,
    photo_path TEXT,
    medical_conditions TEXT,
    medical_dnr INTEGER DEFAULT 0,
    dnr_document_path TEXT,
    emergency_proxy_name TEXT,
    medical_proxy_phone TEXT,
    poa_name TEXT,
    poa_phone TEXT,
    notes TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_by TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY,
    family_circle_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    start_time TEXT,
    end_time TEXT,
    location TEXT,
    driver_name TEXT,
    driver_contact_id TEXT,
    pickup_time TEXT,
    leave_time TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS named_places (
    location_id TEXT PRIMARY KEY,
    family_circle_id TEXT NOT NULL,
    location_name TEXT,
    gps_latitude REAL,
    gps_longitude REAL,
    radius_metres INTEGER DEFAULT 150,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS location_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    location_name TEXT,
    notes TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- For future APNS (iOS) and FCM (Android) push
CREATE TABLE IF NOT EXISTS user_push_tokens (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('ios','android')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS call_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    from_user_id TEXT NOT NULL,
    to_user_id TEXT NOT NULL,
    from_display_name TEXT,
    status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'acknowledged')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id),
    FOREIGN KEY (from_user_id) REFERENCES users(id),
    FOREIGN KEY (to_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS kiosk_emergency_alerts (
    family_circle_id TEXT PRIMARY KEY,
    activated INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

