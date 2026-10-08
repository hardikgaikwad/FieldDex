from dex import db


def _card(conn, photo_id, key):
    db.insert_card(conn, {"species_key": key, "name": key.title(), "kind": "bird", "rarity": "rare",
                          "flavour": "", "stats": {}, "photo_id": photo_id, "found": "2026-10-08T07:00:00"})


def test_unrevealed_finds_stay_hidden(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    seen = db.add_photo(conn, "a", "2026-10-08T07:00:00")
    hidden = db.add_photo(conn, "b", "2026-10-08T07:05:00")
    _card(conn, seen, "myna")
    _card(conn, hidden, "crow")
    db.add_xp(conn, 40, "find", seen)
    db.add_xp(conn, 80, "find", hidden)
    db.mark_seen(conn, [seen])

    assert [c["species_key"] for c in db.revealed_cards(conn)] == ["myna"]
    assert db.revealed_xp(conn) == 40
    assert db.total_xp(conn) == 120

    db.mark_seen(conn, [hidden])
    assert db.revealed_xp(conn) == 120


def test_duplicate_upload_is_ignored(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    assert db.add_photo(conn, "same", "2026-10-08T07:00:00") is not None
    assert db.add_photo(conn, "same", "2026-10-08T07:00:00") is None
    # The failed insert must not leave the database locked for another connection.
    other = db.connect(tmp_path / "t.db")
    other.execute("PRAGMA busy_timeout = 100")
    other.execute("UPDATE photos SET status = 'done'")
