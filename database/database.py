import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "newsdesk.db")

def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(reset=False):
    if reset and os.path.exists(DATABASE):
        os.remove(DATABASE)

    connection = get_connection()
    cursor = connection.cursor()

    # One row per story (one per real-world event).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            draft TEXT NOT NULL,
            final_text TEXT,
            status TEXT NOT NULL DEFAULT 'DRAFT',
                -- DRAFT -> IN_REVIEW -> PUBLISHED  (or MERGED, which points at merged_into_id)
            merged_into_id INTEGER,
            editor_note TEXT,
            created_at TEXT NOT NULL,
            submitted_at TEXT,
            published_at TEXT,
            FOREIGN KEY (merged_into_id) REFERENCES stories(id)
        )
    """)

    # Every raw incoming item that was grouped into a story.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS story_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            headline TEXT NOT NULL,
            content TEXT NOT NULL,
            received_at TEXT,
            added_after_publish INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (story_id) REFERENCES stories(id)
        )
    """)

    # Audit trail so the desk head can see what happened and when.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (story_id) REFERENCES stories(id)
        )
    """)

    connection.commit()
    connection.close()


def log_activity(connection, story_id, role, action, detail=""):
    from datetime import datetime
    connection.execute(
        """
        INSERT INTO activity_log (story_id, role, action, detail, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (story_id, role, action, detail, datetime.now().isoformat()),
    )