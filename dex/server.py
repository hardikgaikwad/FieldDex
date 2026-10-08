"""Field Dex server. Run on the laptop, open it in Safari on the iPhone over the Personal Hotspot.

    python -m uvicorn dex.server:app --host 0.0.0.0 --port 8765
"""
import socket
import threading
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, game, process
from .config import PHOTO_DIR, WEB_DIR, load_profile

# How many of each kind make a "complete" page in the Dex. Empty slots show as silhouettes.
DEX_GOALS = {"bird": 30, "plant": 30, "tree": 20, "insect": 20, "animal": 15, "fungus": 10}

conn = db.connect()
wake = threading.Event()
worker_state = {"busy": False, "error": None}


def worker() -> None:
    """Single background worker: one GPU, one job at a time."""
    own = db.connect()
    while True:
        wake.wait(timeout=300)
        wake.clear()
        worker_state["busy"] = True
        try:
            profile = load_profile()
            process.ensure_wanted(own, profile, config.today())
            while db.queue_size(own):
                process.run_queue(own, profile)
            worker_state["error"] = None
        except Exception as e:
            traceback.print_exc()
            worker_state["error"] = str(e)[:200]
        finally:
            worker_state["busy"] = False


def lan_addresses(port: int) -> list[str]:
    try:
        ips = {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except socket.gaierror:
        ips = set()
    return [f"http://{ip}:{port}" for ip in sorted(ips) if not ip.startswith("127.")]


@asynccontextmanager
async def lifespan(_app):
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    wake.set()
    lines = ["", "  Field Dex is up. On your iPhone (same hotspot) open:"]
    lines += [f"    {url}" for url in lan_addresses(8765)] or ["    (no network found: join the iPhone hotspot)"]
    print("\n".join(lines) + "\n", flush=True)
    yield


app = FastAPI(title="Field Dex", lifespan=lifespan)


class Ids(BaseModel):
    ids: list[int]


@app.get("/api/state")
def state():
    today = config.today()
    stats = db.player_stats(conn)
    have = set(game.unlocked(stats))
    wanted = db.get_wanted(conn, today.isoformat())
    if wanted is None:
        wake.set()
    return {
        "name": load_profile().get("name", "Keeper"),
        "today": today.isoformat(),
        "debug": config.DEBUG,
        "player": {"xp": db.revealed_xp(conn), **game.level_for_xp(db.revealed_xp(conn))},
        "avatar": db.get_setting(conn, "avatar"),
        "unlocks": [{k: u[k] for k in ("id", "name", "desc")} | {"have": u["id"] in have} for u in game.UNLOCKS],
        "wanted": wanted,
        "days": db.last_30_days(conn, today),
        "species": len(db.revealed_cards(conn)),
        "days_out": stats["days_out"],
        "queue": db.queue_size(conn),
        "unseen": len(db.unseen_results(conn)),
        "new_chapter": any(not c["seen"] for c in db.chapters(conn)),
        "worker": worker_state,
    }


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    added = duplicates = failed = 0
    for f in files:
        try:
            if process.ingest(conn, await f.read()) is None:
                duplicates += 1
            else:
                added += 1
        except Exception:
            failed += 1
    wake.set()
    return {"added": added, "duplicates": duplicates, "failed": failed}


@app.get("/api/reveal")
def reveal():
    return {"queue": db.queue_size(conn), "busy": worker_state["busy"], "items": db.unseen_results(conn)}


@app.post("/api/reveal/seen")
def reveal_seen(body: Ids):
    db.mark_seen(conn, body.ids)
    return {"ok": True}


@app.get("/api/dex")
def dex():
    cards = db.revealed_cards(conn)
    counts = {k: sum(c["kind"] == k for c in cards) for k in DEX_GOALS}
    return {"cards": cards, "counts": counts, "goals": DEX_GOALS}


@app.get("/api/story")
def story():
    return {"chapters": db.chapters(conn)}


@app.post("/api/story/seen")
def story_seen():
    conn.execute("UPDATE chapters SET seen = 1")
    conn.commit()
    return {"ok": True}


@app.post("/api/debug/next-day")
def next_day():
    """Demo only: pretend a day has passed. Needs DEX_DEBUG=1 when starting the server."""
    if not config.DEBUG:
        raise HTTPException(404, "Start the server with DEX_DEBUG=1 to enable this.")
    config.advance_day()
    wake.set()  # writes tomorrow's Wanted poster in the background
    return {"today": config.today().isoformat()}


@app.post("/api/avatar")
def save_avatar(avatar: dict):
    db.set_setting(conn, "avatar", avatar)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/photos", StaticFiles(directory=PHOTO_DIR, check_dir=False), name="photos")
app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
