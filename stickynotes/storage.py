# stickynotes/storage.py
"""
SQLite database storage layer for Sticky Notes.

Replaces the legacy INI (QSettings) backend for note persistence.
Provides:
- ACID transactional integrity and crash resistance using WAL mode.
- Fast individual note reads/writes (updating one note does not rewrite all others).
- Seamless, zero-data-loss migration from legacy QSettings on upgrade.
- Binary BLOB support for window geometry.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import QByteArray, QSettings, QStandardPaths
from . import config

_db_instance: Optional[NoteDatabase] = None


def get_default_db_path() -> Path:
    """Return the default SQLite database path according to XDG data standards."""
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if not data_dir:
        # Fallback to config location or home directory
        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        data_dir = config_dir or os.path.expanduser("~/.local/share/stickynotes")

    dir_path = Path(data_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / "notes.db"


class NoteDatabase:
    """Manages persistent SQLite storage for Sticky Notes."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            self.db_path = get_default_db_path()
        else:
            self.db_path = Path(db_path)
            if self.db_path.parent != Path("."):
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Initialize database tables and optimizations."""
        with self._conn:
            # Enable Write-Ahead Logging (WAL) for concurrency and durability
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL DEFAULT '',
                    geometry BLOB,
                    theme TEXT NOT NULL DEFAULT 'yellow',
                    collapsed INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    last_edited TEXT,
                    pinned INTEGER NOT NULL DEFAULT 0
                );
            """)

    def save_note(
        self,
        note_id: str,
        content: str = "",
        geometry: Any = None,
        theme: str = config.DEFAULT_THEME,
        collapsed: bool = False,
        title: Optional[str] = None,
        last_edited: Optional[str] = None,
        pinned: bool = False,
    ):
        """Insert or update a note record."""
        # Convert QByteArray or bytearray to bytes for BLOB storage
        geo_blob: Optional[bytes] = None
        if isinstance(geometry, QByteArray):
            geo_blob = bytes(geometry.data())
        elif isinstance(geometry, (bytes, bytearray)):
            geo_blob = bytes(geometry)

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO notes (id, content, geometry, theme, collapsed, title, last_edited, pinned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content = excluded.content,
                    geometry = excluded.geometry,
                    theme = excluded.theme,
                    collapsed = excluded.collapsed,
                    title = excluded.title,
                    last_edited = excluded.last_edited,
                    pinned = excluded.pinned;
                """,
                (
                    note_id,
                    content,
                    geo_blob,
                    theme,
                    1 if collapsed else 0,
                    title,
                    last_edited,
                    1 if pinned else 0,
                ),
            )

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """Retrieve all notes ordered by last_edited descending."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT id, content, geometry, theme, collapsed, title, last_edited, pinned
            FROM notes
            ORDER BY CASE WHEN last_edited IS NULL THEN 1 ELSE 0 END, last_edited DESC
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "content": row[1] or "",
                "geometry": row[2],  # bytes or None
                "theme": row[3] or config.DEFAULT_THEME,
                "collapsed": bool(row[4]),
                "title": row[5],
                "last_edited": row[6],
                "pinned": bool(row[7]),
            })
        return results

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single note by ID."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT id, content, geometry, theme, collapsed, title, last_edited, pinned
            FROM notes WHERE id = ?
        """, (note_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "content": row[1] or "",
            "geometry": row[2],
            "theme": row[3] or config.DEFAULT_THEME,
            "collapsed": bool(row[4]),
            "title": row[5],
            "last_edited": row[6],
            "pinned": bool(row[7]),
        }

    def delete_note(self, note_id: str):
        """Delete a note by ID."""
        with self._conn:
            self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def count_notes(self) -> int:
        """Return total count of notes."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT count(*) FROM notes")
        return cursor.fetchone()[0]

    def migrate_from_qsettings(self, settings: QSettings) -> int:
        """Seamlessly migrate notes from legacy QSettings into SQLite.

        Runs only if SQLite database is currently empty and legacy notes exist.
        Returns the number of notes migrated.
        """
        if self.count_notes() > 0:
            return 0

        settings.beginGroup("notes")
        note_ids = settings.childGroups()
        if not note_ids:
            settings.endGroup()
            return 0

        migrated_count = 0
        for nid in note_ids:
            content = settings.value(f"{nid}/content", "")
            theme = settings.value(f"{nid}/theme", config.DEFAULT_THEME)
            collapsed = settings.value(f"{nid}/collapsed", False, type=bool)
            pinned = settings.value(f"{nid}/pinned", False, type=bool)
            title = settings.value(f"{nid}/title", None)
            last_edited = settings.value(f"{nid}/last_edited", None)
            geometry = settings.value(f"{nid}/geometry", None)

            self.save_note(
                note_id=nid,
                content=content,
                geometry=geometry,
                theme=theme,
                collapsed=collapsed,
                title=title,
                last_edited=last_edited,
                pinned=pinned,
            )
            migrated_count += 1

        settings.endGroup()
        if migrated_count > 0:
            print(f"✓ Migrated {migrated_count} notes from QSettings into SQLite database ({self.db_path})")
            settings.setValue("notes_migrated_to_sqlite", True)

        return migrated_count

    def close(self):
        """Close database connection."""
        self._conn.close()


def get_db(db_path: str | Path | None = None) -> NoteDatabase:
    """Return global singleton database instance."""
    global _db_instance
    if _db_instance is None or db_path is not None:
        _db_instance = NoteDatabase(db_path)
    return _db_instance


def set_db(db: Optional[NoteDatabase]):
    """Override singleton database (primarily used for unit testing)."""
    global _db_instance
    _db_instance = db
