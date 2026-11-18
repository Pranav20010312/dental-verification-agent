import json
from types import SimpleNamespace

from agent import parser
from agent.eob_check import compare, load_eobs
from agent.pipeline import run_all, verify


def test_inactive_plan_goes_to_review(appts, fees):
    res = verify(appts["P003"], fees)
    assert res.status == "NEEDS_REVIEW"
    assert res.reasons == ["plan inactive per 271"]
    assert res.sources == ["clearinghouse"]  # no point calling the portal


def test_complete_271_is_verified_without_portal(appts, fees):
    res = verify(appts["P001"], fees)
    assert res.status == "VERIFIED"
    assert res.sources == ["clearinghouse"]


def test_missing_fields_trigger_portal_path(appts, fees):
    res = verify(appts["P006"], fees)  # Cedar Mutual 271 has no frequency or history
    assert "portal" in res.sources
    assert res.fields["freq.prophy"].source == "portal:regex"
    assert res.fields["hist.prophy"].value == ["2026-04-22"]
    assert res.status == "VERIFIED"


def test_low_confidence_goes_to_review(appts, fees):
    res = verify(appts["P007"], fees)  # portal says "2x/yr?? ... (verify)"
    assert res.status == "NEEDS_REVIEW"
    assert any("low confidence on freq.prophy" in r for r in res.reasons)


def test_source_conflict_goes_to_review(appts, fees):
    res = verify(appts["P009"], fees)  # 271 deductible 0, portal says $50
    assert res.status == "NEEDS_REVIEW"
    assert any("source conflict on deductible_remaining" in r for r in res.reasons)


def test_regex_parser_handles_messy_text():
    text = "Ded rem $1,250.00 / Max rem $800\nPrev 100% / Major (crowns) 50%, 12 mo wait"
    out = parser.parse_regex(text)
    assert out["deductible_remaining"].value == 1250.0
    assert out["annual_max_remaining"].value == 800.0
    assert out["coverage.major"].value == 50.0
    assert out["major_wait_months"].value == 12
    assert all(fv.confidence == parser.HIGH for fv in out.values())


def test_model_path_maps_schema_output(monkeypatch):
    """No network: a fake client returns what the structured-output call would."""
    payload = {k.replace(".", "__"): {"found": False, "value": 0, "confidence": 0}
               for k in parser.FIELD_TYPES}
    payload["coverage__basic"] = {"found": True, "value": 80, "confidence": 0.97}
    fake_resp = SimpleNamespace(stop_reason="end_turn",
                                content=[SimpleNamespace(type="text", text=json.dumps(payload))])
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: fake_resp))
    out = parser.parse_with_model("Basic 80%", client=fake_client)
    assert list(out) == ["coverage.basic"]
    assert out["coverage.basic"].value == 80
    assert out["coverage.basic"].source.startswith("portal:model")


def test_eob_mismatch_logged():
    report = compare(run_all(use_model=False), load_eobs())
    p008 = [m for m in report.mismatches if m.patient_id == "P008"]
    assert {m.field for m in p008} == {"insurance_paid", "patient_paid"}
    assert p008[0].payer == "Dunmore Benefits"
    assert p008[0].agent_status == "VERIFIED"  # an auto-verified estimate was wrong
    assert list(report.by_payer()) == ["Dunmore Benefits"]
    assert report.fields_checked == 60
