-- # vaulture/vaulture/src/infrastructure/database/migrations/001_users_table.sql
-- users TABLE
CREATE TABLE IF NOT EXISTS users(
    user_id                BLOB CHECK (length(user_id) = 16) PRIMARY KEY,        -- 16-byte UUID binary
    username               TEXT COLLATE NOCASE UNIQUE NOT NULL,
    hashed_master_password TEXT NOT NULL,           
    rec_email              TEXT CHECK (length(rec_email) <= 254) NOT NULL,
    rec_mobile_number      TEXT CHECK (rec_mobile_number GLOB '+[0-9]*' AND length(rec_mobile_number) BETWEEN 7 AND 20) NOT NULL,
    created_at             TEXT NOT NULL
) WITHOUT ROWID