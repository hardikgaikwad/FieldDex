from collections import Counter

from dex import game


def test_species_key_normalises():
    assert game.species_key("  Indian   Peafowl ") == "indian peafowl"


def test_roll_is_deterministic_per_photo():
    assert game.roll_rarity("bird", True, 4, False, "abc") == game.roll_rarity("bird", True, 4, False, "abc")


def test_effort_raises_rarity():
    def spread(**kw):
        return Counter(game.roll_rarity(seed=str(i), **kw)[0] for i in range(2000))

    lazy = spread(kind="plant", is_new=False, quality=2, golden_hour=False)
    keen = spread(kind="bird", is_new=True, quality=5, golden_hour=True)
    assert lazy["common"] > 1000 and lazy["legendary"] == 0
    assert keen["legendary"] > 0 and keen["common"] == 0


def test_better_keeps_higher_tier():
    assert game.better("rare", "common") == "rare"
    assert game.better("epic", "legendary") == "legendary"


def test_xp_for_find():
    assert game.xp_for_find("common", True, False) == 35
    assert game.xp_for_find("rare", False, True) == 95


def test_level_curve():
    assert game.level_for_xp(0) == {"level": 1, "into": 0, "needed": 60}
    assert game.level_for_xp(60)["level"] == 2
    assert game.level_for_xp(10_000)["level"] > 10


def test_unlocks():
    base = {"level": 1, "kinds": {}, "days_out": 0, "legendaries": 0}
    after = {"level": 3, "kinds": {"bird": 5}, "days_out": 1, "legendaries": 0}
    assert [u["id"] for u in game.new_unlocks(base, after)] == ["camera", "binoculars"]
