import pytest
from pydantic import ValidationError

from teju import coach, foods, parse


def ids(items):
    return [(i["food"]["id"], i["quantity"]) for i in items if i["matched"]]


def test_schema_rejects_bad_model_output():
    with pytest.raises(ValidationError):
        parse.ParsedMeal.model_validate({"items": [{"name": "idli", "quantity": 0, "unit": "piece", "confidence": 0.9}]})
    with pytest.raises(ValidationError):
        parse.ParsedMeal.model_validate({"items": [{"name": "", "quantity": 1, "unit": "piece", "confidence": 0.9}]})
    with pytest.raises(ValidationError):
        parse.ParsedMeal.model_validate({"items": [{"name": "dal", "quantity": 1, "unit": "bowl", "confidence": 1.5}]})
    ok = parse.ParsedMeal.model_validate({"items": [{"name": "Idli", "quantity": 2, "unit": "piece", "confidence": 0.9}]})
    assert ok.items[0].quantity == 2


@pytest.mark.parametrize("text,expected", [
    ("2 rotis, dal, curd", [("chapati", 2), ("dal", 1), ("curd", 1)]),
    ("రెండు ఇడ్లీ సాంబార్", [("idli", 2), ("sambar", 1)]),
    ("rendu idli tho sambar", [("idli", 2), ("sambar", 1)]),
    ("perugu annam, avakaya", [("curd_rice", 1), ("avakaya", 1)]),
    ("1 plate pulihora and a glass of majjiga", [("pulihora", 1), ("buttermilk", 1)]),
])
def test_rules_parser_english_telugu_and_romanised(text, expected):
    assert ids(parse.parse_rules(text)) == expected


def test_telugu_normalisation_keeps_vowel_signs():
    assert foods.norm("ఇడ్లీ!") == "ఇడ్లీ"
    assert foods.resolve("గోంగూర పచ్చడి")["id"] == "gongura_pachadi"


def test_approximate_matches_are_marked():
    assert foods.get("gongura_pachadi")["approx_of"]
    assert foods.get("idli")["approx_of"] is None


def test_unmatched_item_returns_candidates():
    item = parse.review_item("zzqx unknown dish", 1, "")
    assert item["matched"] is False and isinstance(item["candidates"], list)


def test_parse_text_falls_back_to_rules_without_ai():
    out = parse.parse_text("3 dosa with coconut chutney")
    assert out["engine"] == "rules" and out["notice"] == "ai_unavailable"
    assert ids(out["items"]) == [("plain_dosa", 3), ("coconut_chutney", 1)]


def test_search_finds_telugu_and_romanised_names():
    assert foods.search("pesarattu")[0]["id"] == "pesarattu"
    assert foods.search("పులిహోర")[0]["id"] == "pulihora"
    assert any(f["id"] == "idli" for f in foods.search("idly"))


def test_coach_safety_filter_drops_medical_advice():
    kept = coach.safe([
        {"title": "Add dal", "body": "A katori of dal with lunch adds protein."},
        {"title": "Ask about metformin", "body": "Take your tablet after food."},
        {"title": "Possible diabetes", "body": "Your sugar intake suggests a disease."},
    ])
    assert [s["title"] for s in kept] == ["Add dal"]
