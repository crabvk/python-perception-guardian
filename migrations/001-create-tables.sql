CREATE TABLE settings (
    chat_id INTEGER NOT NULL,
    setting_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (chat_id, setting_id)
);
