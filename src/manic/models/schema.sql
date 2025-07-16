-- Compounds -------------------------------------------------------
CREATE TABLE IF NOT EXISTS compounds (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_name TEXT NOT NULL UNIQUE,
    retention_time REAL,
    loffset       REAL DEFAULT 0,
    roffset       REAL DEFAULT 0,
    mass0         REAL,
    label_atoms   INTEGER DEFAULT 0,
    deleted       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_compounds_name
          ON compounds(compound_name);

-- Samples ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS samples (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_name  TEXT NOT NULL UNIQUE,
    file_name    TEXT,
    deleted      INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_samples_name
          ON samples(sample_name);

-- EICs ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eic (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_name    TEXT NOT NULL,
    compound_name  TEXT NOT NULL,
    x_axis         BLOB,   -- pickled list/array of time points
    y_axis         BLOB,   -- pickled list/array of intensities
    rt_window      REAL,
    corrected      INTEGER DEFAULT 0,
    deleted        INTEGER DEFAULT 0,
    spectrum_pos   INTEGER,
    chromat_pos    INTEGER,
    FOREIGN KEY (sample_name)   REFERENCES samples(sample_name),
    FOREIGN KEY (compound_name) REFERENCES compounds(compound_name)
);

-- Session activity -----------------------------------------------
CREATE TABLE IF NOT EXISTS session_activity (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_name  TEXT NOT NULL,
    sample_name    TEXT NOT NULL,
    mass0          REAL,
    loffset        REAL,
    roffset        REAL,
    sample_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (compound_name) REFERENCES compounds(compound_name),
    FOREIGN KEY (sample_name)   REFERENCES samples(sample_name)
);
