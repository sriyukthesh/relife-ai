import tempfile
from pathlib import Path

from app.services import evaluation as ev

CSV = """filename,category,label,resistance_ohm,capacitance_uf,voltage_v,color,polarity,buzzer_type,part_number,tags
a.jpg,resistor,220,220,,,,,,,easy
b.jpg,led,Red LED,,,,Red,,,,hard
b.jpg,resistor,10k,10000,,,,,,,hard;blurry
"""


def _truth():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.csv"
        p.write_text(CSV)
        return ev.load_ground_truth(p)


def _p(cat, specs, conf=0.9, review=False):
    return {"category": cat, "specs": specs, "ai_confidence": conf, "needs_review": review}


def test_load_ground_truth_normalises():
    t = _truth()
    assert t["a.jpg"][0].specs == {"resistance_ohm": 220.0}
    assert t["b.jpg"][0].specs == {"color": "red"}
    assert t["b.jpg"][1].tags == ["hard", "blurry"]


def test_perfect_photo():
    t = _truth()
    s = ev.score_photo("a.jpg", t["a.jpg"], [_p("resistor", {"resistance_ohm": 220})])
    assert s.items[0].fully_correct and s.confident_wrong == 0


def test_tolerance_and_wrong_value_confident_wrong():
    t = _truth()
    ok = ev.score_photo("a.jpg", t["a.jpg"], [_p("resistor", {"resistance_ohm": 220.5})])
    assert ok.items[0].fully_correct
    bad = ev.score_photo("a.jpg", t["a.jpg"], [_p("resistor", {"resistance_ohm": 330})])
    assert bad.items[0].found and not bad.items[0].fully_correct
    assert bad.confident_wrong == 1  # wrong and not flagged: the dangerous case


def test_flagged_wrong_is_not_confident_wrong():
    t = _truth()
    s = ev.score_photo("a.jpg", t["a.jpg"], [_p("resistor", {"resistance_ohm": 330}, conf=0.4, review=True)])
    assert s.confident_wrong == 0


def test_missing_and_extra():
    t = _truth()
    s = ev.score_photo("b.jpg", t["b.jpg"], [_p("led", {"color": "red"}), _p("capacitor", {}, review=True)])
    assert [i.found for i in s.items].count(False) == 1
    assert s.extra_proposals == 1


def test_summary_and_report_render():
    t = _truth()
    scores = [
        ev.score_photo("a.jpg", t["a.jpg"], [_p("resistor", {"resistance_ohm": 220})]),
        ev.score_photo("b.jpg", t["b.jpg"], [_p("led", {"color": "red"})]),
    ]
    sm = ev.summarize(scores)
    assert sm["ground_truth_items"] == 3 and sm["category_accuracy"] == round(2 / 3, 3)
    assert "hard" in sm["by_tag"]
    assert "Confident-wrong" in ev.render_report(sm, model="m", mode_counts={"whole_image": 2}, failed=[])
