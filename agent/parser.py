"""Turn messy portal text into standard benefits fields, each with a confidence.

If ANTHROPIC_API_KEY is set, a hosted language model extracts the fields
against a JSON schema. Otherwise, or if that call fails, the regex parser is
used. Model confidence is self-reported and not calibrated.
"""
import json
import os
import re
from datetime import datetime

from .models import FieldValue

MODEL = "claude-haiku-5-5"
HIGH, LOW = 0.95, 0.6
AMBIGUOUS = re.compile(r"\?|verify|unclear|call payer", re.I)
DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
FREQ = re.compile(r"(\d+)\s*x\s*/\s*(?:yr|year)", re.I)
MONEY = r"\$?\s*([\d,]+(?:\.\d{2})?)"
SCALARS = {
    "active": re.compile(r"\b(inactive|termed|active)\b", re.I),
    "effective_date": re.compile(r"eff(?:ective)?\.?:?\s*(\d{1,2}/\d{1,2}/\d{4})", re.I),
    "deductible_remaining": re.compile(r"ded(?:uctible)?\.?\s*rem(?:aining)?\W{0,3}" + MONEY, re.I),
    "annual_max_remaining": re.compile(r"max(?:imum)?\s*rem(?:aining)?\W{0,3}" + MONEY, re.I),
    "coverage.preventive": re.compile(r"prev(?:entive)?[^\d%\n]{0,8}(\d{1,3})\s*%", re.I),
    "coverage.basic": re.compile(r"basic[^\d%\n]{0,8}(\d{1,3})\s*%", re.I),
    "coverage.major": re.compile(r"(?:major|crowns?)[^\d%\n]{0,12}(\d{1,3})\s*%", re.I),
    "major_wait_months": re.compile(r"(\d{1,2})\s*mo(?:nths?)?\.?\s*wait|\b(no)\s+wait", re.I),
}
GROUPS = {"prophy": r"prophy|cleanings?", "exam": r"exams?|evals?",
          "bwx": r"bwx|bitewings?", "fluoride": r"fluoride"}
FIELD_TYPES: dict[str, dict] = {
    "active": {"type": "boolean"}, "effective_date": {"type": "string"},
    "deductible_remaining": {"type": "number"}, "annual_max_remaining": {"type": "number"},
    **{f"coverage.{c}": {"type": "number"} for c in ("preventive", "basic", "major")},
    "major_wait_months": {"type": "number"},
    **{f"freq.{g}": {"type": "number"} for g in GROUPS},
    **{f"hist.{g}": {"type": "array", "items": {"type": "string"}} for g in GROUPS},
}


def _iso(mdy: str) -> str:
    return datetime.strptime(mdy, "%m/%d/%Y").date().isoformat()


def _convert(key: str, m: re.Match):
    raw = next(g for g in m.groups() if g is not None)
    if key == "active":
        return raw.lower() == "active"
    if key == "effective_date":
        return _iso(raw)
    if key == "major_wait_months":
        return 0 if raw.lower() == "no" else int(raw)
    return float(raw.replace(",", ""))


def parse_regex(text: str) -> dict[str, FieldValue]:
    out: dict[str, FieldValue] = {}
    for line in text.splitlines():
        conf = LOW if AMBIGUOUS.search(line) else HIGH

        def put(key, value):
            if key not in out:
                out[key] = FieldValue(value=value, confidence=conf, source="portal:regex")

        for key, rx in SCALARS.items():
            if m := rx.search(line):
                put(key, _convert(key, m))
        for group, label in GROUPS.items():
            if re.match(rf"\s*(?:{label})\b", line, re.I) and (f := FREQ.search(line)):
                put(f"freq.{group}", int(f.group(1)))
                put(f"hist.{group}", [_iso(d) for d in DATE.findall(line)])
    return out


def _schema() -> dict:
    props = {}
    for key, vtype in FIELD_TYPES.items():
        props[key.replace(".", "__")] = {
            "type": "object", "additionalProperties": False,
            "required": ["found", "value", "confidence"],
            "properties": {"found": {"type": "boolean"}, "value": vtype,
                           "confidence": {"type": "number"}},
        }
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


PROMPT = """Extract dental benefits from this payer portal text.
For every field, set found=false if the text does not state it.
Dates are YYYY-MM-DD. Percentages and dollar amounts are plain numbers.
freq__X is the allowed count per year; hist__X lists prior service dates.
confidence is 0 to 1. Use a low value when the text is hedged, ambiguous,
or incomplete (for example a partial date or a question mark).

<portal_text>
{text}
</portal_text>"""


def parse_with_model(text: str, client=None) -> dict[str, FieldValue]:
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL, max_tokens=4096,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": _schema()}},
        messages=[{"role": "user", "content": PROMPT.format(text=text)}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"Model stopped early: {response.stop_reason}")
    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    out = {}
    for skey, item in data.items():
        if item["found"]:
            conf = min(max(float(item["confidence"]), 0.0), 1.0)
            out[skey.replace("__", ".")] = FieldValue(
                value=item["value"], confidence=conf, source=f"portal:model:{MODEL}")
    return out


def model_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def parse_portal_text(text: str, use_model: bool | None = None) -> dict[str, FieldValue]:
    if use_model is None:
        use_model = model_enabled()
    if use_model:
        try:
            return parse_with_model(text)
        except Exception as exc:  # never block the nightly run on the model call
            print(f"  [parser] model call failed ({type(exc).__name__}); using regex fallback")
    return parse_regex(text)
