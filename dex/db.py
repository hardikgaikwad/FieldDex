import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config
from .config import DB_PATH

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT UNIQUE NOT NULL,
    taken_at TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',   -- queued | identified | done | rejected | error
    vision TEXT,                             -- vision model JSON
    result TEXT,                             -- what the reveal screen shows
    seen INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    rarity TEXT NOT NULL,
    stars INTEGER NOT NULL DEFAULT 1,
    flavour TEXT,
    stats TEXT,
    photo_id INTEGER NOT NULL,             -- best photo so far (card art)
    first_photo_id INTEGER NOT NULL,       -- the photo that discovered it; hidden until revealed
    first_found TEXT NOT NULL,
    last_found TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS xp_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    xp INTEGER NOT NULL,
    reason TEXT NOT NULL,
    photo_id INTEGER
);
CREATE TABLE IF NOT EXISTS chapters (
    n INTEGER PRIMARY KEY,
    day TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    summary TEXT NOT NULL,
    seen INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wanted (
    day TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    hint TEXT,
    photo_id INTEGER
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now_iso() -> str:
    return config.now().isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Autocommit: every statement commits on its own, so a failed INSERT (duplicate photo)
    # can never leave a write transaction open and lock out the worker thread.
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --- photos -----------------------------------------------------------------

def add_photo(conn, sha256: str, taken_at: str) -> int | None:
    """Returns the new id, or None if this exact photo was uploaded before."""
    try:
        cur = conn.execute("INSERT INTO photos (sha256, taken_at, uploaded_at) VALUES (?, ?, ?)",
                           (sha256, taken_at, now_iso()))
    except sqlite3.IntegrityError:
        return None
    conn.commit()
    return cur.lastrowid


def photos_with_status(conn, status: str) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM photos WHERE status = ? ORDER BY id", (status,))]


def set_photo(conn, photo_id: int, **fields) -> None:
    for key in ("vision", "result"):
        if key in fields and not isinstance(fields[key], str):
            fields[key] = json.dumps(fields[key])
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE photos SET {cols} WHERE id = ?", (*fields.values(), photo_id))
    conn.commit()


def unseen_results(conn) -> list[dict]:
    rows = conn.execute("SELECT id, result FROM photos WHERE seen = 0 AND status IN ('done', 'rejected', 'error') ORDER BY id")
    return [{"photo_id": r["id"], **json.loads(r["result"] or "{}")} for r in rows]


def mark_seen(conn, ids: list[int]) -> None:
    conn.executemany("UPDATE photos SET seen = 1 WHERE id = ?", [(i,) for i in ids])
    conn.commit()


def queue_size(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM photos WHERE status IN ('queued', 'identified')").fetchone()[0]


# --- cards ------------------------------------------------------------------

def get_card(conn, species_key: str) -> dict | None:
    row = conn.execute("SELECT * FROM cards WHERE species_key = ?", (species_key,)).fetchone()
    return _card(row) if row else None


def insert_card(conn, card: dict) -> None:
    conn.execute(
        "INSERT INTO cards (species_key, name, kind, rarity, stars, flavour, stats, photo_id, first_photo_id, first_found, last_found) "
        "VALUES (:species_key, :name, :kind, :rarity, 1, :flavour, :stats, :photo_id, :photo_id, :found, :found)",
        {**card, "stats": json.dumps(card["stats"])},
    )
    conn.commit()


def upgrade_card(conn, species_key: str, rarity: str, stars: int, photo_id: int | None, found: str) -> None:
    if photo_id is None:
        conn.execute("UPDATE cards SET rarity = ?, stars = ?, last_found = ? WHERE species_key = ?",
                     (rarity, stars, found, species_key))
    else:
        conn.execute("UPDATE cards SET rarity = ?, stars = ?, photo_id = ?, last_found = ? WHERE species_key = ?",
                     (rarity, stars, photo_id, found, species_key))
    conn.commit()


def all_cards(conn) -> list[dict]:
    return [_card(r) for r in conn.execute("SELECT * FROM cards ORDER BY first_found DESC")]


def revealed_cards(conn) -> list[dict]:
    """Cards the player has actually flipped. Unopened finds stay a surprise."""
    rows = conn.execute("SELECT c.* FROM cards c JOIN photos p ON p.id = c.first_photo_id "
                        "WHERE p.seen = 1 ORDER BY c.first_found DESC")
    return [_card(r) for r in rows]


def _card(row) -> dict:
    d = dict(row)
    d["stats"] = json.loads(d["stats"] or "{}")
    return d


# --- player -----------------------------------------------------------------

def add_xp(conn, xp: int, reason: str, photo_id: int | None = None) -> None:
    conn.execute("INSERT INTO xp_log (at, xp, reason, photo_id) VALUES (?, ?, ?, ?)", (now_iso(), xp, reason, photo_id))
    conn.commit()


def total_xp(conn) -> int:
    return conn.execute("SELECT COALESCE(SUM(xp), 0) FROM xp_log").fetchone()[0]


def revealed_xp(conn) -> int:
    """XP the player has collected on the reveal screen (what the HUD shows)."""
    return conn.execute("SELECT COALESCE(SUM(x.xp), 0) FROM xp_log x LEFT JOIN photos p ON p.id = x.photo_id "
                        "WHERE x.photo_id IS NULL OR p.seen = 1").fetchone()[0]


def days_out(conn, since: date | None = None) -> list[str]:
    q = "SELECT DISTINCT substr(taken_at, 1, 10) d FROM photos WHERE status = 'done'"
    args = ()
    if since:
        q += " AND taken_at >= ?"
        args = (since.isoformat(),)
    return [r["d"] for r in conn.execute(q + " ORDER BY d", args)]


def player_stats(conn) -> dict:
    """The numbers that badges and unlocks are judged on."""
    from .game import level_for_xp

    kinds = {r["kind"]: r["n"] for r in conn.execute("SELECT kind, COUNT(*) n FROM cards GROUP BY kind")}
    legend = conn.execute("SELECT COUNT(*) FROM cards WHERE rarity = 'legendary'").fetchone()[0]
    return {"level": level_for_xp(total_xp(conn))["level"], "kinds": kinds,
            "days_out": len(days_out(conn)), "legendaries": legend}


def last_30_days(conn, today: date) -> list[dict]:
    out = set(days_out(conn, today - timedelta(days=29)))
    return [{"day": d.isoformat(), "out": d.isoformat() in out}
            for d in (today - timedelta(days=i) for i in range(29, -1, -1))]


# --- story, wanted, settings --------------------------------------------------

def chapters(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM chapters ORDER BY n")]


def add_chapter(conn, day: str, title: str, text: str, summary: str) -> None:
    n = conn.execute("SELECT COALESCE(MAX(n), 0) + 1 FROM chapters").fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO chapters (n, day, title, text, summary) VALUES (?, ?, ?, ?, ?)",
                 (n, day, title, text, summary))
    conn.commit()


def get_wanted(conn, day: str) -> dict | None:
    row = conn.execute("SELECT * FROM wanted WHERE day = ?", (day,)).fetchone()
    return dict(row) if row else None


def set_wanted(conn, day: str, target: str, hint: str) -> None:
    conn.execute("INSERT OR IGNORE INTO wanted (day, target, hint) VALUES (?, ?, ?)", (day, target, hint))
    conn.commit()


def fulfil_wanted(conn, day: str, photo_id: int) -> None:
    conn.execute("UPDATE wanted SET photo_id = ? WHERE day = ? AND photo_id IS NULL", (photo_id, day))
    conn.commit()


def get_setting(conn, key: str, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(conn, key: str, value) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, json.dumps(value)))
    conn.commit()
