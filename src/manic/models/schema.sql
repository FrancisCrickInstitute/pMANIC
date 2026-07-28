-- Compounds -------------------------------------------------------
CREATE TABLE IF NOT EXISTS compounds (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_name TEXT NOT NULL UNIQUE,
    retention_time REAL,
    loffset       REAL DEFAULT 0,
    roffset       REAL DEFAULT 0,
    mass0         REAL,
    label_atoms   INTEGER DEFAULT 0,
    formula       TEXT,  -- Molecular formula for natural abundance correction
    label_type    TEXT DEFAULT 'C',  -- Element being labeled (C, N, etc.)
    tbdms         INTEGER DEFAULT 0,  -- Number of TBDMS derivatizations
    meox          INTEGER DEFAULT 0,  -- Number of MeOX derivatizations
    me            INTEGER DEFAULT 0,  -- Number of methylations
    amount_in_std_mix REAL,  -- Known concentration in standard mixture (for MRRF calculation)
    int_std_amount REAL,     -- Amount of internal standard added to each sample
    mm_files      TEXT,      -- Comma-separated list of MM file patterns (e.g., "*_MM_01*,*_MM_02*")
    baseline_correction INTEGER DEFAULT 1,  -- Enable linear baseline subtraction for this compound
    deconvolution_level TEXT DEFAULT '4',   -- Per-compound chromatographic deconvolution level ('off', '1'-'7')
    deconvolution_fit_type TEXT DEFAULT 'auto',  -- Per-compound peak-shape fit type ('auto','gaussian','bi_gaussian','emg')
    deconvolution_noise_gate TEXT DEFAULT 'balanced',  -- Per-compound noise gate ('off','lenient','balanced','aggressive')
    deleted       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_compounds_name
          ON compounds(compound_name);

-- Explicit diagnostic ions for unlabelled targeted analysis. Labelled
-- compounds continue to derive M+0...M+n from mass0 and label_atoms.
CREATE TABLE IF NOT EXISTS compound_ions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_name  TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('quantifier', 'qualifier')),
    ordinal        INTEGER NOT NULL DEFAULT 0,
    mz             REAL NOT NULL CHECK (mz > 0),
    expected_ratio REAL,
    ratio_tolerance REAL,
    FOREIGN KEY (compound_name) REFERENCES compounds(compound_name)
        ON DELETE CASCADE,
    UNIQUE(compound_name, role, ordinal),
    UNIQUE(compound_name, mz)
);

CREATE INDEX IF NOT EXISTS idx_compound_ions_compound
          ON compound_ions(compound_name, role, ordinal);

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
    retention_time REAL,
    loffset        REAL,
    roffset        REAL,
    sample_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (compound_name) REFERENCES compounds(compound_name),
    FOREIGN KEY (sample_name)   REFERENCES samples(sample_name),
    UNIQUE(compound_name, sample_name)
);

-- Corrected EIC data ---------------------------------------------
CREATE TABLE IF NOT EXISTS eic_corrected (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_name    TEXT NOT NULL,
    compound_name  TEXT NOT NULL,
    x_axis         BLOB,   -- Same time points as raw EIC
    y_axis_corrected BLOB, -- Natural abundance corrected intensities
    correction_applied INTEGER DEFAULT 1,  -- Flag if correction was successful
    timestamp      REAL,   -- When correction was performed
    deleted        INTEGER DEFAULT 0,
    FOREIGN KEY (sample_name)   REFERENCES samples(sample_name),
    FOREIGN KEY (compound_name) REFERENCES compounds(compound_name),
    UNIQUE(sample_name, compound_name)
);

CREATE INDEX IF NOT EXISTS idx_eic_corrected_sample_compound
          ON eic_corrected(sample_name, compound_name);
