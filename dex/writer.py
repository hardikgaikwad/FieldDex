"""Everything the text model writes: card flavour, the daily Wanted poster, story chapters."""
import json
import random

import ollama

from .config import OLLAMA_OPTIONS


def _ask(model: str, prompt: str, schema: dict, temperature: float = 0.9) -> dict:
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}],
                           format=schema, options={**OLLAMA_OPTIONS, "temperature": temperature})
    return json.loads(response.message.content)


CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "flavour": {"type": "string"},
        "charm": {"type": "integer"},
        "stealth": {"type": "integer"},
        "grit": {"type": "integer"},
    },
    "required": ["flavour", "charm", "stealth", "grit"],
}


def card_text(model: str, name: str, kind: str, rarity: str, features: list[str]) -> dict:
    prompt = (
        f"Write the flavour text for a collectible card in a cosy pixel-art nature game.\n"
        f"Creature: {name} ({kind}), rarity: {rarity}. Seen details: {', '.join(features) or 'none'}.\n"
        "flavour: one witty sentence, under 22 words, about a real habit or trait of this creature, "
        "like a nature documentary narrator with a sense of humour. Do not mention stats, rarity or the game. "
        'Example for a house crow: "Remembers your face, your route, and that one time you didn\'t share."\n'
        "charm, stealth, grit: game stats from 1 to 99 that suit this creature."
    )
    try:
        out = _ask(model, prompt, CARD_SCHEMA)
    except Exception:
        out = {"flavour": f"A wild {name} appeared.", "charm": 50, "stealth": 50, "grit": 50}
    stats = {k: max(1, min(99, int(out.get(k, 50)))) for k in ("charm", "stealth", "grit")}
    return {"flavour": out["flavour"].strip(), "stats": stats}


WANTED_SCHEMA = {
    "type": "object",
    "properties": {"target": {"type": "string"}, "hint": {"type": "string"}},
    "required": ["target", "hint"],
}

# Used when the model is unavailable, and as examples of the right style.
FALLBACK_WANTED = [
    ("a bird with a long tail", "Look along wires and treetops in the early morning."),
    ("a leaf with jagged edges", "Check the hedges and the trees near a wall."),
    ("a flower with yellow petals", "Roadside weeds count too."),
    ("an insect on a flower", "Stand still near flowers in the sun for a minute."),
    ("a tree with peeling or patterned bark", "Get close; bark is a whole world."),
    ("a bird drinking or near water", "Puddles, tanks and lake edges."),
    ("a mushroom or fungus", "Shady, damp ground after rain."),
]


def wanted_poster(model: str, region: str, month: str, collected: list[str], seed: str) -> dict:
    examples = "; ".join(t for t, _ in FALLBACK_WANTED[:4])
    prompt = (
        f"You set the daily bounty in a nature collecting game. Player lives in {region}; it is {month}.\n"
        f"Already collected: {', '.join(collected[:30]) or 'nothing yet'}.\n"
        "target: ONE thing to photograph today in 3 to 8 words, described ONLY by what you can see "
        "(colour, shape, behaviour), never a species name. Common enough to find within 30 minutes in any "
        f"neighbourhood. Examples of the style: {examples}.\n"
        "hint: under 12 words on where or when to look, somewhere ordinary (a lane, a wall, a park, a rooftop)."
    )
    try:
        out = _ask(model, prompt, WANTED_SCHEMA)
        if 3 <= len(out["target"]) <= 60:
            return {"target": out["target"].strip().rstrip("."), "hint": out["hint"].strip()}
    except Exception:
        pass
    target, hint = random.Random(seed).choice(FALLBACK_WANTED)
    return {"target": target, "hint": hint}


CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "text": {"type": "string"}, "summary": {"type": "string"}},
    "required": ["title", "text", "summary"],
}


def story_chapter(model: str, hero: str, region: str, n: int, story_so_far: str, finds: list[dict]) -> dict:
    # Rarity steers how big a role each find plays, without the words leaking into the prose.
    roles = {"legendary": "the key to today's twist", "epic": "a powerful ally", "rare": "an important clue",
             "uncommon": "a helpful guide", "common": "a small friendly detail"}
    found = "; ".join(f"{f['name']} = {roles[f['rarity']]}" for f in finds)
    opening = ("This is chapter 1. The Green Archive, an ancient living book that remembers every creature of "
               f"{region}, has started to fade, its pages going blank. You are its new Keeper. "
               "Every creature you meet restores a page. Something, or someone, is erasing it.")
    prompt = (
        f"You narrate an ongoing cosy-mystery fantasy adventure set in a magical version of {region}. "
        f"The reader, {hero}, is the hero. Chapters unlock only when the reader photographs real creatures outside.\n"
        f"Story so far: {story_so_far or opening}\n"
        f"Today's creatures and their role in this chapter: {found}.\n"
        f"Write chapter {n}:\n"
        "- title: 2 to 5 words.\n"
        "- text: 110 to 160 words, second person ('you'), vivid, warm and concrete. Every creature above must "
        "appear doing something true to its real nature. Never use the words common, uncommon, rare, epic or legendary. "
        "Move the mystery forward by one step, then end with a sharp cliffhanger: a sound, a shadow, a message, "
        "a discovery, cut off mid-moment.\n"
        "- summary: 2 sentences covering the whole story so far including this chapter, for continuity."
    )
    out = _ask(model, prompt, CHAPTER_SCHEMA, temperature=1.0)
    return {k: out[k].strip() for k in ("title", "text", "summary")}
