"""The pipeline: photo in -> identified -> rarity rolled -> card, XP, unlocks -> story chapter.

All vision calls for a batch run before any text calls, so Ollama swaps models once
instead of once per photo on a 4GB GPU.
"""
import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun

from . import config, db, game, imaging, vision, writer
from .config import PHOTO_DIR

MAX_PHOTO_AGE_DAYS = 7
GOLDEN_MINUTES = 75


def region(profile: dict) -> str:
    return f"{profile['home']['city']}, India" if profile.get("timezone") == "Asia/Kolkata" else profile["home"]["city"]


def photo_paths(photo_id: int):
    return PHOTO_DIR / f"{photo_id}.jpg", PHOTO_DIR / f"{photo_id}_px.png"


def ingest(conn, data: bytes) -> int | None:
    """Store an uploaded photo and queue it. Returns None for an exact duplicate."""
    img, taken = imaging.open_image(data)
    photo_id = db.add_photo(conn, imaging.sha256(data), taken or db.now_iso())
    if photo_id is not None:
        view, pixel = photo_paths(photo_id)
        imaging.save_view(img, view)
        imaging.save_pixel_art(img, pixel)
    return photo_id


def is_golden_hour(profile: dict, taken_at: str) -> bool:
    tz = ZoneInfo(profile.get("timezone", "UTC"))
    when = datetime.fromisoformat(taken_at).replace(tzinfo=tz)
    home = profile["home"]
    s = sun(LocationInfo("", "", tz.key, home["lat"], home["lon"]).observer, date=when.date(), tzinfo=tz)
    window = timedelta(minutes=GOLDEN_MINUTES)
    return any(abs(when - s[k]) <= window for k in ("sunrise", "sunset"))


def ensure_wanted(conn, profile: dict, day: date) -> dict:
    existing = db.get_wanted(conn, day.isoformat())
    if existing:
        return existing
    poster = writer.wanted_poster(profile["models"]["text"], region(profile), day.strftime("%B"),
                                  [c["name"] for c in db.all_cards(conn)], seed=day.isoformat())
    db.set_wanted(conn, day.isoformat(), poster["target"], poster["hint"])
    return db.get_wanted(conn, day.isoformat())


def _identify_all(conn, profile: dict, wanted: dict) -> None:
    for photo in db.photos_with_status(conn, "queued"):
        try:
            view, _ = photo_paths(photo["id"])
            img, _ = imaging.open_image(view.read_bytes())
            target = None if wanted["photo_id"] else wanted["target"]
            result = vision.identify(imaging.vision_bytes(img), profile["models"]["vision"], region(profile), target)
            db.set_photo(conn, photo["id"], status="identified", vision=result)
        except Exception as e:  # keep the queue moving; show the failure on the reveal screen
            db.set_photo(conn, photo["id"], status="error", result={"outcome": "error", "reason": str(e)[:200]})


def _reject(conn, photo: dict, reason: str) -> None:
    db.add_xp(conn, game.ATTEMPT_XP, "attempt", photo["id"])
    db.set_photo(conn, photo["id"], status="rejected",
                 result={"outcome": "rejected", "reason": reason, "xp": game.ATTEMPT_XP})


def _resolve(conn, profile: dict, photo: dict, v: dict, wanted: dict, today: date) -> dict | None:

    taken = datetime.fromisoformat(photo["taken_at"])
    if (config.now() - taken).days > MAX_PHOTO_AGE_DAYS:
        _reject(conn, photo, "That one's from the archive. Fresh finds only: go make a new memory!")
        return None
    if v["is_photo_of_screen"]:
        _reject(conn, photo, "Nice try. That's a screen! Real world only.")
        return None
    if not v["is_living_thing"]:
        _reject(conn, photo, "No living thing spotted. Get closer to a plant, bird or bug.")
        return None

    before = db.player_stats(conn)
    level_before = game.level_for_xp(db.total_xp(conn))
    key = game.species_key(v["common_name"])
    existing = db.get_card(conn, key)
    rolled, score = game.roll_rarity(v["kind"], existing is None, v["photo_quality"],
                                     is_golden_hour(profile, photo["taken_at"]), seed=photo["sha256"])
    rolled = os.environ.get("DEX_FORCE_RARITY", rolled)  # for testing the big reveal effects

    is_wanted = v["matches_wanted"] and not wanted["photo_id"]
    if is_wanted:
        db.fulfil_wanted(conn, wanted["day"], photo["id"])
        wanted["photo_id"] = photo["id"]

    if existing is None:
        text = writer.card_text(profile["models"]["text"], v["common_name"], v["kind"], rolled, v["features"])
        db.insert_card(conn, {"species_key": key, "name": v["common_name"].strip().title(), "kind": v["kind"],
                              "rarity": rolled, "flavour": text["flavour"], "stats": text["stats"],
                              "photo_id": photo["id"], "found": photo["taken_at"]})
    else:
        upgraded = game.RARITIES.index(rolled) > game.RARITIES.index(existing["rarity"])
        db.upgrade_card(conn, key, game.better(existing["rarity"], rolled),
                        min(game.MAX_STARS, existing["stars"] + 1), photo["id"] if upgraded else None, photo["taken_at"])

    xp = game.xp_for_find(rolled, existing is None, is_wanted)
    db.add_xp(conn, xp, "find", photo["id"])
    result = {
        "outcome": "new" if existing is None else "duplicate",
        "rolled": rolled,
        "score": score,
        "xp": xp,
        "wanted": is_wanted,
        "card": db.get_card(conn, key),
        "identified": {k: v[k] for k in ("confidence", "features", "photo_quality")},
        "level_before": level_before,
        "level_after": game.level_for_xp(db.total_xp(conn)),
        "unlocks": game.new_unlocks(before, db.player_stats(conn)),
    }
    db.set_photo(conn, photo["id"], status="done", result=json.dumps(result))
    return result


def _write_chapter(conn, profile: dict, day: date, finds: list[dict]) -> None:
    if any(c["day"] == day.isoformat() for c in db.chapters(conn)):
        return
    past = db.chapters(conn)
    chapter = writer.story_chapter(profile["models"]["text"], profile.get("name", "the hero"), region(profile),
                                   len(past) + 1, past[-1]["summary"] if past else "", finds)
    db.add_chapter(conn, day.isoformat(), chapter["title"], chapter["text"], chapter["summary"])


def run_queue(conn, profile: dict) -> int:
    """Process everything waiting. Returns how many photos were handled."""
    today = config.today()
    wanted = ensure_wanted(conn, profile, today)
    _identify_all(conn, profile, wanted)

    finds = []
    pending = db.photos_with_status(conn, "identified")
    for photo in pending:
        try:
            result = _resolve(conn, profile, photo, json.loads(photo["vision"]), wanted, today)
            if result:
                finds.append({"name": result["card"]["name"], "rarity": result["rolled"]})
        except Exception as e:
            db.set_photo(conn, photo["id"], status="error", result={"outcome": "error", "reason": str(e)[:200]})

    if finds:
        try:
            _write_chapter(conn, profile, today, finds)
        except Exception:
            pass  # the story can wait for the next batch
    return len(pending)


if __name__ == "__main__":
    import sys

    from .config import load_profile

    conn = db.connect()
    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            print(path, "->", ingest(conn, f.read()) or "duplicate")
    run_queue(conn, load_profile())
    for item in db.unseen_results(conn):
        card = item.get("card") or {}
        print(json.dumps({"photo": item["photo_id"], "outcome": item["outcome"], "rolled": item.get("rolled"),
                          "name": card.get("name"), "flavour": card.get("flavour"), "xp": item.get("xp"),
                          "reason": item.get("reason")}, ensure_ascii=False))
