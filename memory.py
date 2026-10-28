import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _database_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        return Path(local_app_data) / "LARVA" / "memory.db"
    return Path.home() / ".larva" / "memory.db"


def _connect() -> sqlite3.Connection:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _database_connection() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    """Create the memory database and table if they do not already exist."""
    with _database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL COLLATE NOCASE UNIQUE,
                category TEXT NOT NULL DEFAULT 'general',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_memory(content: str, category: str = "general") -> int:
    """Save a memory, returning its ID or the ID of an existing duplicate."""
    if not isinstance(content, str):
        raise TypeError("content must be a string.")
    content = content.strip()
    if not content:
        raise ValueError("content must not be empty.")

    if not isinstance(category, str):
        raise TypeError("category must be a string.")
    category = category.strip()
    if not category:
        raise ValueError("category must not be empty.")

    init_db()
    with _database_connection() as connection:
        connection.execute(
            """
            INSERT INTO memories (content, category)
            VALUES (?, ?)
            ON CONFLICT(content) DO NOTHING
            """,
            (content, category),
        )
        row = connection.execute(
            "SELECT id FROM memories WHERE content = ? COLLATE NOCASE",
            (content,),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError(
                "Memory insert completed but the saved row could not be found."
            )
        return int(row["id"])


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer.")
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")


def _memory_rows(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT id, content, category, created_at
        FROM memories
        WHERE content LIKE ? COLLATE NOCASE
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (f"%{query}%", limit),
    )
    return [dict(row) for row in rows]


def search_memories(
    query: str = "",
    limit: int = 5,
) -> list[dict[str, object]]:
    """Search memory text with LIKE, or list recent memories for a blank query."""
    if not isinstance(query, str):
        raise TypeError("query must be a string.")
    _validate_limit(limit)

    init_db()
    with _database_connection() as connection:
        return _memory_rows(connection, query.strip(), limit)


def list_memories(limit: int = 100) -> list[dict[str, object]]:
    """Return the most recently created memories."""
    _validate_limit(limit)
    init_db()
    with _database_connection() as connection:
        return _memory_rows(connection, "", limit)


def delete_memory(memory_id: int) -> bool:
    """Delete one memory and report whether it existed."""
    if isinstance(memory_id, bool) or not isinstance(memory_id, int):
        raise TypeError("memory_id must be an integer.")
    if memory_id <= 0:
        raise ValueError("memory_id must be greater than zero.")

    init_db()
    with _database_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,),
        )
        return cursor.rowcount > 0
