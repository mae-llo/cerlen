-- Reminder bookkeeping, poll votes, and who Cerlen has already welcomed.

CREATE TABLE reminder_log (
    club_read_id INTEGER NOT NULL REFERENCES club_reads (id) ON DELETE CASCADE,
    days_before  INTEGER NOT NULL,
    sent_at      TEXT NOT NULL,
    PRIMARY KEY (club_read_id, days_before)
);

CREATE TABLE poll_votes (
    poll_id INTEGER NOT NULL REFERENCES polls (id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL REFERENCES books (id),
    PRIMARY KEY (poll_id, user_id)
);

CREATE TABLE seen_users (
    user_id    INTEGER PRIMARY KEY,
    first_seen TEXT NOT NULL
);
