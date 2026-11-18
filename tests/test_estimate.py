from datetime import date

from agent.estimate import estimate
from agent.models import Appointment

BASE = {"active": True, "deductible_remaining": 0, "annual_max_remaining": 1500,
        "coverage.preventive": 100, "coverage.basic": 80, "coverage.major": 50,
        "effective_date": "2020-01-01", "major_wait_months": 0}


def appt(*codes, when=date(2026, 11, 20)):
    return Appointment(patient_id="T1", name="Test Person", dob=date(1990, 1, 1),
                       payer="Test Payer", member_id="T-1", appt_date=when,
                       cdt_codes=list(codes))


def test_estimate_math_filling_with_deductible(fees):
    # D2391 fee 180, $50 deductible left, basic 80%: (180 - 50) * 0.8 = 104 paid.
    est = estimate(appt("D2391"), {**BASE, "deductible_remaining": 50}, fees)
    line = est.lines[0]
    assert line.insurance == 104.00
    assert line.patient == 76.00


def test_estimate_math_crown_major(fees):
    # D2740 fee 1200, $50 deductible, major 50%: (1200 - 50) * 0.5 = 575 paid.
    est = estimate(appt("D2740"), {**BASE, "deductible_remaining": 50}, fees)
    assert est.insurance_total == 575.00
    assert est.patient_total == 625.00


def test_preventive_skips_deductible(fees):
    est = estimate(appt("D1110"), {**BASE, "deductible_remaining": 50,
                                   "freq.prophy": 2, "hist.prophy": []}, fees)
    assert est.patient_total == 0.00


def test_frequency_limit_hit(fees):
    benefits = {**BASE, "freq.prophy": 2, "hist.prophy": ["2026-02-10", "2026-08-12"]}
    line = estimate(appt("D1110"), benefits, fees).lines[0]
    assert not line.covered
    assert line.patient == 110.00
    assert "frequency" in line.note


def test_frequency_history_from_last_year_does_not_count(fees):
    benefits = {**BASE, "freq.bwx": 1, "hist.bwx": ["2025-11-02"]}
    assert estimate(appt("D0274"), benefits, fees).lines[0].covered


def test_annual_max_exhausted(fees):
    # Two SRP quadrants at 250, basic 80% = 200 each, but only $200 max left.
    est = estimate(appt("D4341", "D4341"), {**BASE, "annual_max_remaining": 200}, fees)
    first, second = est.lines
    assert first.insurance == 200.00
    assert second.insurance == 0.00
    assert second.note == "annual max reached"
    assert est.patient_total == 300.00


def test_major_waiting_period(fees):
    benefits = {**BASE, "effective_date": "2026-06-01", "major_wait_months": 12}
    line = estimate(appt("D2740"), benefits, fees).lines[0]
    assert not line.covered
    assert line.patient == 1200.00
    assert "2027-06-01" in line.note


def test_inactive_plan_patient_pays_everything(fees):
    est = estimate(appt("D0120", "D1110"), {"active": False}, fees)
    assert est.insurance_total == 0
    assert est.patient_total == 175.00
