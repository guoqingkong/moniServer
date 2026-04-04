import sqlite3
from pathlib import Path

from app.config import Settings


def get_connection(settings: Settings) -> sqlite3.Connection:
    db_path = Path(settings.sqlite_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(settings: Settings) -> None:
    with get_connection(settings) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metric_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                metric_key TEXT NOT NULL,
                metric_label TEXT NOT NULL,
                unit TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL,
                period INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'tencent_monitor',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(resource_type, resource_id, metric_key, timestamp)
            );

            CREATE INDEX IF NOT EXISTS idx_metric_points_lookup
            ON metric_points(resource_type, resource_id, metric_key, timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_metric_points_timestamp
            ON metric_points(timestamp DESC);

            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                metric_key TEXT NOT NULL,
                metric_label TEXT NOT NULL,
                threshold_value REAL NOT NULL,
                current_value REAL NOT NULL,
                triggered_at TEXT NOT NULL,
                notify_email TEXT,
                notify_status TEXT NOT NULL DEFAULT 'pending',
                message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(resource_type, resource_id, metric_key, triggered_at)
            );

            CREATE INDEX IF NOT EXISTS idx_alert_events_triggered
            ON alert_events(triggered_at DESC);

            CREATE TABLE IF NOT EXISTS poll_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                points_written INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
