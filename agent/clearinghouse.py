"""Mock clearinghouse: a stand-in for an X12 270 request / 271 response.

No network calls. Responses come from data/clearinghouse_271.json. Two payers
(Cedar Mutual, Dunmore) deliberately return no frequency limits or service
history, which is common in real 271s and forces the portal path.
"""
from .data import load_json
from .models import FieldValue

SOURCE = "clearinghouse_271"
CONFIDENCE = 0.99  # structured data, but payers still make mistakes


def check_eligibility(member_id: str) -> dict[str, FieldValue]:
    """Return the flattened benefits fields the 271 contained for this member."""
    record = load_json("clearinghouse_271.json").get(member_id)
    if record is None:  # payer rejected the 270: subscriber not found
        return {"active": FieldValue(value=False, confidence=CONFIDENCE, source=SOURCE)}
    return {k: FieldValue(value=v, confidence=CONFIDENCE, source=SOURCE)
            for k, v in flatten(record).items()}


def flatten(record: dict) -> dict:
    """Turn the nested 271 record into flat keys like 'coverage.basic'."""
    flat: dict = {}
    for key, value in record.items():
        if key == "coverage":
            flat.update({f"coverage.{c}": pct for c, pct in value.items()})
        elif key == "frequency":
            flat.update({f"freq.{g}": n for g, n in value.items()})
        elif key == "history":
            flat.update({f"hist.{g}": dates for g, dates in value.items()})
        else:
            flat[key] = value
    return flat
