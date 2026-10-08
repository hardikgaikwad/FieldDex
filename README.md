# Field Dex

A pixel-art creature collecting game played in the real world. You photograph living things outside, then come home and **open them like a card pack**. A local open-weight vision model identifies each find. A rarity roll, XP, levels, gear for your pixel avatar, and a story that continues one chapter at a time are what bring you back the next day.

Everything runs on your own laptop through [Ollama](https://ollama.com). No accounts, no cloud, no API keys. Your photos never leave your devices.

## How a day works

1. **Outside:** use the normal iPhone Camera. No app, no laptop, no signal needed.
2. **Home:** the laptop is on your iPhone's Personal Hotspot. Open Field Dex in Safari, tap **Open today's pack**, and pick today's photos.
3. **On the laptop:**
   - `qwen2.5vl:3b` identifies each photo (about 6 s each on a 4GB RTX 3050).
   - The game rolls a rarity: harder subjects, first finds, sharp photos and golden-hour shots are luckier.
   - `qwen2.5:3b` writes the card's flavour text and the next story chapter.
4. **Reveal:** tap each face-down card to flip it, then collect XP, level up, and unlock gear.

What it rejects:
- Photos of screens.
- Photos with no living thing.
- Photos more than 7 days old.
- Photos you've already uploaded.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
ollama pull qwen2.5vl:3b
ollama pull qwen2.5:3b

.venv\Scripts\python -m uvicorn dex.server:app --host 0.0.0.0 --port 8765
```

The server prints the address to open on the iPhone. On iPhone hotspot it is usually `http://172.20.10.x:8765`. The first time, allow Python through Windows Firewall on private networks. In Safari, use **Share → Add to Home Screen** to get an app icon.

Other commands:
- Process photos from the terminal without the UI: `.venv\Scripts\python -m dex.process photo1.jpg photo2.jpg`
- Tests: `.venv\Scripts\python -m pytest`
- See the effects without real photos: open `/?debug=1` for fake Legendary, Rare and miss reveals and a level-up.
- Force a rarity during testing: set `DEX_FORCE_RARITY=legendary` before starting the server.

## Swap models

Edit `profile.yaml`. Any Ollama vision model works for `vision` (for example `gemma3:4b`), and any chat model works for `text`.

## Layout

| Path | What it does |
|---|---|
| `dex/game.py` | Rarity, XP, levels and unlocks. Pure functions, no AI. |
| `dex/vision.py` | Vision prompt plus a JSON schema; the name decides the category, because small models mislabel categories. |
| `dex/writer.py` | Card flavour text, the daily Wanted poster, and story chapters. |
| `dex/process.py` | The pipeline. A batch runs all vision calls before any text calls, so a 4GB GPU swaps models only once. |
| `dex/imaging.py` | HEIC/JPEG handling and the photo-to-pixel-art card art. |
| `dex/server.py` | FastAPI app and a single background worker. |
| `web/` | The game: plain HTML/CSS/JS. `sprites.js` draws the avatar from text grids; `sfx.js` synthesises 8-bit sounds. |

Fonts: Press Start 2P and Pixelify Sans, bundled locally under the SIL Open Font License (see `web/fonts/`).
