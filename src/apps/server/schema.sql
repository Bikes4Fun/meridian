-- Schema for Meridian


CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    photo_filename TEXT,
    family_circle_id TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS family_circles (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS user_family_circle (
    user_id TEXT NOT NULL,
    family_circle_id TEXT NOT NULL,
    PRIMARY KEY (user_id, family_circle_id),
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
    priority TEXT,
    photo_filename TEXT,
    notes TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS medication_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    time TEXT, must be in morning, noon, evening, bedtime, prn?
    display_name TEXT
);

CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    notes TEXT,
    max_daily INTEGER,
    current_quantity INTEGER,
    last_taken TEXT,
    taken_today TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS medication_to_time (
    medication_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (medication_id, group_id),
    FOREIGN KEY (medication_id) REFERENCES medications(id),
    FOREIGN KEY (group_id) REFERENCES medication_time(id)
);

CREATE TABLE IF NOT EXISTS allergies (
    family_circle_id TEXT NOT NULL,
    allergen TEXT NOT NULL,
    PRIMARY KEY (family_circle_id, allergen),
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);

CREATE TABLE IF NOT EXISTS conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    condition_name TEXT,
    diagnosis_date TEXT,
    notes TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
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

CREATE TABLE IF NOT EXISTS user_display_settings (
    user_id TEXT PRIMARY KEY,
    font_sizes TEXT,
    colors TEXT,
    spacing TEXT,
    touch_targets TEXT,
    window_width INTEGER,
    window_height INTEGER,
    window_left INTEGER,
    window_top INTEGER,
    clock_icon_size INTEGER,
    clock_icon_height INTEGER,
    clock_text_height INTEGER,
    clock_day_height INTEGER,
    clock_time_height INTEGER,
    clock_date_height INTEGER,
    clock_spacing INTEGER,
    clock_padding TEXT,
    main_padding TEXT,
    home_layout TEXT,
    clock_proportion REAL,
    todo_proportion REAL,
    med_events_split REAL,
    navigation_height INTEGER,
    button_flat_style INTEGER,
    clock_background_color TEXT,
    med_background_color TEXT,
    events_background_color TEXT,
    contacts_background_color TEXT,
    medical_background_color TEXT,
    calendar_background_color TEXT,
    nav_background_color TEXT,
    clock_orientation TEXT,
    med_orientation TEXT,
    events_orientation TEXT,
    bottom_section_orientation TEXT,
    high_contrast INTEGER,
    large_text INTEGER,
    reduced_motion INTEGER,
    navigation_buttons TEXT,
    borders TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
