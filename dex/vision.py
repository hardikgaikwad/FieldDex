"""Identify what's in a photo with a local vision model."""
import json

import ollama

from .config import OLLAMA_OPTIONS

KINDS = ["bird", "plant", "tree", "insect", "fungus", "animal"]

# Field order matters for small models: describe first, then classify, then judge.
SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "features": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "kind": {"type": "string", "enum": KINDS + ["none"]},
        "common_name": {"type": "string"},
        "confidence": {"type": "number"},
        "is_photo_of_screen": {"type": "boolean"},
        "photo_quality": {"type": "integer"},
        "matches_wanted": {"type": "boolean"},
    },
    "required": ["subject", "features", "kind", "common_name", "confidence",
                 "is_photo_of_screen", "photo_quality", "matches_wanted"],
}

PROMPT = """You are the identifier in a nature collecting game played in {region}.
- subject: in a few words, what is the main subject of this photo?
- features: up to 4 short visible details of that subject (colours, shapes, markings).
- kind: the category of the most prominent plant, animal or fungus in the photo, even if it is not centred
  (a tree beside a building counts as "tree"). Use "none" only if there is no plant, animal or fungus
  clearly visible (buildings, streets, objects, food, people, sky).
- common_name: the most specific everyday name you are sure of for that living thing (e.g. "Indian Peafowl",
  "Neem tree", "Plain Tiger butterfly"). If unsure, use an honest general name like "small brown bird".
- confidence: 0 to 1, how sure you are about common_name.
- is_photo_of_screen: true if this is a photo of a phone, monitor or printed picture rather than a real scene.
- photo_quality: 1 (blurry, tiny, dark) to 5 (sharp, close, well lit).
- matches_wanted: true only if the photo clearly shows: "{wanted}".
Answer in JSON."""


# Small vision models name things well but sort them into categories badly
# (a butterfly as "plant", a peacock as "animal"). The name decides first.
KIND_WORDS = [
    ("bird", "bird peafowl peacock peahen myna mynah crow sparrow parrot parakeet pigeon dove kingfisher eagle kite "
             "hawk owl heron egret bulbul robin drongo babbler barbet hornbill woodpecker sunbird tailorbird cuckoo "
             "koel duck swan stork ibis lapwing magpie starling weaver finch munia hoopoe roller bee-eater oriole "
             "shrike wagtail swallow swift lark chicken hen rooster"),
    ("insect", "insect butterfly moth bee wasp hornet ant beetle ladybird ladybug dragonfly damselfly grasshopper "
               "cricket locust cicada caterpillar bug fly mosquito mantis termite spider"),
    ("fungus", "fungus fungi mushroom toadstool lichen mould mold bracket"),
    ("tree", "tree palm banyan peepal pipal neem mango gulmohar teak bamboo eucalyptus ashoka sal bark trunk"),
    ("plant", "plant flower hibiscus rose lotus lily marigold jasmine sunflower daisy orchid bougainvillea "
              "tulsi basil leaf leaves grass shrub bush fern moss cactus succulent weed vine creeper herb "
              "petal blossom bud seed fruit"),
    ("animal", "dog cat cow buffalo goat sheep horse donkey squirrel lizard gecko monkey langur macaque snake "
               "frog toad turtle tortoise rabbit rat mouse mongoose deer bat fish crab snail"),
]


def refine_kind(model_kind: str, *texts: str) -> str:
    words = set(" ".join(texts).lower().replace("-", " ").replace(",", " ").split())
    for kind, vocab in KIND_WORDS:
        if words & set(vocab.replace("-", " ").split()):
            return kind
    return model_kind if model_kind in KINDS else "none"


def identify(image_jpeg: bytes, model: str, region: str, wanted: str | None) -> dict:
    response = ollama.chat(
        model=model,
        messages=[{"role": "user",
                   "content": PROMPT.format(region=region, wanted=wanted or "(no target today)"),
                   "images": [image_jpeg]}],
        format=SCHEMA,
        options={**OLLAMA_OPTIONS, "temperature": 0.1},
    )
    result = json.loads(response.message.content)
    result["kind"] = refine_kind(result["kind"], result["common_name"], result["subject"])
    result["is_living_thing"] = result["kind"] in KINDS
    result["photo_quality"] = max(1, min(5, int(result["photo_quality"])))
    result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    result["matches_wanted"] = bool(result["matches_wanted"]) and bool(wanted)
    return result
