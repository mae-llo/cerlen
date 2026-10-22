-- Ratings are whole quarter-stars: 4 (1 star) to 20 (5 stars).
-- Timestamps are UTC ISO text. Discord IDs are stored as INTEGER (64-bit safe).

CREATE TABLE guild_settings (
    guild_id                INTEGER PRIMARY KEY,
    admin_role_id           INTEGER,
    announcement_channel_id INTEGER,
    discussion_channel_id   INTEGER,
    reviews_channel_id      INTEGER,
    tag_book_of_the_month   TEXT NOT NULL DEFAULT 'Book of the Month',
    tag_other_reads         TEXT NOT NULL DEFAULT 'Other Reads',
    reminder_time           TEXT NOT NULL DEFAULT '09:00',
    reminder_timezone       TEXT NOT NULL DEFAULT 'America/New_York',
    reminder_days           TEXT NOT NULL DEFAULT '7,3,1,0'
);

CREATE TABLE books (
    id                INTEGER PRIMARY KEY,
    isbn13            TEXT UNIQUE,
    open_library_key  TEXT UNIQUE,
    google_id         TEXT,
    title             TEXT NOT NULL,
    authors           TEXT NOT NULL DEFAULT '',
    year              INTEGER,
    pages             INTEGER,
    subjects          TEXT NOT NULL DEFAULT '',
    cover_url         TEXT,
    blurb             TEXT,
    goodreads_rating  REAL,
    storygraph_rating REAL,
    fetched_at        TEXT NOT NULL
);
CREATE INDEX books_title_idx ON books (title COLLATE NOCASE);

CREATE TABLE club_reads (
    id                      INTEGER PRIMARY KEY,
    guild_id                INTEGER NOT NULL,
    book_id                 INTEGER NOT NULL REFERENCES books (id),
    kind                    TEXT NOT NULL CHECK (kind IN ('book_of_the_month', 'other_read')),
    status                  TEXT NOT NULL DEFAULT 'active'
                                 CHECK (status IN ('active', 'finished', 'cancelled')),
    started_at              TEXT NOT NULL,
    deadline                TEXT,
    finished_at             TEXT,
    discussion_post_id      INTEGER,
    announcement_message_id INTEGER,
    reminders_enabled       INTEGER NOT NULL DEFAULT 1,
    reminder_days           TEXT,
    last_reminder_sent      TEXT
);
CREATE INDEX club_reads_status_idx ON club_reads (guild_id, status);

CREATE TABLE queue_items (
    id       INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    book_id  INTEGER NOT NULL REFERENCES books (id),
    position INTEGER NOT NULL,
    added_by INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (guild_id, book_id)
);

CREATE TABLE polls (
    id             INTEGER PRIMARY KEY,
    guild_id       INTEGER NOT NULL,
    channel_id     INTEGER NOT NULL,
    message_id     INTEGER,
    closes_at      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    winner_book_id INTEGER REFERENCES books (id)
);

CREATE TABLE poll_options (
    poll_id INTEGER NOT NULL REFERENCES polls (id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books (id),
    PRIMARY KEY (poll_id, book_id)
);

-- One row per member per book. Club reads link in through club_read_id, so
-- progress and reviews are entered once whether or not the book is a club read.
CREATE TABLE readings (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    book_id      INTEGER NOT NULL REFERENCES books (id),
    club_read_id INTEGER REFERENCES club_reads (id),
    status       TEXT NOT NULL DEFAULT 'reading'
                      CHECK (status IN ('reading', 'finished', 'dnf', 'paused')),
    current_page INTEGER NOT NULL DEFAULT 0,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    UNIQUE (user_id, book_id)
);

CREATE TABLE log_entries (
    id         INTEGER PRIMARY KEY,
    reading_id INTEGER NOT NULL REFERENCES readings (id) ON DELETE CASCADE,
    page       INTEGER NOT NULL DEFAULT 0,
    text       TEXT NOT NULL,
    spoiler    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE reviews (
    id           INTEGER PRIMARY KEY,
    reading_id   INTEGER NOT NULL UNIQUE REFERENCES readings (id) ON DELETE CASCADE,
    rating_units INTEGER NOT NULL CHECK (rating_units BETWEEN 4 AND 20),
    comment      TEXT,
    spoiler      INTEGER NOT NULL DEFAULT 0,
    message_id   INTEGER,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE user_tbr (
    user_id  INTEGER NOT NULL,
    book_id  INTEGER NOT NULL REFERENCES books (id),
    position INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, book_id)
);

CREATE TABLE profiles (
    user_id        INTEGER PRIMARY KEY,
    goodreads      TEXT,
    storygraph     TEXT,
    favorite_genre TEXT
);

CREATE TABLE favorites (
    user_id INTEGER NOT NULL,
    slot    INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 5),
    book_id INTEGER NOT NULL REFERENCES books (id),
    PRIMARY KEY (user_id, slot),
    UNIQUE (user_id, book_id)
);
