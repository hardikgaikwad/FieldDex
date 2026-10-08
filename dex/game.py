"""Game rules: rarity, XP, levels, unlocks. Pure functions, no AI, no I/O."""
import random
import re

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

# How hard each kind usually is to photograph well.
KIND_BASE = {"plant": 0.0, "tree": 0.0, "insect": 1.0, "animal": 1.0, "fungus": 1.5, "bird": 2.0, "other": 0.0}

# Score thresholds for each tier after the common one.
TIER_CUTS = [2.5, 4.0, 5.5, 7.5]
NEW_SPECIES_BONUS = 1.5

RARITY_XP = {"common": 10, "uncommon": 20, "rare": 40, "epic": 80, "legendary": 160}
NEW_SPECIES_XP = 25
DUPLICATE_XP = 5
ATTEMPT_XP = 2
WANTED_XP = 50
MAX_STARS = 5


def species_key(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip().lower()


def roll_rarity(kind: str, is_new: bool, quality: int, golden_hour: bool, seed: str) -> tuple[str, float]:
    """Return (tier, score). The seeded roll is the surprise; the rest rewards effort."""
    rng = random.Random(seed)
    score = KIND_BASE.get(kind, 0.0)
    score += NEW_SPECIES_BONUS if is_new else 0.0
    score += (max(1, min(5, quality)) - 3) * 0.5
    score += 1.0 if golden_hour else 0.0
    score += (rng.random() ** 2) * 4.5  # skewed low, so high rolls feel special
    tier = sum(score >= cut for cut in TIER_CUTS)
    return RARITIES[tier], round(score, 2)


def better(a: str, b: str) -> str:
    return max(a, b, key=RARITIES.index)


def xp_for_find(rarity: str, is_new: bool, wanted: bool) -> int:
    xp = RARITY_XP[rarity] + (NEW_SPECIES_XP if is_new else DUPLICATE_XP)
    return xp + (WANTED_XP if wanted else 0)


def xp_to_next(level: int) -> int:
    """XP needed to go from `level` to `level + 1`."""
    return int(60 * level ** 1.4)


def level_for_xp(total_xp: int) -> dict:
    level, remaining = 1, total_xp
    while remaining >= xp_to_next(level):
        remaining -= xp_to_next(level)
        level += 1
    return {"level": level, "into": remaining, "needed": xp_to_next(level)}


# Each unlock is a badge plus a cosmetic for the avatar.
UNLOCKS = [
    {"id": "camera", "name": "Shutterbug", "desc": "Reach level 3", "test": lambda s: s["level"] >= 3},
    {"id": "binoculars", "name": "Birdwatcher", "desc": "Collect 5 bird species", "test": lambda s: s["kinds"].get("bird", 0) >= 5},
    {"id": "leaf_crown", "name": "Green Thumb", "desc": "Collect 10 plants or trees",
     "test": lambda s: s["kinds"].get("plant", 0) + s["kinds"].get("tree", 0) >= 10},
    {"id": "bug_net", "name": "Bug Hunter", "desc": "Collect 3 insect species", "test": lambda s: s["kinds"].get("insect", 0) >= 3},
    {"id": "explorer_hat", "name": "Explorer", "desc": "Go outside on 7 different days", "test": lambda s: s["days_out"] >= 7},
    {"id": "cape", "name": "Legend", "desc": "Find a Legendary", "test": lambda s: s["legendaries"] >= 1},
]


def unlocked(stats: dict) -> list[str]:
    return [u["id"] for u in UNLOCKS if u["test"](stats)]


def new_unlocks(before: dict, after: dict) -> list[dict]:
    gained = set(unlocked(after)) - set(unlocked(before))
    return [{k: u[k] for k in ("id", "name", "desc")} for u in UNLOCKS if u["id"] in gained]
