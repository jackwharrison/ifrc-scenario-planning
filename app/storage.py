"""Stores trees, uploads and saved versions in SQLite.

On Azure App Service, put the database under /home (for example /home/data/app.db): that folder
is persistent storage that survives restarts and deployments. SQLite suits a small internal tool
on a single instance. See the README for moving to PostgreSQL if more people use it at once.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS trees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    tree_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tree_id INTEGER NOT NULL REFERENCES trees(id),
    filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    uploaded_by TEXT,
    content BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tree_id INTEGER NOT NULL REFERENCES trees(id),
    saved_at TEXT NOT NULL,
    saved_by TEXT,
    snapshot TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def db():
    if "db" not in g:
        path = current_app.config["DATABASE_PATH"]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(app):
    with app.app_context():
        db().executescript(SCHEMA)
        db().commit()
    app.teardown_appcontext(close_db)


def _tree(row):
    if row is None:
        return None
    t = dict(row)
    t["data"] = json.loads(t["data"] or "{}")
    return t


def create_tree(country, tree_type, user):
    """tree_type is always "risk" for now; the column is kept so older databases still work."""
    cur = db().execute("INSERT INTO trees (country, tree_type, created_at, created_by, updated_at, data) VALUES (?,?,?,?,?,?)",
                       (country, tree_type, now(), user, now(), "{}"))
    db().commit()
    return cur.lastrowid


def get_tree(tree_id):
    return _tree(db().execute("SELECT * FROM trees WHERE id = ?", (tree_id,)).fetchone())


def list_trees():
    return [_tree(r) for r in db().execute("SELECT * FROM trees ORDER BY updated_at DESC").fetchall()]


def save_data(tree_id, data):
    db().execute("UPDATE trees SET data = ?, updated_at = ? WHERE id = ?", (json.dumps(data), now(), tree_id))
    db().commit()


def add_upload(tree_id, filename, user, content):
    db().execute("INSERT INTO uploads (tree_id, filename, uploaded_at, uploaded_by, content) VALUES (?,?,?,?,?)",
                 (tree_id, filename, now(), user, content))
    db().commit()


def add_version(tree_id, user, snapshot):
    db().execute("INSERT INTO versions (tree_id, saved_at, saved_by, snapshot) VALUES (?,?,?,?)",
                 (tree_id, now(), user, json.dumps(snapshot)))
    db().commit()


def list_versions(tree_id):
    return [dict(r) for r in db().execute(
        "SELECT id, saved_at, saved_by FROM versions WHERE tree_id = ? ORDER BY id DESC", (tree_id,)).fetchall()]
