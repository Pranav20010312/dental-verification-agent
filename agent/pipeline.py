"""Full flow per patient:
clearinghouse -> missing fields? -> portal + parser -> estimate -> route.

Routing rule: NEEDS_REVIEW if the plan is inactive, any cost-driving field is
missing or has confidence < 0.9, or two sources disagree. Otherwise VERIFIED.
Every review decision stores a human-readable reason.
"""
from .clearinghouse import check_eligibility
from .data import load_appointments, load_fees
from .estimate import estimate
from .models import Appointment, FeeItem, FieldValue, VerificationResult
from .parser import parse_portal_text
from .portal import fetch_portal_page

CONFIDENCE_THRESHOLD = 0.9


def required_fields(appt: Appointment, fees: dict[str, FeeItem]) -> list[str]:
    """Cost-driving fields for this appointment's procedures."""
    need = ["active", "deductible_remaining", "annual_max_remaining"]
    for code in appt.cdt_codes:
        item = fees[code]
        need.append(f"coverage.{item.category}")
        if item.frequency_group:
            need += [f"freq.{item.frequency_group}", f"hist.{item.frequency_group}"]
        if item.category == "major":
            need += ["effective_date", "major_wait_months"]
    return list(dict.fromkeys(need))  # dedupe, keep order


def _normalize(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, list):
        return sorted(value)
    return str(value)


def verify(appt: Appointment, fees: dict[str, FeeItem],
           use_llm: bool | None = None) -> VerificationResult:
    fields: dict[str, FieldValue] = check_eligibility(appt.member_id)
    sources, reasons = ["clearinghouse"], []
    need = required_fields(appt, fees)

    if fields["active"].value is False:
        reasons.append("plan inactive per 271")
    else:
        missing = [k for k in need if k not in fields]
        if missing:
            text = fetch_portal_page(appt.member_id)
            sources.append("portal")
            parsed = parse_portal_text(text, use_llm) if text else {}
            for key, fv in parsed.items():
                if key not in fields:
                    fields[key] = fv
                elif _normalize(fv.value) != _normalize(fields[key].value):
                    reasons.append(f"source conflict on {key}: 271={fields[key].value}, "
                                   f"portal={fv.value}")
        still_missing = [k for k in need if k not in fields]
        if still_missing:
            reasons.append("missing after portal: " + ", ".join(still_missing))
        for key in need:
            if key in fields and fields[key].confidence < CONFIDENCE_THRESHOLD:
                reasons.append(f"low confidence on {key} ({fields[key].confidence:.2f})")

    values = {k: fv.value for k, fv in fields.items()}
    return VerificationResult(
        appointment=appt,
        status="NEEDS_REVIEW" if reasons else "VERIFIED",
        reasons=reasons, sources=sources, fields=fields,
        estimate=estimate(appt, values, fees),
    )


def run_all(use_llm: bool | None = None) -> list[VerificationResult]:
    fees = load_fees()
    return [verify(appt, fees, use_llm) for appt in load_appointments()]
