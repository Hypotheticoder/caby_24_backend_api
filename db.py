"""Compatibility layer.

Some routes/snippets expect `db.get_db` and `db.Base`. This project uses
`database.py`, so this file re-exports the same primitives.
"""

from database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
