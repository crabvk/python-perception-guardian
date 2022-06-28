CREATE TABLE settings (
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (chat_id, name)
);
