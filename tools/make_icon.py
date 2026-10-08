"""Draws the 180x180 home-screen icon (iOS needs a PNG) from a pixel grid."""
from pathlib import Path

from PIL import Image

GRID = [
    "............",
    "........GG..",
    "......GGGG..",
    ".....GGGgG..",
    "....GGGgGG..",
    "...GGGgGGG..",
    "...GGgGGG...",
    "...GgGGG....",
    "...gGGG.....",
    "..g.........",
    ".g..........",
    "............",
]
COLOURS = {"G": (76, 194, 106), "g": (46, 125, 79)}
BG = (20, 18, 31)

cell = 15
img = Image.new("RGB", (len(GRID[0]) * cell, len(GRID) * cell), BG)
for y, row in enumerate(GRID):
    for x, ch in enumerate(row):
        if ch in COLOURS:
            img.paste(COLOURS[ch], (x * cell, y * cell, (x + 1) * cell, (y + 1) * cell))
out = Path(__file__).resolve().parent.parent / "web" / "icon-180.png"
img.save(out)
print("wrote", out, img.size)
