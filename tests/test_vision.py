from dex.vision import refine_kind


def test_name_beats_model_kind():
    assert refine_kind("plant", "Tiger butterfly", "butterfly") == "insect"
    assert refine_kind("animal", "Indian Peafowl", "Peacock") == "bird"
    assert refine_kind("none", "Hibiscus", "Flower") == "plant"
    assert refine_kind("plant", "Neem tree", "tree") == "tree"


def test_falls_back_to_model_kind_or_none():
    assert refine_kind("fungus", "orange blob", "something") == "fungus"
    assert refine_kind("none", "table and chairs", "table and chairs") == "none"
